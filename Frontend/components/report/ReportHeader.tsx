/**
 * ReportHeader: entry header of the report, styled like an AlphaFold DB /
 * UniProt entry: a mono entry ID, the comparison as the title, and the
 * metadata as a compact key/value table.
 *
 * Also holds a "Human ⟷ <species>" banner (names and taxonomic group only,
 * no distances), the download buttons and a button to start over.
 */

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { getSpecies } from "@/lib/species";
import type { Report } from "@/lib/types";
import { DownloadButtons } from "./DownloadButtons";
import { Silhouette, type SilhouetteKind } from "./Silhouette";

interface ReportHeaderProps {
  report: Report;
  /** Returns the workspace to the empty form. */
  onReset: () => void;
}

/** One side of the comparison banner: figure, common and Latin name, group. */
function Organism({ kind, name, latin, group }: { kind: SilhouetteKind; name: string; latin: string; group: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="text-accent">
        <Silhouette kind={kind} />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="truncate font-semibold">{name}</p>
        {/* Latin names are conventionally italicised. */}
        <p className="truncate text-xs italic text-muted">{latin}</p>
        <p className="text-[11px] text-muted">{group}</p>
      </div>
    </div>
  );
}

export function ReportHeader({ report, onReset }: ReportHeaderProps) {
  const species = getSpecies(report.request.species);

  // Format the ISO timestamp in the viewer's locale, e.g. "7 Nov 2026, 14:32".
  const generated = new Date(report.generatedAt).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  // Short, readable entry ID from the report UUID, e.g. "ASRA-3f2a9c1b".
  const entryId = `ASRA-${report.id.replace(/-/g, "").slice(0, 8)}`;

  // Metadata rows; the sequence row only appears if a FASTA header was pasted.
  const rows: { label: string; value: string; className?: string }[] = [
    { label: "Species", value: species.scientificName, className: "italic" },
    ...(report.request.sequenceLabel
      ? [{ label: "Sequence", value: report.request.sequenceLabel, className: "font-mono text-[13px]" }]
      : []),
    { label: "Generated", value: generated },
  ];

  return (
    <header className="rounded border border-rule bg-surface px-4 py-4 sm:px-5">
      {/* Stacked on phones; details left, banner + actions right from `md` up. */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          {/* Entry ID + origin. Mock must be impossible to mistake for real results. */}
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className="rounded-sm bg-accent-soft px-1.5 py-0.5 font-mono text-xs font-medium text-accent">{entryId}</span>
            {/* Fixture reports must never read as a live retrieval. */}
            {report.origin === "mock" ? (
              <Badge tone="warn">Mock data · backend not connected</Badge>
            ) : report.origin === "fixture" ? (
              <Badge tone="warn">Demo fixture data · not a live retrieval</Badge>
            ) : (
              <Badge tone="ok">Live</Badge>
            )}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Human vs {species.commonName.toLowerCase()}
          </h1>

          {/* Metadata as a two-column key/value table. */}
          <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1 text-sm">
            {rows.map((r) => (
              <div key={r.label} className="contents">
                <dt className="text-muted">{r.label}</dt>
                {/* truncate: long FASTA headers get an ellipsis instead of overflowing. */}
                <dd className={`truncate ${r.className ?? ""}`}>{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="flex flex-col gap-3 md:items-end">
          {/* Comparison banner: who is compared with whom. */}
          <div className="flex items-center gap-3 self-start rounded border border-rule bg-sunken px-3 py-2 md:self-end">
            <Organism kind="Human" name="Human" latin="Homo sapiens" group="Reference" />
            {/* Double arrow: the two organisms being compared. */}
            <span aria-label="compared with" className="text-lg text-muted">⟷</span>
            <Organism kind={species.group} name={species.commonName} latin={species.scientificName} group={species.group} />
          </div>
          {/* Actions: downloads + start over. Hidden in print/PDF since
              buttons are useless on paper. */}
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <DownloadButtons report={report} />
            <Button onClick={onReset}>New assessment</Button>
          </div>
        </div>
      </div>
    </header>
  );
}
