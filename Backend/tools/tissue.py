"""Layer 4, Tissue expression (stretch goal).

Target (design doc): GTEx (human) + Bgee (species calls), returning tissue
distribution with matched anatomical IDs. Never divide GTEx by Bgee to claim
a fold difference; they use different methods and scales.
"""

from contract import LayerResult
from tools.base import unavailable
from tools.fixtures import fixture
from tools.resolver import ResolvedQuery


def run_tissue_expression(query: ResolvedQuery) -> LayerResult:
    """GTEx/Bgee lookups need a gene; unavailable until one is resolved."""
    # Demo evidence first, when ASRA_FIXTURES is on (see tools/fixtures.py).
    demo = fixture("tissue_expression", query)
    if demo:
        return demo
    if query.gene is None:
        return unavailable("tissue_expression", query, "Needs a resolved gene identifier; none was supplied.")
    # TODO: fetch GTEx + Bgee and align on anatomical IDs.
    return unavailable("tissue_expression", query, "GTEx/Bgee integration not implemented yet.")
