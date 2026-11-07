/**
 * SequenceEvidence: readable view of the gene-based sequence layer
 * (human vs animal reference proteins from Ensembl, Biopython alignment,
 * UniProt features). Replaces the raw JSON observation rows in LayerPanel.
 *
 * Shows only values the backend computed (lib/sequenceEvidence.ts reads
 * them); percentages are rounded for display, the raw JSON stays available
 * in the collapsed "Raw evidence" block.
 */

import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import { pct, type SequenceEvidence as Evidence } from "@/lib/sequenceEvidence";
import type { LayerResult } from "@/lib/types";

/** How many substitution chips to show before "show all". */
const VISIBLE_SUBSTITUTIONS = 30;

/** Colour per motif residue state. */
const MOTIF_STATE: Record<string, string> = {
  identical: "bg-ok-soft text-ok",
  substitution: "bg-warn-soft text-warn",
};

/** One substitution chip; annotated ones are tinted and list their features on hover. */
function Chip({ label, annotated, features }: Evidence["substitutions"][number]) {
  return (
    <span
      title={features.length ? features.join("\n") : undefined}
      className={`rounded-sm px-1.5 py-0.5 font-mono text-[11px] ${annotated ? "bg-warn-soft text-warn" : "bg-sunken text-muted"}`}
    >
      {label}
    </span>
  );
}

/** Small uppercase sub-heading inside the panel. */
function Heading({ children }: { children: string }) {
  return <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{children}</p>;
}

interface SequenceEvidenceProps {
  evidence: Evidence;
  layer: LayerResult;
  /** Animal column heading, e.g. "Mouse". */
  speciesName: string;
}

