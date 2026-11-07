"""Shared helpers for the four layer tools.

Every layer function has the same signature, `(context) -> LayerResult`, so the
pipeline can run them in a loop. `run_isolated` enforces the design doc rule
that one layer failing never stops the others.
"""

import logging
from typing import Callable

from contract import LayerName, LayerResult
from tools.resolver import ResolvedQuery

log = logging.getLogger("asra.tools")

# The uniform calling pattern for a layer.
LayerFn = Callable[[ResolvedQuery], LayerResult]


def unavailable(layer: LayerName, query: ResolvedQuery, reason: str) -> LayerResult:
    """Standard result for a layer that could not run. Never invents data."""
    return LayerResult(
        gene=query.gene,
        species=query.species,
        layer=layer,
        status="unavailable",
        limitations=[reason],
    )


def run_isolated(layer: LayerName, fn: LayerFn, query: ResolvedQuery) -> LayerResult:
    """Run one layer; convert any exception into an 'unavailable' result."""
    try:
        return fn(query)
    except Exception as exc:  # deliberate catch-all: a crash must not sink the report
        log.exception("Layer %s failed", layer)
        return unavailable(layer, query, f"Layer failed: {type(exc).__name__}: {exc}")
