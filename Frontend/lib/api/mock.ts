/**
 * In-browser stand-in for the backend, used until POST /assess exists.
 *
 * It deliberately invents nothing: the only real numbers are the sequence
 * statistics computed from the user's input. Every layer is "unavailable",
 * which also lets you see how the UI handles missing data.
 */

import { LAYER_ORDER } from "../layers";
import { computeStats } from "../sequence";
import type { AssessmentRequest, LayerResult, Report } from "../types";

/** Artificial latency so the loading state is visible, like a real request. */
const MOCK_DELAY_MS = 900;

/**
 * Promise-based sleep that rejects with an AbortError if cancelled,
 * matching how fetch() behaves when its signal aborts.
 */
function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

/**
 * Stand-in for the backend. Only the sequence statistics are real (computed
 * from the input). No layer has run, so every layer is "unavailable" and there
 * are no findings — nothing is invented.
 */
export async function submitAssessmentMock(
  request: AssessmentRequest,
  signal?: AbortSignal,
): Promise<Report> {
  await wait(MOCK_DELAY_MS, signal);

  // One placeholder LayerResult per layer, following the contract shape.
  const layers: LayerResult[] = LAYER_ORDER.map((layer) => ({
    gene: null,
    species: request.species,
    layer,
    status: "unavailable",
    observations: [],
    source_records: [],
    limitations: ["Backend not connected — this layer has not been run."],
    data_version: null,
  }));

  return {
    id: crypto.randomUUID(),
    generatedAt: new Date().toISOString(),
    origin: "mock", // drives the "Mock data" badge in the report header
    request,
    sequenceStats: computeStats(request.sequence),
    layers,
    findings: [], // no evidence -> no findings
    recommendedExperiments: [],
    limitations: [
      "Generated in the browser without the ASRA backend. Only the sequence statistics are computed from your input.",
      "Connect the backend (NEXT_PUBLIC_USE_MOCK=false) to run the comparison layers and agents.",
    ],
  };
}
