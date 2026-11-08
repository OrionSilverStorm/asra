from __future__ import annotations
"""Layer tools: pure Python, no LLM.

`LAYERS` is the registry the pipeline iterates over, in display order. To add
or swap a layer, change this mapping; nothing else needs to know.
"""

from contract import LayerName
from tools.base import LayerFn
from tools.cell_expression import run_cell_expression
from tools.localisation import run_localisation
from tools.sequence_layer import run_sequence_layer
from tools.tissue_expression import run_tissue_expression

LAYERS: dict[LayerName, LayerFn] = {
    # Gene-based comparison when a gene is known, legacy fallback otherwise.
    "sequence": run_sequence_layer,
    "localisation": run_localisation,
    "cell_expression": run_cell_expression,
    "tissue_expression": run_tissue_expression,
}

__all__ = ["LAYERS"]
