"""Sceptic: rejects unsupported claims and downgrades weak ones.

Gets the RAW layer results, not just the Interpreter's output, so it checks
claims against evidence instead of reinforcing the same error.

Two passes, in this order:

1. Deterministic checks, which run even with no API key:
   - a finding whose citation doesn't match an observation that exists is rejected
   - a finding resting on an 'incomplete' layer is forced to concern 'flagged'
2. A Gemini pass that challenges what survived. It can only weaken a finding
   (downgrade or reject), never promote one, and a failed call leaves the
   deterministic result standing.
"""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agents import llm
from contract import Finding, LayerResult

log = logging.getLogger("asra.agents")

# Prompt template, loaded once at import.
PROMPT = (Path(__file__).parent / "prompts" / "sceptic.md").read_text(encoding="utf-8")


class Verdict(BaseModel):
    """The model's ruling on one finding. It never rewrites the claim itself."""

    finding_id: str
    verdict: Literal["accept", "downgrade", "reject"]
    note: str


def _check(findings: list[Finding], layers: list[LayerResult]) -> tuple[list[Finding], list[str]]:
    """Deterministic pass: citation must resolve, incomplete evidence is flagged."""
    # Every citation a layer actually supports: ("<layer>.<field>", source id).
    cited = {(f"{l.layer}.{o.field}", o.source_record_id) for l in layers for o in l.observations}
    # Status of the layer behind each source record, for the incomplete rule.
    status_by_source = {s.id: l.status for l in layers for s in l.source_records}
    accepted: list[Finding] = []
    feedback: list[str] = []

    for f in findings:
        status = status_by_source.get(f.source_record_id)
        if status is None or status == "unavailable":
            # No matching evidence: reject outright.
            feedback.append(f"Rejected '{f.claim}': source '{f.source_record_id}' not in the evidence.")
        elif (f.cited_field, f.source_record_id) not in cited:
            # The source exists but says nothing about the field being cited.
            feedback.append(
                f"Rejected '{f.claim}': no observation '{f.cited_field}' is backed by '{f.source_record_id}'."
            )
        elif status == "incomplete" and f.concern != "flagged":
            # Rests on partial data: keep it, but never ranked high.
            accepted.append(f.model_copy(update={
                "concern": "flagged",
                "sceptic_note": "Rests on incomplete data; downgraded.",
            }))
        else:
            accepted.append(f)
    return accepted, feedback


def _challenge(findings: list[Finding], layers: list[LayerResult]) -> tuple[list[Finding], list[str]]:
    """Gemini pass: apply per-finding verdicts. Only ever weakens a finding."""
    if not findings or not llm.available():
        return findings, []
    prompt = PROMPT.format(
        evidence=json.dumps([l.model_dump(mode="json") for l in layers], indent=2),
        findings=json.dumps([f.model_dump(mode="json") for f in findings], indent=2),
    )
    try:
        verdicts = {v.finding_id: v for v in llm.ask_json(prompt, Verdict, agent="sceptic")}
    except Exception:  # a failed challenge must not promote unchecked claims
        log.exception("Sceptic call failed")
        return findings, []

    accepted: list[Finding] = []
    feedback: list[str] = []
    for f in findings:
        verdict = verdicts.get(f.id)
        if verdict is None:  # not ruled on: keep the deterministic result
            accepted.append(f)
        elif verdict.verdict == "reject":
            feedback.append(f"Rejected '{f.claim}': {verdict.note}")
        else:
            # 'downgrade' lowers concern to flagged; 'accept' leaves it alone.
            concern = "flagged" if verdict.verdict == "downgrade" else f.concern
            accepted.append(f.model_copy(update={"concern": concern, "sceptic_note": verdict.note}))
    return accepted, feedback


def review(
    findings: list[Finding],
    layers: list[LayerResult],
    # Deterministic-only review, for tests that must not reach Gemini.
    use_llm: bool = True,
) -> tuple[list[Finding], list[str]]:
    """Return (accepted findings, feedback notes for one revision pass)."""
    accepted, feedback = _check(findings, layers)
    if use_llm:
        accepted, more = _challenge(accepted, layers)
        feedback += more
    return accepted, feedback
