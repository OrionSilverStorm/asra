"""Runs the three agents in order: Investigator -> Interpreter <-> Sceptic.

Exactly one revision cycle after the Sceptic replies (design doc): no
open-ended debate, so a demo can never hang.
"""

from dataclasses import dataclass, field

from agents.interpreter import interpret
from agents.investigator import select_evidence
from agents.sceptic import review
from contract import Finding, LayerResult


@dataclass
class AgentOutput:
    """What the agent stage hands to the report builder."""

    findings: list[Finding] = field(default_factory=list)
    recommended_experiments: list[str] = field(default_factory=list)


def run_agents(layers: list[LayerResult]) -> AgentOutput:
    """Select evidence, draft findings, review, and revise at most once."""
    evidence = select_evidence(layers)
    findings, feedback = review(interpret(evidence), layers)
    if feedback:
        # Single revision pass with the Sceptic's notes, then a final review.
        findings, _ = review(interpret(evidence, feedback), layers)
    return AgentOutput(findings=findings)
