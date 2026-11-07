/**
 * Public entry point of the API layer.
 *
 * Components only ever call `submitAssessment()` from here. Whether that hits
 * the in-browser mock or the real FastAPI backend is decided by one env var,
 * so swapping data sources never requires touching UI code.
 */

import type { AssessmentRequest, Report } from "../types";
import { submitAssessmentHttp } from "./http";
import { submitAssessmentMock } from "./mock";

/**
 * Mock unless NEXT_PUBLIC_USE_MOCK is explicitly "false".
 * NEXT_PUBLIC_* vars are inlined into the browser bundle at build time, so a
 * dev-server restart is needed after changing it.
 */
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

/**
 * Run an assessment and resolve with a Report.
 * @param request  validated species + sequence from the form
 * @param signal   optional AbortSignal to cancel an in-flight request
 */
export function submitAssessment(
  request: AssessmentRequest,
  signal?: AbortSignal,
): Promise<Report> {
  return USE_MOCK
    ? submitAssessmentMock(request, signal)
    : submitAssessmentHttp(request, signal);
}
