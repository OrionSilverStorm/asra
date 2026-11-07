"""Single entry point for Gemini calls. Agents never touch the SDK directly.

The API key is read from Backend/.env (GEMINI_API_KEY), which is git-ignored.
If no key is set, `available()` is False and agents skip the model, so the
pipeline, tests and offline demos still work.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Optional, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

log = logging.getLogger("asra.llm")

# Load Backend/.env into os.environ (no-op if the file doesn't exist).
load_dotenv()

# Override in .env if Google renames or you want a different model.
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

T = TypeVar("T", bound=BaseModel)


def available() -> bool:
    """True when a Gemini key is configured."""
    return bool(os.getenv("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def _client():
    """Create the SDK client once, on first use (import is deferred so the
    package isn't needed when no key is set)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    from google import genai

    return genai.Client(api_key=api_key)


def ask_json(prompt: str, schema: type[T], agent: str) -> list[T]:
    """Ask Gemini for a JSON list of `schema` objects and parse it.

    Structured output (response_schema) forces the model to return data in
    our shape instead of free text. Every prompt and response is logged
    (design doc: "log every prompt and response").

    Failure containment:
    - If the API key is missing, returns [] without calling Gemini.
    - If quota is exceeded, network times out, or the API fails, logs the error
      and raises so the caller (Interpreter) can catch it and return [] without
      inventing findings.
    - If response parsing encounters formatting anomalies, attempts robust JSON
      fallback before failing.
    """
    # Deferred import to prevent circular imports with pipeline package
    from pipeline.run_log import log_event

    if not available():
        log.warning("GEMINI_API_KEY not configured; skipping LLM call")
        return []

    try:
        response = _client().models.generate_content(
            model=MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": list[schema],
            },
        )
    except Exception as exc:
        log.error("Gemini API call failed for %s: %s", agent, exc)
        log_event(
            "llm_error",
            {"agent": agent, "model": MODEL, "error": str(exc)},
        )
        raise

    response_text = getattr(response, "text", "") or ""
    log_event(
        "llm",
        {
            "agent": agent,
            "model": MODEL,
            "prompt": prompt,
            "response": response_text,
        },
    )

    # 1. Primary: use the SDK's built-in pydantic parsing
    parsed: Optional[list[T]] = getattr(response, "parsed", None)
    if parsed is not None:
        return parsed

    # 2. Fallback: if response.parsed was None, attempt manual JSON extraction
    if response_text.strip():
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", response_text.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            raw_data = json.loads(cleaned)
            if isinstance(raw_data, list):
                return [
                    schema(**item)
                    for item in raw_data
                    if isinstance(item, dict)
                ]
            elif isinstance(raw_data, dict):
                return [schema(**raw_data)]
        except Exception as parse_exc:
            log.warning("Fallback JSON parsing failed for %s: %s", agent, parse_exc)

    return []
