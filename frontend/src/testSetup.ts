import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";
Object.defineProperty(Element.prototype, "scrollIntoView", {
  value: vi.fn(),
  writable: true,
});
Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
  value: vi.fn(),
  writable: true,
});
Object.defineProperty(HTMLDialogElement.prototype, "close", {
  value: vi.fn(),
  writable: true,
});
Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  value: () => ({
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
  }),
  writable: true,
});
