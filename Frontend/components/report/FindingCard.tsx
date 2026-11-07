/**
 * FindingCard: one agent finding.
 *
 * Always shows where the claim comes from (cited layer field + source
 * record), because the design doc says no claim may appear without a
 * source. Concern is a qualitative label, never a number, and is echoed
 * by the coloured left rule.
 */

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { Concern, Finding } from "@/lib/types";

/** Badge tone, label, left-rule colour and legend fill per concern level. */
export const CONCERN: Record<Concern, { tone: BadgeTone; label: string; rule: string; fill: string }> = {
  high: { tone: "danger", label: "High concern", rule: "border-l-danger", fill: "bg-danger" },
  moderate: { tone: "warn", label: "Moderate concern", rule: "border-l-warn", fill: "bg-warn" },
  low: { tone: "accent", label: "Low concern", rule: "border-l-accent", fill: "bg-accent" },
  // Rests on incomplete data: shown grey so it is never read as a strong signal.
  flagged: { tone: "na", label: "Flagged · incomplete data", rule: "border-l-na", fill: "bg-na" },
};

/** DOM id of a finding's card, so the matrix and sources table can link to it. */
export function findingAnchor(id: string): string {
  return `finding-${id}`;
}

/** Small mono chip for a provenance value. */
function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-sm border border-rule bg-sunken px-1.5 py-0.5">
      <span className="text-muted">{label}</span> {value}
    </span>
  );
}

export function FindingCard({ finding }: { finding: Finding }) {
  const concern = CONCERN[finding.concern];
  return (
    // scroll-mt-4: leave a gap above when jumped to from the matrix.
    <article id={findingAnchor(finding.id)} className={`scroll-mt-4 flex flex-col gap-2.5 rounded border border-l-4 border-rule bg-surface p-4 ${concern.rule}`}>
      {/* Claim + concern badge */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-sm font-semibold leading-snug">{finding.claim}</h3>
        <Badge tone={concern.tone}>{concern.label}</Badge>
      </header>

      {/* Interpreter's mechanism explanation */}
      <p className="text-sm leading-6 text-muted">{finding.mechanism}</p>

      {/* Sceptic's comment, if it challenged or qualified the claim, as an indented quote */}
      {finding.scepticNote && (
        <blockquote className="border-l-2 border-rule bg-sunken px-3 py-1.5 text-sm">
          <span className="font-medium">Sceptic: </span>
          {finding.scepticNote}
        </blockquote>
      )}

      {/* Provenance: which evidence field and source record back the claim */}
      <footer className="flex flex-wrap gap-1.5 font-mono text-[11px]">
        <Chip label="field" value={finding.citedField} />
        <Chip label="source" value={finding.sourceRecordId} />
      </footer>
    </article>
  );
}
