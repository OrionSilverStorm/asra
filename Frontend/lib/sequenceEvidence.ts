/**
 * Decoder for the gene-based sequence layer (Backend/tools/sequence_layer.py).
 *
 * That layer's observation values are JSON strings (see claude.md). This
 * module turns them into a small typed summary for the UI and Markdown
 * export. Pure and defensive: a value that fails to parse is skipped and
 * listed in `invalidFields`, never thrown. Nothing is recomputed, only
 * read; the one derived thing is the "E72A" display label.
 */

import type { LayerResult } from "./types";

/** Alignment measurements exactly as the backend reports them. */
export type Measurements = Partial<Record<
  | "human_length" | "animal_length" | "alignment_columns" | "paired_columns" | "exact_matches"
  | "substitutions" | "insertion_events" | "deletion_events" | "inserted_residues" | "deleted_residues"
  | "identity_percent" | "paired_identity_percent" | "human_coverage_percent" | "animal_coverage_percent",
  number
>>;

/** One side of the compared protein pair. */
export interface ProteinRef {
  proteinId: string | null;
  geneId: string | null;
  /** UniProt accession/isoform, when functional analysis verified the mapping. */
  accession: string | null;
  isoform: string | null;
  /** Feature-annotation status for this protein (e.g. "ok", "unavailable"). */
  annotationStatus: string | null;
}

/** A residue substitution, labelled like "E72A" (human residue, human position, animal residue). */
export interface Substitution {
  label: string;
  /** True when it overlaps an annotated UniProt feature. */
  annotated: boolean;
  /** Human feature names it overlaps, e.g. "Transmembrane: Helical; Name=1". */
  features: string[];
}

/** The curated SLC29A1 motif check (only present for that gene). */
export interface MotifCheck {
  humanWindow: string;
  animalWindow: string | null;
  /** Per-position comparison, in human coordinates. */
  residues: { position: number; human: string; animal: string | null; state: string }[];
  pattern: string | null;
  mechanism: string | null;
  scope: string | null;
  sourceRecordId: string | null;
}

export interface SequenceEvidence {
  measurements: Measurements;
  human: ProteinRef;
  animal: ProteinRef;
  /** More than one optimal alignment exists (mappings may shift). */
  tied: boolean;
  substitutions: Substitution[];
  /** Overall functional-annotation status, or null if not run. */
  functionalStatus: string | null;
  motif: MotifCheck | null;
  /** Observation fields whose JSON failed to parse. */
  invalidFields: string[];
}

// Loose JSON object type for reading decoded values safely.
type Json = Record<string, unknown>;

/** Narrow unknown to a plain object. */
const obj = (v: unknown): Json | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Json) : null);
/** Read a string field or null. */
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
/** Read an array or empty. */
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

/** Decode every observation; returns field → parsed value plus parse failures. */
function decode(layer: LayerResult): { values: Record<string, unknown>; invalid: string[] } {
  const values: Record<string, unknown> = {};
  const invalid: string[] = [];
  for (const o of layer.observations) {
    try {
      values[o.field] = JSON.parse(o.value);
    } catch {
      invalid.push(o.field);
    }
  }
  return { values, invalid };
}

/** Build a ProteinRef from the top-level protein record and its functional identity. */
function protein(record: unknown, functional: Json | null): ProteinRef {
  const r = obj(record);
  const identity = obj(functional?.identity);
  return {
    proteinId: str(r?.protein_id),
    geneId: str(r?.gene_id),
    accession: str(identity?.accession),
    isoform: str(identity?.isoform),
    annotationStatus: str(functional?.status),
  };
}

/** "E72A"-style label for one substitution record. */
function label(s: Json): string {
  return `${str(s.human_residue) ?? "?"}${s.human_position ?? "?"}${str(s.animal_residue) ?? "?"}`;
}

