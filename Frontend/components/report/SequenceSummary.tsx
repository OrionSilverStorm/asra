/**
 * SequenceSummary: basic facts about the submitted sequence.
 *
 * Everything here is computed from the user's input (lib/sequence.ts), so
 * it is real data even when the rest of the report is mock.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import type { SequenceStats } from "@/lib/types";

/** How many residues to show in the composition chart. */
const TOP_RESIDUES = 10;

export function SequenceSummary({ stats }: { stats: SequenceStats }) {
  // Composition is pre-sorted most-common first, so slicing gives the top N.
  const top = stats.composition.slice(0, TOP_RESIDUES);
  // Bars are scaled relative to the most common residue (= full width).
  const max = top[0]?.fraction ?? 1;

  return (
    <Card>
      <CardHeader eyebrow="Input" title="Sequence summary" />
      {/* Two columns on larger screens: key stats | composition chart. */}
      <CardBody className="grid gap-6 sm:grid-cols-[200px_minmax(0,1fr)]">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-1">
          <Stat label="Length" value={`${stats.length.toLocaleString()} aa`} />
          <Stat label="Estimated mass" value={`${stats.estimatedMassKDa.toFixed(1)} kDa`} />
        </dl>

        {/* Horizontal bar chart of residue frequencies. */}
        <div>
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
            Composition · top {top.length}
          </p>
          <ul className="flex flex-col gap-1.5">
            {top.map(({ residue, fraction }) => (
              // Three columns: letter | bar | percentage
              <li key={residue} className="grid grid-cols-[1.5rem_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm">
                <span className="font-mono font-semibold">{residue}</span>
                {/* Track */}
                <span className="h-2 overflow-hidden rounded-full bg-sunken">
                  {/* Fill: width proportional to frequency */}
                  <span
                    className="block h-full rounded-full bg-accent"
                    style={{ width: `${(fraction / max) * 100}%` }}
                  />
                </span>
                <span className="text-right font-mono text-xs text-muted">
                  {(fraction * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}

/** A single labelled statistic (small label above a large monospace value). */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-xl font-semibold">{value}</dd>
    </div>
  );
}
