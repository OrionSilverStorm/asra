/**
 * Real backend client: sends the assessment to FastAPI over HTTP.
 * Used when NEXT_PUBLIC_USE_MOCK=false (see ./index.ts).
 */

import type { AssessmentRequest, Report } from "../types";

/** Backend base URL; defaults to the local uvicorn server. */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Give up after this long. A gene run makes several Ensembl/UniProt calls
 * (30 s timeouts, retried on 5xx) plus up to three Gemini calls, so allow
 * well over a minute, but never leave the user on a spinner forever.
 */
const TIMEOUT_MS = 150_000;

/**
 * Extracts a readable message from an error response. FastAPI sends
 * `{"detail": "text"}` or, for validation errors (422),
 * `{"detail": [{"msg": "..."}, ...]}`.
 */
async function errorDetail(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const { detail } = JSON.parse(text);
    if (typeof detail === "string") return `: ${detail}`;
    if (Array.isArray(detail)) return `: ${detail.map((d: { msg: string }) => d.msg).join("; ")}`;
  } catch {
    // Not JSON: fall through to the raw text.
  }
  return text ? `: ${text}` : "";
}

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
  // Abort on whichever comes first: the caller cancelling, or the time limit.
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  try {
    res = await fetch(`${API_URL}/assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (err) {
    // Hit the time limit (not a user cancel): say so plainly.
    if (timeout.aborted && !signal?.aborted) {
      throw new Error(
        `The assessment took longer than ${TIMEOUT_MS / 60_000} minutes. The backend or an upstream database may be slow; try again.`,
      );
    }
    // A cancelled request is not an error worth showing; rethrow untouched.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    // fetch only throws on network failure (server down, CORS, DNS...).
    throw new Error(`Could not reach the ASRA backend at ${API_URL}.`);
  }

  // The server answered but with 4xx/5xx; include its message if any.
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}${await errorDetail(res)}`);
  }

  // Trust the backend to follow the contract in ../types.ts.
  return (await res.json()) as Report;
}
