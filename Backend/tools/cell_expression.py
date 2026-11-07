"""Layer 3, Cell-type expression (stretch goal).

Target (design doc): CELLxGENE Census get_anndata(), returning detection
fractions per cell population with dataset IDs, cell counts and assay.
Cross-species cell-type labels are not guaranteed equivalent; flag fuzzy matches.
"""

from contract import LayerResult
from tools.base import unavailable
from tools.fixtures import fixture
from tools.resolver import ResolvedQuery


def run_cell_expression(query: ResolvedQuery) -> LayerResult:
    """Census queries need a gene; unavailable until one is resolved."""
    # Demo evidence first, when ASRA_FIXTURES is on (see tools/fixtures.py).
    demo = fixture("cell_expression", query)
    if demo:
        return demo
    if query.gene is None:
        return unavailable("cell_expression", query, "Needs a resolved gene identifier; none was supplied.")
    # TODO: query CELLxGENE Census (install cellxgene-census separately; it is heavy).
    return unavailable("cell_expression", query, "CELLxGENE integration not implemented yet.")
