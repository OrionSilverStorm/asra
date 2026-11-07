"use client";
// ^ Client Component: reads and changes the theme in the browser.

/**
 * ThemeToggle: one icon button that swaps between light and dark.
 *
 * The theme lives on <html data-theme> (lib/theme.ts). useSyncExternalStore
 * reads it, and renders "light" (the default) on the server and during
 * hydration so the markup always matches, then switches to the real value.
 */

import { useSyncExternalStore } from "react";
import { applyTheme, readTheme, subscribeTheme, type Theme } from "@/lib/theme";

/** Label and icon path per theme. Icons are 16×16, stroked. */
const META: Record<Theme, { label: string; icon: string }> = {
  // Sun
  light: {
    label: "Light",
    icon: "M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1",
  },
  // Moon
  dark: { label: "Dark", icon: "M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" },
};

export function ThemeToggle() {
  // Server snapshot is "light": the server can't know the saved choice.
  const theme = useSyncExternalStore(subscribeTheme, readTheme, () => "light" as Theme);
  // The other theme: what a click switches to.
  const next: Theme = theme === "light" ? "dark" : "light";

  return (
    <button
      type="button"
      onClick={() => applyTheme(next)}
      // Say both the current state and what a click does.
      aria-label={`Theme: ${META[theme].label}. Switch to ${META[next].label}.`}
      title={`Switch to ${META[next].label.toLowerCase()} mode`}
      className="inline-flex h-8 items-center gap-1.5 rounded border border-chrome-muted/40 px-2 text-xs text-chrome-ink transition hover:bg-white/10"
    >
      <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <path d={META[theme].icon} />
      </svg>
      {/* Text label only where there is room. */}
      <span className="hidden sm:inline">{META[theme].label}</span>
    </button>
  );
}
