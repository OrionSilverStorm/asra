/**
 * LayerGrid: card holding all four LayerPanels in a 2×2 grid (one column
 * on phones), topped by an evidence-availability track: one coloured cell
 * per layer, like a cBioPortal OncoPrint row or the AlphaFold confidence
 * bar, so data coverage reads at a glance.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Legend } from "@/components/ui/Legend";
import { STATUS } from "@/components/ui/StatusBadge";
import { LAYER_META } from "@/lib/layers";
import type { LayerResult } from "@/lib/types";
import { LayerPanel } from "./LayerPanel";

/** Legend entries, one per status, built from the shared status map. */
const STATUS_KEY = Object.values(STATUS).map((s) => ({ label: s.label, swatch: s.fill }));

interface LayerGridProps {
  layers: LayerResult[];
  /** Animal column heading for the comparison tables, e.g. "Mouse". */
  speciesName: string;
}

export function LayerGrid({ layers, speciesName }: LayerGridProps) {
  // Only "ok" counts as complete; incomplete layers are not.
  const ready = layers.filter((l) => l.status === "ok").length;
  return (
    <Card>
      <CardHeader
        eyebrow="Evidence"
        title="Comparison layers"
        actions={<span className="font-mono text-xs text-muted">{ready}/{layers.length} complete</span>}
      />
      <CardBody className="flex flex-col gap-4">
        {/* Availability track: label + status above a solid status bar. */}
        <div className="flex flex-col gap-2">
          <ol aria-label="Data availability by layer" className="grid grid-cols-2 gap-1 sm:grid-cols-4">
            {layers.map((l) => (
              <li key={l.layer} className="flex flex-col gap-1">
                <span aria-hidden className={`h-2.5 rounded-sm ${STATUS[l.status].fill}`} />
                {/* Text repeats the colour's meaning for colour-blind readers. */}
                <span className="text-xs">
                  {LAYER_META[l.layer].title}
                  <span className="text-muted"> · {STATUS[l.status].label}</span>
                </span>
              </li>
            ))}
          </ol>
          <Legend label="Status key" items={STATUS_KEY} />
        </div>

        {/* The panels themselves. */}
        <div className="grid gap-4 md:grid-cols-2">
          {layers.map((l) => (
            <LayerPanel key={l.layer} layer={l} speciesName={speciesName} />
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
