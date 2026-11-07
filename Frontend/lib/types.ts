/**
 * Shared TypeScript types for the whole frontend.
 *
 * This file is the single source of truth for data shapes. Components, the
 * mock, and the HTTP client all import from here, so if the backend's
 * response format changes, this is the one file to update.
 *
 * `LayerResult` mirrors the JSON contract from the ASRA design doc exactly
 * (including snake_case field names), so the mock and the real FastAPI
 * response are interchangeable.
 */

/**
 * Machine IDs for the comparison species. They follow Ensembl's naming
 * convention (lowercase genus_species), which is what the backend will use
 * when it queries Ensembl / UniProt.
 */
export type SpeciesId =
  | "mus_musculus"
  | "rattus_norvegicus"
  | "macaca_mulatta"
  | "macaca_fascicularis"
  | "canis_lupus_familiaris"
  | "sus_scrofa"
  | "oryctolagus_cuniculus"
  | "cavia_porcellus"
  | "danio_rerio";

/** A species as shown in the dropdown. */
export interface Species {
  id: SpeciesId;
  /** Human-friendly name, e.g. "Mouse". */
  commonName: string;
  /** Latin binomial, e.g. "Mus musculus" (rendered in italics). */
  scientificName: string;
  /** Used to group options in the <select> via <optgroup>. */
  group: "Rodent" | "Non-human primate" | "Non-rodent mammal" | "Other";
}

/** What the form sends to the backend (or the mock). */
export interface AssessmentRequest {
  species: SpeciesId;
  /** Normalised amino-acid sequence (uppercase, no whitespace, no header). */
  sequence: string;
  /** FASTA header without the leading ">", if one was supplied. */
  sequenceLabel: string | null;
}

/** The four evidence layers from the design doc. */
export type LayerName =
  | "sequence"
  | "localisation"
  | "cell_expression"
  | "tissue_expression";

/**
 * Status of a layer, per the design doc contract:
 * - ok: the layer ran and returned data
 * - incomplete: it ran but data is partial (e.g. missing annotation)
 * - unavailable: it did not run / failed; nothing is shown as if it were real
 */
export type LayerStatus = "ok" | "incomplete" | "unavailable";

/** A citation: where a piece of evidence came from. */
export interface SourceRecord {
  /** Stable ID, e.g. a UniProt accession or dataset ID. */
  id: string;
  /** Database or publication name, e.g. "UniProt". */
  source: string;
  /** Optional link to the record (the backend sends null when absent). */
  url?: string | null;
}

/** One measured fact inside a layer, e.g. field "global_identity", value "85%". */
export interface Observation {
  field: string;
  value: string;
  /** Points at a SourceRecord.id so every value is traceable. */
  sourceRecordId?: string;
}

/** The contract every layer returns (see design doc, "The contract"). */
export interface LayerResult {
  gene: string | null;
  species: SpeciesId;
  layer: LayerName;
  status: LayerStatus;
  observations: Observation[];
  source_records: SourceRecord[];
  /** Human-readable caveats about this layer's data. */
  limitations: string[];
  /** Version / release of the data source, if known. */
  data_version: string | null;
}

/**
 * Qualitative level of concern an agent attaches to a finding.
 * Deliberately not a number: the design doc forbids numeric risk scores.
 * "flagged" = the claim rests on incomplete data and must not be ranked high.
 */
export type Concern = "high" | "moderate" | "low" | "flagged";

/** A claim produced by the agents, always tied back to evidence. */
export interface Finding {
  id: string;
  /** One-sentence statement of the difference found. */
  claim: string;
  /** The Interpreter's explanation of why it might matter. */
  mechanism: string;
  concern: Concern;
  /** "<layer>.<field>" the claim rests on. */
  citedField: string;
  /** The SourceRecord.id backing the claim (no claim without a source). */
  sourceRecordId: string;
  /** Optional comment from the Sceptic agent. */
  scepticNote?: string;
}

/** Simple statistics computed directly from the submitted sequence. */
export interface SequenceStats {
  /** Number of residues. */
  length: number;
  /** Approximate molecular mass in kilodaltons. */
  estimatedMassKDa: number;
  /** Fraction of each residue, sorted most common first. */
  composition: { residue: string; fraction: number }[];
}

/**
 * Where a report's data came from: the real backend ("live"), the backend
 * with hand-entered demo fixtures in any layer ("fixture"), or the
 * in-browser mock ("mock").
 */
export type DataOrigin = "mock" | "live" | "fixture";

/** The full report rendered by <ReportView>. */
export interface Report {
  id: string;
  /** ISO timestamp of generation. */
  generatedAt: string;
  origin: DataOrigin;
  /** Echo of the request, so the report is self-describing. */
  request: AssessmentRequest;
  sequenceStats: SequenceStats;
  layers: LayerResult[];
  findings: Finding[];
  recommendedExperiments: string[];
  /** Report-wide caveats (in addition to per-layer limitations). */
  limitations: string[];
}
