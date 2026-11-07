/**
 * Display metadata for the four evidence layers.
 *
 * Keeps titles, data sources and descriptions in one place so the
 * "How it works" sidebar, the layer panels and the mock all agree.
 */

import type { LayerName } from "./types";

/** Canonical order in which layers are shown (matches the design doc). */
export const LAYER_ORDER: LayerName[] = [
  "sequence",
  "localisation",
  "cell_expression",
  "tissue_expression",
];

/** Human-readable info for each layer, keyed by LayerName. */
export const LAYER_META: Record<LayerName, { title: string; source: string; description: string }> = {
  sequence: {
    title: "Sequence",
    source: "Ensembl orthologues · Biopython",
    description: "Global identity and identity at mapped functional residues.",
  },
  localisation: {
    title: "Subcellular localisation",
    source: "UniProt",
    description: "Shared, human-only and animal-only compartments.",
  },
  cell_expression: {
    title: "Cell-type expression",
    source: "CELLxGENE Census",
    description: "Detection fractions per cell population.",
  },
  tissue_expression: {
    title: "Tissue expression",
    source: "GTEx · Bgee",
    description: "Tissue distribution with matched anatomical IDs.",
  },
};
