/**
 * DownloadButtons: one button per export format (JSON, Markdown, PDF).
 *
 * The buttons are generated from EXPORT_FORMATS, so adding a format in
 * lib/export.ts adds its button here automatically. All file-building
 * logic lives in lib/export.ts; this component only wires up clicks.
 */

import { Button } from "@/components/ui/Button";
import { downloadReport, EXPORT_FORMATS, type ExportFormat } from "@/lib/export";
import type { Report } from "@/lib/types";

/** Small download-arrow icon (decorative). */
function DownloadIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M8 2v8m0 0L5 7m3 3 3-3M3 13h10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function DownloadButtons({ report }: { report: Report }) {
  // Object.keys loses the literal type, so cast back to ExportFormat[].
  const formats = Object.keys(EXPORT_FORMATS) as ExportFormat[];
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Download report">
      {formats.map((format) => (
        <Button key={format} variant="secondary" onClick={() => downloadReport(report, format)}>
          <DownloadIcon />
          {EXPORT_FORMATS[format].label}
        </Button>
      ))}
    </div>
  );
}
