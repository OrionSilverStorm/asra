/**
 * Alert: a coloured message box (info / warning / error).
 * Used, for example, to show "Assessment failed" when a request errors.
 */

import type { ReactNode } from "react";

type Tone = "info" | "warn" | "danger";

/** Tinted border + soft background per tone. */
const TONES: Record<Tone, string> = {
  info: "border-accent/30 bg-accent-soft text-ink",
  warn: "border-warn/30 bg-warn-soft text-ink",
  danger: "border-danger/30 bg-danger-soft text-ink",
};

interface AlertProps {
  tone?: Tone;
  /** Optional bold first line. */
  title?: string;
  children: ReactNode;
  /**
   * ARIA role. Use "alert" for errors (screen readers announce it
   * immediately), "status" for polite updates, "note" for static info.
   */
  role?: "alert" | "status" | "note";
}

export function Alert({ tone = "info", title, children, role = "note" }: AlertProps) {
  return (
    <div role={role} className={`rounded-md border px-4 py-3 text-sm ${TONES[tone]}`}>
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      <div className="text-ink/85">{children}</div>
    </div>
  );
}
