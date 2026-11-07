/**
 * Physicochemical residue classes, for colouring composition charts.
 *
 * Colours follow the familiar Clustal-style convention (hydrophobic blue,
 * positive red, negative magenta, polar green). The swatch classes map to
 * --res-* tokens in app/globals.css. Pure lookup, no logic.
 */

/** Class key, also the suffix of its colour token. */
export type ResidueClass = "hydrophobic" | "polar" | "positive" | "negative" | "special";

/** Display order, label and Tailwind fill for each class (also the legend). */
export const RESIDUE_CLASSES: { id: ResidueClass; label: string; swatch: string }[] = [
  { id: "hydrophobic", label: "Hydrophobic", swatch: "bg-res-hydrophobic" },
  { id: "polar", label: "Polar", swatch: "bg-res-polar" },
  { id: "positive", label: "Positive", swatch: "bg-res-positive" },
  { id: "negative", label: "Negative", swatch: "bg-res-negative" },
  { id: "special", label: "Special (G, P, X)", swatch: "bg-res-special" },
];

/** Residues in each class, as one string per class. */
const MEMBERS: Record<ResidueClass, string> = {
  hydrophobic: "AVLIMFW",
  polar: "STNQYC",
  positive: "KRH",
  negative: "DE",
  special: "GPX",
};

/** Tailwind fill class for a residue letter (unknown letters → special). */
export function residueSwatch(residue: string): string {
  const cls = RESIDUE_CLASSES.find((c) => MEMBERS[c.id].includes(residue));
  return (cls ?? RESIDUE_CLASSES[RESIDUE_CLASSES.length - 1]).swatch;
}
