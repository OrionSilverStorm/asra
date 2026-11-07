"""Role 3: global comparison with optional Milestone 3 annotation evidence.

Gene API: run_sequence(gene, species) -> JSON-compatible dict. The existing
run_sequence(ResolvedQuery) -> LayerResult call remains a sequence-only fallback;
it cannot identify a gene from a submitted sequence. Role 1 must provide a gene
and explicitly call tools.sequence_adapter.to_layer_result before integration.
No shared contract or route is changed here.

Definitions: L = all alignment columns (including terminal/internal gaps),
P = columns with residues on both sides, M = identical standard amino-acid pairs.
Identity = 100*M/L; paired identity = 100*M/P (0 if P=0).
Human/animal coverage = 100*P/N for that protein's full length N, not global
span coverage (which would trivially be 100%). All percentages are unrounded.
B, Z and X are scored by BLOSUM62 but never establish exact identity or a
resolved substitution. Unsupported symbols (including stops, U, O, J), empty
strings, lowercase, whitespace and pre-gapped sequences are rejected unchanged.
"""

from datetime import datetime, timezone
from hashlib import sha256
from typing import overload

from contract import LayerResult, Observation, SourceRecord
from tools.resolver import (ResolvedQuery, resolve_orthologue, SUPPORTED_RESIDUES,
                            validate_protein_sequence)

STANDARD_RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWY")
GAP_OPEN_SCORE = -10.0
GAP_EXTEND_SCORE = -0.5

METRIC_DEFINITIONS = {
    "alignment_columns": "L: all columns, including internal and terminal gap columns",
    "paired_columns": "P: columns containing a residue on both sides, including B/Z/X",
    "exact_matches": "M: equal letters from the 20 standard amino acids only",
    "substitutions": "Unequal pairs of standard amino acids; no gaps or B/Z/X",
    "ambiguous_pairs": "Paired columns containing B, Z or X on either side",
    "identity_percent": "100*M/L; gap and ambiguous columns remain in denominator",
    "paired_identity_percent": "100*M/P, or 0 when P=0; ambiguous pairs included in P",
    "human_coverage_percent": "100*P/human_length; residues opposite gaps are uncovered",
    "animal_coverage_percent": "100*P/animal_length; residues opposite gaps are uncovered",
    "indels": "Maximal contiguous gap runs; insertion/deletion relative to human, not evolutionary events",
    "coordinates": "1-based inclusive positions; mapping value null means opposite a gap; JSON map keys are strings",
}


def _validate_sequence(sequence: str, label: str) -> None:
    validate_protein_sequence(sequence, label)


def align_proteins(human: str, animal: str) -> dict:
    """Align unchanged proteins and return measurements plus reciprocal maps.

    A gap of length k scores -10 - 0.5*(k-1), identically for both sequences
    and for internal and terminal gaps. Only the first optimal traceback is
    used; a second traceback is checked without enumerating all alignments.
    Biopython is imported lazily so the legacy pipeline needs no new package.
    """
    _validate_sequence(human, "human")
    _validate_sequence(animal, "animal")
    import Bio
    from Bio.Align import PairwiseAligner, substitution_matrices

    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    # These aggregate setters apply to left, internal and right gaps on both sides.
    aligner.open_gap_score = GAP_OPEN_SCORE
    aligner.extend_gap_score = GAP_EXTEND_SCORE
    aligner.epsilon = 1e-6
    alignments = iter(aligner.align(human, animal))
    alignment = next(alignments)
    alternative_optimum = next(alignments, None) is not None
    h_aligned, a_aligned = alignment[0], alignment[1]
    human_map, animal_map = {}, {}
    substitutions, ambiguous_pairs, indels = [], [], []
    h_pos = a_pos = matches = paired = 0
    current_gap = None
    for column, (h_res, a_res) in enumerate(zip(h_aligned, a_aligned), 1):
        h_before, a_before = h_pos, a_pos
        h_pos += h_res != "-"
        a_pos += a_res != "-"
        if h_res != "-":
            human_map[h_pos] = a_pos if a_res != "-" else None
        if a_res != "-":
            animal_map[a_pos] = h_pos if h_res != "-" else None
        if h_res != "-" and a_res != "-":
            current_gap = None
            paired += 1
            position = {
                "alignment_column": column,
                "human_position": h_pos, "animal_position": a_pos,
                "human_residue": h_res, "animal_residue": a_res,
            }
            if h_res not in STANDARD_RESIDUES or a_res not in STANDARD_RESIDUES:
                ambiguous_pairs.append(position)
            elif h_res == a_res:
                matches += 1
            else:
                substitutions.append(position)
            continue
        kind = "insertion" if h_res == "-" else "deletion"
        if current_gap is None or current_gap["type"] != kind:
            current_gap = {
                "type": kind, "alignment_start": column, "alignment_end": column,
                "length": 0,
                "human_start": None, "human_end": None,
                "animal_start": None, "animal_end": None,
                # Anchors are counts before the run; 0 denotes before residue 1.
                "human_anchor_before": h_before, "animal_anchor_before": a_before,
            }
            indels.append(current_gap)
        current_gap["alignment_end"] = column
        current_gap["length"] += 1
        for label, residue, pos in (("human", h_res, h_pos), ("animal", a_res, a_pos)):
            if residue != "-":
                if current_gap[f"{label}_start"] is None:
                    current_gap[f"{label}_start"] = pos
                current_gap[f"{label}_end"] = pos

    insertions = [event for event in indels if event["type"] == "insertion"]
    deletions = [event for event in indels if event["type"] == "deletion"]
    columns = len(h_aligned)
    limitations = [
        "Alignment differences do not establish toxicity, biological effects or functional equivalence.",
        "Gap runs describe this alignment, not inferred evolutionary insertion/deletion events.",
        "Results and residue mappings depend on scoring parameters and the selected protein isoforms.",
        "No functional annotations, motifs or functional-residue analysis are included (Milestone 3).",
    ]
    if alternative_optimum:
        limitations.append("Multiple optimal alignments exist; only the first traceback is reported. Gap placement and residue mappings may differ.")
    if (set(human) | set(animal)) - STANDARD_RESIDUES:
        limitations.append("B/Z/X residues are ambiguous: they are scored by BLOSUM62 but excluded from exact matches and resolved substitutions.")
    return {
        "alignment": {"human": h_aligned, "animal": a_aligned, "score": float(alignment.score)},
        "parameters": {
            "mode": "global", "substitution_matrix": "BLOSUM62",
            "gap_open_score": GAP_OPEN_SCORE, "gap_extend_score": GAP_EXTEND_SCORE,
            "gap_score_formula": "open + (length - 1) * extend",
            "terminal_gaps": "same penalties as internal gaps, both proteins",
            "algorithm": aligner.algorithm, "biopython_version": Bio.__version__,
            "epsilon": aligner.epsilon, "traceback_policy": "first optimal alignment",
            "alternative_optimal_alignment_exists": alternative_optimum,
        },
        "measurements": {
            "human_length": len(human), "animal_length": len(animal),
            "alignment_columns": columns, "paired_columns": paired,
            "exact_matches": matches, "substitutions": len(substitutions),
            "ambiguous_pairs": len(ambiguous_pairs),
            "insertion_events": len(insertions), "deletion_events": len(deletions),
            "inserted_residues": sum(event["length"] for event in insertions),
            "deleted_residues": sum(event["length"] for event in deletions),
            "identity_percent": 100.0 * matches / columns,
            "paired_identity_percent": 100.0 * matches / paired if paired else 0.0,
            "human_coverage_percent": 100.0 * paired / len(human),
            "animal_coverage_percent": 100.0 * paired / len(animal),
        },
        "metric_definitions": dict(METRIC_DEFINITIONS),
        "human_to_animal": human_map, "animal_to_human": animal_map,
        "substitutions": substitutions, "ambiguous_pairs": ambiguous_pairs,
        "indels": indels, "limitations": limitations,
    }


