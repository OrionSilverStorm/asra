/**
 * Collects every source record across a report's layers, de-duplicated,
 * with the layers it appears in and the findings that cite it.
 * Feeds the Sources table and the "Sources" count in the summary.
 */

import type { Finding, LayerName, LayerResult, SourceRecord } from "./types";

/** One unique source record and where it's used. */
export interface SourceUsage {
  record: SourceRecord;
  /** Layers that returned this record, in report order. */
  layers: LayerName[];
  /** Data version of the first layer that returned it, if known. */
  dataVersion: string | null;
  /** Finding ids whose sourceRecordId matches. */
  citedBy: string[];
}

export function collectSources(layers: LayerResult[], findings: Finding[]): SourceUsage[] {
  // Keyed by record id; Map keeps first-seen order.
  const byId = new Map<string, SourceUsage>();
  for (const layer of layers) {
    for (const record of layer.source_records) {
      const entry = byId.get(record.id);
      if (entry) {
        // Same record from another layer: just note the extra layer.
        if (!entry.layers.includes(layer.layer)) entry.layers.push(layer.layer);
      } else {
        byId.set(record.id, {
          record,
          layers: [layer.layer],
          dataVersion: layer.data_version,
          citedBy: findings.filter((f) => f.sourceRecordId === record.id).map((f) => f.id),
        });
      }
    }
  }
  return [...byId.values()];
}
