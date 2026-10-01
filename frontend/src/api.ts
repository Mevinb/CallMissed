export type Session = {
  authorized: boolean;
  access_code_required: boolean;
  provider_configured: boolean;
  models: { chat: string; image: string; voice: string };
  voice_max_seconds: number;
};
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  failed?: boolean;
};
export type GeneratedImage = {
  id: string;
  prompt: string;
  size: string;
  model: string;
  blob: Blob;
  created: number;
  url?: string;
};
export async function jsonRequest<T>(
  path: string,
  body?: unknown,
  method = body === undefined ? "GET" : "POST",
  signal?: AbortSignal,
): Promise<T> {
  const timeout = AbortSignal.timeout(path === "/images" ? 200000 : 30000);
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}
export async function errorMessage(response: Response) {
  try {
    return (
      (await response.json()).error?.message ||
      `Request failed (${response.status}). Please try again.`
    );
  } catch {
    return `Request failed (${response.status}). Please try again.`;
  }
}
export async function streamChat(
  messages: ChatMessage[],
  signal: AbortSignal,
  token: (text: string) => void,
) {
  const response = await fetch("/api/chat", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
      stream: true,
    }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(130000)]),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  if (!response.body)
    throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const event = frame
          .split("\n")
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim();
        const raw = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");
        if (!raw) continue;
        const data = JSON.parse(raw);
        if (event === "error") throw new Error(data.message);
        if (event === "token") token(data.content);
        if (event === "done") finished = true;
      }
      if (done) break;
    }
    if (!finished)
      throw new Error("The response was interrupted. Please try again.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
const imageSession =
  sessionStorage.getItem("cm-image-session") || crypto.randomUUID();
sessionStorage.setItem("cm-image-session", imageSession);
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("callmissed-images", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("images", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function loadImages(): Promise<GeneratedImage[]> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("images", "readwrite");
    const store = tx.objectStore("images");
    const req = store.getAll();
    req.onsuccess = () => {
      const all = req.result as (GeneratedImage & { session: string })[];
      all
        .filter((x) => Date.now() - x.created > 86400000)
        .forEach((x) => store.delete(x.id));
      const current = all
        .filter(
          (x) =>
            x.session === imageSession && Date.now() - x.created <= 86400000,
        )
        .sort((a, b) => b.created - a.created);
      current.slice(6).forEach((x) => store.delete(x.id));
      tx.oncomplete = () => {
        db.close();
        resolve(
          current
            .slice(0, 6)
            .map((x) => ({ ...x, url: URL.createObjectURL(x.blob) })),
        );
      };
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function saveImage(image: GeneratedImage) {
  const db = await database();
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction("images", "readwrite");
    const { url: _url, ...record } = image;
    tx.objectStore("images").put({ ...record, session: imageSession });
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function clearImages() {
  const db = await database();
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction("images", "readwrite");
    const store = tx.objectStore("images");
    const req = store.getAll();
    req.onsuccess = () =>
      req.result
        .filter((x) => x.session === imageSession)
        .forEach((x) => store.delete(x.id));
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
