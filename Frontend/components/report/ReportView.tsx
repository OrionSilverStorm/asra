/**
 * ReportView: assembles the full report from its sections.
 *
 * Purely compositional: header + caveat on top, then an entry-page layout
 * (AlphaFold DB / UniProt style) with a sticky "On this page" nav on the
 * left and the sections on the right. To add, remove or reorder a section,
 * edit the `sections` list; the nav is generated from it.
 */

import type { ReactNode } from "react";
import { getSpecies } from "@/lib/species";
import type { Report } from "@/lib/types";
import { CaveatBanner } from "./CaveatBanner";
import { FindingsList } from "./FindingsList";
import { LayerGrid } from "./LayerGrid";
import { Limitations } from "./Limitations";
import { RecommendedExperiments } from "./RecommendedExperiments";
import { ReportHeader } from "./ReportHeader";
import { ReportSummary } from "./ReportSummary";
import { SectionNav } from "./SectionNav";
import { SequenceSummary } from "./SequenceSummary";
import { SourcesTable } from "./SourcesTable";

interface ReportViewProps {
  report: Report;
  /** Passed down to the header's "New assessment" button. */
  onReset: () => void;
}

export function ReportView({ report, onReset }: ReportViewProps) {
  // Ordered sections: anchor id, nav label, content. Limitations is left
  // out when empty so the nav never links to nothing.
  const sections: { id: string; label: string; node: ReactNode }[] = [
    // Counts at a glance: coverage, findings, sources
    { id: "summary", label: "Summary", node: <ReportSummary report={report} /> },
    // Real stats from the input sequence
    { id: "sequence", label: "Sequence", node: <SequenceSummary stats={report.sequenceStats} sequence={report.request.sequence} /> },
    // The four evidence layers
    { id: "evidence", label: "Evidence layers", node: <LayerGrid layers={report.layers} speciesName={getSpecies(report.request.species).commonName} /> },
    // Agent findings, each with a citation
    { id: "findings", label: "Findings", node: <FindingsList findings={report.findings} layers={report.layers} /> },
    // Suggested follow-up work
    { id: "experiments", label: "Experiments", node: <RecommendedExperiments items={report.recommendedExperiments} /> },
    // Every source record and what cites it
    { id: "sources", label: "Sources", node: <SourcesTable layers={report.layers} findings={report.findings} /> },
    // Report-wide caveats
    ...(report.limitations.length
      ? [{ id: "limitations", label: "Limitations", node: <Limitations items={report.limitations} /> }]
      : []),
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* What was compared, when, mock vs live */}
      <ReportHeader report={report} onReset={onReset} />
      {/* Mandatory caveat, prominent at the top of every report */}
      <CaveatBanner />
      {/* Nav column from `lg` up; single column below. */}
      <div className="grid gap-6 lg:grid-cols-[160px_minmax(0,1fr)]">
        <SectionNav sections={sections} />
        <div className="flex min-w-0 flex-col gap-5">
          {sections.map((s) => (
            // Anchor target; scroll-mt-4 leaves a gap above when jumped to.
            <div key={s.id} id={s.id} className="scroll-mt-4">
              {s.node}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
