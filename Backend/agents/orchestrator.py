"""Runs the three agents in order: Investigator -> Interpreter <-> Sceptic.

Exactly one revision cycle after the Sceptic replies (design doc): no
open-ended debate, so a demo can never hang.
"""

from dataclasses import dataclass, field

from agents.interpreter import Draft, interpret
from agents.investigator import Evidence, select_evidence
from agents.sceptic import review
from contract import Finding, LayerResult


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


def run_agents(layers: list[LayerResult]) -> AgentOutput:
    """Select evidence, draft findings, review, and revise at most once."""
    evidence = select_evidence(layers)
    draft = interpret(evidence.citable)
    findings, feedback = review(draft.findings, layers)
    if feedback:
        # Single revision pass with the Sceptic's notes, then a final review.
        draft = interpret(evidence.citable, feedback)
        findings, _ = review(draft.findings, layers)
    return AgentOutput(
        findings=findings,
        recommended_experiments=_experiments(draft, findings, evidence),
        limitations=evidence.gaps,
    )
