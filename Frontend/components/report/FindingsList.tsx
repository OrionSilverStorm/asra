/**
 * FindingsList: card listing every finding, or an explicit empty state.
 * An empty list is expected when no layer returned evidence.
 *
 * With findings, an overview comes first: the concern distribution and the
 * evidence matrix (which layer each finding cites). The header carries a
 * concern-level key so the colours explain themselves.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Legend } from "@/components/ui/Legend";
import type { Finding, LayerResult } from "@/lib/types";
import { ConcernBar } from "./ConcernBar";
import { EmptyState } from "./EmptyState";
import { EvidenceMatrix } from "./EvidenceMatrix";
import { CONCERN, FindingCard } from "./FindingCard";

/** Legend entries, one per concern level, built from the shared map. */
const CONCERN_KEY = Object.values(CONCERN).map((c) => ({ label: c.label, swatch: c.fill }));

interface FindingsListProps {
  findings: Finding[];
  /** Needed by the evidence matrix (columns + status). */
  layers: LayerResult[];
}

export function FindingsList({ findings, layers }: FindingsListProps) {
  return (
    <Card>
      <CardHeader
        eyebrow="Interpretation"
        title="Findings"
        // Key only matters when there are findings to colour.
        actions={findings.length > 0 && <Legend label="Concern key" items={CONCERN_KEY} />}
      />
      <CardBody className="flex flex-col gap-3">
        {findings.length ? (
          <>
            {/* Overview: distribution, then the findings × layers matrix. */}
            <ConcernBar findings={findings} />
            <EvidenceMatrix findings={findings} layers={layers} />
            {findings.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </>
        ) : (
          // Explain WHY it's empty rather than leaving a blank card.
          <EmptyState icon="findings" hint="Each finding must cite an observation from a layer that ran.">
            No findings yet.
          </EmptyState>
        )}
      </CardBody>
    </Card>
  );
}
