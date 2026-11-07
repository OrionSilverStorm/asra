"""Pipeline entry for the sequence layer: `(ResolvedQuery) -> LayerResult`.

Wraps Role 3's engine at the orchestration boundary without changing it
(INTEGRATE4U.md §4-5):
- no verified gene  -> legacy submitted-sequence path (status incomplete)
- verified gene     -> Ensembl orthologue + alignment + UniProt features,
                       adapted to the shared contract by `to_layer_result`
- scientific errors -> 'unavailable' with the reason; ambiguous orthologues
                       keep every raw candidate as evidence, none is chosen
Anything else still falls through to `run_isolated`'s catch-all.
"""

import json

from contract import LayerResult, Observation, SourceRecord
from tools.base import unavailable
from tools.resolver import AmbiguousOrthologueError, OrthologueResolutionError, ResolvedQuery
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result

# Citation for evidence that comes straight from an Ensembl homology response.
_ENSEMBL = SourceRecord(id="ensembl_orthology", source="Ensembl REST homology")


def run_sequence_layer(query: ResolvedQuery) -> LayerResult:
    """Run the gene-based comparison when a gene is known, else the fallback."""
    if query.gene is None:
        # Sequence-only request: nothing to look up, report submitted length only.
        return run_sequence(query)
    try:
        return to_layer_result(run_sequence(query.gene, query.species, functional=True))
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
