import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "./api";
afterEach(() => vi.unstubAllGlobals());
function response(parts: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(c) {
        parts.forEach((part) => c.enqueue(encoder.encode(part)));
        c.close();
      },
    }),
    { headers: { "content-type": "text/event-stream" } },
  );
}
describe("stream reader", () => {
  it("decodes split network chunks and UTF-8 tokens", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response([
          "event: tok",
          'en\ndata: {"content":"Hello नमस्ते"}\n',
          "\nevent: done\ndata: {}\n\n",
        ]),
      ),
    );
    const token = vi.fn();
    await streamChat(
      [{ id: "1", role: "user", content: "Hello" }],
      new AbortController().signal,
      token,
    );
    expect(token).toHaveBeenCalledWith("Hello नमस्ते");
  });
  it("rejects an interrupted stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response(['event: token\ndata: {"content":"Partial"}\n\n']),
      ),
    );
    await expect(
      streamChat([], new AbortController().signal, vi.fn()),
    ).rejects.toThrow("interrupted");
  });
  it("shows a normalized backend error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { message: "Insufficient credits" } }),
            { status: 503 },
          ),
      ),
    );
    await expect(
      streamChat([], new AbortController().signal, vi.fn()),
    ).rejects.toThrow("Insufficient credits");
  });
});
