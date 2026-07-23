import "@testing-library/jest-dom/vitest";

// jsdom reports 0 for offsetWidth/offsetHeight, so Recharts'
// ResponsiveContainer never sees a usable size and renders nothing —
// without this, every chart test would silently test an empty <div>
// instead of the real SVG bars. Stubbed at a fixed size so charts
// actually render and are clickable in tests.
Object.defineProperties(HTMLElement.prototype, {
  offsetWidth: { configurable: true, value: 600 },
  offsetHeight: { configurable: true, value: 300 },
});

// jsdom has no ResizeObserver at all; Recharts' ResponsiveContainer uses
// one to detect its size and never renders its children without it. The
// callback must actually fire (with a non-zero size) for the chart body
// to render at all — a no-op observe() leaves it stuck at 0x0 forever.
class MockResizeObserver {
  #callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.#callback = callback;
  }
  observe(target: Element) {
    this.#callback(
      [{ target, contentRect: { width: 600, height: 300 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    );
  }
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

// jsdom doesn't implement scrollIntoView (used when a chart click scrolls
// the table into view).
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});

// jsdom doesn't implement matchMedia at all (used for the dark-mode
// toggle's system-preference default and prefers-reduced-motion checks).
window.matchMedia =
  window.matchMedia ??
  ((query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList);
