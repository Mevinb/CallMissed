import { useEffect, useRef } from "react";
import {
  Radio,
  AudioLines,
  MicOff,
  Mic,
  Square,
  ShieldCheck,
  MessageSquare,
} from "lucide-react";
import type { useVoice } from "../useVoice";
import type { Session } from "../api";
import { Notice } from "./Shared";
export default function VoiceAgent({
  voice,
  session,
}: {
  voice: ReturnType<typeof useVoice>;
  session: Session;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<HTMLDivElement>(null);
  useEffect(() => {
    last.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [voice.transcript]);
  useEffect(() => {
    let frame: number;
    const draw = () => {
      const ctx = canvas.current?.getContext("2d");
      if (ctx) {
        const w = 320,
          h = 70;
        ctx.clearRect(0, 0, w, h);
        const analyser = voice.analyser();
        const data = new Uint8Array(128);
        if (analyser) analyser.getByteTimeDomainData(data);
        ctx.strokeStyle = voice.muted ? "#68758d" : "#8aabff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < data.length; i++) {
          const y = analyser ? h / 2 + (data[i] - 128) * 0.7 : h / 2;
          const x = (i * w) / (data.length - 1);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      frame = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(frame);
  }, [voice.active, voice.muted]);
  const statusLabels = {
    disconnected: "Ready when you are",
    connecting: "Connecting…",
    listening: voice.muted ? "Microphone muted" : "Listening to you",
    thinking: "Thinking…",
    speaking: "Agent speaking",
    error: "Connection needs attention",
  };
  return (
    <section className="voice-workspace" aria-label="Voice conversation">
      <div className="voice-stage">
        <div className="voice-stage-label">
          <Radio size={15} />
          Real-time conversation
        </div>
        <div className={`voice-orb ${voice.status}`} aria-hidden="true">
          <div className="orb-inner">
            <AudioLines size={64} strokeWidth={1.3} />
          </div>
        </div>
        <h2 role="status" aria-live="polite">
          {statusLabels[voice.status]}
        </h2>
        <p>
          {voice.active
            ? "Speak naturally. You can interrupt the agent at any time."
            : "An open mic. A helpful voice. A conversation that flows."}
        </p>
        <canvas
          ref={canvas}
          width={320}
          height={70}
          className="voice-wave"
          aria-label="Live microphone waveform"
        />
        <div className="voice-controls">
          {voice.active ? (
            <>
              <button
                className="round-button"
                aria-label={
                  voice.muted ? "Unmute microphone" : "Mute microphone"
                }
                onClick={voice.toggleMute}
                disabled={voice.status === "connecting"}
              >
                {voice.muted ? <MicOff size={20} /> : <Mic size={20} />}
              </button>
              <button className="stop-button" onClick={() => voice.stop()}>
                <Square size={15} />
                Stop conversation
              </button>
            </>
          ) : (
            <button
              className="primary-button"
              onClick={() => void voice.start()}
            >
              <Mic size={18} />
              Start conversation
            </button>
          )}
        </div>
        <div className="voice-status">
          <span className={`status-dot ${voice.active ? "connected" : ""}`} />
          <span>
            {voice.active
              ? `${String(Math.floor(voice.seconds / 60)).padStart(2, "0")}:${String(voice.seconds % 60).padStart(2, "0")}`
              : "Disconnected"}
          </span>
          <span className="status-divider" />
          {voice.active
            ? voice.muted
              ? "Mic off"
              : voice.status === "connecting"
                ? "Requesting microphone"
                : "Mic on"
            : `Up to ${Math.floor(session.voice_max_seconds / 60)} minutes per call`}
        </div>
        {voice.error && <Notice>{voice.error}</Notice>}
        <div className="voice-tip">
          <ShieldCheck size={17} />
          <p>
            Microphone access starts with your permission.
            <br />
            Stopping a call releases the microphone.
          </p>
        </div>
      </div>
      <div className="transcript-panel">
        <div className="gallery-header">
          <h3>Conversation transcript</h3>
          <span className="live-label">
            {voice.active ? "Live" : "This session"}
          </span>
        </div>
        <div className="transcript-scroll">
          {voice.transcript.length === 0 ? (
            <div className="transcript-empty">
              <MessageSquare size={28} />
              <h3>Words, as they happen.</h3>
              <p>
                Your conversation will appear here
                <br />
                once you start talking.
              </p>
            </div>
          ) : (
            voice.transcript.map((m) => (
              <div key={m.id} className={`transcript-message ${m.role}`}>
                <span>{m.role === "user" ? "You" : "Voice agent"}</span>
                <p>{m.content}</p>
              </div>
            ))
          )}
          <div ref={last} />
        </div>
      </div>
    </section>
  );
}
