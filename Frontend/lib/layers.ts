/**
 * Display metadata for the four evidence layers.
 *
 * Keeps titles, data sources and descriptions in one place so the
 * "How it works" sidebar, the layer panels and the mock all agree.
 */

import type { LayerName, LayerResult, Report } from "./types";

/**
 * data_version the backend gives hand-entered demo evidence
 * (Backend/tools/fixtures.py FIXTURE_VERSION). Keep the two in sync.
 */
export const FIXTURE_DATA_VERSION = "fixture (hand-entered)";

/**
 * Substrings the backend puts in `data_version` for evidence that is not a
 * fresh live retrieval. Keep in sync with Backend/tools/cell_expression.py
 * ("<census release> (recorded run)") and Backend/tools/sequence_pinned.py
 * ("Pinned Ensembl homology (...)").
 */
const RECORDED_MARKER = "(recorded run)";
const PINNED_MARKER = "Pinned Ensembl homology";

/** Where a layer's evidence came from. "live" = fetched during this request. */
export type Provenance = "live" | "fixture" | "recorded" | "pinned";

/** Short badge text and a plain-language explanation for each non-live kind. */
export const PROVENANCE_INFO: Record<Exclude<Provenance, "live">, { badge: string; note: string }> = {
  fixture: { badge: "Demo fixture", note: "hand-entered demo evidence, not a live retrieval" },
  recorded: { badge: "Recorded run", note: "a previously recorded benchmark run, not a fresh live retrieval" },
  pinned: { badge: "Pinned snapshot", note: "a pinned Ensembl homology snapshot, not a fresh live retrieval" },
};

/** Classifies one layer by its data_version (null/unknown versions count as live). */
export function layerProvenance(layer: LayerResult): Provenance {
  const v = layer.data_version ?? "";
  if (v === FIXTURE_DATA_VERSION) return "fixture";
  if (v.includes(RECORDED_MARKER)) return "recorded";
  if (v.includes(PINNED_MARKER)) return "pinned";
  return "live";
}

/** Layers in a report that are recorded or pinned (fixtures have their own origin label). */
export function snapshotLayers(report: Report): { layer: LayerResult; kind: "recorded" | "pinned" }[] {
  return report.layers.flatMap((layer) => {
    const kind = layerProvenance(layer);
    return kind === "recorded" || kind === "pinned" ? [{ layer, kind }] : [];
  });
}

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
