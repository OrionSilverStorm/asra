/**
 * CaveatBanner: the mandatory "not a safety prediction" notice.
 *
 * The design doc requires this on every screen and export. Two variants:
 * - "strip": a thin full-width info bar (used under the site header)
 * - "block": a callout with an amber left rule (used at the top of the report)
 *
 * The wording lives in lib/caveat.ts so downloads use the exact same text.
 * Note: the word "safe" on its own must never appear in the UI; only the
 * phrase "safety prediction", to say what ASRA is NOT.
 */

import { CAVEAT_TEXT } from "@/lib/caveat";

/** Circled "i" info icon (decorative), shared by both variants. */
function InfoIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0 text-warn" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.25v3.5M8 5.1v.01" />
    </svg>
  );
}

export function CaveatBanner({ variant = "block" }: { variant?: "strip" | "block" }) {
  if (variant === "strip") {
    return (
      <div className="border-b border-warn/30 bg-warn-soft">
        {/* Same width/padding as Container so text aligns with the header. */}
        <p className="mx-auto flex max-w-6xl gap-2 px-4 py-1.5 text-xs text-ink/85 sm:px-6 lg:px-8">
          <InfoIcon />
          {CAVEAT_TEXT}
        </p>
      </div>
    );
  }
  return (
    <div role="note" className="flex gap-3 rounded border border-l-4 border-warn/30 border-l-warn bg-warn-soft px-4 py-3 text-sm leading-6">
      <InfoIcon />
      <div>
        <p className="font-semibold">Scientific caveat</p>
        <p className="text-ink/85">{CAVEAT_TEXT}</p>
      </div>
    </div>
  );
}
