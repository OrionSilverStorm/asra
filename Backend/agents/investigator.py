"""Investigator: selects which layer results are usable evidence.

Hard rule (design doc): no biological claim without a source record. So only
layers that ran (ok/incomplete) AND carry source records become evidence.

Deliberately deterministic: the four layers are fixed, so there is no tool
choice left for a model to make. It also keeps the layers it rejected, so the
gaps can be stated in the report instead of being read as agreement.
"""

from dataclasses import dataclass, field

from contract import LayerResult


@dataclass
class Evidence:
    """Layers split into what may be cited and what may not."""

    citable: list[LayerResult] = field(default_factory=list)
    excluded: list[LayerResult] = field(default_factory=list)

    @property
    def gaps(self) -> list[str]:
        """One line per unusable layer, naming the missing data (design doc)."""
        return [
            f"Layer '{l.layer}' contributed no evidence (status: {l.status})."
            + (f" {' '.join(l.limitations)}" if l.limitations else "")
            for l in self.excluded
        ]


def select_evidence(layers: list[LayerResult]) -> Evidence:
    """Partition layers into citable evidence and excluded ones."""
    evidence = Evidence()
    for layer in layers:
        usable = layer.status != "unavailable" and bool(layer.source_records)
        (evidence.citable if usable else evidence.excluded).append(layer)
    return evidence
