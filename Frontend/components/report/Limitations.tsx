/**
 * Limitations: report-wide caveats (separate from per-layer limitations,
 * which appear inside each LayerPanel). Hidden entirely if there are none.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";

export function Limitations({ items }: { items: string[] }) {
  // Returning null renders nothing.
  if (!items.length) return null;
  return (
    <Card>
      <CardHeader eyebrow="Read before use" title="Limitations" />
      <CardBody>
        <ul className="flex list-disc flex-col gap-2 pl-5 text-sm leading-6 text-muted">
          {items.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
