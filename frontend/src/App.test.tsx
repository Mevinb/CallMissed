import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";
vi.mock("./api", () => ({
  jsonRequest: vi.fn(),
  streamChat: vi.fn(),
  loadImages: vi.fn(async () => []),
  saveImage: vi.fn(),
  clearImages: vi.fn(),
}));
const session = {
  authorized: true,
  access_code_required: false,
  provider_configured: true,
  models: {
    chat: "sarvam-105b",
    image: "sdxl-lightning",
    voice: "gpt-oss-120b",
  },
  voice_max_seconds: 240,
};
beforeEach(() => {
  sessionStorage.clear();
  vi.resetAllMocks();
  vi.mocked(api.jsonRequest).mockResolvedValue(session);
  vi.mocked(api.loadImages).mockResolvedValue([]);
});
afterEach(cleanup);
describe("playground workflows", () => {
  it("navigates to all three working interfaces and prompt suggestions fill the composer", async () => {
    render(<App />);
    await screen.findByText("Where shall we begin?");
    fireEvent.click(screen.getByText("Make something click"));
    expect(screen.getByRole("textbox", { name: "Your message" })).toHaveValue(
      "Explain how WebSockets work using a simple everyday analogy.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Image Studio" }));
    expect(screen.getByRole("textbox", { name: "Your prompt" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Voice Agent" }));
    expect(
      screen.getByRole("button", { name: "Start conversation" }),
    ).toBeVisible();
    expect(screen.getByText("Disconnected")).toBeVisible();
  });
  it("displays real streamed content supplied by the backend and preserves context", async () => {
    vi.mocked(api.streamChat).mockImplementation(
      async (_messages, _signal, token) => {
        token("Mocked actual backend stream");
      },
    );
    render(<App />);
    await screen.findByText("Where shall we begin?");
    const input = screen.getByRole("textbox", { name: "Your message" });
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByText("Mocked actual backend stream");
    expect(api.streamChat).toHaveBeenCalledWith(
      [expect.objectContaining({ role: "user", content: "Hello" })],
      expect.any(AbortSignal),
      expect.any(Function),
    );
    fireEvent.change(input, { target: { value: "Follow up" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(api.streamChat).toHaveBeenCalledTimes(2));
    expect(
      vi.mocked(api.streamChat).mock.calls[1][0].map((m) => m.role),
    ).toEqual(["user", "assistant", "user"]);
  });
  it("shows upstream errors without a fabricated answer", async () => {
    vi.mocked(api.streamChat).mockRejectedValue(
      new Error("CallMissed is unavailable."),
    );
    render(<App />);
    await screen.findByText("Where shall we begin?");
    fireEvent.change(screen.getByRole("textbox", { name: "Your message" }), {
      target: { value: "Hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByText("CallMissed is unavailable.");
    expect(screen.getByText("No complete answer received.")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Your message" })).toHaveValue(
      "Hello",
    );
  });
  it("requires the access code before exposing protected workflows", async () => {
    vi.mocked(api.jsonRequest).mockResolvedValue({
      ...session,
      authorized: false,
      access_code_required: true,
    });
    render(<App />);
    await screen.findByLabelText("Demo access code");
    expect(screen.queryByText("Where shall we begin?")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Demo access code"), {
      target: { value: "test-reviewer-code" },
    });
    vi.mocked(api.jsonRequest).mockResolvedValue({
      ...session,
      access_code_required: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock playground" }));
    await screen.findByText("Where shall we begin?");
    expect(api.jsonRequest).toHaveBeenCalledWith("/session", {
      access_code: "test-reviewer-code",
    });
  });
  it("handles microphone permission denial without starting a fake call", async () => {
    Object.defineProperty(window, "isSecureContext", {
      value: true,
      configurable: true,
    });
    const close = vi.fn(async () => {});
    vi.stubGlobal(
      "AudioContext",
      class {
        resume = vi.fn(async () => {});
        close = close;
      },
    );
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn(async () => {
          throw new DOMException("denied", "NotAllowedError");
        }),
      },
      configurable: true,
    });
    render(<App />);
    await screen.findByText("Where shall we begin?");
    fireEvent.click(screen.getByRole("button", { name: "Voice Agent" }));
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await screen.findByText(
      "Microphone permission was denied. Allow access in your browser and try again.",
    );
    expect(close).toHaveBeenCalled();
    expect(screen.getByText("Disconnected")).toBeVisible();
    vi.unstubAllGlobals();
  });
});

it("starting a new conversation during a pending answer keeps the new chat empty", async () => {
  let rejectStream: (reason: Error) => void = () => {};
  vi.mocked(api.streamChat).mockImplementation(
    () =>
      new Promise<void>((_resolve, reject) => {
        rejectStream = reject;
      }),
  );
  render(<App />);
  await screen.findByText("Where shall we begin?");
  fireEvent.change(screen.getByRole("textbox", { name: "Your message" }), {
    target: { value: "Discard this pending question" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));
  await screen.findByRole("button", { name: "Stop response" });
  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
  rejectStream(new Error("Aborted old answer"));
  await screen.findByText("Where shall we begin?");
  expect(screen.getByRole("textbox", { name: "Your message" })).toHaveValue("");
  expect(
    screen.queryByText("Discard this pending question"),
  ).not.toBeInTheDocument();
});
