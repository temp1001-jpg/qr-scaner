import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { Button } from "./components/ui/button";
import { Progress } from "./components/ui/progress";
import { Textarea } from "./components/ui/textarea";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

function useQuery() { const { search } = useLocation(); return useMemo(() => new URLSearchParams(search), [search]); }

function wsUrlFor(path) {
  const base = new URL(process.env.REACT_APP_BACKEND_URL || window.location.origin);
  const scheme = base.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${base.host}${path}`;
}

const PC_CONFIG = { iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:global.stun.twilio.com:3478"] }] };

function useDarkMode() {
  const [dark, setDark] = useState(() => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  useEffect(() => { const root = document.documentElement; if (dark) root.classList.add('dark'); else root.classList.remove('dark'); }, [dark]);
  return { dark, setDark };
}

function Home() {
  const navigate = useNavigate();
  const q = useQuery();
  const { dark, setDark } = useDarkMode();
  const joinSid = q.get("s");
  useEffect(() => { if (joinSid) navigate(`/session?s=${encodeURIComponent(joinSid)}`, { replace: true }); }, [joinSid, navigate]);
  const start = () => { const sid = crypto.randomUUID(); try { sessionStorage.setItem(`hostFor:${sid}`, "1"); } catch {} navigate(`/session?s=${encodeURIComponent(sid)}`); };
  return (
    <div className="app-wrap">
      <div className="sidebar neu-surface card fade-in">
        <div className="header"><div className="title">EasyMesh</div><div className="toggle neu-pressable" onClick={() => setDark(!dark)}>{dark?"Light":"Dark"} mode</div></div>
        <p className="muted">Cross‑platform local file transfer. Start a session on your PC and scan the QR from your phone.</p>
        <div className="section-gap" />
        <Button onClick={start} className="neu-pressable" style={{ width: "100%" }}>Start Session</Button>
        <div className="section-gap" />
        <div className="neu-inset card"><div style={{ padding: 12 }}><div className="title" style={{ fontSize: 16 }}>How it works</div><ol className="muted" style={{ marginTop: 8, lineHeight: 1.7 }}><li>1. Click Start Session on your PC</li><li>2. Scan the QR with your phone camera</li><li>3. Send files and text over a direct WebRTC link</li></ol></div></div>
      </div>
      <div className="main neu-surface card fade-in"><div className="header"><div className="title">Session Preview</div></div><div className="muted">You&#39;ll see pairing QR, file panes and chat once you start a session.</div></div>
      <div className="rightbar neu-surface card fade-in"><div className="header"><div className="title">Clipboard Chat</div></div><div className="muted">Live chat and copy/paste text between devices appears here inside a session.</div></div>
    </div>
  );
}

function Session() {
  const q = useQuery();
  const sessionId = q.get("s");
  const [clientId] = useState(() => crypto.randomUUID());
  const [peers, setPeers] = useState([]);
  const [connected, setConnected] = useState(false);
  const [role, setRole] = useState("peer");

  const wsRef = useRef(null);
  const wsReadyRef = useRef(false);
  const wsQueueRef = useRef([]);
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const remoteIdRef = useRef(null);

  // chat state
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState([]);
  const chatQueueRef = useRef([]);

  // file state
  const [sendQueue, setSendQueue] = useState([]);
  const [progressMap, setProgressMap] = useState({});
  const [received, setReceived] = useState([]);

  const sendSignal = useCallback((obj) => {
    const ws = wsRef.current;
    const payload = JSON.stringify(obj);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      wsQueueRef.current.push(payload);
    }
  }, []);

  const flushSignalQueue = () => {
    const ws = wsRef.current; if (!ws) return; if (ws.readyState !== WebSocket.OPEN) return;
    wsReadyRef.current = true;
    while (wsQueueRef.current.length) { ws.send(wsQueueRef.current.shift()); }
  };

  const buildQrLink = () => {
    const origin = window.location.origin; const url = `${origin}/?s=${encodeURIComponent(sessionId)}`;
    const qrURL = `https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(url)}&amp;size=240x240&amp;margin=0`;
    return { url, qrURL };
  };

  const initWebSocket = useCallback(() => {
    if (!sessionId) return;
    const url = wsUrlFor(`/api/ws/session/${encodeURIComponent(sessionId)}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      const isHost = sessionStorage.getItem(`hostFor:${sessionId}`) === "1";
      setRole(isHost ? "host" : "peer");
      ws.send(JSON.stringify({ type: "join", clientId, role: isHost ? "host" : "peer" }));
      flushSignalQueue();
      // Keepalive
      setInterval(() => { try { sendSignal({ type: "ping" }); } catch {} }, 15000);
    };

    ws.onmessage = async (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "peers") {
        const others = (msg.peers || []).filter((p) => p !== clientId);
        setPeers(others);
        if (!remoteIdRef.current && others.length > 0) {
          remoteIdRef.current = others[0];
          const isHost = sessionStorage.getItem(`hostFor:${sessionId}`) === "1";
          if (isHost) { await ensurePeerConnection(true); await createOffer(); }
        }
      }
      if (msg.type === "sdp-offer") {
        await ensurePeerConnection(false);
        await pcRef.current.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        const answer = await pcRef.current.createAnswer();
        await pcRef.current.setLocalDescription(answer);
        sendSignal({ type: "sdp-answer", to: msg.from, sdp: answer });
        remoteIdRef.current = msg.from;
      }
      if (msg.type === "sdp-answer") {
        if (pcRef.current) { await pcRef.current.setRemoteDescription(new RTCSessionDescription(msg.sdp)); }
      }
      if (msg.type === "ice-candidate") {
        if (pcRef.current && msg.candidate) { try { await pcRef.current.addIceCandidate(msg.candidate); } catch(e) { console.error(e); } }
      }
    };

    ws.onclose = () => { wsReadyRef.current = false; setConnected(false); };
  }, [sessionId, clientId, sendSignal]);

  const ensurePeerConnection = useCallback(async (createDCIfHost = false) => {
    if (pcRef.current) return pcRef.current;
    const pc = new RTCPeerConnection(PC_CONFIG); pcRef.current = pc;

    pc.onicecandidate = (ev) => {
      if (ev.candidate && remoteIdRef.current) { sendSignal({ type: "ice-candidate", to: remoteIdRef.current, candidate: ev.candidate }); }
    };
    pc.onconnectionstatechange = () => { const st = pc.connectionState; if (st === "connected") setConnected(true); if (["disconnected","failed","closed"].includes(st)) setConnected(false); };

    const isHost = sessionStorage.getItem(`hostFor:${sessionId}`) === "1";
    if (isHost && createDCIfHost) {
      const dc = pc.createDataChannel("file"); attachDataChannel(dc);
    } else { pc.ondatachannel = (ev) => attachDataChannel(ev.channel); }
    return pc;
  }, [sendSignal, sessionId]);

  const attachDataChannel = (dc) => {
    dcRef.current = dc; dc.binaryType = "arraybuffer";
    let recvState = { expecting: null, receivedBytes: 0, chunks: [] };
    dc.onopen = () => { sendQueue.forEach((item) => sendFile(item)); setSendQueue([]); };
    dc.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        if (ev.data.startsWith("META:")) { const meta = JSON.parse(ev.data.slice(5)); recvState = { expecting: meta, receivedBytes: 0, chunks: [] }; setProgressMap((m) => ({ ...m, [meta.id]: { name: meta.name, total: meta.size, sent: 0, recv: 0 } })); }
        else if (ev.data.startsWith("DONE:")) { const meta = JSON.parse(ev.data.slice(5)); const blob = new Blob(recvState.chunks, { type: recvState.expecting?.mime || "application/octet-stream" }); const url = URL.createObjectURL(blob); setReceived((r) => [{ id: meta.id, name: recvState.expecting.name, size: recvState.expecting.size, url }, ...r]); setProgressMap((m) => ({ ...m, [meta.id]: { ...(m[meta.id] || {}), recv: recvState.expecting.size, total: recvState.expecting.size, name: recvState.expecting.name } })); recvState = { expecting: null, receivedBytes: 0, chunks: [] }; }
        else if (ev.data.startsWith("TEXT:")) { const payload = JSON.parse(ev.data.slice(5)); setChat((c) => [{ id: payload.id, who: "peer", text: payload.text, ts: Date.now() }, ...c]); }
      } else {
        if (recvState.expecting) { recvState.chunks.push(ev.data); recvState.receivedBytes += ev.data.byteLength; setProgressMap((m) => { const id = recvState.expecting.id; const curr = m[id] || { name: recvState.expecting.name, total: recvState.expecting.size, sent: 0, recv: 0 }; return { ...m, [id]: { ...curr, recv: Math.min(recvState.receivedBytes, recvState.expecting.size) } }; }); }
      }
    };
  };

  const createOffer = useCallback(async () => {
    const pc = pcRef.current || (await ensurePeerConnection(true));
    const offer = await pc.createOffer(); await pc.setLocalDescription(offer); sendSignal({ type: "sdp-offer", to: remoteIdRef.current, sdp: offer });
  }, [ensurePeerConnection, sendSignal]);

  useEffect(() => { initWebSocket(); }, [initWebSocket]);

  const onFilesPicked = (files) => { Array.from(files).forEach((f) => queueSend(f)); };

  const queueSend = (file) => { const job = { file, id: crypto.randomUUID() }; if (!dcRef.current || dcRef.current.readyState !== "open") { setSendQueue((q) => [...q, job]); } else { sendFile(job); } };

  const sendFile = ({ file, id }) => {
    const dc = dcRef.current; if (!dc || dc.readyState !== "open") return;
    const meta = { id, name: file.name, size: file.size, mime: file.type }; dc.send(`META:${JSON.stringify(meta)}`);
    setProgressMap((m) => ({ ...m, [id]: { name: file.name, total: file.size, sent: 0, recv: m[id]?.recv || 0 } }));
    const reader = file.stream().getReader(); let sentBytes = 0;
    const pump = () => reader.read().then(({ done, value }) => { if (done) { dc.send(`DONE:${JSON.stringify({ id })}`); return; } sentBytes += value.byteLength; dc.send(value); setProgressMap((m) => { const curr = m[id] || { name: file.name, total: file.size, sent: 0, recv: 0 }; return { ...m, [id]: { ...curr, sent: Math.min(sentBytes, file.size) } }; }); if (dc.bufferedAmount > 8 * 1024 * 1024) { setTimeout(pump, 50); } else { pump(); } }); pump();
  };

  const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer?.files?.length) onFilesPicked(e.dataTransfer.files); };

  const sendText = () => { const text = chatInput.trim(); if (!text) return; const dc = dcRef.current; const payload = { id: crypto.randomUUID(), text }; if (dc && dc.readyState === "open") { dc.send(`TEXT:${JSON.stringify(payload)}`); setChat((c) => [{ id: payload.id, who: "me", text, ts: Date.now() }, ...c]); setChatInput(""); } };

  const { url, qrURL } = buildQrLink();

  return (
    <div className="app-wrap">
      <div className="sidebar neu-surface card">
        <div className="header"><div className="title">Session</div><div className="muted">ID: {sessionId?.slice(0, 8)}...</div></div>
        <div className="neu-inset qr"><img src={qrURL} alt="QR" width={220} height={220} /></div>
        <div className="section-gap" />
        <div className="muted" style={{ fontSize: 12 }}>Scan with your phone camera to open: {url}</div>
        <div className="section-gap" />
        <div className="neu-inset card" style={{ padding: 12 }}>
          <div className="title" style={{ fontSize: 16, marginBottom: 8 }}>Peers</div>
          {peers.length === 0 ? (<div className="muted">Waiting for a device to join…</div>) : (peers.map((p) => (<div key={p} className="file-row"><span className="file-name">{p.slice(0, 8)}…</span><span className="file-meta">connected</span></div>)))}
          <div className="section-gap" />
          <div className="file-meta">Connection: {connected ? "WebRTC Connected" : "Not connected"}</div>
        </div>
      </div>

      <div className="main neu-surface card">
        <div className="header"><div className="title">Transfer</div><div className="muted">Bidirectional</div></div>
        <div className="pane neu-inset dropzone" onDragOver={(e) => { e.preventDefault(); }} onDrop={handleDrop}>
          <div style={{ marginBottom: 8 }}><strong>Drop files here</strong> or</div>
          <label className="neu-pressable" style={{ display: "inline-block", padding: "12px 18px", cursor: "pointer" }}>
            <input type="file" multiple onChange={(e) => onFilesPicked(e.target.files)} style={{ display: "none" }} />
            Choose Files
          </label>
        </div>
        <div className="file-list">
          {Object.entries(progressMap).map(([id, p]) => { const sentPct = p.total ? Math.round((p.sent / p.total) * 100) : 0; const recvPct = p.total ? Math.round((p.recv / p.total) * 100) : 0; return (
            <div className="progress-row" key={id}>
              <div className="file-row"><span className="file-name">{p.name}</span><span className="file-meta">{Math.round((p.sent || p.recv || 0)/1024)} KB / {Math.round((p.total||0)/1024)} KB</span></div>
              <div style={{ display: "grid", gap: 6 }}>
                <div className="file-meta">Sent {sentPct}%</div><Progress value={sentPct} />
                <div className="file-meta">Received {recvPct}%</div><Progress value={recvPct} />
              </div>
            </div>
          ); })}
        </div>
        {received.length > 0 && (<div style={{ marginTop: 16 }}><div className="title" style={{ fontSize: 16, marginBottom: 8 }}>Received Files</div>{received.map((f) => (<div key={f.id} className="file-row"><span className="file-name">{f.name}</span><a className="file-meta" href={f.url} download={f.name}>Download</a></div>))}</div>)}
      </div>

      <div className="rightbar neu-surface card">
        <div className="header"><div className="title">Clipboard Chat</div></div>
        <div className="neu-inset card" style={{ minHeight: 220, padding: 12, display: 'grid', gap: 10 }}>
          <Textarea rows={4} value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="Type text here and send…" />
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <Button onClick={() => { setChatInput(""); }} variant="ghost" className="neu-pressable">Clear</Button>
            <Button onClick={sendText} className="neu-pressable">Send</Button>
          </div>
        </div>
        <div className="section-gap" />
        <div className="neu-inset card" style={{ maxHeight: 360, overflow: 'auto', padding: 12 }}>
          {chat.length === 0 ? (<div className="muted">No messages yet.</div>) : (chat.map((m) => (<div key={m.id} className="file-row" style={{ alignItems: 'flex-start' }}><div className="file-name" style={{ fontWeight: 700 }}>{m.who === 'me' ? 'Me' : 'Peer'}</div><div className="file-meta" style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div></div>)))}
        </div>
      </div>
    </div>
  );
}

export default function App() { return (<BrowserRouter><Routes><Route path="/" element={<Home />} /><Route path="/session" element={<Session />} /></Routes></BrowserRouter>); }