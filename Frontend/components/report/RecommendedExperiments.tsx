/**
 * RecommendedExperiments: numbered list of follow-up experiments the agents
 * suggest, or an empty state when there's no evidence to base them on.
 */

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "./EmptyState";

export function RecommendedExperiments({ items }: { items: string[] }) {
  return (
    <Card>
      <CardHeader eyebrow="Next steps" title="Recommended experiments" />
      <CardBody>
        {items.length ? (
          // Numbered list with muted numbers.
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm leading-6 marker:text-muted">
            {items.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ol>
        ) : (
          <EmptyState>No recommendations without evidence from the comparison layers.</EmptyState>
        )}
      </CardBody>
    </Card>
  );
}
