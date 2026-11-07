/**
 * LayerPanel: one evidence layer (sequence, localisation, ...).
 *
 * Key rule from the design doc: a missing layer must be visibly marked, never
 * left blank or shown as if it had data. So any status other than "ok"
 * renders as a grey, dashed-border panel.
 */

import { StatusBadge } from "@/components/ui/StatusBadge";
import { LAYER_META } from "@/lib/layers";
import type { LayerResult } from "@/lib/types";

export function LayerPanel({ layer }: { layer: LayerResult }) {
  const meta = LAYER_META[layer.layer];
  // incomplete / unavailable -> grey "missing data" styling
  const muted = layer.status !== "ok";

  return (
    <article
      className={`flex flex-col gap-3 rounded-lg border p-5 ${
        muted ? "border-dashed border-na/40 bg-na-soft" : "border-rule bg-surface"
      }`}
    >
      {/* Title, data source and status badge */}
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium">{meta.title}</h3>
          <p className="text-xs text-muted">{meta.source}</p>
        </div>
        <StatusBadge status={layer.status} />
      </header>

      {/* Observations as field/value rows, or an explicit "nothing returned". */}
      {layer.observations.length > 0 ? (
        <dl className="flex flex-col gap-2 text-sm">
          {layer.observations.map((o) => (
            <div key={o.field} className="flex justify-between gap-4 border-b border-rule pb-2 last:border-0">
              <dt className="font-mono text-xs text-muted">{o.field}</dt>
              <dd className="text-right">{o.value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-muted">{meta.description} No observations returned.</p>
      )}

      {/* Layer-specific caveats, pinned to the bottom with mt-auto. */}
      {layer.limitations.length > 0 && (
        <ul className="mt-auto flex flex-col gap-1 border-t border-rule pt-3 text-xs text-muted">
          {layer.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}

      {/* Provenance line: source record IDs and data version. */}
      {(layer.source_records.length > 0 || layer.data_version) && (
        <p className="font-mono text-[11px] text-muted">
          {layer.source_records.map((s) => s.id).join(" · ")}
          {layer.data_version && ` · ${layer.data_version}`}
        </p>
      )}
    </article>
  );
}
