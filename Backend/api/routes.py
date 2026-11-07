"""HTTP routes for the ASRA backend.

Exposes endpoints for the Next.js frontend:
- GET  /health  — health and liveness check
- POST /assess  — executes the multi-agent pipeline and returns a full Report
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from api.agents import run_agents
from api.models import (
    AssessmentRequest,
    Finding,
    LayerResult,
    Observation,
    Report,
    SequenceStats,
    SourceRecord,
)
from api.sequence import compute_sequence_stats

log = logging.getLogger("asra.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check for deployment health probes."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Assessment endpoint
# ---------------------------------------------------------------------------

def _build_default_layers(request: AssessmentRequest) -> list[LayerResult]:
    """Assemble default biological evidence layers for the given request.

    If database extractors have not yet populated full live datasets for
    an unknown target, this constructs structured baseline evidence following
    the ASRA contract schema so agents can assess available observations
    and explicitly flag missing data.
    """
    gene_label = request.sequenceLabel or "Unknown Target"

    # Default Sequence layer
    seq_layer = LayerResult(
        gene=gene_label,
        species=request.species,
        layer="sequence",
        status="ok",
        observations=[
            Observation(
                field="sequence_length",
                value=f"{len(request.sequence)} aa",
                sourceRecordId="InputSequence",
            ),
        ],
        source_records=[
            SourceRecord(
                id="InputSequence",
                source="User Query Submission",
            ),
        ],
        limitations=[
            "Sequence evaluation based on user-supplied FASTA without automated isoform resolution.",
        ],
        data_version="1.0",
    )

    # Incomplete Localisation layer
    loc_layer = LayerResult(
        gene=gene_label,
        species=request.species,
        layer="localisation",
        status="incomplete",
        observations=[],
        source_records=[],
        limitations=[
            f"Experimental subcellular localisation data for {request.species} requires primary validation.",
        ],
        data_version=None,
    )

    # Incomplete Cell-type expression layer
    cell_layer = LayerResult(
        gene=gene_label,
        species=request.species,
        layer="cell_expression",
        status="incomplete",
        observations=[],
        source_records=[],
        limitations=[
            f"Single-cell expression data across {request.species} cell types currently unindexed.",
        ],
        data_version=None,
    )

    # Incomplete Tissue expression layer
    tissue_layer = LayerResult(
        gene=gene_label,
        species=request.species,
        layer="tissue_expression",
        status="incomplete",
        observations=[],
        source_records=[],
        limitations=[
            f"Cross-species tissue expression atlas for {request.species} requires orthologue mapping.",
        ],
        data_version=None,
    )

    return [seq_layer, loc_layer, cell_layer, tissue_layer]


@router.post("/assess", response_model=Report)
def assess(request: AssessmentRequest) -> Report:
    """Run the multi-agent pipeline and return a complete translational risk Report.

    Accepts an AssessmentRequest from the frontend containing species,
    sequence, and optional label. Executes the Investigator, Interpreter,
    Sceptic, and Revision cycle, returning the Report object.
    """
    try:
        # 1. Calculate sequence physicochemical metrics
        stats_raw = compute_sequence_stats(request.sequence)
        sequence_stats = SequenceStats(**stats_raw)

        # 2. Assemble evidence layers
        layers = _build_default_layers(request)
        evidence_dicts = [layer.model_dump() for layer in layers]

        # 3. Formulate query and run multi-agent pipeline
        query = (
            f"Investigate {request.sequenceLabel or 'target sequence'} "
            f"translational risks in {request.species}"
        )
        log.info("Running agent assessment for query: %s", query)
        agent_out = run_agents(query, evidence_dicts)

        final_report = agent_out.get("final_report", {})
        raw_findings = final_report.get("findings", [])
        translational_concerns = final_report.get("translational_concerns", [])
        recommended_experiments = final_report.get("recommended_experiments", [])
        sceptic = agent_out.get("sceptic_critique", {})

        # 4. Map agent findings to the frontend Finding schema
        findings: list[Finding] = []
        for idx, item in enumerate(raw_findings):
            layer_name = item.get("layer", "sequence")
            matching_layer = next(
                (l for l in layers if l.layer == layer_name), None
            )

            # Mark concern as 'flagged' if the backing layer had missing/incomplete data
            if matching_layer and matching_layer.status != "ok":
                concern_val = "flagged"
            else:
                concern_val = "moderate"

            citations = item.get("citations", [])
            primary_citation = citations[0] if citations else "InputSequence"

            # Check if any sceptic warning applied to this finding
            sceptic_notes = sceptic.get("missing_data_warnings", [])
            sceptic_note = sceptic_notes[0] if sceptic_notes else None

            # Mechanism explanation from translational concerns if available
            mechanism = (
                translational_concerns[idx]
                if idx < len(translational_concerns)
                else item.get("evidence_quote", "Mechanistic impact unannotated.")
            )

            findings.append(
                Finding(
                    id=str(uuid.uuid4()),
                    claim=item.get("claim", "Observation noted."),
                    mechanism=mechanism,
                    concern=concern_val,
                    citedField=f"{layer_name}.observation",
                    sourceRecordId=primary_citation,
                    scepticNote=sceptic_note,
                )
            )

        # 5. Compile global limitations
        report_limitations = [
            "Retrospective cross-species biological risk assessment only; does not provide safety predictions.",
            "Findings derived exclusively from pre-computed observations audited by the Sceptic agent.",
        ]
        for warning in sceptic.get("missing_data_warnings", []):
            report_limitations.append(f"Audit Warning: {warning}")

        return Report(
            id=str(uuid.uuid4()),
            generatedAt=datetime.now(timezone.utc).isoformat(),
            origin="live",
            request=request,
            sequenceStats=sequence_stats,
            layers=layers,
            findings=findings,
            recommendedExperiments=recommended_experiments,
            limitations=report_limitations,
        )

    except Exception as exc:
        log.exception("Error executing assessment")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
