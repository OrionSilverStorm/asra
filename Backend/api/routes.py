"""HTTP routes for the ASRA backend.

Every endpoint the frontend calls is declared here on a single APIRouter,
which main.py mounts onto the app. Routes stay thin: validate (via the
contract models), call the pipeline, return the result.
"""

from fastapi import APIRouter

from contract import AssessmentRequest, Report
from pipeline import run_assessment

# A router groups routes so they can live outside main.py.
router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check: `curl localhost:8000/health` -> {"status": "ok"}."""
    return {"status": "ok"}


@router.post("/assess", response_model=Report)
def assess(request: AssessmentRequest) -> Report:
    """Run the full pipeline for one species + sequence.

    FastAPI validates the body against AssessmentRequest (bad input -> 422
    with field errors) and serialises the Report using its camelCase aliases,
    which is exactly the shape Frontend/lib/types.ts expects.
    """
    return run_assessment(request)
