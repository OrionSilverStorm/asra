/**
 * LayerGrid: card holding all four LayerPanels in a 2×2 grid
 * (one column on phones), with a "N of 4 complete" counter.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import type { LayerResult } from "@/lib/types";
import { LayerPanel } from "./LayerPanel";

export function LayerGrid({ layers }: { layers: LayerResult[] }) {
  // Only "ok" counts as complete; incomplete layers are not.
  const ready = layers.filter((l) => l.status === "ok").length;
  return (
    <Card>
      <CardHeader
        eyebrow="Evidence"
        title="Comparison layers"
        actions={<span className="text-sm text-muted">{ready} of {layers.length} complete</span>}
      />
      <CardBody className="grid gap-4 md:grid-cols-2">
        {layers.map((l) => (
          <LayerPanel key={l.layer} layer={l} />
        ))}
      </CardBody>
    </Card>
  );
}
