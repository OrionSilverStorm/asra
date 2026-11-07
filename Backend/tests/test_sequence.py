"""Synthetic alignment checks; real Ensembl comparison is explicitly opt-in."""

from copy import deepcopy
import json
import os
from unittest.mock import patch

import pytest

from contract import LayerResult
from tools import resolver, sequence

PROTEIN = "ACDEFGHIKLMNPQRSTVWY"


def check_invariants(result):
    m = result["measurements"]
    assert m["paired_columns"] == m["exact_matches"] + m["substitutions"] + m["ambiguous_pairs"]
    assert m["alignment_columns"] == m["paired_columns"] + m["inserted_residues"] + m["deleted_residues"]
    assert m["human_length"] == m["paired_columns"] + m["deleted_residues"]
    assert m["animal_length"] == m["paired_columns"] + m["inserted_residues"]
    for label, opposite in (("human", "animal"), ("animal", "human")):
        mapping = result[f"{label}_to_{opposite}"]
        assert set(mapping) == set(range(1, m[f"{label}_length"] + 1))
        for position, target in mapping.items():
            if target is not None:
                assert result[f"{opposite}_to_{label}"][target] == position
                assert 1 <= target <= m[f"{opposite}_length"]
    json.dumps(result, allow_nan=False)


def test_identical():
    result = sequence.align_proteins(PROTEIN, PROTEIN)
    m = result["measurements"]
    assert m["exact_matches"] == len(PROTEIN)
    assert m["substitutions"] == m["insertion_events"] == m["deletion_events"] == 0
    assert m["identity_percent"] == m["human_coverage_percent"] == m["animal_coverage_percent"] == 100
    assert result["human_to_animal"] == dict(enumerate(range(1, 21), 1))
    assert result["substitutions"] == result["indels"] == []
    check_invariants(result)


def test_single_substitution():
    animal = PROTEIN[:9] + "I" + PROTEIN[10:]
    result = sequence.align_proteins(PROTEIN, animal)
    assert result["measurements"]["exact_matches"] == 19
    assert result["measurements"]["identity_percent"] == 95
    assert result["measurements"]["human_coverage_percent"] == 100
    assert result["substitutions"] == [{
        "alignment_column": 10, "human_position": 10, "animal_position": 10,
        "human_residue": "L", "animal_residue": "I",
    }]
    check_invariants(result)


@pytest.mark.parametrize("reverse", [False, True])
def test_internal_gap_run_and_shifted_substitution(reverse):
    # Unique flanks fix the internal two-residue gap and downstream coordinates.
    animal = PROTEIN[:10] + "GG" + PROTEIN[10:15] + "T" + PROTEIN[16:]
    h, a = (animal, PROTEIN) if reverse else (PROTEIN, animal)
    result = sequence.align_proteins(h, a)
    m = result["measurements"]
    kind = "deletion" if reverse else "insertion"
    assert m[f"{kind}_events"] == 1
    assert m["deleted_residues" if reverse else "inserted_residues"] == 2
    assert m["exact_matches"] == 19 and m["substitutions"] == 1
    assert m["identity_percent"] == pytest.approx(100 * 19 / 22)
    assert m["human_coverage_percent"] == pytest.approx(100 * 20 / len(h))
    assert m["animal_coverage_percent"] == pytest.approx(100 * 20 / len(a))
    short_map = result["animal_to_human" if reverse else "human_to_animal"]
    long_map = result["human_to_animal" if reverse else "animal_to_human"]
    assert short_map[10] == 10 and short_map[11] == 13
    assert long_map[11] is None and long_map[12] is None
    event = result["indels"][0]
    assert event["type"] == kind and event["length"] == 2
    assert event["alignment_start"] == 11 and event["alignment_end"] == 12
    assert event["human_anchor_before"] == event["animal_anchor_before"] == 10
    assert event["human_start" if reverse else "animal_start"] == 11
    assert event["human_end" if reverse else "animal_end"] == 12
    assert event["animal_start" if reverse else "human_start"] is None
    change = result["substitutions"][0]
    assert (change["human_position"], change["animal_position"]) == ((18, 16) if reverse else (16, 18))
    check_invariants(result)


@pytest.mark.parametrize("reverse", [False, True])
def test_both_terminal_gaps_have_affine_penalties(reverse):
    longer = "WW" + PROTEIN + "CC"
    h, a = (longer, PROTEIN) if reverse else (PROTEIN, longer)
    result = sequence.align_proteins(h, a)
    base_score = sequence.align_proteins(PROTEIN, PROTEIN)["alignment"]["score"]
    assert result["alignment"]["score"] == base_score - 2 * 10.5
    assert result["measurements"]["identity_percent"] == pytest.approx(100 * 20 / 24)
    assert len(result["indels"]) == 2
    assert result["indels"][0]["human_anchor_before"] == result["indels"][0]["animal_anchor_before"] == 0
    long_map = result["human_to_animal" if reverse else "animal_to_human"]
    assert [long_map[p] for p in (1, 2, 23, 24)] == [None] * 4
    assert long_map[3] == 1 and long_map[22] == 20
    check_invariants(result)


def test_multiple_internal_gap_events():
    result = sequence.align_proteins(PROTEIN * 3, PROTEIN + "GG" + PROTEIN + "SS" + PROTEIN)
    assert result["measurements"]["insertion_events"] == 2
    assert result["measurements"]["inserted_residues"] == 4
    check_invariants(result)


@pytest.mark.parametrize("bad", ["", None, 123, "acde", "AC DE", "AC\nDE", "AC-DE", "AC*", "ACU", "ACO", "ACJ", "123"])
@pytest.mark.parametrize("side", ["human", "animal"])
def test_rejects_invalid_unchanged_sequences(bad, side):
    with pytest.raises(ValueError, match=side):
        sequence.align_proteins(bad if side == "human" else PROTEIN,
                                bad if side == "animal" else PROTEIN)


