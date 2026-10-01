import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "./api";
export type VoiceStatus =
  | "disconnected"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "error";
type Resources = {
  closed: boolean;
  ready: boolean;
  stream?: MediaStream;
  ctx?: AudioContext;
  socket?: WebSocket;
  worklet?: AudioWorkletNode;
  analyser?: AnalyserNode;
  sources: Set<AudioBufferSourceNode>;
  next: number;
  timer?: ReturnType<typeof setInterval>;
  deadline?: ReturnType<typeof setTimeout>;
};
export function useVoice() {
  const [status, setStatus] = useState<VoiceStatus>("disconnected");
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState<ChatMessage[]>([]);
  const [seconds, setSeconds] = useState(0);
  const [muted, setMuted] = useState(false);
  const resources = useRef<Resources | null>(null);
  const statusRef = useRef(status);
  statusRef.current = status;
  function flush(r: Resources) {
    r.sources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already ended */
      }
    });
    r.sources.clear();
    r.next = r.ctx?.currentTime || 0;
  }
  function stop(next: VoiceStatus = "disconnected") {
    const r = resources.current;
    if (r) {
      r.closed = true;
      clearInterval(r.timer);
      clearTimeout(r.deadline);
      flush(r);
      r.worklet?.disconnect();
      r.stream?.getTracks().forEach((t) => t.stop());
      r.socket?.close();
      void r.ctx?.close().catch(() => {});
      resources.current = null;
    }
    setStatus(next);
    setMuted(false);
  }
  async function start() {
    if (resources.current) return;
    setError("");
    setStatus("connecting");
    setSeconds(0);
    setTranscript([]);
    setMuted(false);
    const r: Resources = {
      closed: false,
      ready: false,
      sources: new Set(),
      next: 0,
    };
    resources.current = r;
    function fail(message: string) {
      if (r.closed) return;
      setError(message);
      stop("error");
    }
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Microphone access requires HTTPS or localhost and a supported browser.",
        );
      // Resume playback from the user gesture before permission/network awaits.
      r.ctx = new AudioContext();
      await r.ctx.resume();
      if (r.closed) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (r.closed) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      r.stream = stream;
      stream.getAudioTracks().forEach((t) => {
        t.onended = () =>
          fail("Microphone access ended. Reconnect to continue.");
      });
      await r.ctx.audioWorklet.addModule("/pcm-capture.js");
      if (r.closed) return;
      const source = r.ctx.createMediaStreamSource(stream);
      r.analyser = r.ctx.createAnalyser();
      r.analyser.fftSize = 256;
      r.worklet = new AudioWorkletNode(r.ctx, "pcm-capture");
      const silent = r.ctx.createGain();
      silent.gain.value = 0;
      source.connect(r.analyser);
      r.analyser.connect(r.worklet);
      r.worklet.connect(silent);
      silent.connect(r.ctx.destination);
      const socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/voice`,
      );
      r.socket = socket;
      socket.binaryType = "arraybuffer";
      r.deadline = setTimeout(
        () =>
          fail(
            "The voice service did not connect in time. Check access and try again.",
          ),
        40000,
      );
      r.worklet.port.onmessage = (event) => {
        if (r.ready && socket.readyState === WebSocket.OPEN) {
          if (socket.bufferedAmount > 192000) {
            fail(
              "The network cannot keep up with microphone audio. Reconnect on a faster connection.",
            );
            return;
          }
          socket.send(event.data);
        }
      };
      socket.onmessage = (event) => {
        if (r.closed) return;
        if (event.data instanceof ArrayBuffer) {
          const view = new DataView(event.data);
          if (view.byteLength % 2 || !r.ctx) {
            fail("The voice service sent invalid audio.");
            return;
          }
          const buffer = r.ctx.createBuffer(1, view.byteLength / 2, 24000);
          const data = buffer.getChannelData(0);
          for (let i = 0; i < data.length; i++)
            data[i] = view.getInt16(i * 2, true) / 32768;
          if (r.next - r.ctx.currentTime > 15) {
            fail("Audio playback fell behind. Start a new conversation.");
            return;
          }
          const playback = r.ctx.createBufferSource();
          playback.buffer = buffer;
          playback.connect(r.ctx.destination);
          r.sources.add(playback);
          playback.onended = () => {
            r.sources.delete(playback);
            if (
              !r.closed &&
              r.sources.size === 0 &&
              statusRef.current === "speaking"
            )
              setStatus("listening");
          };
          const startAt = Math.max(r.next, r.ctx.currentTime + 0.025);
          playback.start(startAt);
          r.next = startAt + buffer.duration;
          setStatus("speaking");
          return;
        }
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "SettingsApplied") {
            clearTimeout(r.deadline);
            r.ready = true;
            setStatus("listening");
            const started = Date.now();
            r.timer = setInterval(() => {
              setSeconds(Math.floor((Date.now() - started) / 1000));
              if (socket.readyState === WebSocket.OPEN)
                socket.send(JSON.stringify({ type: "KeepAlive" }));
            }, 1000);
            r.deadline = setTimeout(() => {
              if (!r.closed) {
                setError(
                  "The demo conversation reached its time limit. Start a new conversation.",
                );
                stop();
              }
            }, msg.max_seconds * 1000);
          } else if (msg.type === "ConversationText")
            setTranscript((t) => [
              ...t.slice(-99),
              { id: crypto.randomUUID(), role: msg.role, content: msg.content },
            ]);
          else if (msg.type === "UserStartedSpeaking") {
            flush(r);
            setStatus("listening");
          } else if (msg.type === "AgentThinking") setStatus("thinking");
          else if (msg.type === "AgentStartedSpeaking") setStatus("speaking");
          else if (msg.type === "AgentAudioDone" && r.sources.size === 0)
            setStatus("listening");
          else if (msg.type === "Error") fail(msg.message);
          else if (msg.type === "Warning") setError(msg.message);
        } catch {
          fail("The voice service sent an unreadable event. Please reconnect.");
        }
      };
      socket.onerror = () =>
        fail(
          "Voice connection failed. Check your session, API configuration and network, then reconnect.",
        );
      socket.onclose = () => {
        if (!r.closed)
          fail("The voice connection closed. Start a new conversation.");
      };
    } catch (e) {
      if (r.closed) return;
      const message =
        e instanceof DOMException &&
        (e.name === "NotAllowedError" || e.name === "PermissionDeniedError")
          ? "Microphone permission was denied. Allow access in your browser and try again."
          : e instanceof DOMException && e.name === "NotFoundError"
            ? "No microphone was found. Connect one and try again."
            : e instanceof Error
              ? e.message
              : "Could not start the microphone.";
      fail(message);
    }
  }
  function toggleMute() {
    const r = resources.current;
    if (r?.stream) {
      r.stream.getAudioTracks().forEach((t) => {
        t.enabled = muted;
      });
      setMuted(!muted);
    }
  }
  useEffect(
    () => () => {
      const r = resources.current;
      if (r) {
        r.closed = true;
        clearInterval(r.timer);
        clearTimeout(r.deadline);
        flush(r);
        r.stream?.getTracks().forEach((t) => t.stop());
        r.socket?.close();
        void r.ctx?.close().catch(() => {});
      }
    },
    [],
  );
  return {
    status,
    error,
    seconds,
    transcript,
    muted,
    start,
    stop,
    toggleMute,
    analyser: () => resources.current?.analyser,
    active: !["disconnected", "error"].includes(status),
  };
}
