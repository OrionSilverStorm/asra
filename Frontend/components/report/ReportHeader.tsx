/**
 * ReportHeader: title block of the report.
 *
 * Shows which comparison this is (human vs <species>), the sequence label,
 * when it was generated, whether the data is mock or live, download
 * buttons, and a button to start over.
 */

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DownloadButtons } from "./DownloadButtons";
import { getSpecies } from "@/lib/species";
import type { Report } from "@/lib/types";

interface ReportHeaderProps {
  report: Report;
  /** Returns the workspace to the empty form. */
  onReset: () => void;
}

export function ReportHeader({ report, onReset }: ReportHeaderProps) {
  const species = getSpecies(report.request.species);

  // Format the ISO timestamp in the viewer's locale, e.g. "7 Nov 2026, 14:32".
  const generated = new Date(report.generatedAt).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    // Stacked on phones; title left, button right from `sm` up.
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted">Assessment report</p>
          {/* Make it impossible to mistake mock output for real results. */}
          {report.origin === "mock" ? (
            <Badge tone="warn">Mock data · backend not connected</Badge>
          ) : (
            <Badge tone="accent">Live</Badge>
          )}
        </div>
        <h1 className="font-serif text-2xl font-semibold tracking-tight sm:text-3xl">
          Human vs {species.commonName.toLowerCase()}
        </h1>

        {/* Metadata row as a description list. */}
        <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
          <div className="flex gap-1.5">
            <dt>Species</dt>
            {/* Latin names are conventionally italicised. */}
            <dd className="italic text-ink">{species.scientificName}</dd>
          </div>
          {/* Only shown if the user pasted a FASTA header. */}
          {report.request.sequenceLabel && (
            <div className="flex min-w-0 gap-1.5">
              <dt>Sequence</dt>
              {/* truncate: long FASTA headers get an ellipsis instead of overflowing. */}
              <dd className="truncate font-mono text-ink">{report.request.sequenceLabel}</dd>
            </div>
          )}
          <div className="flex gap-1.5">
            <dt>Generated</dt>
            <dd className="text-ink">{generated}</dd>
          </div>
        </dl>
      </div>
      {/* Actions: downloads + start over. Wrap onto a new line on narrow
          screens; hidden in print/PDF since buttons are useless on paper. */}
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <DownloadButtons report={report} />
        <Button onClick={onReset}>New assessment</Button>
      </div>
    </header>
  );
}
