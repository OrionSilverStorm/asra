"""The ASRA pipeline: request -> resolver -> 4 layers -> agents -> report.

Python computes every value; agents only interpret the layer results.
"""

from concurrent.futures import ThreadPoolExecutor

from agents import run_agents
from contract import AssessmentRequest, Report
from pipeline.run_log import log_event
from report import build_report
from tools import LAYERS
from tools.base import run_isolated
from tools.resolver import resolve
from tools.sequence_stats import compute_stats


def run_assessment(request: AssessmentRequest) -> Report:
    """Run the full pipeline for one request and log the result."""
    query = resolve(request)
    # Layers are independent network calls, so they run in parallel threads;
    # map() keeps LayerName order. Each runs in isolation: a crash becomes an
    # 'unavailable' result instead of sinking the others.
    with ThreadPoolExecutor(max_workers=len(LAYERS)) as pool:
        layers = list(pool.map(lambda item: run_isolated(item[0], item[1], query), LAYERS.items()))
    agents = run_agents(layers)
    report = build_report(request, compute_stats(query.sequence), layers, agents)
    log_event("assessment", {"report": report.model_dump(mode="json", by_alias=True)})
    return report
