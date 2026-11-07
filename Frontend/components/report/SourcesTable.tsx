/**
 * SourcesTable: every source record behind the report, one row each:
 * ID (linked when a URL exists), database, layer(s), data version, and
 * which findings cite it. Makes "no claim without a source" checkable.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { LAYER_META } from "@/lib/layers";
import { collectSources } from "@/lib/sources";
import type { Finding, LayerResult } from "@/lib/types";
import { EmptyState } from "./EmptyState";
import { findingAnchor } from "./FindingCard";

/** Shared cell padding for header and body cells. */
const CELL = "px-3 py-2 text-left";

export function SourcesTable({ layers, findings }: { layers: LayerResult[]; findings: Finding[] }) {
  const sources = collectSources(layers, findings);
  return (
    <Card>
      <CardHeader
        eyebrow="Provenance"
        title="Sources"
        actions={<span className="font-mono text-xs text-muted">{sources.length} records</span>}
      />
      <CardBody>
        {sources.length ? (
          // Scrolls inside its own box on narrow screens.
          <div className="overflow-x-auto rounded border border-rule">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="bg-sunken text-xs text-muted">
                <tr>
                  {["Record", "Database", "Layer", "Version", "Cited by"].map((h) => (
                    <th key={h} scope="col" className={`${CELL} font-medium`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sources.map(({ record, layers: used, dataVersion, citedBy }) => (
                  <tr key={record.id} className="border-t border-rule align-top">
                    <td className={`${CELL} font-mono text-xs`}>
                      {record.url ? (
                        <a href={record.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                          {record.id}
                        </a>
                      ) : (
                        record.id
                      )}
                    </td>
                    <td className={CELL}>{record.source}</td>
                    <td className={CELL}>{used.map((l) => LAYER_META[l].short).join(", ")}</td>
                    <td className={`${CELL} font-mono text-xs text-muted`}>{dataVersion ?? "n/a"}</td>
                    <td className={CELL}>
                      {citedBy.length ? (
                        // Chips link to the citing finding cards.
                        <span className="flex flex-wrap gap-1">
                          {citedBy.map((id) => (
                            <a key={id} href={`#${findingAnchor(id)}`} className="rounded-sm bg-accent-soft px-1.5 font-mono text-xs text-accent hover:underline">
                              {id}
                            </a>
                          ))}
                        </span>
                      ) : (
                        <span className="text-xs text-muted">not cited</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="data" hint="Records appear when a comparison layer returns data.">
            No source records.
          </EmptyState>
        )}
      </CardBody>
    </Card>
  );
}
