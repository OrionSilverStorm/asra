"""HTTP routes for the ASRA backend.

Every endpoint the frontend and external clients call is declared here on a
single APIRouter, which main.py mounts onto the FastAPI application.

Endpoints:
- GET  /health               — liveness / readiness probe
- POST /assess               — full pipeline (resolver + 4 layers + agents + report)
"""

from __future__ import annotations

from fastapi import APIRouter

# Remote branch imports: contract and full pipeline runner
from contract import AssessmentRequest, Report
from pipeline import run_assessment

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

