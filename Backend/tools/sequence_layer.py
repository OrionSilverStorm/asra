from __future__ import annotations
"""Pipeline entry for the sequence layer: `(ResolvedQuery) -> LayerResult`.

Wraps Role 3's engine at the orchestration boundary without changing it
(INTEGRATE4U.md §4-5):
- no verified gene  -> legacy submitted-sequence path (status incomplete)
- verified gene     -> Ensembl orthologue + alignment + UniProt features,
                       adapted to the shared contract by `to_layer_result`
- scientific errors -> 'unavailable' with the reason; ambiguous orthologues
                       keep every raw candidate as evidence, none is chosen
- transient Ensembl failures retry at most twice, respecting Retry-After within
  a five-second total sleep cap; only the verified SLC29A1 mouse pair may use
  explicitly recorded raw evidence after confirmed transient failures
Anything else still falls through to `run_isolated`'s catch-all.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
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
MAX_RETRY_DELAY = 5.0  # cap total sleep, excluding the three existing 30 s HTTP timeouts

# EnsemblAPIError messages (tools/resolver.py) that describe a passing fault:
# server errors, rate limiting, timeouts and transport failures. A 4xx such
# as 400/404 is a real answer and is not retried.
_TRANSIENT = re.compile(r"HTTP (5\d\d|429)\b|timed out|request failed")


def _retry_after(value):
    """HTTP delta-seconds or HTTP-date, in seconds; invalid values use backoff."""
    if value is None:
        return 0.0
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 0.0
    return max(0.0, delay) if math.isfinite(delay) else MAX_RETRY_DELAY + 1


def _compare(query: ResolvedQuery) -> LayerResult:
    """Three attempts, capped sleep, then an exact-pair verified snapshot only."""
    slept = 0.0
    confirmed = True
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            return to_layer_result(run_sequence(query.gene, query.species, functional=True))
        except EnsemblAPIError as exc:
            transient = exc.transient if exc.transient is not None else bool(_TRANSIENT.search(str(exc)))
            confirmed = confirmed and exc.transient is True
            wait = max(delay or 0, _retry_after(exc.retry_after))
            if not transient or delay is None or slept + wait > MAX_RETRY_DELAY:
                reason = f"{exc} (after {attempt} attempt{'s' if attempt > 1 else ''})"
                if transient and confirmed and (query.gene, query.species) == ("SLC29A1", "mus_musculus"):
                    from tools.sequence_pinned import pinned_slc29a1
                    # A stated UniProt accession must identify the pinned human protein.
                    accession = re.match(r"(?:sp|tr)\|([^|]+)\|", (query.sequence_label or "").lstrip(">"))
                    if accession and accession.group(1) != "Q99808":
                        raise EnsemblAPIError(reason + "; submitted accession does not match pinned Q99808") from exc
                    return to_layer_result(pinned_slc29a1(query.gene, query.species, reason))
                raise EnsemblAPIError(reason, transient=transient, retry_after=exc.retry_after) from exc
            time.sleep(wait)
            slept += wait
    raise AssertionError("unreachable")


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
