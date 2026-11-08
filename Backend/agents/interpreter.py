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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from agents import llm
from agents.evidence import compact_for_prompt
from contract import Concern, Finding, LayerResult

log = logging.getLogger("asra.agents")

# Prompt template, loaded once at import.
PROMPT = (Path(__file__).parent / "prompts" / "interpreter.md").read_text(encoding="utf-8")


# Report limitations for the two ways the model can be missing. Neither is a
# scientific result: "no findings" below is not the same as "no differences".
NOT_CONFIGURED = (
    "The AI interpretation step did not run because no Gemini API key is configured, "
    "so no findings were generated. This does not mean no cross-species differences exist."
)
API_FAILED = (
    "The AI interpretation step failed ({kind}; for example API quota, timeout or network error), "
    "so no findings were generated. This does not mean no cross-species differences exist."
)


class FindingDraft(BaseModel):
    """What the model may return: a Finding minus fields we control (id, sceptic note)."""

    claim: str
    mechanism: str
    concern: Concern
    cited_field: str
    source_record_id: str
    # The experiment that would settle this claim. Dropped with the finding if
    # the Sceptic rejects it, so no suggestion outlives its evidence.
    experiment: str = ""


@dataclass
class Draft:
    """The Interpreter's output: findings plus the experiment each one suggests."""

    findings: list[Finding] = field(default_factory=list)
    # Finding id -> suggested follow-up experiment.
    experiments: dict[str, str] = field(default_factory=dict)
    # Report-ready explanation when the model did not run or failed; "" when it
    # ran (even if it returned no findings). Never carries keys or raw errors.
    failure: str = ""


def _build_prompt(evidence: list[LayerResult], feedback: Optional[list[str]]) -> str:
    """Fill the template with the evidence JSON and any Sceptic feedback."""
    notes = "\nThe Sceptic rejected parts of your previous answer:\n- " + "\n- ".join(feedback) if feedback else ""
    return PROMPT.format(
        species=evidence[0].species,
        # Condensed copy: residue maps and raw features would swamp the prompt.
        evidence=json.dumps(compact_for_prompt(evidence)),
        feedback=notes,
    )


def interpret(evidence: list[LayerResult], feedback: Optional[list[str]] = None) -> Draft:
    """Draft findings from evidence; `feedback` is the Sceptic's notes on a revision pass."""
    # Nothing to interpret: no claims, and nothing failed.
    if not evidence:
        return Draft()
    # No model configured: make no claims, and say why.
    if not llm.available():
        return Draft(failure=NOT_CONFIGURED)
    try:
        drafts = llm.ask_json(_build_prompt(evidence, feedback), FindingDraft, agent="interpreter")
    except Exception as exc:  # network/quota/parse errors must not sink the report
        log.exception("Interpreter call failed")
        # Exception type only: messages can echo request details.
        return Draft(failure=API_FAILED.format(kind=type(exc).__name__))
    # Assign stable IDs ourselves; the model never chooses them.
    out = Draft()
    for i, d in enumerate(drafts, start=1):
        fields = d.model_dump()
        experiment = fields.pop("experiment", "").strip()
        out.findings.append(Finding(id=f"f{i}", **fields))
        if experiment:
            out.experiments[f"f{i}"] = experiment
    return out
