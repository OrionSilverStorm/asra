"""Single entry point for Gemini calls. Agents never touch the SDK directly.

The API key is read from Backend/.env (GEMINI_API_KEY), which is git-ignored.
If no key is set, `available()` is False and agents skip the model, so the
pipeline, tests and offline demos still work.
"""

import os
from functools import lru_cache
from typing import Optional, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

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
    from google import genai

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def ask_json(prompt: str, schema: type[T], agent: str) -> Optional[T]:
    """Ask Gemini for one JSON object shaped like `schema` and parse it.

    Structured output (response_schema) forces the model to return data in
    our shape instead of free text. Every prompt and response is logged
    (design doc: "log every prompt and response").
    """
    # Deferred import: importing anything under `pipeline` runs its __init__,
    # which imports the runner, which imports agents -> circular at load time.
    from pipeline.run_log import log_event

    response = _client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": list[schema]},
    )
    log_event("llm", {"agent": agent, "model": MODEL, "prompt": prompt, "response": response.text})
    parsed: Optional[list[T]] = response.parsed
    return parsed or []
