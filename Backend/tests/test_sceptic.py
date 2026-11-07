"""Unit tests for the strengthened Sceptic agent audit checks.

Verifies that the Sceptic rejects all 6 scientifically invalid patterns:
1. Claims that missing annotations prove biological absence
2. Unsupported clinical safety predictions
3. Comparisons of incompatible cell populations
4. Treating RNA expression as protein abundance
5. Unsupported numerical comparisons between GTEx and Bgee
6. Findings with unrelated or missing citations / invalid field references
"""

from agents.sceptic import review
from contract import Finding, LayerResult, Observation, SourceRecord


def _make_fixture_layers() -> list[LayerResult]:
    """Create a realistic set of 4 layer results with known sources and observations."""
    seq_obs = [
        Observation(field="global_identity", value="78.4%", source_record_id="seq_rec"),
        Observation(field="mitochondrial_motif", value="Human 1-24; Mouse absent", source_record_id="seq_rec"),
    ]
    seq_records = [SourceRecord(id="seq_rec", source="Ensembl v1.0")]

    loc_records = [SourceRecord(id="loc_rec", source="UniProtKB")]

    cell_obs = [
        Observation(field="fraction_expressing", value="0.45", source_record_id="cell_rec"),
    ]
    cell_records = [SourceRecord(id="cell_rec", source="CELLxGENE Census")]

    tissue_obs = [
        Observation(field="tpm", value="12.5", source_record_id="tissue_rec"),
    ]
    tissue_records = [SourceRecord(id="tissue_rec", source="GTEx v8")]

    return [
        LayerResult(
            species="mus_musculus",
            layer="sequence",
            status="ok",
            observations=seq_obs,
            source_records=seq_records,
        ),
        LayerResult(
            species="mus_musculus",
            layer="localisation",
            status="incomplete",
            observations=[],
            source_records=loc_records,
            limitations=["Mouse subcellular compartment unannotated in UniProt"],
        ),
        LayerResult(
            species="mus_musculus",
            layer="cell_expression",
            status="ok",
            observations=cell_obs,
            source_records=cell_records,
        ),
        LayerResult(
            species="mus_musculus",
            layer="tissue_expression",
            status="ok",
            observations=tissue_obs,
            source_records=tissue_records,
        ),
    ]


def test_sceptic_rejects_missing_citation():
    """Finding citing a non-existent source record must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Human and mouse differ at residue 42.",
        mechanism="Possible conformational change.",
        concern="moderate",
        cited_field="sequence.global_identity",
        source_record_id="non_existent_source",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "not in the evidence" in feedback[0]


def test_sceptic_rejects_invalid_cited_field():
    """Finding citing a field that does not exist in the layer must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Human and mouse differ at non-existent metric.",
        mechanism="Mechanism claim.",
        concern="moderate",
        cited_field="sequence.non_existent_field",
        source_record_id="seq_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "does not match any observation" in feedback[0]


def test_sceptic_rejects_clinical_safety_prediction():
    """Claims using 'safe', 'safety', or predicting lack of toxicity must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="The compound is expected to be safe in humans based on mouse homology.",
        mechanism="Will not cause toxicity because mouse model tolerated it.",
        concern="low",
        cited_field="sequence.global_identity",
        source_record_id="seq_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "unsupported clinical safety prediction" in feedback[0]


def test_sceptic_rejects_missing_annotation_treated_as_biological_absence():
    """Claiming biological absence based on incomplete UniProt annotation must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Mouse ENT1 is absent in mitochondrial membrane.",
        mechanism="Does not localize to mitochondria because UniProt lacks annotation.",
        concern="high",
        cited_field="localisation.compartment",
        source_record_id="loc_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "missing annotation" in feedback[0]
    assert "not evidence of biological absence" in feedback[0]


def test_sceptic_rejects_incompatible_cell_populations():
    """Comparing incompatible cell populations without normalisation must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Expression diverges in incompatible cell population comparison.",
        mechanism="Mismatched population across unnormalised datasets.",
        concern="high",
        cited_field="cell_expression.fraction_expressing",
        source_record_id="cell_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "incompatible cell populations" in feedback[0]


def test_sceptic_rejects_rna_conflated_with_protein_abundance():
    """Treating single-cell RNA transcript count as proof of protein abundance must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="High transcript levels confirm high protein abundance in mouse cells.",
        mechanism="Protein expression confirmed directly by RNA expression.",
        concern="moderate",
        cited_field="cell_expression.fraction_expressing",
        source_record_id="cell_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "cannot be treated as a direct proxy for protein abundance" in feedback[0]


def test_sceptic_rejects_gtex_bgee_numerical_comparison():
    """Computing a fold difference or dividing GTEx by Bgee must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Expression shows 4-fold difference between GTEx and Bgee.",
        mechanism="Calculated by dividing GTEx TPM by Bgee expression score.",
        concern="high",
        cited_field="tissue_expression.tpm",
        source_record_id="tissue_rec",
    )
    accepted, feedback = review([f], layers)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "numerical comparison between GTEx and Bgee" in feedback[0]


def test_sceptic_accepts_valid_finding_and_downgrades_incomplete():
    """Valid findings pass audit, and findings resting on incomplete layers are downgraded."""
    layers = _make_fixture_layers()
    valid_seq = Finding(
        id="f1",
        claim="Human and mouse canonical SLC29A1 share 78.4% global identity.",
        mechanism="Sequence divergence in transmembrane domains may alter substrate affinity.",
        concern="moderate",
        cited_field="sequence.global_identity",
        source_record_id="seq_rec",
    )
    valid_loc_caveat = Finding(
        id="f2",
        claim="UniProt records indicate mouse mitochondrial localization data is unannotated.",
        mechanism="Empirical cross-species validation required.",
        concern="high",
        cited_field="localisation.subcellular_location",
        source_record_id="loc_rec",
    )
    accepted, feedback = review([valid_seq, valid_loc_caveat], layers)
    assert len(accepted) == 2
    assert len(feedback) == 0
    # First finding from complete layer remains 'moderate'
    assert accepted[0].concern == "moderate"
    assert accepted[0].sceptic_note is None
    # Second finding from incomplete layer is downgraded to 'flagged' with note
    assert accepted[1].concern == "flagged"
    assert "downgraded" in accepted[1].sceptic_note.lower()
