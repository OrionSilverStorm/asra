/**
 * EmptyState: grey dashed box for "nothing here yet" messages, with an
 * optional icon and a hint saying what would fill it. Matches the
 * unavailable-layer styling, so missing data always looks the same across
 * the report.
 */

import type { ReactNode } from "react";

/** Which small line icon to show. */
export type EmptyIconName = "data" | "findings" | "experiments";

/** 16×16 stroked icon paths, one per kind. */
const ICONS: Record<EmptyIconName, string> = {
  // Database cylinder: no data returned
  data: "M3 4c0-1.1 2.2-2 5-2s5 .9 5 2-2.2 2-5 2-5-.9-5-2zM3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4M3 8c0 1.1 2.2 2 5 2s5-.9 5-2",
  // Magnifier: nothing found
  findings: "M7 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM10.3 10.3 14 14",
  // Lab flask: no experiments
  experiments: "M6 2h4M7 2v4.5L3.2 12.8A1 1 0 0 0 4.1 14.3h7.8a1 1 0 0 0 .9-1.5L9 6.5V2M5 10h6",
};

/** The icon alone, also used inside unavailable layer panels. */
export function EmptyIcon({ name }: { name: EmptyIconName }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-6 text-na" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICONS[name]} />
    </svg>
  );
}

interface EmptyStateProps {
  children: ReactNode;
  icon?: EmptyIconName;
  /** Secondary line: what would populate this section. */
  hint?: ReactNode;
}

export function EmptyState({ children, icon, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded border border-dashed border-na/40 bg-na-soft px-4 py-6 text-center text-sm text-muted">
      {icon && <EmptyIcon name={icon} />}
      <p>{children}</p>
      {hint && <p className="text-xs">{hint}</p>}
    </div>
  );
}
