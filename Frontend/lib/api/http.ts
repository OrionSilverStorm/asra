/**
 * Real backend client: sends the assessment to FastAPI over HTTP.
 * Used when NEXT_PUBLIC_USE_MOCK=false (see ./index.ts).
 */

import type { AssessmentRequest, Report } from "../types";

/** Backend base URL; defaults to the local uvicorn server. */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Calls the FastAPI backend. Expects POST /assess to return a Report.
 * Network and HTTP errors are turned into readable Error messages that the
 * workspace shows in an alert.
 */
export async function submitAssessmentHttp(
  request: AssessmentRequest,
  signal?: AbortSignal,
): Promise<Report> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal, // lets the caller cancel (e.g. user submits again)
    });
  } catch (err) {
    // A cancelled request is not an error worth showing; rethrow untouched.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    // fetch only throws on network failure (server down, CORS, DNS...).
    throw new Error(`Could not reach the ASRA backend at ${API_URL}.`);
  }

  // The server answered but with 4xx/5xx; include its message if any.
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend returned ${res.status}${detail ? `: ${detail}` : ""}`);
  }

  // Trust the backend to follow the contract in ../types.ts.
  return (await res.json()) as Report;
}
