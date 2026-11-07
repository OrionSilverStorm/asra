/**
 * ReportSummary: "At a glance" row of stat tiles at the top of the report:
 * evidence coverage, findings by concern, Sceptic-qualified findings,
 * experiments and source records. Every value is a count read straight
 * from the report; nothing is scored or combined.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { STATUS } from "@/components/ui/StatusBadge";
import { StatTile } from "@/components/ui/StatTile";
import { LAYER_META } from "@/lib/layers";
import { collectSources } from "@/lib/sources";
import type { Report } from "@/lib/types";
import { ConcernBar } from "./ConcernBar";

export function ReportSummary({ report }: { report: Report }) {
  const { layers, findings } = report;
  // Layers that ran with full data.
  const complete = layers.filter((l) => l.status === "ok").length;
  // Findings the Sceptic commented on (downgraded or qualified).
  const qualified = findings.filter((f) => f.scepticNote).length;
  const sources = collectSources(layers, findings);

  return (
    <Card>
      <CardHeader eyebrow="Summary" title="At a glance" />
      {/* 2 columns on phones, 3 on tablets, all 5 in a row on desktop. */}
      <CardBody className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile label="Evidence" value={`${complete}/${layers.length}`}>
          {/* Mini status track, one cell per layer (titles in tooltips). */}
          <span className="grid grid-cols-4 gap-0.5">
            {layers.map((l) => (
              <span
                key={l.layer}
                title={`${LAYER_META[l.layer].title}: ${STATUS[l.status].label}`}
                className={`h-1.5 rounded-sm ${STATUS[l.status].fill}`}
              />
            ))}
          </span>
          <span className="text-xs text-muted">layers complete</span>
        </StatTile>
        <StatTile label="Findings" value={findings.length}>
          <ConcernBar findings={findings} />
        </StatTile>
        <StatTile label="Sceptic-qualified" value={qualified}>
          <span className="text-xs text-muted">findings with a Sceptic note</span>
        </StatTile>
        <StatTile label="Experiments" value={report.recommendedExperiments.length}>
          <span className="text-xs text-muted">suggested follow-ups</span>
        </StatTile>
        <StatTile label="Sources" value={sources.length}>
          <span className="text-xs text-muted">unique source records</span>
        </StatTile>
      </CardBody>
    </Card>
  );
}
