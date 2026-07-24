import type { MouseEvent } from "react";

/** Shared prefers-reduced-motion check — every hover/entrance animation
 * (KPI tilt, chart entrance, spotlight glow) gates on this so a user who's
 * asked the OS for reduced motion gets the static version everywhere. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** A subtle pointer-tilt for a whole card (chart containers, KPI cards).
 * Deliberately imperative (direct style mutation, no React state) — a
 * setState-per-mousemove re-renders the tree on every pixel of movement,
 * which for a chart card detaches the SVG mid-interaction and silently
 * swallows a click-to-filter click (see DistributionBarChart's comment).
 * Plain style mutation never re-renders, so it's safe on clickable charts
 * too. */
export function tiltHandlers(maxDeg = 3) {
  return {
    onMouseMove: (e: MouseEvent<HTMLElement>) => {
      if (prefersReducedMotion()) return;
      const card = e.currentTarget;
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      // perspective() lives inside the transform itself (rather than as a
      // separate CSS `perspective` property on a parent) so this works
      // whether or not the caller controls the element's parent.
      card.style.transform = `perspective(800px) rotateY(${px * maxDeg}deg) rotateX(${-py * maxDeg}deg)`;
    },
    onMouseLeave: (e: MouseEvent<HTMLElement>) => {
      e.currentTarget.style.transform = "";
    },
  };
}
