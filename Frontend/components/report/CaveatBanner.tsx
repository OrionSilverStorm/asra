/**
 * CaveatBanner: the mandatory "not a safety prediction" notice.
 *
 * The design doc requires this on every screen and export. Two variants:
 * - "strip": a thin full-width bar (used under the site header)
 * - "block": a boxed callout (used at the top of the report)
 *
 * The wording lives in lib/caveat.ts so downloads use the exact same text.
 * Note: the word "safe" on its own must never appear in the UI; only the
 * phrase "safety prediction", to say what ASRA is NOT.
 */

import { CAVEAT_TEXT } from "@/lib/caveat";

export function CaveatBanner({ variant = "block" }: { variant?: "strip" | "block" }) {
  if (variant === "strip") {
    return (
      <div className="border-t border-rule bg-warn-soft">
        {/* Same width/padding as Container so text aligns with the header. */}
        <p className="mx-auto max-w-6xl px-4 py-2 text-xs text-ink/80 sm:px-6 lg:px-8">{CAVEAT_TEXT}</p>
      </div>
    );
  }
  return (
    <div role="note" className="rounded-lg border border-warn/30 bg-warn-soft px-5 py-4 text-sm leading-6">
      <p className="font-semibold">Scientific caveat</p>
      <p className="text-ink/85">{CAVEAT_TEXT}</p>
    </div>
  );
}
