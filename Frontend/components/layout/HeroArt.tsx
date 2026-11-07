/**
 * HeroArt: decorative illustration for the home-page intro. An abstract
 * two-row alignment (a human row over an animal row of residue blocks),
 * matched columns joined by lines, and mismatched columns outlined in amber.
 * It echoes what ASRA compares.
 *
 * Purely decorative: the pattern is fixed and represents no real data, so
 * it's aria-hidden and left out of print.
 */

import type { ResidueClass } from "@/lib/residues";

/** Literal fill classes per residue class (Tailwind needs full class names). */
const FILL: Record<ResidueClass, string> = {
  hydrophobic: "fill-res-hydrophobic",
  polar: "fill-res-polar",
  positive: "fill-res-positive",
  negative: "fill-res-negative",
  special: "fill-res-special",
};

/** Fixed illustrative pattern: top = "human", bottom = "animal". */
const TOP: ResidueClass[] = ["hydrophobic", "polar", "polar", "positive", "hydrophobic", "special", "negative", "hydrophobic", "polar", "positive"];
const BOTTOM: ResidueClass[] = ["hydrophobic", "polar", "polar", "negative", "hydrophobic", "special", "polar", "hydrophobic", "polar", "positive"];

/** Block geometry in viewBox units. */
const W = 22;
const GAP = 6;
const H = 28;
const ROW_Y = [24, 98];

export function HeroArt() {
  return (
    <svg aria-hidden viewBox="0 0 290 150" className="hidden w-72 shrink-0 md:block print:hidden">
      {TOP.map((top, i) => {
        const x = 6 + i * (W + GAP);
        const differs = top !== BOTTOM[i];
        return (
          <g key={i}>
            {/* Connector: solid for a match, dashed amber for a difference. */}
            <line
              x1={x + W / 2}
              x2={x + W / 2}
              y1={ROW_Y[0] + H}
              y2={ROW_Y[1]}
              className={differs ? "stroke-warn" : "stroke-rule"}
              strokeWidth="1.5"
              strokeDasharray={differs ? "3 3" : undefined}
            />
            {/* Human and animal residue blocks. */}
            {[top, BOTTOM[i]].map((cls, row) => (
              <rect
                key={row}
                x={x}
                y={ROW_Y[row]}
                width={W}
                height={H}
                rx="3"
                className={`${FILL[cls]} ${differs ? "stroke-warn" : "stroke-surface"}`}
                strokeWidth={differs ? 2 : 1}
                opacity="0.85"
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
