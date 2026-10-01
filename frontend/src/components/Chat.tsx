import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  ChevronRight,
  AudioLines,
  LoaderCircle,
  Square,
  ArrowUp,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "../api";
import type { ChatMessage, Session } from "../api";
import { Notice, CopyButton } from "./Shared";
function restoreChat(): ChatMessage[] {
  try {
    const data = JSON.parse(sessionStorage.getItem("cm-chat") || "[]");
    return Array.isArray(data)
      ? data
          .filter(
            (x) =>
              ["user", "assistant"].includes(x.role) &&
              typeof x.content === "string",
          )
          .slice(-80)
      : [];
  } catch {
    return [];
  }
}
export default function Chat({
  session,
  resetToken,
}: {
  session: Session;
  resetToken: number;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(restoreChat);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const resetSeen = useRef(resetToken);
  useEffect(() => {
    try {
      sessionStorage.setItem("cm-chat", JSON.stringify(messages));
    } catch {
      /* Keep current in-memory conversation if browser storage is full. */
    }
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    if (resetSeen.current !== resetToken) {
      resetSeen.current = resetToken;
      abort.current?.abort();
      abort.current = null;
      setBusy(false);
      setMessages([]);
      setError("");
      setInput("");
    }
  }, [resetToken]);
  const suggestions = [
    {
      label: "Make something click",
      text: "Explain how WebSockets work using a simple everyday analogy.",
    },
    {
      label: "Find a fresh perspective",
      text: "Give me three unusual project ideas that combine voice and AI.",
    },
    {
      label: "Get a head start",
      text: "Help me plan a focused week of learning Python backend development.",
    },
  ];
  async function send(prompt = input) {
    const text = prompt.trim();
    if (!text || busy) return;
    const history = messages.filter((m) => !m.failed && m.content);
    if (history.length >= 39) {
      setError(
        "This conversation has reached its limit. Start a new chat to continue.",
      );
      return;
    }
    const user: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    const assistant: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
    };
    setInput("");
    setError("");
    setBusy(true);
    setMessages((m) => [...m, user, assistant]);
    const controller = new AbortController();
    abort.current = controller;
    try {
      await streamChat([...history, user], controller.signal, (content) => {
        if (abort.current === controller)
          setMessages((m) =>
            m.map((x) =>
              x.id === assistant.id
                ? { ...x, content: x.content + content }
                : x,
            ),
          );
      });
    } catch (e) {
      if (abort.current !== controller) return;
      const msg = controller.signal.aborted
        ? "Response stopped."
        : e instanceof Error
          ? e.message
          : "Could not send your message.";
      setError(msg);
      setMessages((m) =>
        m.map((x) =>
          x.id === assistant.id || x.id === user.id
            ? { ...x, failed: true }
            : x,
        ),
      );
      setInput(text);
    } finally {
      if (abort.current === controller) {
        setBusy(false);
        abort.current = null;
        textarea.current?.focus();
      }
    }
  }
  return (
    <section className="chat-workspace" aria-label="AI chat">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="welcome-mark">
              <Sparkles size={28} />
            </div>
            <span className="small-muted">Your everyday thinking partner</span>
            <h2>Where shall we begin?</h2>
            <p>
              Ask a question, work through an idea,
              <br />
              or follow your curiosity.
            </p>
            <div className="suggestion-grid">
              {suggestions.map((s) => (
                <button
                  key={s.label}
                  onClick={() => {
                    setInput(s.text);
                    textarea.current?.focus();
                  }}
                >
                  <span>{s.label}</span>
                  <p>{s.text}</p>
                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages">
            {messages.map((m) => (
              <div className={`message ${m.role}`} key={m.id}>
                <div className="message-avatar">
                  {m.role === "assistant" ? <AudioLines size={17} /> : "M"}
                </div>
                <div className="message-body">
                  <div className="message-author">
                    {m.role === "assistant" ? "CallMissed" : "You"}
                    {m.failed && (
                      <span className="interrupted">Interrupted</span>
                    )}
                  </div>
                  {m.content ? (
                    <div className="markdown">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ children, ...props }) => (
                            <a
                              {...props}
                              target="_blank"
                              rel="noreferrer noopener"
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  ) : !m.failed ? (
                    <div className="thinking">
                      <LoaderCircle className="spin" size={15} />
                      Thinking…
                    </div>
                  ) : (
                    <p className="small-muted">No complete answer received.</p>
                  )}
                  {m.role === "assistant" && m.content && (
                    <CopyButton text={m.content} />
                  )}
                </div>
              </div>
            ))}
            <div ref={end} />
          </div>
        )}
      </div>
      <div className="composer-area">
        {error && <Notice>{error}</Notice>}
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <textarea
            ref={textarea}
            aria-label="Your message"
            placeholder="Ask anything, or think out loud…"
            value={input}
            maxLength={8000}
            rows={2}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="composer-bottom">
            <span>
              <Sparkles size={13} />
              {session.models.chat}
            </span>
            {busy ? (
              <button
                className="send-button"
                type="button"
                aria-label="Stop response"
                onClick={() => abort.current?.abort()}
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                className="send-button"
                type="submit"
                disabled={!input.trim()}
                aria-label="Send message"
              >
                <ArrowUp size={20} />
              </button>
            )}
          </div>
        </form>
        <div className="composer-caption">
          <span>Enter to send · Shift + Enter for a new line</span>
          <span>AI can make mistakes. Check important details.</span>
        </div>
      </div>
    </section>
  );
}
