/**
 * Report export: turns a Report into downloadable files.
 *
 * Three formats:
 * - JSON: the exact Report object, for archiving or feeding into other tools
 * - Markdown: a human-readable document (opens in any editor, renders on GitHub)
 * - PDF: the on-screen report via the browser's print dialog ("Save as PDF").
 *   Print-specific styling (hidden buttons, light colours, no awkward page
 *   breaks) lives in app/globals.css and the `print:` Tailwind classes.
 *
 * Every export carries the caveat, as the design doc requires.
 * These are pure functions apart from `downloadFile` and `printReport`,
 * which touch the DOM.
 */

import { CAVEAT_TEXT } from "./caveat";
import { LAYER_META } from "./layers";
import { parseSequenceEvidence, pct, type SequenceEvidence } from "./sequenceEvidence";
import { getSpecies } from "./species";
import type { Concern, LayerStatus, Report } from "./types";

/**
 * Readable Markdown for the gene-based sequence layer, in place of its raw
 * JSON observations (the JSON export keeps those in full).
 */
function sequenceMarkdown(e: SequenceEvidence, species: string): string[] {
  const m = e.measurements;
  const annotated = e.substitutions.filter((s) => s.annotated);
  const lines = [
    `- **Identity:** ${pct(m.identity_percent)} (${m.exact_matches ?? "?"}/${m.alignment_columns ?? "?"} columns) · paired identity ${pct(m.paired_identity_percent)}`,
    `- **Coverage:** human ${pct(m.human_coverage_percent)} · ${species} ${pct(m.animal_coverage_percent)}`,
    `- **Lengths:** human ${m.human_length ?? "?"} aa · ${species} ${m.animal_length ?? "?"} aa`,
    `- **Gaps:** ${m.insertion_events ?? 0} insertion (${m.inserted_residues ?? 0} aa), ${m.deletion_events ?? 0} deletion (${m.deleted_residues ?? 0} aa)`,
    `- **Proteins:** human ${e.human.isoform ?? e.human.accession ?? "?"} / ${e.human.proteinId ?? "?"} · ${species} ${e.animal.isoform ?? e.animal.accession ?? "?"} / ${e.animal.proteinId ?? "?"}`,
  ];
  if (e.tied) lines.push("- **Tied optimal alignments:** residue mappings may shift between equally good alignments.");
  if (e.functionalStatus) lines.push(`- **UniProt annotation:** ${e.functionalStatus}`);
  if (e.motif) {
    lines.push(`- **Motif check:** human ${e.motif.humanWindow} vs ${species} ${e.motif.animalWindow ?? "not contiguous"}${e.motif.pattern ? ` (published pattern ${e.motif.pattern})` : ""}`);
  }
  lines.push(
    `- **Substitutions (${e.substitutions.length}, ${annotated.length} overlap annotated features):** ${e.substitutions.map((s) => (s.annotated ? `**${s.label}**` : s.label)).join(", ") || "none"}`,
    "",
  );
  return lines;
}

/** Supported export formats and their file details. */
export const EXPORT_FORMATS = {
  json: { label: "JSON", extension: "json", mime: "application/json" },
  markdown: { label: "Markdown", extension: "md", mime: "text/markdown" },
  pdf: { label: "PDF", extension: "pdf", mime: "application/pdf" },
} as const;

export type ExportFormat = keyof typeof EXPORT_FORMATS;

/** Formats we build as text in JS (PDF is produced by the browser instead). */
type TextFormat = Exclude<ExportFormat, "pdf">;

/** Human-readable labels, mirroring the on-screen badges. */
const STATUS_LABEL: Record<LayerStatus, string> = {
  ok: "Complete",
  incomplete: "Incomplete",
  unavailable: "Unavailable",
};
const CONCERN_LABEL: Record<Concern, string> = {
  high: "High concern",
  moderate: "Moderate concern",
  low: "Low concern",
  flagged: "Flagged (incomplete data)",
};

/**
 * Builds a descriptive file name, e.g.
 * "asra-report-mus_musculus-2026-11-07.md"
 */
export function reportFilename(report: Report, format: ExportFormat): string {
  const date = report.generatedAt.slice(0, 10); // YYYY-MM-DD from the ISO string
  return `asra-report-${report.request.species}-${date}.${EXPORT_FORMATS[format].extension}`;
}

/**
 * JSON export: the report plus the caveat as a top-level field, so the
 * warning travels with the data even when read by a machine.
 */
export function reportToJson(report: Report): string {
  return JSON.stringify({ caveat: CAVEAT_TEXT, ...report }, null, 2);
}

