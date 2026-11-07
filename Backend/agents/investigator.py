"""Investigator: selects which layer results are usable evidence.

Hard rule (design doc): no biological claim without a source record. So only
layers that ran (ok/incomplete) AND carry source records are passed on.
"""

from contract import LayerResult


def select_evidence(layers: list[LayerResult]) -> list[LayerResult]:
    """Keep layers that ran and can be cited; drop unavailable ones."""
    return [l for l in layers if l.status != "unavailable" and l.source_records]