@overload
def run_sequence(gene: str, species: str, *, functional: bool = False) -> dict: ...


@overload
def run_sequence(gene: ResolvedQuery) -> LayerResult: ...


def run_sequence(gene: str | ResolvedQuery, species: str | None = None, *, functional: bool = False) -> dict | LayerResult:
    """Resolve and compare a unique orthologue; propagate resolver errors intact.

    AmbiguousOrthologueError retains all candidates; no first candidate is picked.
    The one-argument legacy call retains submitted-sequence evidence only, even
    if its query has a gene, because it cannot equate the submitted protein with
    an Ensembl protein. Gene-based results describe the retrieved proteins.
    Set functional=True for verified UniProt features and the curated SLC29A1
    literature check. The default preserves the Milestone 2 schema/network cost.
    """
    if isinstance(gene, ResolvedQuery):
        if species is not None:
            raise ValueError("Do not supply species alongside a ResolvedQuery.")
        return LayerResult(
            gene=gene.gene, species=gene.species, layer="sequence", status="incomplete",
            observations=[Observation(field="animal_length", value=f"{len(gene.sequence)} aa",
                                      source_record_id="user_input")],
            source_records=[SourceRecord(id="user_input", source="Submitted sequence")],
            limitations=["Human orthologue not fetched for the sequence-only request; gene-based alignment requires a human gene symbol."],
        )
    resolved = resolve_orthologue(gene, species)
    result = align_proteins(resolved["source"]["sequence"], resolved["target"]["sequence"])
    output = {
        "gene": resolved["gene"], "species": resolved["species"],
        "layer": "sequence", "status": ("incomplete" if result["parameters"]["alternative_optimal_alignment_exists"] else "ok"),
        "human": resolved["source"], "animal": resolved["target"],
        "orthology": resolved["orthology"],
        "source_records": [{"id": "ensembl_orthology", "source": "Ensembl REST homology",
                            "url": resolved["source_url"]}],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "data_version": None,
        "provenance": {
            "human": {"protein_id": resolved["source"]["protein_id"],
                      "sequence_sha256": sha256(resolved["source"]["sequence"].encode("ascii")).hexdigest()},
            "animal": {"protein_id": resolved["target"]["protein_id"],
                       "sequence_sha256": sha256(resolved["target"]["sequence"].encode("ascii")).hexdigest()},
            "sequence_hash_definition": "SHA-256 of the exact unchanged ASCII sequence, without header or newline",
            "source_release": "unknown",
            "source_release_evidence": "Homology response provides no verified source release; REST API version and retrieval date are not data releases.",
        },
        **result,
        "limitations": result["limitations"] + [
            "Only the resolver's unique one-to-one relationship is compared; this is not evidence of functional equivalence.",
            "Ensembl release is not supplied by the resolver; data_version is unknown. Retrieval time is recorded.",
        ],
    }
    if functional:
        from tools.sequence_functional import add_functional_analysis
        return add_functional_analysis(output)
    return output
