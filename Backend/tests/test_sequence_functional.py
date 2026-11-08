from __future__ import annotations
"""Focused Role 3 annotation identity, coordinates, partial evidence and replay."""

from copy import deepcopy
import json
from unittest.mock import patch

import httpx
import pytest

from tools import sequence_functional as functional
from tools.sequence import align_proteins, run_sequence
from tools.sequence_adapter import to_layer_result
from tools.sequence_demo import FIXTURES, PROTEINS, demonstration


@pytest.fixture
def human():
    accession, protein_id, gene_id, species, _ = PROTEINS["human"]
    entry = json.loads((FIXTURES / f"{accession}.json").read_text())
    protein = {"protein_id": protein_id, "gene_id": gene_id, "species": species,
               "sequence": entry["sequence"]["value"]}
    return protein, entry


def test_real_replay_preserves_identity_sources_and_observed_motif():
    result = demonstration()
    analysis = result["functional_analysis"]
    assert analysis["proteins"]["human"]["identity"]["isoform"] == "Q99808-1"
    assert analysis["proteins"]["animal"]["identity"]["isoform"] == "Q9JIM1-1"
    assert all(p["identity"]["release"] == "2026_04" for p in analysis["proteins"].values())
    motif = analysis["slc29a1_motif"]
    assert motif["status"] == "observed"
    assert motif["sequence_observation"]["human_window"] == "PERN"
    assert motif["sequence_observation"]["animal_window"] == "PARS"
    rows = motif["sequence_observation"]["residues"]
    assert [r["human_position"] for r in rows] == [71, 72, 73, 74]
    assert [r["state"] for r in rows] == ["identical", "substitution", "identical", "substitution"]
    assert (len(analysis["functional_substitutions"]), len(analysis["other_substitutions"]),
            len(analysis["unclassified_substitutions"])) == (42, 47, 0)
    for pos in (72, 74):
        s = next(s for s in analysis["functional_substitutions"] if s["human_position"] == pos)
        assert any(o["source_record_id"] == functional.LITERATURE_ID for o in s["annotation_overlaps"])
    human_features = analysis["proteins"]["human"]["features"]
    assert any(f["start"] == 414 and f["type"] == "Site" and
               f["evidence_references"][0]["id"] == "21795683" for f in human_features)
    assert not any(f["type"] == "Motif" for f in human_features)  # Literature is a separate origin.
    adapted = to_layer_result(result)
    observation = next(o for o in adapted.observations if o.field == "functional_analysis")
    assert json.loads(observation.value) == json.loads(json.dumps(analysis))
    assert observation.source_record_id == "sequence_functional_analysis"
    ids = {s.id for s in adapted.source_records}
    assert all(o.source_record_id in ids for o in adapted.observations)
    assert result["data_version"] is None  # UniProt release cannot supply Ensembl release.


