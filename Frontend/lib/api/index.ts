/**
 * Public entry point of the API layer.
 *
 * Components only ever call `submitAssessment()` from here. Whether that hits
 * the real FastAPI backend or the in-browser mock is decided by one env var,
 * so swapping data sources never requires touching UI code.
 */

import type { AssessmentRequest, Report } from "../types";
import { submitAssessmentHttp } from "./http";
import { submitAssessmentMock } from "./mock";

/**
 * Live backend unless NEXT_PUBLIC_USE_MOCK is explicitly "true" (useful for
 * UI work without running Python). NEXT_PUBLIC_* vars are inlined at build
 * time, so restart the dev server after changing it.
 */
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

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
