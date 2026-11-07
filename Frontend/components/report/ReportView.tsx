/**
 * ReportView: assembles the full report from its sections.
 *
 * Purely compositional: no logic, just order. To add, remove or reorder a
 * report section, edit the list below; each section is its own component.
 */

import type { Report } from "@/lib/types";
import { CaveatBanner } from "./CaveatBanner";
import { FindingsList } from "./FindingsList";
import { LayerGrid } from "./LayerGrid";
import { Limitations } from "./Limitations";
import { RecommendedExperiments } from "./RecommendedExperiments";
import { ReportHeader } from "./ReportHeader";
import { SequenceSummary } from "./SequenceSummary";

interface ReportViewProps {
  report: Report;
  /** Passed down to the header's "New assessment" button. */
  onReset: () => void;
}

export function ReportView({ report, onReset }: ReportViewProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* 1. What was compared, when, mock vs live */}
      <ReportHeader report={report} onReset={onReset} />
      {/* 2. Mandatory caveat, prominent at the top of every report */}
      <CaveatBanner />
      {/* 3. Real stats from the input sequence */}
      <SequenceSummary stats={report.sequenceStats} />
      {/* 4. The four evidence layers */}
      <LayerGrid layers={report.layers} />
      {/* 5. Agent findings, each with a citation */}
      <FindingsList findings={report.findings} />
      {/* 6. Suggested follow-up work */}
      <RecommendedExperiments items={report.recommendedExperiments} />
      {/* 7. Report-wide caveats */}
      <Limitations items={report.limitations} />
    </div>
  );
}
