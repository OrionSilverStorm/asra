"""Resolver: turns the raw request into the identifiers the layers need.

The design doc's layers are keyed on (gene, species). The current form only
supplies (species, sequence), so `gene` stays None until a resolution step
exists (e.g. a sequence search against UniProt, or a gene field on the form).
Layers that need a gene report themselves 'unavailable' with that reason.
"""

from dataclasses import dataclass
from typing import Optional

from contract import AssessmentRequest, SpeciesId


@dataclass(frozen=True)
class ResolvedQuery:
    """Everything a layer may need, resolved once and shared by all layers."""

    species: SpeciesId
    sequence: str
    sequence_label: Optional[str]
    # Gene symbol (e.g. "SLC29A1"); None until resolution is implemented.
    gene: Optional[str] = None


def resolve(request: AssessmentRequest) -> ResolvedQuery:
    """Build the shared query, extracting a candidate gene symbol from sequence_label if present."""
    gene: Optional[str] = None
    if request.sequence_label:
        candidate = request.sequence_label.strip().lstrip(">").strip()
        if candidate:
            # Extract first token, removing common FASTA delimiters like pipe or space
            gene = candidate.split()[0].split("|")[0].strip().upper()

    return ResolvedQuery(
        species=request.species,
        sequence=request.sequence,
        sequence_label=request.sequence_label,
        gene=gene,
    )
