"""HTTP routes for the ASRA backend.

Every endpoint the frontend and external clients call is declared here on a
single APIRouter, which main.py mounts onto the FastAPI application.

Endpoints:
- GET  /health               — liveness / readiness probe
- POST /assess               — full pipeline (resolver + 4 layers + agents + report)
- POST /assess/agent-pipeline — direct execution of the 4-stage multi-agent pipeline
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Remote branch imports: contract and full pipeline runner
from contract import AssessmentRequest, Report
from pipeline import run_assessment

# Local branch imports: direct multi-agent pipeline
from api.agents import run_agents as run_multi_agent_pipeline

log = logging.getLogger("asra.routes")

# A router groups routes so they can live outside main.py.
router = APIRouter()


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check: `curl localhost:8000/health` -> {"status": "ok"}."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Primary assessment endpoint (Full Pipeline)
# ---------------------------------------------------------------------------

@router.post("/assess", response_model=Report)
def assess(request: AssessmentRequest) -> Report:
    """Run the full pipeline for one species + sequence.

    FastAPI validates the body against AssessmentRequest (bad input -> 422
    with field errors) and serialises the Report using its camelCase aliases,
    which is exactly the shape Frontend/lib/types.ts expects.
    """
    return run_assessment(request)


# ---------------------------------------------------------------------------
# Direct Multi-Agent Pipeline endpoint (Role 2: AI Agents & Reasoning)
# ---------------------------------------------------------------------------

class AgentPipelineRequest(BaseModel):
    """Payload for directly running the four-stage agent pipeline."""

    query: str = Field(
        ...,
        description="Free-text research question or target investigation prompt.",
    )
    evidence: List[Dict[str, Any]] = Field(
        ...,
        description="List of pre-computed layer evidence dictionaries.",
    )


class AgentPipelineResponse(BaseModel):
    """Response capturing all intermediate reasoning stages and final report."""

    investigator: Dict[str, Any]
    interpreter_draft: Dict[str, Any]
    sceptic_critique: Dict[str, Any]
    final_report: Dict[str, Any]
    revision_was_needed: bool


@router.post("/assess/agent-pipeline", response_model=AgentPipelineResponse)
def assess_with_agent_pipeline(request: AgentPipelineRequest) -> AgentPipelineResponse:
    """Run the standalone four-stage multi-agent pipeline directly.

    Executes Investigator -> Interpreter Draft -> Sceptic Audit -> Revision,
    returning intermediate reasoning and final audited findings.
    """
    try:
        result = run_multi_agent_pipeline(request.query, request.evidence)
        return AgentPipelineResponse(**result)
    except Exception as exc:
        log.exception("Agent pipeline execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
