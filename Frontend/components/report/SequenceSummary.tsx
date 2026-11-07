/**
 * SequenceSummary: basic facts about the submitted sequence.
 *
 * Everything here is computed from the user's input (lib/sequence.ts), so
 * it is real data even when the rest of the report is mock. Layout: key
 * stats | composition chart, then the sequence itself.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Legend } from "@/components/ui/Legend";
import { StatTile } from "@/components/ui/StatTile";
import { RESIDUE_CLASSES, residueSwatch } from "@/lib/residues";
import type { SequenceStats } from "@/lib/types";
import { SequenceViewer } from "./SequenceViewer";

/** How many residues to show in the composition chart. */
const TOP_RESIDUES = 10;

interface SequenceSummaryProps {
  stats: SequenceStats;
  /** The cleaned input sequence, shown in the viewer. */
  sequence: string;
}

export function SequenceSummary({ stats, sequence }: SequenceSummaryProps) {
  // Composition is pre-sorted most-common first, so slicing gives the top N.
  const top = stats.composition.slice(0, TOP_RESIDUES);
  // Bars are scaled relative to the most common residue (= full width).
  const max = top[0]?.fraction ?? 1;

  return (
    <Card>
      <CardHeader eyebrow="Input" title="Sequence" />
      <CardBody className="flex flex-col gap-5">
        {/* Two columns on larger screens: key stats | composition chart. */}
        <div className="grid gap-5 sm:grid-cols-[180px_minmax(0,1fr)]">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-1 sm:content-start">
            <StatTile label="Length" value={`${stats.length.toLocaleString()} aa`} />
            <StatTile label="Estimated mass" value={`${stats.estimatedMassKDa.toFixed(1)} kDa`} />
          </div>

          {/* Horizontal bar chart of residue frequencies, coloured by class. */}
          <div className="flex flex-col gap-3">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
              Composition · top {top.length}
            </p>
            <ul className="flex flex-col gap-1">
              {top.map(({ residue, fraction }) => (
                // Three columns: letter | bar | percentage
                <li key={residue} className="grid grid-cols-[1.25rem_minmax(0,1fr)_3.25rem] items-center gap-3 text-sm">
                  <span className="font-mono font-semibold">{residue}</span>
                  {/* Track */}
                  <span className="h-2.5 overflow-hidden rounded-sm bg-sunken">
                    {/* Fill: width proportional to frequency, colour = residue class */}
                    <span
                      className={`block h-full ${residueSwatch(residue)}`}
                      style={{ width: `${(fraction / max) * 100}%` }}
                    />
                  </span>
                  <span className="text-right font-mono text-xs text-muted">
                    {(fraction * 100).toFixed(1)}%
                  </span>
                </li>
              ))}
            </ul>
            {/* Key for the bar colours. */}
            <Legend label="Residue class key" items={RESIDUE_CLASSES} />
          </div>
        </div>

        {/* The sequence itself, UniProt-style. */}
        <SequenceViewer sequence={sequence} />
      </CardBody>
    </Card>
  );
}

