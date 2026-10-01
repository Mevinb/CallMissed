import { useEffect, useRef, useState } from "react";
import {
  Image,
  LoaderCircle,
  Sparkles,
  Plus,
  Trash2,
  Maximize2,
  RefreshCw,
  Download,
} from "lucide-react";
import { jsonRequest, loadImages, saveImage, clearImages } from "../api";
import type { GeneratedImage, Session } from "../api";
import { Notice, Dialog } from "./Shared";
export default function ImageStudio({ session }: { session: Session }) {
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState("1024x1024");
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<GeneratedImage | null>(null);
  const [storageNote, setStorageNote] = useState("");
  const imagesRef = useRef(images);
  const controller = useRef<AbortController | null>(null);
  imagesRef.current = images;
  useEffect(() => {
    let canceled = false;
    void loadImages()
      .then((result) => {
        if (canceled) result.forEach((x) => URL.revokeObjectURL(x.url!));
        else
          setImages((current) => {
            const merged = [...current];
            result.forEach((image) => {
              if (merged.some((x) => x.id === image.id))
                URL.revokeObjectURL(image.url!);
              else merged.push(image);
            });
            merged.sort((a, b) => b.created - a.created);
            merged.slice(6).forEach((x) => URL.revokeObjectURL(x.url!));
            return merged.slice(0, 6);
          });
      })
      .catch(() =>
        setStorageNote(
          "Browser storage is unavailable. Images will remain available while this page is open.",
        ),
      );
    return () => {
      canceled = true;
      controller.current?.abort();
      controller.current = null;
      imagesRef.current.forEach((x) => URL.revokeObjectURL(x.url!));
    };
  }, []);
  async function generate() {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setError("");
    const request = new AbortController();
    controller.current = request;
    const requestedPrompt = prompt.trim();
    const requestedSize = size;
    try {
      const result = await jsonRequest<{
        b64_json: string;
        mime_type: string;
        model: string;
      }>(
        "/images",
        { prompt: requestedPrompt, size: requestedSize },
        "POST",
        request.signal,
      );
      if (request.signal.aborted) return;
      const bytes = Uint8Array.from(atob(result.b64_json), (c) =>
        c.charCodeAt(0),
      );
      const blob = new Blob([bytes], { type: result.mime_type });
      const image: GeneratedImage = {
        id: crypto.randomUUID(),
        prompt: requestedPrompt,
        size: requestedSize,
        model: result.model,
        blob,
        created: Date.now(),
        url: URL.createObjectURL(blob),
      };
      setImages((old) => {
        old.slice(5).forEach((x) => URL.revokeObjectURL(x.url!));
        return [image, ...old].slice(0, 6);
      });
      try {
        await saveImage(image);
      } catch {
        setStorageNote(
          "Could not save this image to browser storage. Download it to keep a copy.",
        );
      }
    } catch (e) {
      if (!request.signal.aborted)
        setError(e instanceof Error ? e.message : "Image generation failed.");
    } finally {
      if (controller.current === request) {
        controller.current = null;
        setBusy(false);
      }
    }
  }
  async function clear() {
    try {
      await clearImages();
      images.forEach((x) => URL.revokeObjectURL(x.url!));
      setImages([]);
    } catch {
      setError("Could not clear browser image storage. Please try again.");
    }
  }
  function download(image: GeneratedImage) {
    const a = document.createElement("a");
    a.href = image.url!;
    a.download = `callmissed-${image.id}.${image.blob.type === "image/jpeg" ? "jpg" : "png"}`;
    a.click();
  }
  return (
    <section className="studio-workspace" aria-label="Image generation">
      <div className="studio-controls">
        <div className="section-title">
          <div className="feature-icon">
            <Image size={20} />
          </div>
          <h2>
            A picture starts
            <br />
            with a few words.
          </h2>
          <p>
            Describe your scene. Be specific about light, mood, and the little
            details.
          </p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void generate();
          }}
        >
          <label htmlFor="image-prompt">Your prompt</label>
          <textarea
            id="image-prompt"
            rows={7}
            maxLength={4000}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A quiet bookshop on a rainy evening, warm light spilling onto the street, cinematic photography…"
          />
          <div className="field-caption">
            {prompt.length.toLocaleString()} / 4,000 characters
          </div>
          <label htmlFor="image-size">Image dimensions</label>
          <select
            id="image-size"
            value={size}
            onChange={(e) => setSize(e.target.value)}
          >
            <option value="1024x1024">Square · 1024 × 1024</option>
            <option value="1024x1536">Portrait · 1024 × 1536</option>
            <option value="1536x1024">Landscape · 1536 × 1024</option>
            <option value="768x768">Square · 768 × 768</option>
            <option value="512x512">Small square · 512 × 512</option>
          </select>
          <button
            type="submit"
            className="primary-button full-width"
            disabled={busy || !prompt.trim()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}{" "}
            {busy ? "Creating your image…" : "Generate image"}
          </button>
        </form>
        {error && <Notice>{error}</Notice>}
        <div className="prompt-starters">
          <h3>Need a starting point?</h3>
          {[
            "An architectural sketch of a cabin by a lake, pencil on textured paper",
            "A tiny astronaut tending a garden on the moon, playful illustration",
            "A glass of iced coffee in soft morning light, editorial photography",
          ].map((text) => (
            <button key={text} onClick={() => setPrompt(text)}>
              {text}
              <Plus size={14} />
            </button>
          ))}
        </div>
        <p className="model-note">
          Powered by {session.models.image}. Each successful image uses
          CallMissed credits.
        </p>
      </div>
      <div className="gallery">
        <div className="gallery-header">
          <h3>
            Your creations <span>{images.length}</span>
          </h3>
          {images.length > 0 && (
            <button
              className="text-button"
              onClick={() => void clear()}
              disabled={busy}
            >
              <Trash2 size={14} />
              Clear history
            </button>
          )}
        </div>
        {storageNote && <Notice>{storageNote}</Notice>}
        {images.length === 0 && !busy ? (
          <div className="gallery-empty">
            <div className="empty-image">
              <Image size={38} />
            </div>
            <h3>A blank canvas. All yours.</h3>
            <p>
              Your generated images will appear here.
              <br />
              Start with a prompt on the left.
            </p>
          </div>
        ) : (
          <div className="image-grid">
            {busy && (
              <div className="image-loading">
                <LoaderCircle className="spin" size={26} />
                <h3>Bringing your idea to life</h3>
                <p>This can take a few minutes.</p>
              </div>
            )}
            {images.map((image) => (
              <article className="image-card" key={image.id}>
                <button
                  className="image-preview-button"
                  onClick={() => setPreview(image)}
                  aria-label="Preview generated image"
                >
                  <img
                    src={image.url}
                    alt={image.prompt}
                    onError={() =>
                      setError(
                        "The generated image could not be displayed. Try another generation or download it to inspect the file.",
                      )
                    }
                  />
                  <span>
                    <Maximize2 size={17} />
                  </span>
                </button>
                <div className="image-details">
                  <p>{image.prompt}</p>
                  <div>
                    <span>{image.size.replace("x", " × ")}</span>
                    <button
                      className="icon-button"
                      onClick={() => {
                        setPrompt(image.prompt);
                        setSize(image.size);
                      }}
                      aria-label="Reuse prompt"
                    >
                      <RefreshCw size={15} />
                    </button>
                    <button
                      className="icon-button"
                      onClick={() => download(image)}
                      aria-label="Download image"
                    >
                      <Download size={15} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
        <p className="gallery-note">
          The six most recent images stay in this tab for up to 24 hours.
          Download your favorites.
        </p>
      </div>
      {preview && (
        <Dialog title="Your generated image" close={() => setPreview(null)}>
          <img
            className="full-preview"
            src={preview.url}
            alt={preview.prompt}
          />
          <p className="preview-prompt">{preview.prompt}</p>
          <button className="primary-button" onClick={() => download(preview)}>
            <Download size={16} />
            Download image
          </button>
        </Dialog>
      )}
    </section>
  );
}
