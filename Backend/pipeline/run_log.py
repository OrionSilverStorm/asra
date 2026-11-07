"""Append-only run log (design doc: "log every prompt and response").

Each assessment is written as one JSON line to data/logs/runs.jsonl, so you
can show exactly what went in and what came out. Agent prompts/responses
should be logged through `log_event` too once the LLM is wired in.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# Backend/data/logs, resolved relative to this file so the CWD doesn't matter.
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "logs" / "runs.jsonl"


def log_event(kind: str, payload: dict) -> None:
    """Write one timestamped event. Logging must never break a request."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # e.g. read-only disk; the report is still returned
