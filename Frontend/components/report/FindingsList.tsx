/**
 * FindingsList: card listing every finding, or an explicit empty state.
 * An empty list is expected when no layer returned evidence.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import type { Finding } from "@/lib/types";
import { EmptyState } from "./EmptyState";
import { FindingCard } from "./FindingCard";

export function FindingsList({ findings }: { findings: Finding[] }) {
  return (
    <Card>
      <CardHeader eyebrow="Interpretation" title="Findings" />
      <CardBody className="flex flex-col gap-4">
        {findings.length ? (
          findings.map((f) => <FindingCard key={f.id} finding={f} />)
        ) : (
          // Explain WHY it's empty rather than leaving a blank card.
          <EmptyState>
            No findings. Findings appear only when a layer returns evidence the agents can cite.
          </EmptyState>
        )}
      </CardBody>
    </Card>
  );
}
