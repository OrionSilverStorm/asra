/**
 * FindingCard: one agent finding.
 *
 * Always shows where the claim comes from (cited layer field + source
 * record), because the design doc says no claim may appear without a
 * source. Concern is a qualitative label, never a number.
 */

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { Concern, Finding } from "@/lib/types";

/** Colour + label for each concern level. */
const CONCERN: Record<Concern, { tone: BadgeTone; label: string }> = {
  high: { tone: "danger", label: "High concern" },
  moderate: { tone: "warn", label: "Moderate concern" },
  low: { tone: "neutral", label: "Low concern" },
  // Rests on incomplete data: shown grey so it is never read as a strong signal.
  flagged: { tone: "na", label: "Flagged · incomplete data" },
};

export function FindingCard({ finding }: { finding: Finding }) {
  const concern = CONCERN[finding.concern];
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-rule bg-surface p-5">
      {/* Claim + concern badge */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="font-medium leading-snug">{finding.claim}</h3>
        <Badge tone={concern.tone}>{concern.label}</Badge>
      </header>

      {/* Interpreter's mechanism explanation */}
      <p className="text-sm leading-6 text-muted">{finding.mechanism}</p>

      {/* Sceptic's comment, if it challenged or qualified the claim */}
      {finding.scepticNote && (
        <p className="rounded-md bg-sunken px-3 py-2 text-sm">
          <span className="font-medium">Sceptic: </span>
          {finding.scepticNote}
        </p>
      )}

      {/* Provenance: which evidence field and source record back the claim */}
      <footer className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted">
        <span>field: {finding.citedField}</span>
        <span>source: {finding.sourceRecordId}</span>
      </footer>
    </article>
  );
}