@pytest.mark.parametrize("kind", ["Active site", "Domain", "Binding site", "Motif"])
def test_selected_features_keep_exact_inclusive_boundaries_and_references(human, kind):
    protein, entry = deepcopy(human)
    identity = functional.verify_entry(protein, entry, {})
    entry["features"] = [{"type": kind, "location": {
        "start": {"value": 1, "modifier": "EXACT"}, "end": {"value": 3, "modifier": "EXACT"}},
        "evidences": [{"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "123"}]}]
    feature = functional.extract_features(entry, identity)[0]
    aligned = align_proteins("ACDE", "ACDF")
    aligned.update(human={"sequence": "ACDE"}, animal={"sequence": "ACDF"})
    assert [r["human_position"] for r in functional.map_feature(feature, aligned)["residues"]] == [1, 2, 3]
    assert feature["source_record_id"] == "uniprot:Q99808"
    assert feature["evidence_references"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"


@pytest.mark.parametrize("change", ["species", "taxon", "sequence", "protein", "gene", "version", "isoform", "ambiguous_isoform", "accession"])
def test_refuses_unverified_identity(human, change):
    protein, entry = deepcopy(human)
    refs = [r for r in entry["uniProtKBCrossReferences"] if r["database"] == "Ensembl"]
    ref = next(r for r in refs if any(p["value"].startswith(protein["protein_id"]) for p in r["properties"]))
    if change == "species":
        protein["species"] = "mus_musculus"
    elif change == "taxon":
        protein["metadata"] = {"taxon_id": 10090}
    elif change == "sequence":
        protein["sequence"] = "A" + protein["sequence"][1:]
    elif change == "protein":
        protein["protein_id"] = "ENSP00000000000"
    elif change == "gene":
        protein["gene_id"] = "ENSG00000000000"
    elif change == "version":
        protein["protein_id"] += ".999"
    elif change == "isoform":
        ref["isoformId"] = "Q99808-2"
    elif change == "ambiguous_isoform":
        other = deepcopy(ref)
        other["isoformId"] = "Q99808-2"
        entry["uniProtKBCrossReferences"].append(other)
    else:
        entry.pop("primaryAccession")
    with pytest.raises(functional.AnnotationError):
        functional.verify_entry(protein, entry, {})


def test_live_search_checks_all_candidates_and_accession_response(human):
    protein, entry = human
    wrong = deepcopy(entry)
    wrong["organism"]["scientificName"] = "Mus musculus"
    metadata = {"pagination_present": False, "release": "2026_04"}
    with patch.object(functional, "_get", side_effect=[({"results": [wrong, entry]}, metadata), (entry, metadata)]) as get:
        returned, identity = functional.retrieve_annotations(protein)
    assert returned == entry
    assert identity["accession"] == "Q99808"
    assert len(identity["rejected_candidates"]) == 1
    assert "xref:ensembl-ENSP00000360820" == get.call_args_list[0].kwargs["params"]["query"]


@pytest.mark.parametrize("mode", ["empty", "duplicate", "paginated", "malformed", "different_accession"])
def test_search_never_selects_an_arbitrary_or_inconsistent_mapping(human, mode):
    protein, entry = human
    other = deepcopy(entry)
    other["primaryAccession"] = "P00000"
    payload = {"results": [] if mode == "empty" else [entry, other] if mode == "duplicate" else [entry]}
    if mode == "malformed":
        payload = {"wrong": []}
    with patch.object(functional, "_get", side_effect=[(payload, {"pagination_present": mode == "paginated"}), (other, {})]):
        with pytest.raises(functional.AnnotationError):
            functional.retrieve_annotations(protein)


@pytest.mark.parametrize("error", ["timeout", "http", "json", "shape"])
def test_api_errors_are_explicit(error):
    request = httpx.Request("GET", functional.BASE)
    response = httpx.Response(503 if error == "http" else 200, request=request,
                              content=b"bad" if error == "json" else b"[]" if error == "shape" else b"{}")
    with patch.object(functional.httpx, "get", side_effect=httpx.ReadTimeout("offline") if error == "timeout" else None,
                      return_value=response):
        with pytest.raises(functional.AnnotationError):
            functional._get(functional.BASE)


def test_uncertain_features_retain_raw_evidence_without_projection(human):
    protein, entry = human
    identity = functional.verify_entry(protein, entry, {})
    feature = {"type": "Binding site", "description": "synthetic uncertain endpoint",
               "location": {"start": {"value": 1, "modifier": "EXACT"},
                            "end": {"value": 2, "modifier": "UNKNOWN"}},
               "evidences": [{"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "123"}]}
    entry["features"] = [feature]
    extracted = functional.extract_features(entry, identity)[0]
    assert extracted["raw"] == feature
    assert extracted["coordinate_status"] == "unsupported"
    assert functional.map_feature(extracted, {})["residues"] == []


def test_projection_uses_shifted_reciprocal_maps_and_explicit_gaps():
    human = "ACDEFGHIKLMNPQRSTVWY"
    animal = human[:10] + "GG" + human[10:15] + "T" + human[16:]
    aligned = align_proteins(human, animal)
    aligned.update(human={"sequence": human}, animal={"sequence": animal})
    f = {"start": 16, "end": 16, "coordinate_status": "exact"}
    row = functional.map_feature(f, aligned)["residues"][0]
    assert (row["human_position"], row["animal_position"], row["state"]) == (16, 18, "substitution")
    gapped = align_proteins(animal, human)
    gapped.update(human={"sequence": animal}, animal={"sequence": human})
    row = functional.map_feature({**f, "start": 11, "end": 11}, gapped)["residues"][0]
    assert row["state"] == "gap" and row["animal_position"] is None
    wire = json.loads(json.dumps(aligned))
    assert functional.map_feature(f, wire) == functional.map_feature(f, aligned)
    aligned["animal_to_human"][18] = 3
    with pytest.raises(functional.AnnotationError, match="reciprocal"):
        functional.map_feature(f, aligned)


def test_ambiguous_residue_and_tied_traceback_are_never_resolved_effects():
    result = align_proteins("AAAA", "AAX")
    result.update(human={"sequence": "AAAA"}, animal={"sequence": "AAX"})
    feature = {"start": 1, "end": 4, "coordinate_status": "exact"}
    mapped = functional.map_feature(feature, result)
    assert mapped["mapping_status"] == "selected_traceback_only"
    assert any(r["state"] == "ambiguous" for r in mapped["residues"])
    assert any(r["state"] == "gap" for r in mapped["residues"])


def test_annotation_failure_preserves_alignment_and_unclassified_substitutions():
    original = demonstration()
    original.pop("functional_analysis")
    original["source_records"] = original["source_records"][:1]
    before = deepcopy(original)
    def unavailable(protein):
        raise functional.AnnotationError("synthetic API failure")
    enriched = functional.add_functional_analysis(original, retrieve=unavailable)
    assert original == before
    analysis = enriched["functional_analysis"]
    assert enriched["status"] == analysis["status"] == "incomplete"
    assert analysis["slc29a1_motif"]["status"] == "unsupported"
    assert len(analysis["unclassified_substitutions"]) == 89
    assert analysis["functional_substitutions"] == analysis["other_substitutions"] == []
    assert enriched["alignment"] == original["alignment"]
    to_layer_result(enriched)


def test_known_overlap_survives_missing_animal_annotations():
    original = demonstration()
    original.pop("functional_analysis")
    original["source_records"] = original["source_records"][:1]
    entry = json.loads((FIXTURES / "Q99808.json").read_text())
    def retrieve(protein):
        if protein["species"] == "mus_musculus":
            raise functional.AnnotationError("animal annotation unavailable")
        return entry, {}
    analysis = functional.add_functional_analysis(original, retrieve=retrieve)["functional_analysis"]
    assert analysis["status"] == "incomplete"
    assert analysis["functional_substitutions"] and analysis["unclassified_substitutions"]
    assert not analysis["other_substitutions"]
    assert any(s["human_position"] == 72 for s in analysis["functional_substitutions"])


def test_motif_gap_and_unsupported_anchor_do_not_produce_localisation_claims():
    original = demonstration()
    identity = original["functional_analysis"]["proteins"]["human"]["identity"]
    original["human_to_animal"][72] = None
    motif, _ = functional.slc29a1_motif(original, identity)
    assert motif["sequence_observation"]["animal_window"] is None
    assert motif["sequence_observation"]["residues"][1]["state"] == "gap"
    original["human"]["sequence"] = original["human"]["sequence"][:70] + "AAAA" + original["human"]["sequence"][74:]
    motif, feature = functional.slc29a1_motif(original, identity)
    assert motif["status"] == "unsupported" and feature is None
    original["gene"] = "GAPDH"
    motif, feature = functional.slc29a1_motif(original, identity)
    assert motif["status"] == "unsupported" and feature is None


def test_no_annotations_is_incomplete_and_not_biological_absence(human):
    protein, entry = deepcopy(human)
    entry["features"] = []
    result = {"gene": "SYNTHETIC", "species": "mus_musculus", "source": protein, "target": protein,
              "orthology": {}, "source_url": "https://example.org"}
    with patch("tools.sequence.resolve_orthologue", return_value=result):
        sequence = run_sequence("SYNTHETIC", "mus_musculus")
    # Distinct accession IDs permit this synthetic two-protein evidence fixture.
    animal_entry = deepcopy(entry)
    animal_entry["primaryAccession"] = "P00000"
    enriched = functional.add_functional_analysis(sequence, retrieve=lambda p:
        (entry if p is sequence["human"] else animal_entry, {}))
    assert enriched["functional_analysis"]["status"] == "incomplete"
    assert any("not evidence of biological absence" in x for x in enriched["limitations"])


def test_run_sequence_opt_in_and_legacy_remain_compatible():
    with patch("tools.sequence.resolve_orthologue", return_value={
        "gene": "SYNTHETIC", "species": "mus_musculus", "source": {"protein_id": "H", "sequence": "ACDE"},
        "target": {"protein_id": "A", "sequence": "ACDF"}, "orthology": {}, "source_url": "https://example.org",
    }), patch.object(functional, "add_functional_analysis", side_effect=lambda r: {**r, "enriched": True}) as enrich:
        assert "enriched" not in run_sequence("SYNTHETIC", "mus_musculus")
        assert run_sequence("SYNTHETIC", "mus_musculus", functional=True)["enriched"]
        enrich.assert_called_once()
