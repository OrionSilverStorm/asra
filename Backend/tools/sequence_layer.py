"""Pipeline entry for the sequence layer: `(ResolvedQuery) -> LayerResult`.

Wraps Role 3's engine at the orchestration boundary without changing it
(INTEGRATE4U.md §4-5):
- no verified gene  -> legacy submitted-sequence path (status incomplete)
- verified gene     -> Ensembl orthologue + alignment + UniProt features,
                       adapted to the shared contract by `to_layer_result`
- scientific errors -> 'unavailable' with the reason; ambiguous orthologues
                       keep every raw candidate as evidence, none is chosen
- transient Ensembl failures (HTTP 5xx/429, timeout, transport) are retried
  up to RETRY_DELAYS times; the final reason says how many attempts ran
Anything else still falls through to `run_isolated`'s catch-all.
"""

import json
import re
import time

from contract import LayerResult, Observation, SourceRecord
from tools.base import unavailable
from tools.resolver import (AmbiguousOrthologueError, EnsemblAPIError, OrthologueResolutionError,
                            ResolvedQuery)
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result

# Citation for evidence that comes straight from an Ensembl homology response.
_ENSEMBL = SourceRecord(id="ensembl_orthology", source="Ensembl REST homology")

# Seconds to wait before each retry (so 1 try + len(RETRY_DELAYS) retries).
RETRY_DELAYS = (1.0, 2.0)

# EnsemblAPIError messages (tools/resolver.py) that describe a passing fault:
# server errors, rate limiting, timeouts and transport failures. A 4xx such
# as 400/404 is a real answer and is not retried.
_TRANSIENT = re.compile(r"HTTP (5\d\d|429)\b|timed out|request failed")


def _compare(query: ResolvedQuery) -> LayerResult:
    """Run the comparison, retrying transient Ensembl failures."""
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            return to_layer_result(run_sequence(query.gene, query.species, functional=True))
        except EnsemblAPIError as exc:
            # Out of retries, or not a passing fault: report it with the attempt count.
            if delay is None or not _TRANSIENT.search(str(exc)):
                raise EnsemblAPIError(f"{exc} (after {attempt} attempt{'s' if attempt > 1 else ''})") from exc
            time.sleep(delay)
    raise AssertionError("unreachable")  # the loop always returns or raises


def run_sequence_layer(query: ResolvedQuery) -> LayerResult:
    """Run the gene-based comparison when a gene is known, else the fallback."""
    if query.gene is None:
        # Sequence-only request: nothing to look up, report submitted length only.
        return run_sequence(query)
    try:
        return _compare(query)
    except AmbiguousOrthologueError as exc:
        # Keep the raw candidates for review; never pick the first one.
        return LayerResult(
            gene=query.gene,
            species=query.species,
            layer="sequence",
            status="unavailable",
            observations=[Observation(field="ambiguous_candidates",
                                      value=json.dumps(exc.candidates, sort_keys=True),
                                      source_record_id=_ENSEMBL.id)],
            source_records=[_ENSEMBL],
            limitations=[str(exc), "No orthologue was selected; comparison needs a justified biological choice."],
        )
    except OrthologueResolutionError as exc:
        # Not found / missing sequence / bad response / API failure: say which.
        return unavailable("sequence", query, f"{type(exc).__name__}: {exc}")
