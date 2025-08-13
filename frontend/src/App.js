import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { Button } from "./components/ui/button";
import { Progress } from "./components/ui/progress";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

function useQuery() {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search), [search]);
}

function wsUrlFor(path) {
  // Convert http/https to ws/wss preserving host
  const u = new URL(API_BASE);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  return `${u.origin}${path}`;
}

const PC_CONFIG = { iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:global.stun.twilio.com:3478"] }] };

function Home() {
  const navigate = useNavigate();
  const q = useQuery();
  const joinSid = q.get("s");

  useEffect(() => {
    // If a session id exists (via QR), go straight to the session screen
    if (joinSid) navigate(`/session?s=${encodeURIComponent(joinSid)}`, { replace: true });
  }, [joinSid, navigate]);

  const start = () => {
    const sid = crypto.randomUUID();
    navigate(`/session?s=${encodeURIComponent(sid)}`);
  };

  return (
    <div className="app-wrap">
      <div className="sidebar neu-surface card">
        <div className="header"><div className="title">EasyMesh</div></div>
        <p className="muted">Cross‑platform local file transfer. Start a session on your PC and scan the QR from your phone.</p>
        <div style={{ height: 16 }} />
        <Button onClick={start} className="neu-pressable" style={{ width: "100%" }}>Start Session</Button>
        <div style={{ height: 12 }} />
        <div className="neu-inset card">
          <div style={{ padding: 12 }}>
            <div className="title" style={{ fontSize: 16 }}>How it works</div>
            <ol className="muted" style={{ marginTop: 8, lineHeight: 1.6 }}>
              <li>1. Click Start Session on your PC</li>
              <li>2. Scan the QR with your phone camera</li>
              <li>3. Send files both ways over a direct WebRTC link</li>
            </ol>
          </div>
        </div>
      </div>
      <div className="main neu-surface card">
        <div className="header"><div className="title">Session Preview</div></div>
        <div className="muted">You&#39;ll see pairing QR and file panes once you start a session.</div>
      </div>
    </div>
  );
}

function Session() {
  const q = useQuery();
  const sessionId = q.get("s");
  const [clientId] = useState(() => crypto.randomUUID());
  const [peers, setPeers] = useState([]);
  const [connected, setConnected] = useState(false);
  const [role, setRole] = useState("host"); // assume host if we generated the link locally

  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const remoteIdRef = useRef(null);

  const [sendQueue, setSendQueue] = useState([]);
  const [progressMap, setProgressMap] = useState({});
  const [received, setReceived] = useState([]);

  const buildQrLink = () => {
    const origin = window.location.origin;
    const url = `${origin}/?s=${encodeURIComponent(sessionId)}`;
    const qrURL = `https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(url)}&amp;size=220x220&amp;margin=0`;
    return { url, qrURL };
  };

  const initWebSocket = useCallback(() => {
    if (!sessionId) return;
    const url = wsUrlFor(`/api/ws/session/${encodeURIComponent(sessionId)}?client_id=${encodeURIComponent(clientId)}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "join", clientId, role }));
    };
    ws.onmessage = async (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "peers") {
        const others = (msg.peers || []).filter((p) => p !== clientId);
        setPeers(others);
        if (!remoteIdRef.current && others.length > 0) {
          remoteIdRef.current = others[0];
          // If we are host, start offer
          if (role === "host") {
            await ensurePeerConnection();
            await createOffer();
          }
        }
      }
      if (msg.type === "sdp-offer") {
        await ensurePeerConnection();
        await pcRef.current.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        const answer = await pcRef.current.createAnswer();
        await pcRef.current.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "sdp-answer", to: msg.from, sdp: answer }));
        remoteIdRef.current = msg.from;
      }
      if (msg.type === "sdp-answer") {
        if (pcRef.current) {
          await pcRef.current.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        }
      }
      if (msg.type === "ice-candidate") {
        try {
          if (pcRef.current && msg.candidate) {
            await pcRef.current.addIceCandidate(msg.candidate);
          }
        } catch (e) {
          console.error("ICE error", e);
        }
      }
    };
    ws.onclose = () => {
      setConnected(false);
    };
  }, [sessionId, clientId, role]);

  const ensurePeerConnection = useCallback(async () => {
    if (pcRef.current) return pcRef.current;
    const pc = new RTCPeerConnection(PC_CONFIG);
    pcRef.current = pc;

    pc.onicecandidate = (ev) => {
      if (ev.candidate && wsRef.current && remoteIdRef.current) {
        wsRef.current.send(JSON.stringify({ type: "ice-candidate", to: remoteIdRef.current, candidate: ev.candidate }));
      }
    };

    pc.onconnectionstatechange = () => {
      const st = pc.connectionState;
      if (st === "connected") setConnected(true);
      if (["disconnected", "failed", "closed"].includes(st)) setConnected(false);
    };

    // Host creates data channel; peer listens
    if (role === "host") {
      const dc = pc.createDataChannel("file");
      attachDataChannel(dc);
    } else {
      pc.ondatachannel = (ev) => attachDataChannel(ev.channel);
    }

    return pc;
  }, [role]);

  const attachDataChannel = (dc) => {
    dcRef.current = dc;
    dc.binaryType = "arraybuffer";
    let recvState = { expecting: null, receivedBytes: 0, chunks: [] };

    dc.onopen = () => {
      // drain queued sends
      sendQueue.forEach((item) => sendFile(item));
      setSendQueue([]);
    };

    dc.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        if (ev.data.startsWith("META:")) {
          const meta = JSON.parse(ev.data.slice(5));
          recvState = { expecting: meta, receivedBytes: 0, chunks: [] };
          setProgressMap((m) => ({ ...m, [meta.id]: { name: meta.name, total: meta.size, sent: 0, recv: 0 } }));
        } else if (ev.data.startsWith("DONE:")) {
          const meta = JSON.parse(ev.data.slice(5));
          const blob = new Blob(recvState.chunks, { type: recvState.expecting?.mime || "application/octet-stream" });
          const url = URL.createObjectURL(blob);
          setReceived((r) => [{ id: meta.id, name: recvState.expecting.name, size: recvState.expecting.size, url }, ...r]);
          setProgressMap((m) => ({ ...m, [meta.id]: { ...(m[meta.id] || {}), recv: recvState.expecting.size, total: recvState.expecting.size, name: recvState.expecting.name } }));
          recvState = { expecting: null, receivedBytes: 0, chunks: [] };
        }
      } else {
        // chunk
        if (recvState.expecting) {
          recvState.chunks.push(ev.data);
          recvState.receivedBytes += ev.data.byteLength;
          setProgressMap((m) => {
            const id = recvState.expecting.id;
            const curr = m[id] || { name: recvState.expecting.name, total: recvState.expecting.size, sent: 0, recv: 0 };
            return { ...m, [id]: { ...curr, recv: Math.min(recvState.receivedBytes, recvState.expecting.size) } };
          });
        }
      }
    };
  };

  const createOffer = useCallback(async () => {
    const pc = pcRef.current || (await ensurePeerConnection());
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    wsRef.current?.send(JSON.stringify({ type: "sdp-offer", to: remoteIdRef.current, sdp: offer }));
  }, [ensurePeerConnection]);

  useEffect(() => {
    initWebSocket();
    // if user opened link on phone (came from QR), consider them as peer
    if (window.history.length === 1) {
      setRole("host");
    }
    // If URL existed before navigation (came from QR from Home), role could be peer; but keep host-by-default and host will offer once peer arrives

  }, [sessionId]);

  const onFilesPicked = (files) => {
    const list = Array.from(files);
    list.forEach((f) => queueSend(f));
  };

  const queueSend = (file) => {
    const job = { file, id: crypto.randomUUID() };
    if (!dcRef.current || dcRef.current.readyState !== "open") {
      setSendQueue((q) => [...q, job]);
    } else {
      sendFile(job);
    }
  };

  const sendFile = ({ file, id }) => {
    const dc = dcRef.current;
    if (!dc || dc.readyState !== "open") return;

    const meta = { id, name: file.name, size: file.size, mime: file.type };
    dc.send(`META:${JSON.stringify(meta)}`);

    setProgressMap((m) => ({ ...m, [id]: { name: file.name, total: file.size, sent: 0, recv: m[id]?.recv || 0 } }));

    const chunkSize = 64 * 1024; // 64KB chunks
    const reader = file.stream().getReader();
    let sentBytes = 0;

    const pump = () => reader.read().then(({ done, value }) => {
      if (done) {
        dc.send(`DONE:${JSON.stringify({ id })}`);
        return;
      }
      sentBytes += value.byteLength;
      dc.send(value);
      setProgressMap((m) => {
        const curr = m[id] || { name: file.name, total: file.size, sent: 0, recv: 0 };
        return { ...m, [id]: { ...curr, sent: Math.min(sentBytes, file.size) } };
      });
      // backpressure: if bufferedAmount too high, wait
      if (dc.bufferedAmount > 8 * 1024 * 1024) {
        setTimeout(pump, 50);
      } else {
        pump();
      }
    });

    pump();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer?.files?.length) onFilesPicked(e.dataTransfer.files);
  };

  const { url, qrURL } = buildQrLink();

  return (
    <div className="app-wrap">
      <div className="sidebar neu-surface card">
        <div className="header">
          <div className="title">Session</div>
          <div className="muted">ID: {sessionId?.slice(0, 8)}...</div>
        </div>
        <div className="neu-inset qr">
          <img src={qrURL} alt="QR" width={200} height={200} />
        </div>
        <div style={{ height: 8 }} />
        <div className="muted" style={{ fontSize: 12 }}>Scan with your phone camera to open: {url}</div>
        <div style={{ height: 16 }} />
        <div className="neu-inset card" style={{ padding: 12 }}>
          <div className="title" style={{ fontSize: 16, marginBottom: 8 }}>Peers</div>
          {peers.length === 0 ? (
            <div className="muted">Waiting for a device to join…</div>
          ) : (
            peers.map((p) => (
              <div key={p} className="file-row"><span className="file-name">{p.slice(0, 8)}…</span><span className="file-meta">connected</span></div>
            ))
          )}
          <div style={{ height: 8 }} />
          <div className="file-meta">Connection: {connected ? "WebRTC Connected" : "Not connected"}</div>
        </div>
      </div>

      <div className="main neu-surface card">
        <div className="header">
          <div className="title">Transfer</div>
          <div className="muted">Bidirectional</div>
        </div>

        <div className="pane neu-inset dropzone"
             onDragOver={(e) => { e.preventDefault(); }}
             onDrop={handleDrop}
        >
          <div style={{ marginBottom: 8 }}><strong>Drop files here</strong> or</div>
          <label className="neu-pressable" style={{ display: "inline-block", padding: "10px 16px", cursor: "pointer" }}>
            <input type="file" multiple onChange={(e) => onFilesPicked(e.target.files)} style={{ display: "none" }} />
            Choose Files
          </label>
        </div>

        <div className="file-list">
          {Object.entries(progressMap).map(([id, p]) => {
            const sentPct = p.total ? Math.round((p.sent / p.total) * 100) : 0;
            const recvPct = p.total ? Math.round((p.recv / p.total) * 100) : 0;
            return (
              <div className="progress-row" key={id}>
                <div className="file-row"><span className="file-name">{p.name}</span><span className="file-meta">{Math.round((p.sent || p.recv || 0)/1024)} KB / {Math.round((p.total||0)/1024)} KB</span></div>
                <div style={{ display: "grid", gap: 6 }}>
                  <div className="file-meta">Sent {sentPct}%</div>
                  <Progress value={sentPct} />
                  <div className="file-meta">Received {recvPct}%</div>
                  <Progress value={recvPct} />
                </div>
              </div>
            );
          })}
        </div>

        {received.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="title" style={{ fontSize: 16, marginBottom: 8 }}>Received Files</div>
            {received.map((f) => (
              <div key={f.id} className="file-row">
                <span className="file-name">{f.name}</span>
                <a className="file-meta" href={f.url} download={f.name}>Download</a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/session" element={<Session />} />
      </Routes>
    </BrowserRouter>
  );
}