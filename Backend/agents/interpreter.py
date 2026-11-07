"""Interpreter: explains observations and the possible failure mechanism.

Hard rule (design doc): every claim must cite the layer field behind it.

Calls Gemini via agents/llm.py with the prompt in agents/prompts/interpreter.md.
The model fills a restricted draft schema (no IDs, no free-form fields); IDs
are assigned here. The Sceptic then checks every citation against the raw
evidence. With no API key, or if the call fails, it returns no findings
rather than inventing any.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from agents import llm
from contract import Concern, Finding, LayerResult

log = logging.getLogger("asra.agents")

# Prompt template, loaded once at import.
PROMPT = (Path(__file__).parent / "prompts" / "interpreter.md").read_text(encoding="utf-8")


class FindingDraft(BaseModel):
    """What the model may return: a Finding minus fields we control (id, sceptic note)."""

    claim: str
    mechanism: str
    concern: Concern
    cited_field: str
    source_record_id: str


def _build_prompt(evidence: list[LayerResult], feedback: Optional[list[str]]) -> str:
    """Fill the template with the evidence JSON and any Sceptic feedback."""
    notes = "\nThe Sceptic rejected parts of your previous answer:\n- " + "\n- ".join(feedback) if feedback else ""
    return PROMPT.format(
        species=evidence[0].species,
        evidence=json.dumps([e.model_dump(mode="json") for e in evidence], indent=2),
        feedback=notes,
    )


def interpret(evidence: list[LayerResult], feedback: Optional[list[str]] = None) -> list[Finding]:
    """Draft findings from evidence; `feedback` is the Sceptic's notes on a revision pass."""
    # Nothing to interpret, or no model configured: make no claims.
    if not evidence or not llm.available():
        return []
    try:
        drafts = llm.ask_json(_build_prompt(evidence, feedback), FindingDraft, agent="interpreter")
    except Exception:  # network/quota/parse errors must not sink the report
        log.exception("Interpreter call failed")
        return []
    # Assign stable IDs ourselves; the model never chooses them.
    return [Finding(id=f"f{i}", **d.model_dump()) for i, d in enumerate(drafts, start=1)]