/** Decode the gene-based sequence layer, or null if this layer isn't one. */
export function parseSequenceEvidence(layer: LayerResult): SequenceEvidence | null {
  if (layer.layer !== "sequence") return null;
  // The legacy length-only layer has plain-string values: no "measurements".
  if (!layer.observations.some((o) => o.field === "measurements")) return null;
  const { values, invalid } = decode(layer);
  const measurements = obj(values.measurements);
  if (!measurements) return null;

  const fa = obj(values.functional_analysis);
  const proteins = obj(fa?.proteins);

  // Human feature id → readable name, for labelling annotated substitutions.
  const featureName = new Map(
    arr(fa?.mapped_human_features).map((f) => {
      const o = obj(f) ?? {};
      const desc = str(o.description);
      return [str(o.id), `${str(o.type) ?? "Feature"}${desc ? `: ${desc}` : ""}`] as const;
    }),
  );

  // Prefer functional analysis's split (annotated vs other); fall back to the plain list.
  const annotated = arr(fa?.functional_substitutions).map(obj).filter((s): s is Json => !!s);
  const others = fa
    ? [...arr(fa.other_substitutions), ...arr(fa.unclassified_substitutions)].map(obj).filter((s): s is Json => !!s)
    : arr(values.substitutions).map(obj).filter((s): s is Json => !!s);
  const substitutions: Substitution[] = [
    ...annotated.map((s) => ({
      label: label(s),
      annotated: true,
      // Unique human feature names this substitution overlaps.
      features: [...new Set(arr(s.annotation_overlaps).map((a) => featureName.get(str(obj(a)?.feature_id)) ?? null))]
        .filter((n): n is string => !!n),
    })),
    ...others.map((s) => ({ label: label(s), annotated: false, features: [] })),
  ];

  // SLC29A1 motif: computed observation kept separate from the literature record.
  const motifRaw = obj(fa?.slc29a1_motif);
  const observed = obj(motifRaw?.sequence_observation);
  const literature = obj(motifRaw?.literature);
  const motif: MotifCheck | null = observed && str(observed.human_window)
    ? {
        humanWindow: str(observed.human_window)!,
        animalWindow: str(observed.animal_window),
        residues: arr(observed.residues).map((r) => {
          const o = obj(r) ?? {};
          return {
            position: typeof o.human_position === "number" ? o.human_position : 0,
            human: str(o.human_residue) ?? "?",
            animal: str(o.animal_residue),
            state: str(o.state) ?? "unknown",
          };
        }),
        pattern: str(literature?.pattern),
        mechanism: str(literature?.mechanism),
        scope: str(literature?.scope),
        sourceRecordId: str(motifRaw?.source_record_id),
      }
    : null;

  return {
    measurements: measurements as Measurements,
    human: protein(values.human, obj(proteins?.human)),
    animal: protein(values.animal, obj(proteins?.animal)),
    tied: obj(values.parameters)?.alternative_optimal_alignment_exists === true,
    substitutions,
    functionalStatus: str(fa?.status),
    motif,
    invalidFields: invalid,
  };
}

/** One candidate relationship from an ambiguous Ensembl orthologue lookup. */
export interface OrthologueCandidate {
  type: string | null;
  targetGene: string | null;
  targetProtein: string | null;
}

/** Candidates from an unavailable-but-ambiguous sequence layer, or null. */
export function parseAmbiguousCandidates(layer: LayerResult): OrthologueCandidate[] | null {
  const o = layer.observations.find((x) => x.field === "ambiguous_candidates");
  if (!o) return null;
  try {
    return arr(JSON.parse(o.value)).map((c) => {
      const target = obj(obj(c)?.target);
      return { type: str(obj(c)?.type), targetGene: str(target?.id), targetProtein: str(target?.protein_id) };
    });
  } catch {
    return null;
  }
}

/** Format a percentage for display (raw precision stays in the JSON). */
export const pct = (v: number | undefined): string => (v === undefined ? "n/a" : `${v.toFixed(1)}%`);
