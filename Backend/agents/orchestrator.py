"""Runs the three agents in order: Investigator -> Interpreter <-> Sceptic.

Exactly one revision cycle after the Sceptic replies (design doc): no
open-ended debate, so a demo can never hang.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.interpreter import Draft, interpret
from agents.investigator import Evidence, select_evidence
from agents.sceptic import review
from contract import Finding, LayerResult

log = logging.getLogger("asra.agents")


@dataclass
class AgentOutput:
    """What the agent stage hands to the report builder."""

    findings: list[Finding] = field(default_factory=list)
    recommended_experiments: list[str] = field(default_factory=list)
    # Gaps the Investigator found: layers that produced no citable evidence.
    limitations: list[str] = field(default_factory=list)


def _experiments(draft: Draft, findings: list[Finding], evidence: Evidence) -> list[str]:
    """Suggestions for the findings that survived, plus one per unusable layer."""
    kept = [draft.experiments[f.id] for f in findings if f.id in draft.experiments]
    # Design doc: the missing-data case must recommend further investigation.
    # Built from layer names only, so nothing here is invented.
    return kept + [
        f"Obtain {l.layer.replace('_', ' ')} data for this target; the layer returned no citable evidence."
        for l in evidence.excluded
    ]


def run_agents(
    layers: list[LayerResult],
    query: Optional[str] = None,
) -> AgentOutput:
    """Select evidence, draft findings, review, and revise at most once.

    Parameters
    ----------
    layers:
        Output from the biological tools/layers.
    query:
        Optional original user query string (logged for provenance).

    Returns
    -------
    AgentOutput:
        Audited findings, recommended follow-up assays, and gap limitations.
    """
    log.info("Agent stage started with %d layer(s)", len(layers))
    evidence = select_evidence(layers)
    draft = interpret(evidence.citable)
    log.info("Interpreter produced %d initial draft finding(s)", len(draft.findings))

    findings, feedback = review(draft.findings, layers)
    log.info("Sceptic review: %d accepted, %d feedback note(s)", len(findings), len(feedback))

    if feedback:
        log.info("Single revision pass initiated with Sceptic feedback")
        draft = interpret(evidence.citable, feedback)
        findings, final_feedback = review(draft.findings, layers)
        log.info("Post-revision review: %d accepted, %d remaining feedback note(s)", len(findings), len(final_feedback))

    experiments = _experiments(draft, findings, evidence)
    return AgentOutput(
        findings=findings,
        recommended_experiments=experiments,
        limitations=evidence.gaps,
    )
