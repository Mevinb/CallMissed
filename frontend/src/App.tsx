import { useEffect, useState } from "react";
import {
  MessageSquare,
  Image,
  AudioLines,
  ChevronRight,
  Plus,
  ShieldCheck,
  CircleHelp,
  ExternalLink,
  LogOut,
  RefreshCw,
  LoaderCircle,
} from "lucide-react";
import { jsonRequest } from "./api";
import type { Session } from "./api";
import { useVoice } from "./useVoice";
import Chat from "./components/Chat";
import ImageStudio from "./components/ImageStudio";
import VoiceAgent from "./components/VoiceAgent";
import { Notice, Dialog } from "./components/Shared";
type Tab = "chat" | "images" | "voice";
const nav = [
  {
    id: "chat",
    label: "Chat",
    icon: MessageSquare,
    subtitle: "A little curiosity goes a long way.",
  },
  {
    id: "images",
    label: "Image Studio",
    icon: Image,
    subtitle: "Turn a thought into something you can see.",
  },
  {
    id: "voice",
    label: "Voice Agent",
    icon: AudioLines,
    subtitle: "Good conversations start with hello.",
  },
] as const;
export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [session, setSession] = useState<Session | null>(null);
  const [loadError, setLoadError] = useState("");
  const [access, setAccess] = useState("");
  const [loginError, setLoginError] = useState("");
  const [unlocking, setUnlocking] = useState(false);
  const [help, setHelp] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const voice = useVoice();
  async function refresh() {
    setLoadError("");
    try {
      const info = await jsonRequest<Session>("/session");
      if (!info.authorized && !info.access_code_required) {
        await jsonRequest("/session", { access_code: "" });
        info.authorized = true;
      }
      setSession(info);
    } catch (e) {
      setLoadError(
        e instanceof Error ? e.message : "The backend could not be reached.",
      );
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function unlock() {
    setUnlocking(true);
    setLoginError("");
    try {
      await jsonRequest("/session", { access_code: access });
      setAccess("");
      await refresh();
    } catch (e) {
      setLoginError(
        e instanceof Error ? e.message : "Could not unlock the playground.",
      );
    } finally {
      setUnlocking(false);
    }
  }
  async function logout() {
    voice.stop();
    try {
      await jsonRequest("/session", undefined, "DELETE");
      setSession((s) => (s ? { ...s, authorized: false } : s));
    } catch (e) {
      setLoadError(
        e instanceof Error ? e.message : "Could not lock the session.",
      );
    }
  }
  const active = nav.find((x) => x.id === tab)!;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          aria-label="CallMissed AI Playground home"
        >
          <div className="brand-icon">
            <AudioLines size={23} />
          </div>
          <div>
            callmissed<span>AI Playground</span>
          </div>
        </a>
        <div className="sidebar-section-label">Workspace</div>
        <nav aria-label="Workspace navigation">
          {nav.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${tab === item.id ? "active" : ""}`}
              aria-pressed={tab === item.id}
              onClick={() => setTab(item.id)}
            >
              <item.icon size={19} />
              <span>{item.label}</span>
              {tab === item.id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <button
          className="new-chat"
          onClick={() => {
            setTab("chat");
            setResetToken((t) => t + 1);
          }}
        >
          <Plus size={18} />
          New conversation
        </button>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <ShieldCheck size={19} />
            <h3>Room to explore.</h3>
            <p>
              Three ways to create.
              <br />
              One connected workspace.
            </p>
          </div>
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={17} />
            Help & information
            <ExternalLink size={13} />
          </button>
          <div className="profile">
            <span className="profile-avatar">M</span>
            <div>
              Mevin Benty<span>Personal playground</span>
            </div>
            {session?.authorized && session.access_code_required && (
              <button
                className="icon-button"
                aria-label="Lock playground"
                onClick={() => void logout()}
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Playground</span>
            <ChevronRight size={13} />
            <strong>{active.label}</strong>
          </div>
          <button
            className="api-status"
            onClick={() => void refresh()}
            title="Refresh API configuration status"
          >
            <span
              className={`status-dot ${session?.provider_configured ? "connected" : ""}`}
            />
            {session?.provider_configured ? "API configured" : "Setup required"}
            <RefreshCw size={12} />
          </button>
        </header>
        <div className="workspace-header">
          <div>
            <h1>{active.label}</h1>
            <p>{active.subtitle}</p>
          </div>
          <span className="workspace-tag">Powered by CallMissed</span>
        </div>
        {loadError ? (
          <div className="connection-error">
            <Notice>{loadError}</Notice>
            <button className="primary-button" onClick={() => void refresh()}>
              <RefreshCw size={16} />
              Retry connection
            </button>
          </div>
        ) : !session ? (
          <div className="page-loading">
            <LoaderCircle className="spin" size={25} />
            <p>Connecting to your playground…</p>
          </div>
        ) : !session.authorized ? (
          <div className="unlock-panel">
            <div className="welcome-mark">
              <ShieldCheck size={28} />
            </div>
            <h2>A playground, just for you.</h2>
            <p>Enter the demo access code to start exploring.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void unlock();
              }}
            >
              <label htmlFor="access-code">Demo access code</label>
              <input
                id="access-code"
                type="password"
                autoComplete="current-password"
                required
                value={access}
                maxLength={256}
                onChange={(e) => setAccess(e.target.value)}
              />
              <button
                className="primary-button full-width"
                disabled={unlocking}
              >
                {unlocking ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <ShieldCheck size={16} />
                )}
                Unlock playground
              </button>
            </form>
            {loginError && <Notice>{loginError}</Notice>}
          </div>
        ) : (
          <>
            {!session.provider_configured && (
              <div className="setup-banner">
                <CircleHelp size={16} />
                <span>
                  Connect your CallMissed API key on the server to enable chat,
                  images, and voice.
                </span>
                <button onClick={() => setHelp(true)}>Setup details</button>
              </div>
            )}
            <div className="workspace-content">
              <div hidden={tab !== "chat"}>
                <Chat session={session} resetToken={resetToken} />
              </div>
              <div hidden={tab !== "images"}>
                <ImageStudio session={session} />
              </div>
              <div hidden={tab !== "voice"}>
                <VoiceAgent voice={voice} session={session} />
              </div>
            </div>
          </>
        )}
      </main>
      {help && (
        <Dialog title="About your playground" close={() => setHelp(false)}>
          <div className="help-content">
            <p>
              Chat with an assistant, generate an image, or start a voice
              conversation using your microphone. All AI responses come from
              CallMissed.
            </p>
            <h3>Getting connected</h3>
            <p>
              The app owner must configure the CallMissed API key on the server.
              If a service is unavailable, check key permissions, account
              credits and model availability in the CallMissed console.
            </p>
            <h3>Your conversations</h3>
            <p>
              Chat history stays in this browser tab. The six most recent
              generated images are saved in this tab for up to 24 hours. Voice
              transcripts stay on this page. Prompts and audio are sent to
              CallMissed to provide responses and may be retained under their
              policies.
            </p>
            <h3>Voice access</h3>
            <p>
              Use HTTPS or localhost and allow microphone access. You can mute,
              interrupt the agent, or stop a conversation at any time.
            </p>
            <div className="help-links">
              <a
                href="https://docs.callmissed.com"
                target="_blank"
                rel="noreferrer"
              >
                API documentation <ExternalLink size={14} />
              </a>
              <a
                href="https://github.com/Mevinb/CallMissed"
                target="_blank"
                rel="noreferrer"
              >
                Project on GitHub <ExternalLink size={14} />
              </a>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
