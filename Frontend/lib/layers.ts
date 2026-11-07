/**
 * Display metadata for the four evidence layers.
 *
 * Keeps titles, data sources and descriptions in one place so the
 * "How it works" sidebar, the layer panels and the mock all agree.
 */

import type { LayerName } from "./types";

/**
 * data_version the backend gives hand-entered demo evidence
 * (Backend/tools/fixtures.py FIXTURE_VERSION). Keep the two in sync.
 */
export const FIXTURE_DATA_VERSION = "fixture (hand-entered)";

/** Canonical order in which layers are shown (matches the design doc). */
export const LAYER_ORDER: LayerName[] = [
  "sequence",
  "localisation",
  "cell_expression",
  "tissue_expression",
];

/** Human-readable info for each layer, keyed by LayerName. */
/** `short` is a compact column label (e.g. the evidence matrix header). */
export const LAYER_META: Record<LayerName, { title: string; short: string; source: string; description: string }> = {
  sequence: {
    title: "Sequence",
    short: "Sequence",
    source: "Ensembl orthologues · Biopython",
    description: "Global identity and identity at mapped functional residues.",
  },
  localisation: {
    title: "Subcellular localisation",
    short: "Localisation",
    source: "UniProt",
    description: "Shared, human-only and animal-only compartments.",
  },
  cell_expression: {
    title: "Cell-type expression",
    short: "Cell type",
    // Discover gene-expression API for human/mouse; Census audit for other species.
    source: "CELLxGENE Discover · Census",
    description: "Detection fractions per cell population.",
  },
  tissue_expression: {
    title: "Tissue expression",
    short: "Tissue",
    source: "GTEx · Bgee",
    description: "Tissue distribution with matched anatomical IDs.",
  },
};

/**
 * Layer a finding cites, from its "<layer>.<field>" citedField.
 * Returns null if the prefix isn't a known layer (malformed citation).
 */
export function citedLayer(citedField: string): LayerName | null {
  const prefix = citedField.split(".")[0];
  return LAYER_ORDER.find((l) => l === prefix) ?? null;
}
