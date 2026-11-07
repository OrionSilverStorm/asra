"""Layer tools: pure Python, no LLM.

`LAYERS` is the registry the pipeline iterates over, in display order. To add
or swap a layer, change this mapping; nothing else needs to know.
"""

from contract import LayerName
from tools.base import LayerFn
from tools.cell_expression import run_cell_expression
from tools.localisation import run_localisation
from tools.sequence import run_sequence
from tools.tissue import run_tissue_expression

LAYERS: dict[LayerName, LayerFn] = {
    "sequence": run_sequence,
    "localisation": run_localisation,
    "cell_expression": run_cell_expression,
    "tissue_expression": run_tissue_expression,
}

__all__ = ["LAYERS"]
