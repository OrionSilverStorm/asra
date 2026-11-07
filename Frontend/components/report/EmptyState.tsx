/**
 * EmptyState: grey dashed box for "nothing here yet" messages.
 * Matches the unavailable-layer styling, so missing data always looks the
 * same across the report.
 */

import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-na/40 bg-na-soft px-4 py-6 text-center text-sm text-muted">
      {children}
    </p>
  );
}
