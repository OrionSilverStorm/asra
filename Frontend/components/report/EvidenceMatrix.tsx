/**
 * EvidenceMatrix: findings (rows) × evidence layers (columns). A filled
 * cell means the finding cites that layer, coloured by its concern. Each
 * column header shows the layer's data status, so a finding resting on an
 * incomplete layer stands out at a glance.
 */

import { STATUS } from "@/components/ui/StatusBadge";
import { citedLayer, LAYER_META } from "@/lib/layers";
import type { Finding, LayerResult } from "@/lib/types";
import { CONCERN, findingAnchor } from "./FindingCard";

export function EvidenceMatrix({ findings, layers }: { findings: Finding[]; layers: LayerResult[] }) {
  return (
    // Scrolls inside its own box on narrow screens instead of the page.
    <div className="overflow-x-auto rounded border border-rule">
      <table aria-label="Evidence each finding cites" className="w-full min-w-[480px] text-sm">
        <thead className="bg-sunken text-xs text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium">Finding</th>
            {layers.map((l) => (
              <th key={l.layer} scope="col" className="w-24 px-2 py-2 font-medium">
                <span className="flex items-center justify-center gap-1.5">
                  {/* Status dot: is the evidence behind this column complete? */}
                  <span aria-hidden className={`size-2 rounded-full ${STATUS[l.status].fill}`} />
                  {LAYER_META[l.layer].short}
                  <span className="sr-only">({STATUS[l.status].label})</span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => {
            const cited = citedLayer(f.citedField);
            return (
              <tr key={f.id} className="border-t border-rule">
                {/* Row label links to the full finding below. */}
                <th scope="row" className="max-w-0 px-3 py-2 text-left font-normal">
                  <a href={`#${findingAnchor(f.id)}`} className="flex gap-2 hover:text-accent">
                    <span className="font-mono text-xs text-muted">{f.id}</span>
                    <span className="truncate">{f.claim}</span>
                  </a>
                </th>
                {layers.map((l) => (
                  <td key={l.layer} className="px-2 py-2 text-center">
                    {cited === l.layer ? (
                      <span className={`inline-block size-3.5 rounded-sm ${CONCERN[f.concern].fill}`}>
                        <span className="sr-only">Cited, {CONCERN[f.concern].label}</span>
                      </span>
                    ) : (
                      // Faint dot keeps the grid readable without implying data.
                      <span aria-hidden className="inline-block size-1 rounded-full bg-rule" />
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
