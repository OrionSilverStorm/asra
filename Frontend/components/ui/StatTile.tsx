/**
 * StatTile: a labelled statistic (small label, large monospace value) with
 * an optional visual underneath (mini track, bar, ...). Used by the report
 * summary and the sequence stats.
 */

import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: ReactNode;
  /** Optional small visual or caption below the value. */
  children?: ReactNode;
}

export function StatTile({ label, value, children }: StatTileProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</p>
      <p className="font-mono text-lg font-semibold leading-tight">{value}</p>
      {children}
    </div>
  );
}
