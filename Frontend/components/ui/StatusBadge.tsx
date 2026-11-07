/**
 * StatusBadge: renders a layer's status (ok / incomplete / unavailable)
 * as a coloured Badge with a human-readable label.
 */

import type { LayerStatus } from "@/lib/types";
import { Badge, type BadgeTone } from "./Badge";

/** Maps each contract status to a colour and a label. */
const STATUS: Record<LayerStatus, { tone: BadgeTone; label: string }> = {
  ok: { tone: "ok", label: "Complete" },
  incomplete: { tone: "warn", label: "Incomplete" },
  unavailable: { tone: "na", label: "Unavailable" },
};

export function StatusBadge({ status }: { status: LayerStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
