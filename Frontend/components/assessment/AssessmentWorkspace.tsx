"use client";
// ^ Client Component: holds state and calls the API from the browser.

/**
 * AssessmentWorkspace: the "brain" of the home page.
 *
 * Runs a small state machine:
 *
 *   idle ──submit──▶ submitting ──ok──▶ success (show report)
 *                         │
 *                         └──fail──▶ error (form + alert)
 *
 * In idle/submitting/error it shows the form. In success it swaps the
 * whole area for the report. "New assessment" goes back to idle.
 */

import { useEffect, useRef, useState } from "react";
import { Container } from "@/components/layout/Container";
import { ReportView } from "@/components/report/ReportView";
import { Alert } from "@/components/ui/Alert";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { submitAssessment } from "@/lib/api";
import type { AssessmentRequest, Report } from "@/lib/types";
import { AssessmentForm } from "./AssessmentForm";

/**
 * A discriminated union: `status` says which state we're in, and TypeScript
 * knows `report` only exists in "success" and `message` only in "error".
 */
type State =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success"; report: Report }
  | { status: "error"; message: string };

export function AssessmentWorkspace() {
  const [state, setState] = useState<State>({ status: "idle" });

  // Controller for the in-flight request, so it can be cancelled.
  const abortRef = useRef<AbortController | null>(null);
  // Top of the workspace, used to scroll the new report into view.
  const topRef = useRef<HTMLDivElement>(null);

  // On unmount, cancel any pending request so it can't set state afterwards.
  useEffect(() => () => abortRef.current?.abort(), []);

  /** Called by the form with a validated request. */
  async function run(request: AssessmentRequest) {
    // Cancel a previous request if one is somehow still running.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ status: "submitting" });
    try {
      const report = await submitAssessment(request, controller.signal);
      setState({ status: "success", report });
      // The report replaces the form; scroll so its header is visible.
      topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      // Cancelled on purpose: stay quiet.
      if (controller.signal.aborted) return;
      setState({ status: "error", message: err instanceof Error ? err.message : "Unknown error." });
    }
  }

  return (
    // scroll-mt-4 leaves a little space above when scrolled into view.
    <div ref={topRef} className="scroll-mt-4">
      <Container className="py-6 sm:py-8">
        {/* Invisible live region: screen readers announce progress. */}
        <p className="sr-only" aria-live="polite">
          {state.status === "submitting" && "Running assessment."}
          {state.status === "success" && "Report ready."}
        </p>

        {state.status === "success" ? (
          // ── Report view ──
          <ReportView report={state.report} onReset={() => setState({ status: "idle" })} />
        ) : (
          // ── Form view: a single query panel, capped at a readable width ──
          // id="query" is the target of the header's "Query" nav link.
          <div className="max-w-3xl">
            <Card id="query">
              <CardHeader eyebrow="New assessment" title="Query" />
              <CardBody className="flex flex-col gap-4">
                {/* Error from the last attempt, shown above the form. */}
                {state.status === "error" && (
                  <Alert tone="danger" title="Assessment failed" role="alert">
                    {state.message}
                  </Alert>
                )}
                <AssessmentForm onSubmit={run} submitting={state.status === "submitting"} />
              </CardBody>
            </Card>
          </div>
        )}
      </Container>
    </div>
  );
}
