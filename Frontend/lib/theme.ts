/**
 * Theme (light / dark) state, stored on <html data-theme>.
 *
 * Light is the default (no attribute). The attribute is the single source
 * of truth: globals.css reads it to set `color-scheme`, and ThemeToggle
 * reads it via useSyncExternalStore. The choice is remembered in
 * localStorage (per browser only).
 */

export type Theme = "light" | "dark";

/** localStorage key for the saved choice. */
const STORAGE_KEY = "asra-theme";
/** Window event fired on change, so every toggle re-renders. */
const CHANGE_EVENT = "asra-theme-change";

/** Current theme, read from the <html> attribute. */
export function readTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** Apply a theme now and remember it for next visit. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  // Light = no attribute, so the CSS default applies.
  if (theme === "dark") root.dataset.theme = "dark";
  else delete root.dataset.theme;
  // Storage can throw (private mode, blocked site data); the theme still
  // applies for this page view, it just isn't remembered.
  try {
    if (theme === "dark") localStorage.setItem(STORAGE_KEY, "dark");
    else localStorage.removeItem(STORAGE_KEY);
  } catch {}
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** Subscribe to theme changes (useSyncExternalStore signature). */
export function subscribeTheme(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => window.removeEventListener(CHANGE_EVENT, onChange);
}

/**
 * Inline script run in <head> before first paint (see app/layout.tsx), so
 * a saved dark theme never flashes light. Must stay plain ES5, no imports.
 */
export const THEME_INIT_SCRIPT = `(function(){try{if(localStorage.getItem("${STORAGE_KEY}")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}})()`;
