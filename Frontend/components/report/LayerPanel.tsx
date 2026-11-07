/**
 * LayerPanel: one evidence layer (sequence, localisation, ...).
 *
 * Key rule from the design doc: a missing layer must be visibly marked, never
 * left blank or shown as if it had data. So any status other than "ok"
 * renders as a grey, dashed-border panel.
 *
 * Observations that come as human_/animal_ pairs are shown side by side
 * (Field | Human | <species>), with rows whose values differ marked. The
 * gene-based sequence layer (JSON observations) gets its own readable view,
 * and an ambiguous orthologue lists its candidates. Hand-entered fixture
 * evidence is badged so it is never mistaken for a live retrieval.
 */

import { Badge } from "@/components/ui/Badge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FIXTURE_DATA_VERSION, LAYER_META } from "@/lib/layers";
import { pairObservations } from "@/lib/observations";
import { parseAmbiguousCandidates, parseSequenceEvidence } from "@/lib/sequenceEvidence";
import type { LayerResult } from "@/lib/types";
import { EmptyIcon } from "./EmptyState";
import { SequenceEvidence } from "./SequenceEvidence";

interface LayerPanelProps {
  layer: LayerResult;
  /** Animal column heading, e.g. "Mouse". */
  speciesName: string;
}

export function LayerPanel({ layer, speciesName }: LayerPanelProps) {
  const meta = LAYER_META[layer.layer];
  // incomplete / unavailable -> grey "missing data" styling
  const muted = layer.status !== "ok";
  // Gene-based sequence evidence (null for every other layer / legacy result).
  const evidence = parseSequenceEvidence(layer);
  // Candidate orthologues when Ensembl couldn't give a unique one.
  const candidates = parseAmbiguousCandidates(layer);
  // Side-by-side pairs, and the observations that have no partner. Skipped
  // when one of the dedicated views above takes over.
  const { pairs, rest } = evidence || candidates ? { pairs: [], rest: [] } : pairObservations(layer.observations);

  return (
    <article
      // The sequence evidence view needs the full row width.
      className={`flex flex-col gap-3 rounded border p-4 ${evidence ? "md:col-span-2" : ""} ${
        muted ? "border-dashed border-na/50 bg-na-soft" : "border-rule bg-surface"
      }`}
    >
      {/* Title, data source and status badge */}
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{meta.title}</h3>
          <p className="text-xs text-muted">{meta.source}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          {layer.data_version === FIXTURE_DATA_VERSION && <Badge tone="warn">Demo fixture</Badge>}
          <StatusBadge status={layer.status} />
        </div>
      </header>

      {evidence && <SequenceEvidence evidence={evidence} layer={layer} speciesName={speciesName} />}

      {/* Ambiguous orthologue: list every candidate; none was chosen. */}
      {candidates && (
        <div className="flex flex-col gap-1.5 text-sm">
          <p className="font-medium">{candidates.length} candidate orthologues; none selected</p>
          <ul className="flex flex-col gap-1 font-mono text-xs">
            {candidates.map((c, i) => (
              <li key={i} className="rounded-sm bg-surface px-2 py-1">
                {c.targetGene ?? "unknown gene"} · {c.targetProtein ?? "no protein id"} · {c.type ?? "unknown type"}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Human vs animal comparison table. */}
      {pairs.length > 0 && (
        <table className="w-full overflow-hidden rounded-sm border border-rule text-sm">
          <thead className="bg-sunken text-left text-xs text-muted">
            <tr>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Field</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Human</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">{speciesName}</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((p) => (
              // Differing rows get a faint amber tint so they draw the eye.
              <tr key={p.label} className={`border-t border-rule align-top ${p.differs ? "bg-warn-soft/60" : "bg-surface"}`}>
                <th scope="row" className="px-2.5 py-1.5 text-left font-mono text-xs font-normal leading-5 text-muted">
                  {p.label}
                  {p.differs && <span className="ml-1 font-sans font-semibold text-warn">≠</span>}
                  <span className="sr-only">{p.differs ? " (differs)" : " (same)"}</span>
                </th>
                <td className="px-2.5 py-1.5">{p.human.value}</td>
                <td className="px-2.5 py-1.5">{p.animal.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Remaining observations as a zebra-striped field/value list. */}
      {rest.length > 0 && (
        <dl className="overflow-hidden rounded-sm border border-rule text-sm">
          {rest.map((o) => (
            <div key={o.field} className="flex justify-between gap-4 bg-surface px-2.5 py-1.5 odd:bg-sunken">
              <dt className="font-mono text-xs leading-5 text-muted">{o.field}</dt>
              <dd className="text-right">{o.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* Nothing returned: say what this layer would show and where from. */}
      {layer.observations.length === 0 && (
        <div className="flex items-start gap-3">
          <EmptyIcon name="data" />
          <div className="text-sm text-muted">
            <p>{meta.description}</p>
            <p className="text-xs">No observations returned. Would be sourced from {meta.source}.</p>
          </div>
        </div>
      )}

      {/* Layer-specific caveats, pinned to the bottom with mt-auto. */}
      {layer.limitations.length > 0 && (
        <ul className="mt-auto flex list-disc flex-col gap-1 pl-4 text-xs text-muted">
          {layer.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}

      {/* Provenance line: source records (linked when a URL exists) and data version. */}
      {(layer.source_records.length > 0 || layer.data_version) && (
        <p className="flex flex-wrap gap-x-2 gap-y-0.5 border-t border-rule pt-2 font-mono text-[11px] text-muted">
          <span>Source:</span>
          {layer.source_records.map((s) =>
            s.url ? (
              <a key={s.id} href={s.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                {s.id}
              </a>
            ) : (
              <span key={s.id}>{s.id}</span>
            ),
          )}
          {layer.data_version && <span>· {layer.data_version}</span>}
        </p>
      )}
    </article>
  );
}