export function SequenceEvidence({ evidence, layer, speciesName }: SequenceEvidenceProps) {
  const m = evidence.measurements;
  const annotatedCount = evidence.substitutions.filter((s) => s.annotated).length;
  // Rows for the reference-protein table; a row is skipped if neither side has a value.
  const refs = [
    { label: "UniProt", h: evidence.human.isoform ?? evidence.human.accession, a: evidence.animal.isoform ?? evidence.animal.accession },
    { label: "Ensembl protein", h: evidence.human.proteinId, a: evidence.animal.proteinId },
    { label: "Ensembl gene", h: evidence.human.geneId, a: evidence.animal.geneId },
    { label: "Length", h: m.human_length && `${m.human_length} aa`, a: m.animal_length && `${m.animal_length} aa` },
  ].filter((r) => r.h || r.a);

  return (
    <div className="flex flex-col gap-4">
      {/* Headline measurements. */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Identity" value={pct(m.identity_percent)}>
          <span className="text-xs text-muted">of {m.alignment_columns ?? "?"} alignment columns</span>
        </StatTile>
        <StatTile label="Paired identity" value={pct(m.paired_identity_percent)}>
          <span className="text-xs text-muted">gap columns excluded</span>
        </StatTile>
        <StatTile label="Coverage" value={`${pct(m.human_coverage_percent)} / ${pct(m.animal_coverage_percent)}`}>
          <span className="text-xs text-muted">human / {speciesName.toLowerCase()}</span>
        </StatTile>
        <StatTile label="Exact matches" value={`${m.exact_matches ?? "?"}/${m.alignment_columns ?? "?"}`}>
          <span className="text-xs text-muted">
            {m.insertion_events ?? 0} insertion ({m.inserted_residues ?? 0} aa) · {m.deletion_events ?? 0} deletion ({m.deleted_residues ?? 0} aa)
          </span>
        </StatTile>
      </div>

      {/* Status flags that change how far the numbers can be trusted. */}
      <div className="flex flex-wrap gap-2">
        {evidence.tied && <Badge tone="warn">Tied optimal alignments · mappings may shift</Badge>}
        {evidence.functionalStatus && (
          <Badge tone={evidence.functionalStatus === "ok" ? "ok" : "warn"}>
            UniProt annotation: {evidence.functionalStatus}
          </Badge>
        )}
        {evidence.invalidFields.length > 0 && (
          <Badge tone="danger">Unreadable fields: {evidence.invalidFields.join(", ")}</Badge>
        )}
      </div>

      {/* Which proteins were actually compared. */}
      {refs.length > 0 && (
        <table className="w-full overflow-hidden rounded-sm border border-rule text-sm">
          <thead className="bg-sunken text-left text-xs text-muted">
            <tr>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Reference protein</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Human</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">{speciesName}</th>
            </tr>
          </thead>
          <tbody>
            {refs.map((r) => (
              <tr key={r.label} className="border-t border-rule bg-surface">
                <th scope="row" className="px-2.5 py-1.5 text-left font-mono text-xs font-normal text-muted">{r.label}</th>
                <td className="break-all px-2.5 py-1.5 font-mono text-xs">{r.h || "n/a"}</td>
                <td className="break-all px-2.5 py-1.5 font-mono text-xs">{r.a || "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Curated motif check: computed residues, then the literature context. */}
      {evidence.motif && (
        <div className="flex flex-col gap-2 rounded-sm border border-rule p-3">
          <Heading>Motif check</Heading>
          <div className="flex flex-wrap items-center gap-3 font-mono text-sm">
            <span>Human {evidence.motif.humanWindow}</span>
            <span className="text-muted">⟷</span>
            <span>{speciesName} {evidence.motif.animalWindow ?? "not contiguous"}</span>
            {evidence.motif.pattern && <span className="text-xs text-muted">(published pattern {evidence.motif.pattern})</span>}
          </div>
          {/* Per-position residues: green = identical, amber = substituted. */}
          <div className="flex flex-wrap gap-1">
            {evidence.motif.residues.map((r) => (
              <span key={r.position} className={`rounded-sm px-1.5 py-0.5 font-mono text-[11px] ${MOTIF_STATE[r.state] ?? "bg-na-soft text-na"}`}>
                {r.human}{r.position}{r.animal ?? "–"} · {r.state}
              </span>
            ))}
          </div>
          {evidence.motif.mechanism && <p className="text-xs text-muted">{evidence.motif.mechanism}</p>}
          {evidence.motif.scope && <p className="text-xs italic text-muted">Scope: {evidence.motif.scope}</p>}
          {evidence.motif.sourceRecordId && <p className="font-mono text-[11px] text-muted">source: {evidence.motif.sourceRecordId}</p>}
        </div>
      )}

      {/* Substitutions, annotated ones first. */}
      {evidence.substitutions.length > 0 && (
        <div className="flex flex-col gap-2">
          <Heading>
            {`Substitutions · ${evidence.substitutions.length} total, ${annotatedCount} overlap annotated features`}
          </Heading>
          <div className="flex flex-wrap gap-1">
            {evidence.substitutions.slice(0, VISIBLE_SUBSTITUTIONS).map((s, i) => (
              <Chip key={i} {...s} />
            ))}
          </div>
          {evidence.substitutions.length > VISIBLE_SUBSTITUTIONS && (
            <details className="text-xs">
              <summary className="cursor-pointer text-accent">Show all {evidence.substitutions.length}</summary>
              <div className="mt-2 flex flex-wrap gap-1">
                {evidence.substitutions.slice(VISIBLE_SUBSTITUTIONS).map((s, i) => (
                  <Chip key={i} {...s} />
                ))}
              </div>
            </details>
          )}
          <p className="text-xs text-muted">Tinted = overlaps a UniProt feature (hover for which). Overlap is not evidence of altered function.</p>
        </div>
      )}

      {/* Full evidence for audit, collapsed by default. */}
      <details className="text-xs">
        <summary className="cursor-pointer text-muted">Raw evidence (JSON, {layer.observations.length} fields)</summary>
        <pre className="mt-2 max-h-64 overflow-auto rounded-sm bg-sunken p-2 font-mono text-[11px] whitespace-pre-wrap break-all">
          {layer.observations.map((o) => `${o.field}: ${o.value}`).join("\n\n")}
        </pre>
      </details>
    </div>
  );
}
