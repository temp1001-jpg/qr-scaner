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
      <div className="sidebar glass-surface">
        <div className="header">
          <div>
            <div className="title">EasyMesh</div>
            <div className="subtitle">Cross-platform file transfer</div>
          </div>
          <div className="toggle" onClick={() => setDark(!dark)}>
            {dark ? "☀️ Light" : "🌙 Dark"}
          </div>
        </div>
        <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '32px' }}>
          Connect devices instantly with WebRTC. Start a session on your PC and scan the QR code from your mobile device.
        </p>
        <button onClick={start} className="glass-button accent" style={{ width: "100%", fontSize: '16px', padding: '16px 24px' }}>
          🚀 Start New Session
        </button>
        <div className="section-gap" />
        <div className="glass-inset" style={{ padding: '24px' }}>
          <div style={{ fontSize: '18px', fontWeight: '700', marginBottom: '16px', color: 'var(--text)' }}>
            ✨ How it works
          </div>
          <ol style={{ color: 'var(--text-muted)', lineHeight: 1.8, paddingLeft: '20px' }}>
            <li>Click "Start Session" on your PC</li>
            <li>Scan the QR code with your phone camera</li>
            <li>Send files and messages over direct WebRTC connection</li>
            <li>Enjoy blazing-fast peer-to-peer transfers</li>
          </ol>
        </div>
      </div>
      
      <div className="main glass-surface">
        <div className="header">
          <div>
            <div className="title">Session Preview</div>
            <div className="subtitle">Your session workspace</div>
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '60px 40px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '48px', marginBottom: '20px', animation: 'float 3s ease-in-out infinite' }}>📱💻</div>
          <div style={{ fontSize: '18px', fontWeight: '600', marginBottom: '12px' }}>Ready to Connect</div>
          <div style={{ lineHeight: 1.6 }}>
            Your pairing QR code, file transfer interface, and chat will appear here once you start a session.
          </div>
        </div>
      </div>
      
      <div className="rightbar glass-surface">
        <div className="header">
          <div>
            <div className="title">Live Chat</div>
            <div className="subtitle">Real-time messaging</div>
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '60px 40px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '48px', marginBottom: '20px', animation: 'float 3s ease-in-out infinite', animationDelay: '1s' }}>💬</div>
          <div style={{ fontSize: '18px', fontWeight: '600', marginBottom: '12px' }}>Instant Messaging</div>
          <div style={{ lineHeight: 1.6 }}>
            Copy and paste text between devices, or just chat with connected peers in real-time.
          </div>
        </div>
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
  const [role, setRole] = useState("peer");

  const wsRef = useRef(null);
  const wsReadyRef = useRef(false);
  const wsQueueRef = useRef([]);
  const wsReconnectAttemptsRef = useRef(0);
  const wsReconnectTimerRef = useRef(null);
  const wsKeepAliveTimerRef = useRef(null);

  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const remoteIdRef = useRef(null);
  const isNegotiatingRef = useRef(false);
  const iceRestartAttemptsRef = useRef(0);
  const lastIceRestartAtRef = useRef(0);

  // chat state
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState([]);
  const chatQueueRef = useRef([]);

  // file state
  const [sendQueue, setSendQueue] = useState([]);
  const [progressMap, setProgressMap] = useState({});
  const [received, setReceived] = useState([]);
  const [dataChannelReady, setDataChannelReady] = useState(false);
  const [dragOver, setDragOver] = useState(false);

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

  const scheduleWsReconnect = useCallback(() => {
    if (wsReconnectTimerRef.current) return;
    const attempt = wsReconnectAttemptsRef.current + 1;
    wsReconnectAttemptsRef.current = attempt;
    const delay = Math.min(30000, 1000 * Math.pow(2, attempt));
    console.log(`WebSocket reconnect in ${delay}ms (attempt ${attempt})`);
    wsReconnectTimerRef.current = setTimeout(() => {
      wsReconnectTimerRef.current = null;
      initWebSocket(true);
    }, delay);
  }, []);

  const initWebSocket = useCallback((isReconnect = false) => {
    if (!sessionId) return;

    try {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
      }
    } catch {}

    const url = wsUrlFor(`/api/ws/session/${encodeURIComponent(sessionId)}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      const isHost = sessionStorage.getItem(`hostFor:${sessionId}`) === "1";
      setRole(isHost ? "host" : "peer");
      ws.send(JSON.stringify({ type: "join", clientId, role: isHost ? "host" : "peer" }));
      flushSignalQueue();

      // Reset reconnect attempts on successful open
      wsReconnectAttemptsRef.current = 0;

      // Keepalive
      if (wsKeepAliveTimerRef.current) clearInterval(wsKeepAliveTimerRef.current);
      wsKeepAliveTimerRef.current = setInterval(() => { 
        try { ws.send(JSON.stringify({ type: "ping" })); } catch {}
      }, 15000);
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

    ws.onerror = () => {
      try { ws.close(); } catch {}
    };

    ws.onclose = () => { 
      wsReadyRef.current = false; 
      setConnected(false);
      if (wsKeepAliveTimerRef.current) { clearInterval(wsKeepAliveTimerRef.current); wsKeepAliveTimerRef.current = null; }
      scheduleWsReconnect(); 
    };
  }, [sessionId, clientId, sendSignal, scheduleWsReconnect]);

  const ensurePeerConnection = useCallback(async (createDCIfHost = false) => {
    if (pcRef.current) return pcRef.current;
    const pc = new RTCPeerConnection(PC_CONFIG); pcRef.current = pc;

    pc.onicecandidate = (ev) => {
      if (ev.candidate && remoteIdRef.current) { 
        sendSignal({ type: "ice-candidate", to: remoteIdRef.current, candidate: ev.candidate }); 
      }
    };

    pc.onnegotiationneeded = async () => {
      if (isNegotiatingRef.current) return;
      if (!remoteIdRef.current) return;
      try {
        isNegotiatingRef.current = true;
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        sendSignal({ type: "sdp-offer", to: remoteIdRef.current, sdp: offer });
      } catch (e) {
        console.error("Negotiation failed", e);
      } finally {
        setTimeout(() => { isNegotiatingRef.current = false; }, 500);
      }
    };
    
    pc.onconnectionstatechange = () => { 
      const st = pc.connectionState; 
      console.log("Peer connection state changed:", st);
      
      if (st === "connected") {
        setConnected(true);
        iceRestartAttemptsRef.current = 0;
      } else if (["disconnected","failed","closed"].includes(st)) {
        setConnected(false);
        setDataChannelReady(false);
        
        // Update all pending file transfers to error status on connection loss
        setProgressMap((m) => {
          const updated = { ...m };
          Object.keys(updated).forEach(id => {
            if (updated[id].status === 'sending' || updated[id].status === 'receiving') {
              updated[id].status = 'error';
            }
          });
          return updated;
        });

        // Try a gentle ICE restart on transient disconnect
        if (st === "disconnected" || st === "failed") {
          attemptIceRestart();
        }
      } else if (st === "connecting") {
        console.log("Peer connection reconnecting...");
      }
    };

    // Add ICE connection state monitoring
    pc.oniceconnectionstatechange = () => {
      const iceState = pc.iceConnectionState;
      console.log("ICE connection state changed:", iceState);
      
      if (iceState === "failed" || iceState === "disconnected") {
        console.warn("ICE connection issues detected:", iceState);
        if (iceState === "failed") {
          // Mark all pending transfers as failed
          setProgressMap((m) => {
            const updated = { ...m };
            Object.keys(updated).forEach(id => {
              if (updated[id].status === 'sending' || updated[id].status === 'receiving') {
                updated[id].status = 'error';
              }
            });
            return updated;
          });
        }
        // attempt restart after a short delay
        setTimeout(() => attemptIceRestart(), 1500);
      }
    };

    const attemptIceRestart = async () => {
      const now = Date.now();
      if (!pcRef.current || !remoteIdRef.current) return;
      if (now - lastIceRestartAtRef.current < 5000) return;
      if (iceRestartAttemptsRef.current >= 3) return;
      try {
        const offer = await pc.createOffer({ iceRestart: true });
        await pc.setLocalDescription(offer);
        sendSignal({ type: "sdp-offer", to: remoteIdRef.current, sdp: offer });
        iceRestartAttemptsRef.current += 1;
        lastIceRestartAtRef.current = now;
        console.log("Attempted ICE restart", iceRestartAttemptsRef.current);
      } catch (e) {
        console.error("ICE restart failed", e);
      }
    };

    const isHost = sessionStorage.getItem(`hostFor:${sessionId}`) === "1";
    if (isHost && createDCIfHost) {
      // Configure data channel for reliable ordered file transfer
      const dc = pc.createDataChannel("file", {
        ordered: true
      }); 
      attachDataChannel(dc);
    } else { 
      pc.ondatachannel = (ev) => attachDataChannel(ev.channel); 
    }
    return pc;
  }, [sendSignal, sessionId]);

  const attachDataChannel = (dc) => {
    dcRef.current = dc; 
    dc.binaryType = "arraybuffer";
    // Use buffered amount threshold for proper backpressure
    try { dc.bufferedAmountLowThreshold = 64 * 1024; } catch {}
    
    let recvState = { expecting: null, receivedBytes: 0, chunks: [] };
    let dcKeepAlive = null;
    
    dc.onopen = () => { 
      console.log("Data channel opened, processing queued items");
      setDataChannelReady(true);
      
      // Process queued files
      sendQueue.forEach((item) => { try { sendFile(item); } catch {} }); 
      setSendQueue([]);
      
      // Process queued chat messages
      while (chatQueueRef.current.length) { 
        const msg = chatQueueRef.current.shift(); 
        try { 
          dc.send(msg); 
          console.log("Sent queued message");
        } catch (error) {
          console.error("Failed to send queued message:", error);
        }
      }

      // Lightweight keepalive to preserve NAT bindings
      dcKeepAlive = setInterval(() => {
        if (dc.readyState === "open") {
          try { dc.send("HB"); } catch {}
        }
      }, 20000);
    };
    
    dc.onerror = (error) => {
      console.error("Data channel error:", error);
      setDataChannelReady(false);
      
      // Update all pending file transfers to error status
      setProgressMap((m) => {
        const updated = { ...m };
        Object.keys(updated).forEach(id => {
          if (updated[id].status === 'sending' || updated[id].status === 'receiving') {
            updated[id].status = 'error';
          }
        });
        return updated;
      });
    };
    
    dc.onclose = () => {
      console.log("Data channel closed");
      setDataChannelReady(false);
      if (dcKeepAlive) { clearInterval(dcKeepAlive); dcKeepAlive = null; }
      
      // Update all pending file transfers to error status
      setProgressMap((m) => {
        const updated = { ...m };
        Object.keys(updated).forEach(id => {
          if (updated[id].status === 'sending' || updated[id].status === 'receiving') {
            updated[id].status = 'error';
          }
        });
        return updated;
      });
    };
    
    // Monitor data channel state periodically during file transfers
    const monitorConnection = () => {
      if (dc.readyState !== "open" && dataChannelReady) {
        console.warn("Data channel state changed unexpectedly:", dc.readyState);
        setDataChannelReady(false);
      }
    };
    
    const connectionMonitor = setInterval(monitorConnection, 1000);
    
    // Clean up monitor when data channel closes
    dc.addEventListener('close', () => {
      clearInterval(connectionMonitor);
      if (dcKeepAlive) { clearInterval(dcKeepAlive); dcKeepAlive = null; }
    });
    
    // Check if data channel is already open when attached
    if (dc.readyState === "open") {
      console.log("Data channel was already open when attached");
      setDataChannelReady(true);
    }
    
    dc.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        if (ev.data.startsWith("META:")) { 
          const meta = JSON.parse(ev.data.slice(5)); 
          recvState = { expecting: meta, receivedBytes: 0, chunks: [] }; 
          setProgressMap((m) => ({ 
            ...m, 
            [meta.id]: { 
              name: meta.name, 
              total: meta.size, 
              sent: m[meta.id]?.sent || 0, 
              recv: 0,
              status: 'receiving'
            } 
          })); 
        }
        else if (ev.data.startsWith("DONE:")) { 
          const meta = JSON.parse(ev.data.slice(5)); 
          const blob = new Blob(recvState.chunks, { type: recvState.expecting?.mime || "application/octet-stream" }); 
          const url = URL.createObjectURL(blob); 
          setReceived((r) => [{ id: meta.id, name: recvState.expecting.name, size: recvState.expecting.size, url }, ...r]); 
          setProgressMap((m) => ({ 
            ...m, 
            [meta.id]: { 
              ...(m[meta.id] || {}), 
              recv: recvState.expecting.size, 
              total: recvState.expecting.size, 
              name: recvState.expecting.name,
              status: 'completed'
            } 
          })); 
          recvState = { expecting: null, receivedBytes: 0, chunks: [] }; 
        }
        else if (ev.data.startsWith("TEXT:")) { 
          const payload = JSON.parse(ev.data.slice(5)); 
          setChat((c) => [{ id: payload.id, who: "peer", text: payload.text, ts: Date.now() }, ...c]); 
        } else if (ev.data === "HB") {
          // ignore heartbeat
        }
      } else {
        if (recvState.expecting) { 
          recvState.chunks.push(ev.data); 
          recvState.receivedBytes += ev.data.byteLength; 
          setProgressMap((m) => { 
            const id = recvState.expecting.id; 
            const curr = m[id] || { name: recvState.expecting.name, total: recvState.expecting.size, sent: 0, recv: 0, status: 'receiving' }; 
            return { 
              ...m, 
              [id]: { 
                ...curr, 
                recv: Math.min(recvState.receivedBytes, recvState.expecting.size),
                status: 'receiving'
              } 
            }; 
          }); 
        }
      }
    };
  };

  const createOffer = useCallback(async () => {
    const pc = pcRef.current || (await ensurePeerConnection(true));
    const offer = await pc.createOffer(); await pc.setLocalDescription(offer); sendSignal({ type: "sdp-offer", to: remoteIdRef.current, sdp: offer });
  }, [ensurePeerConnection, sendSignal]);

  useEffect(() => { initWebSocket(); return () => {
    try { if (wsRef.current) wsRef.current.close(); } catch {}
    try { if (wsKeepAliveTimerRef.current) clearInterval(wsKeepAliveTimerRef.current); } catch {}
  }; }, [initWebSocket]);

  const onFilesPicked = (files) => { Array.from(files).forEach((f) => queueSend(f)); };

  // Enhanced file transfer with FTP detection disabled as per user choice (WebRTC-only)
  const detectSameNetwork = async () => { return true; };
  const shouldUseFTP = (fileSize) => { return false; };

  const queueSend = async (file) => { 
    const job = { file, id: crypto.randomUUID() };
    const dc = dcRef.current;
    
    // Using pure WebRTC P2P as per user choice (A)
    if (await detectSameNetwork() && shouldUseFTP(file.size)) {
      console.log(`Large file detected (${file.size} bytes), using WebRTC transfer`);
    }
    
    // Always queue first, then try to send immediately if channel is ready
    setSendQueue((q) => [...q, job]);
    
    if (dc && dc.readyState === "open") {
      // Remove from queue and send immediately
      setSendQueue((q) => q.filter(item => item.id !== job.id));
      sendFile(job);
    }
    // If not ready, it will be sent when data channel opens in attachDataChannel
  };

  const sendFile = async ({ file, id }) => {
    const dc = dcRef.current; 
    
    if (!dc || dc.readyState !== "open") {
      console.log("Data channel not ready for file transfer, keeping in queue");
      return;
    }
    
    try {
      const meta = { id, name: file.name, size: file.size, mime: file.type }; 
      dc.send(`META:${JSON.stringify(meta)}`);
      
      // Initialize progress properly
      setProgressMap((m) => ({ 
        ...m, 
        [id]: { 
          name: file.name, 
          total: file.size, 
          sent: 0, 
          recv: 0,
          status: 'sending'
        } 
      }));
      
      const reader = file.stream().getReader(); 
      let sentBytes = 0;
      let retryCount = 0;
      const MAX_RETRIES = 3;
      const CHUNK_SIZE = 16384; // 16KB chunks for stability and performance
      const BUFFER_LOW_THRESHOLD = dc.bufferedAmountLowThreshold || 64 * 1024; // ~64KB

      const waitForDrain = () => new Promise((resolve) => {
        if (dc.bufferedAmount <= BUFFER_LOW_THRESHOLD) return resolve();
        const handle = () => { dc.removeEventListener('bufferedamountlow', handle); resolve(); };
        dc.addEventListener('bufferedamountlow', handle);
      });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Slice into smaller chunks explicitly
        let offset = 0;
        while (offset < value.byteLength) {
          const chunkEnd = Math.min(offset + CHUNK_SIZE, value.byteLength);
          const chunk = value.slice(offset, chunkEnd);

          try {
            dc.send(chunk);
            sentBytes += chunk.byteLength;
            offset = chunkEnd;
          } catch (error) {
            console.error(`Failed to send file chunk (attempt ${retryCount + 1}):`, error);
            if (retryCount < MAX_RETRIES && dc.readyState === "open") {
              retryCount++;
              await new Promise(r => setTimeout(r, 200 * retryCount));
              continue;
            } else {
              console.error("Max retries exceeded or data channel closed");
              setProgressMap((m) => ({ 
                ...m, 
                [id]: { 
                  ...m[id], 
                  status: 'error'
                } 
              }));
              try { reader.cancel(); } catch {}
              return;
            }
          }

          // Update progress after each successful chunk
          setProgressMap((m) => { 
            const curr = m[id] || { name: file.name, total: file.size, sent: 0, recv: 0, status: 'sending' }; 
            return { 
              ...m, 
              [id]: { 
                ...curr, 
                sent: sentBytes,
                status: 'sending'
              } 
            }; 
          }); 

          // Apply proper backpressure waiting if buffer is high
          if (dc.bufferedAmount > BUFFER_LOW_THRESHOLD) {
            await waitForDrain();
          }
        }
      }

      // Send completion marker
      try {
        dc.send(`DONE:${JSON.stringify({ id })}`); 
        setProgressMap((m) => ({ 
          ...m, 
          [id]: { 
            ...m[id], 
            sent: file.size,
            status: 'completed'
          } 
        }));
      } catch (error) {
        console.error("Failed to send file completion signal:", error);
        setProgressMap((m) => ({ 
          ...m, 
          [id]: { 
            ...m[id], 
            status: 'error'
          } 
        }));
      }
      
    } catch (error) {
      console.error("Failed to initiate file transfer:", error);
      setProgressMap((m) => ({ 
        ...m, 
        [id]: { 
          name: file.name, 
          total: file.size, 
          sent: 0, 
          recv: 0,
          status: 'error'
        } 
      }));
    }
  };

  const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer?.files?.length) onFilesPicked(e.dataTransfer.files); };

  const sendText = () => { 
    const text = chatInput.trim(); 
    if (!text) return; 
    
    const dc = dcRef.current; 
    const payload = { id: crypto.randomUUID(), text };
    const messageToSend = `TEXT:${JSON.stringify(payload)}`;
    
    if (dc && dc.readyState === "open") { 
      // Data channel is ready, send immediately
      try {
        dc.send(messageToSend);
        setChat((c) => [{ id: payload.id, who: "me", text, ts: Date.now() }, ...c]); 
        setChatInput("");
      } catch (error) {
        console.error("Failed to send message:", error);
        // Queue the message for retry
        chatQueueRef.current.push(messageToSend);
        setChat((c) => [{ id: payload.id, who: "me", text, ts: Date.now() }, ...c]); 
        setChatInput("");
      }
    } else {
      // Data channel not ready, queue the message
      console.log("Data channel not ready, queuing message");
      chatQueueRef.current.push(messageToSend);
      setChat((c) => [{ id: payload.id, who: "me", text, ts: Date.now() }, ...c]); 
      setChatInput("");
    }
  };

  const { url, qrURL } = buildQrLink();

  return (
    <div className="app-wrap">
      <div className="sidebar glass-surface">
        <div className="header">
          <div>
            <div className="title">Session</div>
            <div className="subtitle">ID: {sessionId?.slice(0, 8)}...</div>
          </div>
        </div>
        
        <div className="qr">
          <img src={qrURL} alt="QR" width={240} height={240} />
        </div>
        
        <div className="section-gap" />
        
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 }}>
          📱 Scan with camera to open:<br />
          <span style={{ wordBreak: 'break-all' }}>{url}</span>
        </div>
        
        <div className="section-gap" />
        
        <div className="glass-inset" style={{ padding: '20px' }}>
          <div style={{ fontSize: '16px', fontWeight: '700', marginBottom: '16px', color: 'var(--text)' }}>
            👥 Connected Peers
          </div>
          
          {peers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-muted)' }}>
              <div className="loading-spinner" style={{ margin: '0 auto 12px' }}></div>
              <div>Waiting for devices to join...</div>
            </div>
          ) : (
            <div className="peers-list">
              {peers.map((p) => (
                <div key={p} className="peer-item">
                  <div className="peer-avatar">{p.slice(0, 2).toUpperCase()}</div>
                  <div className="peer-info">
                    <div className="peer-name">{p.slice(0, 8)}...</div>
                    <div className="peer-status">✅ Connected</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          <div className="connection-status">
            <div className={`connection-dot ${connected ? (dataChannelReady ? 'connected' : 'connecting') : 'disconnected'}`}></div>
            <div className="connection-text">
              {connected ? (dataChannelReady ? "🚀 Ready for transfers" : "🔄 Establishing connection...") : "❌ Not connected"}
            </div>
          </div>
        </div>
      </div>

      <div className="main glass-surface">
        <div className="header">
          <div>
            <div className="title">File Transfer</div>
            <div className="subtitle">Drag &amp; drop or select files</div>
          </div>
        </div>
        
        <div 
          className={`dropzone glass-inset ${dragOver ? 'dragover' : ''}`} 
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} 
          onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
          onDrop={(e) => { handleDrop(e); setDragOver(false); }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px', animation: 'float 3s ease-in-out infinite' }}>
            📁
          </div>
          <div style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px', color: 'var(--text)' }}>
            Drop files here
          </div>
          <div style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '20px' }}>
            or click to browse
          </div>
          <label className="glass-button accent" style={{ cursor: 'pointer' }}>
            <input type="file" multiple onChange={(e) => onFilesPicked(e.target.files)} style={{ display: 'none' }} />
            📎 Choose Files
          </label>
        </div>
        
        <div className="file-list">
          {Object.entries(progressMap).map(([id, p]) => {
            const sentPct = p.total ? Math.round((p.sent / p.total) * 100) : 0;
            const recvPct = p.total ? Math.round((p.recv / p.total) * 100) : 0;
            
            return (
              <div className="progress-row" key={id}>
                <div className="file-row">
                  <div>
                    <div className="file-name">📄 {p.name}</div>
                    <div className="file-meta">
                      {Math.round((p.sent || p.recv || 0)/1024)} KB / {Math.round((p.total||0)/1024)} KB
                    </div>
                  </div>
                  <div className={`file-status ${p.status || 'sending'}`}>
                    {p.status || 'sending'}
                  </div>
                </div>
                
                <div className="progress-container">
                  {p.sent &gt; 0 &amp;&amp; (
                    <div className="progress-item">
                      <div className="progress-label">📤 Sent</div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${sentPct}%` }}></div>
                      </div>
                      <div className="progress-text">{sentPct}%</div>
                    </div>
                  )}
                  
                  {p.recv &gt; 0 &amp;&amp; (
                    <div className="progress-item">
                      <div className="progress-label">📥 Received</div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${recvPct}%` }}></div>
                      </div>
                      <div className="progress-text">{recvPct}%</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        
        {received.length &gt; 0 &amp;&amp; (
          <div className="received-files">
            <div style={{ fontSize: '18px', fontWeight: '700', marginBottom: '16px', color: 'var(--text)' }}>
              📥 Received Files
            </div>
            {received.map((f) => (
              <div key={f.id} className="received-file">
                <div className="received-file-info">
                  <div className="received-file-name">📄 {f.name}</div>
                  <div className="received-file-size">{Math.round(f.size/1024)} KB</div>
                </div>
                <a className="download-button" href={f.url} download={f.name}>
                  ⬇️ Download
                </a>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rightbar glass-surface">
        <div className="header">
          <div>
            <div className="title">Live Chat</div>
            <div className="subtitle">Instant messaging</div>
          </div>
        </div>
        
        <div className="chat-container">
          <div className="chat-input-area">
            <Textarea 
              rows={4} 
              value={chatInput} 
              onChange={(e) => setChatInput(e.target.value)} 
              placeholder="Type your message here..." 
              style={{ border: 'none', background: 'transparent' }}
            />
            <div className="chat-controls">
              <div className={`chat-status ${!dataChannelReady ? 'connecting' : ''}`}>
                <div className="chat-status-dot"></div>
                {dataChannelReady ? "✅ Ready to send" : "🔄 Connecting..."}
              </div>
              <div className="chat-buttons">
                <button onClick={() => { setChatInput(""); }} className="glass-button">
                  🗑️ Clear
                </button>
                <button 
                  onClick={sendText} 
                  className="glass-button accent"
                  disabled={!chatInput.trim()}
                  style={{ 
                    opacity: !chatInput.trim() ? 0.5 : 1,
                    cursor: !chatInput.trim() ? 'not-allowed' : 'pointer'
                  }}
                >
                  🚀 Send
                </button>
              </div>
            </div>
          </div>
          
          <div className="chat-messages">
            {chat.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>💬</div>
                <div>No messages yet.</div>
                <div style={{ fontSize: '12px', marginTop: '8px' }}>Start the conversation!</div>
              </div>
            ) : (
              chat.map((m) => (
                <div key={m.id} className="message">
                  <div className={`message-author ${m.who === 'me' ? 'me' : ''}`}>
                    {m.who === 'me' ? '👤 You' : '👥 Peer'}
                  </div>
                  <div className="message-content">{m.text}</div>
                </div>
              ))}
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() { return (<BrowserRouter><Routes><Route path="/" element={<Home />} /><Route path="/session" element={<Session />} /></Routes></BrowserRouter>); }