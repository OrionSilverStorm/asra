"""Layer 2, Subcellular localisation.

Target (design doc): UniProt SUBCELLULAR LOCATION + evidence codes, returning
shared, human-only and animal-only compartments. A missing annotation is not
biological absence: report it as 'incomplete', never as a difference.
"""

from contract import LayerResult
from tools.base import unavailable
from tools.resolver import ResolvedQuery


def run_localisation(query: ResolvedQuery) -> LayerResult:
    """UniProt lookups need a gene/accession; unavailable until one is resolved."""
    if query.gene is None:
        return unavailable("localisation", query, "Needs a resolved gene identifier; none was supplied.")
    # TODO: fetch human + animal UniProt entries and compare compartments.
    return unavailable("localisation", query, "UniProt integration not implemented yet.")