def test_ambiguous_pairs_never_count_as_exact_or_resolved_substitutions():
    result = sequence.align_proteins(PROTEIN + "BZX", PROTEIN + "BZX")
    assert result["measurements"]["exact_matches"] == 20
    assert result["measurements"]["ambiguous_pairs"] == 3
    assert result["measurements"]["substitutions"] == 0
    assert result["measurements"]["identity_percent"] == pytest.approx(100 * 20 / 23)
    assert result["measurements"]["human_coverage_percent"] == 100
    check_invariants(result)


def test_tied_alignment_is_disclosed_and_repeatable():
    result = sequence.align_proteins("AAAA", "AAA")
    assert result["parameters"]["alternative_optimal_alignment_exists"] is True
    assert any("Multiple optimal" in text for text in result["limitations"])
    assert result == sequence.align_proteins("AAAA", "AAA")
    check_invariants(result)


def test_short_unequal_sequences():
    result = sequence.align_proteins("A", "AA")
    assert result["measurements"]["identity_percent"] == 50
    assert result["measurements"]["human_coverage_percent"] == 100
    assert result["measurements"]["animal_coverage_percent"] == 50
    check_invariants(result)



def test_no_paired_columns_has_zero_metrics_and_null_maps():
    # For these dissimilar sequences two gap runs score above all mismatches.
    result = sequence.align_proteins("W" * 20, "D" * 20)
    m = result["measurements"]
    assert m["paired_columns"] == m["exact_matches"] == 0
    assert m["identity_percent"] == m["paired_identity_percent"] == 0
    assert m["human_coverage_percent"] == m["animal_coverage_percent"] == 0
    assert list(result["human_to_animal"].values()) == [None] * 20
    assert list(result["animal_to_human"].values()) == [None] * 20
    assert m["insertion_events"] == m["deletion_events"] == 1
    check_invariants(result)


@pytest.fixture
def resolved():
    return {"gene": "SYNTHETIC", "species": "mus_musculus",
            "source": {"gene_id": "H_GENE", "protein_id": "H_PROTEIN", "species": "homo_sapiens", "sequence": PROTEIN, "metadata": {"perc_id": 99}},
            "target": {"gene_id": "A_GENE", "protein_id": "A_PROTEIN", "species": "mus_musculus", "sequence": PROTEIN, "metadata": {}},
            "orthology": {"type": "ortholog_one2one", "dn_ds": None},
            "source_url": "https://rest.ensembl.org/synthetic"}


def test_run_sequence_retains_identifiers_metadata_and_provenance(resolved):
    before = deepcopy(resolved)
    with patch.object(sequence, "resolve_orthologue", return_value=resolved) as resolve:
        result = sequence.run_sequence("SYNTHETIC", "mus_musculus")
    resolve.assert_called_once_with("SYNTHETIC", "mus_musculus")
    assert result["human"] == resolved["source"] and result["animal"] == resolved["target"]
    assert result["orthology"] == resolved["orthology"]
    assert result["source_records"][0]["url"] == resolved["source_url"]
    assert result["status"] == "ok" and result["data_version"] is None
    assert result["retrieved_at"]
    assert resolved == before
    check_invariants(result)


@pytest.mark.parametrize("error", [
    resolver.EnsemblAPIError("offline"), resolver.OrthologueNotFoundError("absent"),
    resolver.MissingSequenceError("missing"), resolver.InvalidEnsemblResponseError("bad response"),
    resolver.AmbiguousOrthologueError("ambiguous", [{"id": "one"}, {"id": "two"}]),
    ValueError("invalid input"),
])
def test_resolver_errors_propagate_without_alignment(error):
    with patch.object(sequence, "resolve_orthologue", side_effect=error), patch.object(sequence, "align_proteins") as align:
        with pytest.raises(type(error)) as caught:
            sequence.run_sequence("SYNTHETIC", "mus_musculus")
    assert caught.value is error
    align.assert_not_called()


def test_invalid_resolved_sequence_is_rejected(resolved):
    resolved["target"]["sequence"] = ""
    with patch.object(sequence, "resolve_orthologue", return_value=resolved):
        with pytest.raises(ValueError, match="animal"):
            sequence.run_sequence("SYNTHETIC", "mus_musculus")


def test_legacy_query_keeps_shared_contract_without_resolving():
    query = resolver.ResolvedQuery("mus_musculus", PROTEIN, None)
    with patch.object(sequence, "resolve_orthologue") as resolve:
        result = sequence.run_sequence(query)
    assert isinstance(result, LayerResult) and result.status == "incomplete"
    assert result.observations[0].source_record_id == "user_input"
    assert result.observations[0].value == "20 aa"
    resolve.assert_not_called()


@pytest.mark.skipif(os.getenv("ASRA_LIVE_ENSEMBL") != "1", reason="Opt-in live Ensembl check")
def test_live_slc29a1_mouse():
    result = sequence.run_sequence("SLC29A1", "mus_musculus")
    assert result["orthology"]["type"] == "ortholog_one2one"
    assert result["measurements"]["human_length"] == 456
    assert result["measurements"]["animal_length"] == 460
    assert 0 < result["measurements"]["identity_percent"] <= 100
    assert 0 < result["measurements"]["human_coverage_percent"] <= 100
    assert 0 < result["measurements"]["animal_coverage_percent"] <= 100
    print(json.dumps({"human": result["human"]["protein_id"], "animal": result["animal"]["protein_id"],
                      "measurements": result["measurements"], "parameters": result["parameters"]}, indent=2))
    check_invariants(result)