/** Markdown export: a readable version of everything shown on screen. */
export function reportToMarkdown(report: Report): string {
  const species = getSpecies(report.request.species);
  const { sequenceStats: stats } = report;

  // Build the document as an array of lines, then join once at the end.
  const lines: string[] = [];
  const push = (...l: string[]) => lines.push(...l);

  // ── Title + metadata ──
  push(`# ASRA report: human vs ${species.commonName.toLowerCase()}`, "");
  push(`> **Caveat.** ${CAVEAT_TEXT}`, "");
  if (report.origin === "mock") {
    push("> **Mock data.** Generated without the ASRA backend; only sequence statistics are real.", "");
  }
  if (report.origin === "fixture") {
    push("> **Demo fixture data.** At least one layer used hand-entered demo evidence, not a live retrieval.", "");
  }
  push(
    `- **Species:** ${species.commonName} (*${species.scientificName}*)`,
    `- **Sequence:** ${report.request.sequenceLabel ?? "unlabelled"}`,
    `- **Generated:** ${report.generatedAt}`,
    `- **Report ID:** ${report.id}`,
    "",
  );

  // ── Sequence summary ──
  push("## Sequence summary", "");
  push(`- Length: ${stats.length} aa`, `- Estimated mass: ${stats.estimatedMassKDa.toFixed(1)} kDa`, "");
  push("| Residue | Fraction |", "|---|---|");
  for (const { residue, fraction } of stats.composition) {
    push(`| ${residue} | ${(fraction * 100).toFixed(1)}% |`);
  }
  push("");
  // Full sequence in a code block so it isn't reflowed by Markdown renderers.
  push("```", report.request.sequence, "```", "");

  // ── Layers ──
  push("## Comparison layers", "");
  for (const layer of report.layers) {
    const meta = LAYER_META[layer.layer];
    push(`### ${meta.title} — ${STATUS_LABEL[layer.status]}`, "", `Source: ${meta.source}`, "");
    // Gene-based sequence evidence gets a readable summary instead of JSON rows.
    const evidence = parseSequenceEvidence(layer);
    if (evidence) {
      push(...sequenceMarkdown(evidence, species.commonName.toLowerCase()));
    } else if (layer.observations.length) {
      push("| Field | Value |", "|---|---|");
      for (const o of layer.observations) push(`| ${o.field} | ${o.value} |`);
      push("");
    } else {
      push("No observations returned.", "");
    }
    for (const l of layer.limitations) push(`- _${l}_`);
    if (layer.limitations.length) push("");
  }

  // ── Findings ──
  push("## Findings", "");
  if (report.findings.length) {
    for (const f of report.findings) {
      push(`### ${f.claim}`, "", `**${CONCERN_LABEL[f.concern]}**`, "", f.mechanism, "");
      if (f.scepticNote) push(`> **Sceptic:** ${f.scepticNote}`, "");
      push(`Cited field: \`${f.citedField}\` · Source: \`${f.sourceRecordId}\``, "");
    }
  } else {
    push("No findings. Findings appear only when a layer returns evidence the agents can cite.", "");
  }

  // ── Recommended experiments ──
  push("## Recommended experiments", "");
  if (report.recommendedExperiments.length) {
    report.recommendedExperiments.forEach((x, i) => push(`${i + 1}. ${x}`));
    push("");
  } else {
    push("No recommendations without evidence from the comparison layers.", "");
  }

  // ── Limitations ──
  if (report.limitations.length) {
    push("## Limitations", "");
    for (const l of report.limitations) push(`- ${l}`);
    push("");
  }

  return lines.join("\n");
}

/** Serialises a report in the requested text format. */
export function serialiseReport(report: Report, format: TextFormat): string {
  return format === "json" ? reportToJson(report) : reportToMarkdown(report);
}

/**
 * Triggers a browser download of `content` as a file.
 * Works by creating a temporary object URL and clicking a hidden <a download>.
 */
export function downloadFile(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Free the memory once the browser has started the download.
  URL.revokeObjectURL(url);
}

/**
 * PDF export: opens the browser's print dialog on the current page, where the
 * user picks "Save as PDF".
 *
 * Browsers use document.title as the default PDF file name, so the title is
 * temporarily set to the report file name (minus ".pdf") and restored once
 * the dialog closes.
 */
export function printReport(report: Report): void {
  const originalTitle = document.title;
  document.title = reportFilename(report, "pdf").replace(/\.pdf$/, "");
  // "afterprint" fires when the dialog closes (saved or cancelled).
  window.addEventListener("afterprint", () => (document.title = originalTitle), { once: true });
  window.print();
}

/** Convenience: export a report in any format with one call. */
export function downloadReport(report: Report, format: ExportFormat): void {
  if (format === "pdf") {
    printReport(report);
    return;
  }
  downloadFile(reportFilename(report, format), serialiseReport(report, format), EXPORT_FORMATS[format].mime);
}
