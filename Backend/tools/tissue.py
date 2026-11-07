"""Layer 4: Tissue expression wrapper (re-exports ``run_tissue_expression``).

Keeps compatibility with both ``tools.tissue`` (used by ``Backend/tools/__init__.py``)
and ``tools.tissue_expression`` (specified in ``Backend/tools/AGENTS.md``).
"""

from __future__ import annotations

try:
    from tools.tissue_expression import (
        DEFAULT_GTEX_DATASET_ID,
        SPECIES_TO_TAX_ID,
        SUBPART_TO_ORGAN_UBERON_MAP,
        run_tissue_expression,
    )
except ImportError:
    from Backend.tools.tissue_expression import (
        DEFAULT_GTEX_DATASET_ID,
        SPECIES_TO_TAX_ID,
        SUBPART_TO_ORGAN_UBERON_MAP,
        run_tissue_expression,
    )

__all__ = [
    "DEFAULT_GTEX_DATASET_ID",
    "SPECIES_TO_TAX_ID",
    "SUBPART_TO_ORGAN_UBERON_MAP",
    "run_tissue_expression",
]
