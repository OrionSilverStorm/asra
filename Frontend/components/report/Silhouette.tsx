/**
 * Silhouette: small line-art figure for the human and each species group,
 * used in the report's species comparison banner. Decorative only
 * (aria-hidden); the names beside it carry the meaning. Drawn with
 * currentColor so it follows the theme.
 */

import type { Species } from "@/lib/types";

/** "Human" plus every species group. */
export type SilhouetteKind = "Human" | Species["group"];

/** 48×48 stroked paths per kind. */
const PATHS: Record<SilhouetteKind, string> = {
  // Standing figure
  Human: "M24 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM24 14v16M15 25l9-7 9 7M24 30l-7 14M24 30l7 14",
  // Mouse: round body, ear, long curled tail
  Rodent: "M10 32c0-7 6-11 13-11s13 4 13 9c0 3-3 5-6 5H14c-2 0-4-1-4-3zM31 21a3.5 3.5 0 1 1 5 4M36 30h4M10 32c-4 1-6 5-3 8s7 1 9-1M18 35v3M29 35v3",
  // Seated monkey: head, curved back, arm, tail
  "Non-human primate": "M30 6a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM28 16c-8 3-12 12-10 22h12M24 22l10 6v8M18 36c-8 2-11-4-8-9",
  // Four-legged mammal: body, head, legs, tail
  "Non-rodent mammal": "M9 22c4-3 21-3 25 0v9H9zM34 22l3-6a4 4 0 1 1 4 6l-7 3M12 31v11M17 31v11M27 31v11M32 31v11M9 23l-5-4",
  // Fish: body, tail fin, eye
  Other: "M7 24c7-11 23-11 30 0-7 11-23 11-30 0zM37 24l8-8v16zM15 22v.01M22 17l4-5 4 6",
};

export function Silhouette({ kind }: { kind: SilhouetteKind }) {
  return (
    <svg aria-hidden viewBox="0 0 48 48" className="size-10 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[kind]} />
    </svg>
  );
}
