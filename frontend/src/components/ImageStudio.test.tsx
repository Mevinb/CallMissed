import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ImageStudio from "./ImageStudio";
import * as api from "../api";
import type { Session } from "../api";

vi.mock("../api", () => ({
  jsonRequest: vi.fn(),
  loadImages: vi.fn(),
  saveImage: vi.fn(),
  clearImages: vi.fn(),
}));
const session: Session = {
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
const result = {
  b64_json: "iVBORw0KGgo=",
  mime_type: "image/png",
  model: "sdxl-lightning",
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.loadImages).mockResolvedValue([]);
  vi.mocked(api.saveImage).mockResolvedValue(undefined);
  vi.mocked(api.clearImages).mockResolvedValue(undefined);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:generated-image"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("keeps the submitted prompt and size when inputs change while generation is pending", async () => {
  let complete!: (value: typeof result) => void;
  vi.mocked(api.jsonRequest).mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  render(<ImageStudio session={session} />);
  await screen.findByText("A blank canvas. All yours.");
  fireEvent.change(screen.getByLabelText("Your prompt"), {
    target: { value: "Original scene" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate image" }));
  fireEvent.change(screen.getByLabelText("Your prompt"), {
    target: { value: "Next scene" },
  });
  fireEvent.change(screen.getByLabelText("Image dimensions"), {
    target: { value: "512x512" },
  });
  await act(async () => {
    complete(result);
  });
  expect(await screen.findByAltText("Original scene")).toHaveAttribute(
    "src",
    "blob:generated-image",
  );
  expect(api.jsonRequest).toHaveBeenCalledWith(
    "/images",
    { prompt: "Original scene", size: "1024x1024" },
    "POST",
    expect.any(AbortSignal),
  );
  expect(api.saveImage).toHaveBeenCalledWith(
    expect.objectContaining({
      prompt: "Original scene",
      size: "1024x1024",
      blob: expect.any(Blob),
    }),
  );
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "Download image" }));
  expect(click).toHaveBeenCalledOnce();
  const anchor = click.mock.instances[0] as HTMLAnchorElement;
  expect(anchor.download).toMatch(/^callmissed-.*\.png$/);
  expect(anchor.href).toBe("blob:generated-image");
  fireEvent.click(screen.getByRole("button", { name: "Reuse prompt" }));
  expect(screen.getByLabelText("Your prompt")).toHaveValue("Original scene");
  fireEvent.click(screen.getByRole("button", { name: "Clear history" }));
  await screen.findByText("A blank canvas. All yours.");
  expect(api.clearImages).toHaveBeenCalledOnce();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:generated-image");
});

it("shows image API failure without adding a successful image", async () => {
  vi.mocked(api.jsonRequest).mockRejectedValue(
    new Error("Image provider unavailable."),
  );
  render(<ImageStudio session={session} />);
  fireEvent.change(screen.getByLabelText("Your prompt"), {
    target: { value: "A scene" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate image" }));
  await screen.findByText("Image provider unavailable.");
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(api.saveImage).not.toHaveBeenCalled();
});

it("aborts an image request on unmount and ignores a late response", async () => {
  let complete!: (value: typeof result) => void;
  vi.mocked(api.jsonRequest).mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const view = render(<ImageStudio session={session} />);
  fireEvent.change(screen.getByLabelText("Your prompt"), {
    target: { value: "A scene" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate image" }));
  const signal = vi.mocked(api.jsonRequest).mock.calls[0][3]!;
  view.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => {
    complete(result);
  });
  expect(URL.createObjectURL).not.toHaveBeenCalled();
  expect(api.saveImage).not.toHaveBeenCalled();
});

it("keeps a newly generated image if loading browser history finishes later", async () => {
  let load!: (value: api.GeneratedImage[]) => void;
  vi.mocked(api.loadImages).mockImplementation(
    () =>
      new Promise((resolve) => {
        load = resolve;
      }),
  );
  vi.mocked(api.jsonRequest).mockResolvedValue(result);
  render(<ImageStudio session={session} />);
  fireEvent.change(screen.getByLabelText("Your prompt"), {
    target: { value: "New scene" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate image" }));
  await screen.findByAltText("New scene");
  await act(async () => {
    load([]);
  });
  await waitFor(() => expect(screen.getByAltText("New scene")).toBeVisible());
});
