"""Assembles the final Report from the pipeline's parts.

Also writes the report-wide limitations, so gaps in the evidence are
stated explicitly instead of being read as "no difference".
"""

import uuid
from datetime import datetime, timezone

from agents import AgentOutput
from contract import AssessmentRequest, LayerResult, Report, SequenceStats
from tools.fixtures import FIXTURE_VERSION


def _fixture_layers(layers: list[LayerResult]) -> list[str]:
    """Names of layers that served hand-entered demo data instead of a live retrieval."""
    return [l.layer for l in layers if l.data_version == FIXTURE_VERSION]


def _limitations(layers: list[LayerResult], agents: AgentOutput) -> list[str]:
    """Report-level caveats from layer statuses and the agents' own gaps."""
    notes = list(agents.limitations)
    missing = [l.layer for l in layers if l.status != "ok"]
    if missing:
        notes.append(
            f"{len(missing)} of {len(layers)} layers did not return complete data "
            f"({', '.join(missing)}). Missing evidence is not evidence of similarity."
        )
    fixtures = _fixture_layers(layers)
    if fixtures:
        notes.append(
            f"Demo fixture data (hand-entered, not a live retrieval) was used for: {', '.join(fixtures)}."
        )
    if all(l.gene is None for l in layers):
        notes.append("No gene identifier was resolved from the submission, so database layers could not run.")
    return notes


def build_report(
    request: AssessmentRequest,
    stats: SequenceStats,
    layers: list[LayerResult],
    agents: AgentOutput,
) -> Report:
    """Combine everything into the contract's Report shape."""
    return Report(
        id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc).isoformat(),
        # Any fixture-backed layer makes the whole report "fixture", never "live".
        origin="fixture" if _fixture_layers(layers) else "live",
        request=request,
        sequence_stats=stats,
        layers=layers,
        findings=agents.findings,
        recommended_experiments=agents.recommended_experiments,
        limitations=_limitations(layers, agents),
    )
