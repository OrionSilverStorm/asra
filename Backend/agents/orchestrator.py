"""Runs the three agents in order: Investigator -> Interpreter <-> Sceptic.

Exactly one revision cycle after the Sceptic replies (design doc): no
open-ended debate, so a demo can never hang.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.interpreter import interpret
from agents.investigator import select_evidence
from agents.sceptic import review
from contract import Finding, LayerResult

log = logging.getLogger("asra.agents")


@dataclass
class AgentOutput:
    """What the agent stage hands to the report builder."""

    findings: list[Finding] = field(default_factory=list)
    recommended_experiments: list[str] = field(default_factory=list)


def _generate_recommended_experiments(
    findings: list[Finding], layers: list[LayerResult]
) -> list[str]:
    """Derive concrete follow-up assays to resolve biological uncertainties.

    Links directly to identified findings and incomplete layers.
    """
    experiments: list[str] = []
    seen = set()

    def _add(exp: str):
        if exp not in seen:
            seen.add(exp)
            experiments.append(exp)

    # Check which layers have findings or incomplete data
    cited_layers = {
        f.cited_field.split(".")[0] for f in findings if "." in f.cited_field
    }

    if "localisation" in cited_layers or any(
        l.layer == "localisation" and l.status == "incomplete" for l in layers
    ):
        _add(
            "Conduct parallel subcellular fractionation and confocal immunofluorescence microscopy "
            "across human and comparison animal primary cells to validate organellar localization."
        )

    if "cell_expression" in cited_layers or any(
        l.layer == "cell_expression" and l.status == "incomplete" for l in layers
    ):
        _add(
            "Perform flow cytometry or targeted single-cell profiling with normalized orthologous cell "
            "population markers to quantify comparative expression across cell subsets."
        )

    if "sequence" in cited_layers:
        _add(
            "Execute in vitro recombinant binding and kinetic transport assays (Km, Vmax) to quantify "
            "the functional impact of divergent sequence motifs."
        )

    if "tissue_expression" in cited_layers or any(
        l.layer == "tissue_expression" and l.status == "incomplete" for l in layers
    ):
        _add(
            "Perform RT-qPCR or Western blot validation across target organs to assess quantitative "
            "expression disparities indicated by tissue atlases."
        )

    return experiments


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
        Audited findings and concrete recommended follow-up assays.
    """
    log.info("Agent stage started with %d layer(s)", len(layers))

    # Stage 1: Investigator selects valid evidence (must carry source records)
    evidence = select_evidence(layers)
    if not evidence:
        log.info("Investigator found no citable evidence; skipping Interpreter")
        return AgentOutput(
            findings=[],
            recommended_experiments=_generate_recommended_experiments([], layers),
        )

    # Stage 2: Interpreter produces initial draft
    initial_draft = interpret(evidence)
    log.info("Interpreter produced %d initial draft finding(s)", len(initial_draft))

    # Stage 3: Sceptic audits the draft against the raw layers
    findings, feedback = review(initial_draft, layers)
    log.info(
        "Sceptic review: %d accepted, %d feedback note(s)",
        len(findings),
        len(feedback),
    )

    # Stage 4: Deterministic single revision pass if the Sceptic gave feedback
    if feedback:
        log.info("Single revision pass initiated with Sceptic feedback")
        revised_draft = interpret(evidence, feedback)
        findings, final_feedback = review(revised_draft, layers)
        log.info(
            "Post-revision review: %d accepted, %d remaining feedback note(s)",
            len(findings),
            len(final_feedback),
        )

    # Stage 5: Compile follow-up experimental recommendations
    experiments = _generate_recommended_experiments(findings, layers)

    return AgentOutput(
        findings=findings,
        recommended_experiments=experiments,
    )
