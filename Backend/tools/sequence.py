"""Layer 1, Sequence: human vs animal sequence comparison.

Target (design doc): Ensembl orthologues + Biopython PairwiseAligner, giving
global identity, identity at mapped functional residues and differing motifs.

Current state: the animal sequence is known (user input) but the human
orthologue is not fetched yet, so the layer reports 'incomplete' with what
it does know and says exactly what is missing.
"""

from contract import LayerResult, Observation, SourceRecord
from tools.resolver import ResolvedQuery

# Source record for values taken straight from the user's submission.
USER_INPUT = SourceRecord(id="user_input", source="Submitted sequence")


def run_sequence(query: ResolvedQuery) -> LayerResult:
    """Return the animal-side facts; alignment awaits the human orthologue."""
    return LayerResult(
        gene=query.gene,
        species=query.species,
        layer="sequence",
        status="incomplete",
        observations=[
            Observation(field="animal_length", value=f"{len(query.sequence)} aa", source_record_id=USER_INPUT.id),
        ],
        source_records=[USER_INPUT],
        limitations=[
            "Human orthologue not fetched, so global and functional-residue identity were not computed.",
        ],
    )
