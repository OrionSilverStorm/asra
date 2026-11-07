/**
 * Badge: a small square-cornered label (status, concern level, data origin).
 * Pick a semantic `tone`; the colours come from globals.css tokens.
 */

import type { ReactNode } from "react";

/** Semantic colour options. "na" = not available (grey). */
export type BadgeTone = "neutral" | "accent" | "ok" | "warn" | "danger" | "na";

/** Soft background + strong text colour for each tone. */
const TONES: Record<BadgeTone, string> = {
  neutral: "bg-sunken text-ink",
  accent: "bg-accent-soft text-accent",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  na: "bg-na-soft text-na",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    // whitespace-nowrap: a badge never breaks across lines.
    <span className={`inline-flex items-center whitespace-nowrap rounded-sm px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}
