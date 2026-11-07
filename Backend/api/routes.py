"""HTTP routes for the ASRA backend.

Every endpoint the frontend calls is declared here on a single APIRouter,
which main.py mounts onto the app. When the pipeline exists, add:

    POST /assess  -> run resolver + four layers + agents, return a Report
                     (shape must match Frontend/lib/types.ts `Report`)
"""

from fastapi import APIRouter

# A router is a group of routes that can be attached to an app later.
# It lets us split endpoints across files without touching main.py.
router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check.

    Returns a fixed payload so you (or a deploy script) can confirm the
    server is up: `curl localhost:8000/health` -> {"status": "ok"}.
    """
    return {"status": "ok"}
