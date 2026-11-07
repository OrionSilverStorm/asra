/**
 * StatusBadge: renders a layer's status (ok / incomplete / unavailable)
 * as a coloured Badge with a human-readable label.
 */

import type { LayerStatus } from "@/lib/types";
import { Badge, type BadgeTone } from "./Badge";

/**
 * Maps each contract status to a badge tone, a label and a solid fill
 * (the fill is used by the availability track and its legend).
 */
export const STATUS: Record<LayerStatus, { tone: BadgeTone; label: string; fill: string }> = {
  ok: { tone: "ok", label: "Complete", fill: "bg-ok" },
  incomplete: { tone: "warn", label: "Incomplete", fill: "bg-warn" },
  unavailable: { tone: "na", label: "Unavailable", fill: "bg-na" },
};

export function StatusBadge({ status }: { status: LayerStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
