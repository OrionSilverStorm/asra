/**
 * ConcernBar: one horizontal bar split by how many findings sit at each
 * concern level, with the counts written underneath. Counts only: concern
 * stays qualitative, there is no combined score.
 */

import type { Concern, Finding } from "@/lib/types";
import { CONCERN } from "./FindingCard";

/** Concern levels in display order (matches the CONCERN map). */
const LEVELS = Object.keys(CONCERN) as Concern[];

export function ConcernBar({ findings, showCounts = true }: { findings: Finding[]; showCounts?: boolean }) {
  // Number of findings per level, zero-count levels dropped.
  const counts = LEVELS.map((level) => ({
    level,
    n: findings.filter((f) => f.concern === level).length,
  })).filter((c) => c.n > 0);

  return (
    <div className="flex flex-col gap-1">
      {/* Track; empty (grey) when there are no findings. */}
      <div aria-hidden className="flex h-2.5 overflow-hidden rounded-sm bg-sunken">
        {counts.map((c) => (
          <span key={c.level} className={CONCERN[c.level].fill} style={{ width: `${(c.n / findings.length) * 100}%` }} />
        ))}
      </div>
      {/* The same information as text (also what screen readers get). */}
      {showCounts && (
        <p className="text-xs text-muted">
          {counts.length
            ? counts.map((c) => `${c.n} ${c.level}`).join(" · ")
            : "No findings"}
        </p>
      )}
    </div>
  );
}
