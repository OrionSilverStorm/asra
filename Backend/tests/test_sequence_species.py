"""Complete current frontend species coverage, with separately opt-in live checks."""

import json
import os
from pathlib import Path
from typing import get_args
from unittest.mock import patch

import httpx
import pytest

from contract import AssessmentRequest, SpeciesId
from tools import resolver
from tools import sequence_functional as functional
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result
from tools.sequence_species_audit import (
    CD28_SPECIES, RecordedHTTP, audit, check_pair, error_record, frontend_species,
)

# Independent inventory: deliberate updates required when the actual dropdown changes.
FRONTEND_IDS = (
    "mus_musculus", "rattus_norvegicus", "cavia_porcellus", "macaca_mulatta",
    "macaca_fascicularis", "canis_lupus_familiaris", "sus_scrofa",
    "oryctolagus_cuniculus", "danio_rerio",
)
SNAPSHOT = Path(__file__).parent / "fixtures" / "role3" / "species_compatibility"


def test_actual_frontend_inventory_matches_shared_contract():
    assert tuple(frontend_species()) == FRONTEND_IDS
    assert set(FRONTEND_IDS) == set(get_args(SpeciesId))


@pytest.mark.parametrize("species", FRONTEND_IDS)
def test_resolver_sequence_functional_adapter_and_legacy_for_every_frontend_species(species):
    human_seq, animal_seq = "ACDEFGHIKLMN", "ACDEFGHIKLMQ"
    human = {"id": "ENSG00000000001", "protein_id": "ENSP00000000001",
             "species": "homo_sapiens", "seq": human_seq}
    animal = {"id": "ENSANIG00000000002", "protein_id": "ENSANIP00000000002",
              "species": species, "seq": animal_seq}
    homology = {"data": [{"id": human["id"], "homologies": [
        {"type": "ortholog_one2one", "source": human, "target": animal}]}]}

    def entry(record, accession):
        return {"primaryAccession": accession,
                "organism": {"scientificName": record["species"].replace("_", " ")},
                "sequence": {"value": record["seq"]},
                "uniProtKBCrossReferences": [{"database": "Ensembl", "id": "synthetic transcript",
                    "properties": [{"key": "ProteinId", "value": record["protein_id"]},
                                   {"key": "GeneId", "value": record["id"]}]}],
                "features": [{"type": "Binding site", "location": {
                    "start": {"value": 12, "modifier": "EXACT"}, "end": {"value": 12, "modifier": "EXACT"}}}]}
    entries = {"P00001": entry(human, "P00001"), "P00002": entry(animal, "P00002")}
    queries = []

    def get(url, **kwargs):
        queries.append((url, kwargs))
        if "homology/" in url:
            assert kwargs["params"]["target_species"] == species
            body = homology
        elif url.endswith("/search"):
            accession = "P00001" if human["protein_id"] in kwargs["params"]["query"] else "P00002"
            body = {"results": [entries[accession]]}
        else:
            body = entries[url.rsplit("/", 1)[1].split(".")[0]]
        return httpx.Response(200, json=body, headers={"x-uniprot-release": "synthetic"},
                              request=httpx.Request("GET", url))

    with patch.object(httpx, "get", side_effect=get):
        resolved = resolver.resolve_orthologue("SYNTHETIC", species)
        assert resolved["species"] == resolved["target"]["species"] == species
        plain = run_sequence("SYNTHETIC", species)
        assert "functional_analysis" not in plain
        rich = run_sequence("SYNTHETIC", species, functional=True)
        assert rich["functional_analysis"]["proteins"]["animal"]["identity"]["accession"] == "P00002"
        assert rich["functional_analysis"]["functional_substitutions"][0]["animal_position"] == 12
        layer = to_layer_result(rich)
        assert layer.species == species and layer.status == "ok"
        assert any(o.field == "functional_analysis" for o in layer.observations)
        before_legacy = len(queries)
        query = resolver.resolve(AssessmentRequest(species=species, sequence=animal_seq))
        legacy = run_sequence(query)
        assert len(queries) == before_legacy
        assert legacy.species == species and legacy.status == "incomplete"


@pytest.mark.parametrize("exc,category", [
    (resolver.OrthologueNotFoundError("none"), "orthologue_unavailable"),
    (resolver.AmbiguousOrthologueError("many", [{"target": "one"}, {"target": "two"}]), "ambiguous_orthologue"),
    (resolver.EnsemblAPIError("HTTP 503"), "api_failure"),
    (resolver.MissingSequenceError("none"), "missing_sequence"),
    (resolver.InvalidEnsemblResponseError("malformed"), "invalid_ensembl_response"),
])
def test_orthology_failure_categories(exc, category):
    assert error_record(exc)["status"] == category
    if isinstance(exc, resolver.AmbiguousOrthologueError):
        assert error_record(exc)["candidates"] == exc.candidates


@pytest.mark.parametrize("body,error", [
    ({"results": []}, functional.MissingUniProtMappingError),
    ({"results": [{}]}, functional.UnverifiedUniProtMappingError),
    ({"not_results": []}, functional.AnnotationError),
])
def test_missing_and_unverified_annotation_mapping_are_distinct(body, error):
    with patch.object(functional, "_get", return_value=(body, {"pagination_present": False})):
        with pytest.raises(error):
            functional.retrieve_annotations({"protein_id": "ENSP00000000001"})


def test_annotation_api_failure_is_distinct_from_missing_mapping():
    with patch.object(functional.httpx, "get", side_effect=httpx.ConnectError("offline")):
        with pytest.raises(functional.AnnotationAPIError) as caught:
            functional._get(functional.BASE)
    assert caught.value.code == "api_failure"


def test_insufficient_annotations_are_distinct_from_missing_mapping():
    from tools.sequence_demo import FIXTURES, demonstration

    original = demonstration()
    original.pop("functional_analysis")
    original["source_records"] = original["source_records"][:1]
    entries = {}
    for label, accession in (("human", "Q99808"), ("animal", "Q9JIM1")):
        entry = json.loads((FIXTURES / f"{accession}.json").read_text())
        entry["features"] = []
        entries[original[label]["protein_id"]] = entry
    result = functional.add_functional_analysis(original, retrieve=lambda p: (entries[p["protein_id"]], {}))
    assert result["status"] == "incomplete"
    for protein in result["functional_analysis"]["proteins"].values():
        assert protein["identity"] is not None  # Mapping succeeded.
        assert protein["status"] == "incomplete"
        assert protein["reason_code"] == "insufficient_functional_annotations"


def test_audit_does_not_retry_before_long_retry_after(tmp_path):
    response = httpx.Response(429, headers={"retry-after": "30"},
                              request=httpx.Request("GET", "https://example.org"))
    with patch.object(httpx, "get", return_value=response) as get:
        recorder = RecordedHTTP(tmp_path)
        returned = recorder.get("https://example.org")
    assert returned.status_code == 429
    get.assert_called_once()


@pytest.mark.parametrize("species", FRONTEND_IDS)
def test_saved_catalogue_and_audit_cover_every_frontend_species(species):
    report = json.loads((SNAPSHOT / "report.json").read_text())
    assert report["frontend_species"] == list(FRONTEND_IDS)
    assert report["catalogue"][species][0]["name"] == species
    row = next(r for r in report["rows"] if r["gene"] == "SLC29A1" and r["frontend_species"] == species)
    assert row["resolver"]["status"] != "unexpected_error"
    assert row["sequence"]["status"] != "unexpected_error"
    if "measurements" in row["sequence"]:
        m = row["sequence"]["measurements"]
        assert 0 <= m["identity_percent"] <= 100
        assert 0 <= m["human_coverage_percent"] <= 100
        assert 0 <= m["animal_coverage_percent"] <= 100
        assert row["sequence"]["adapter_status"] == "ok"


def test_complete_live_http_evidence_replays_through_current_public_interfaces():
    original = json.loads((SNAPSHOT / "report.json").read_text())
    replayed = audit(SNAPSHOT, replay=True)
    assert len(replayed["rows"]) == len(original["rows"]) == 12
    assert replayed["catalogue"] == original["catalogue"]
    for actual, expected in zip(replayed["rows"], original["rows"]):
        assert (actual["gene"], actual["frontend_species"]) == (expected["gene"], expected["frontend_species"])
        for phase in ("resolver", "sequence"):
            assert actual[phase]["status"] == expected[phase]["status"]
        if "measurements" in expected["sequence"]:
            assert actual["sequence"]["measurements"] == expected["sequence"]["measurements"]
            assert actual["sequence"]["proteins"] == expected["sequence"]["proteins"]
            assert actual["sequence"]["adapter_status"] == "ok"


@pytest.mark.skipif(os.getenv("ASRA_LIVE_SPECIES") != "1", reason="Opt-in live full frontend species audit")
@pytest.mark.parametrize("gene,species", [("CD28", s) for s in CD28_SPECIES] + [("SLC29A1", s) for s in FRONTEND_IDS])
def test_live_frontend_pair(gene, species, tmp_path):
    transport = RecordedHTTP(tmp_path)
    with patch.object(httpx, "get", transport.get):
        row = check_pair(gene, species)
    for phase in ("resolver", "sequence"):
        if row[phase]["status"] == "api_failure":
            pytest.skip(f"Live service failure during {phase}: {row[phase]['reason']}")
        assert row[phase]["status"] in {"ok", "incomplete", "orthologue_unavailable", "ambiguous_orthologue", "missing_sequence"}, row
    if "measurements" in row["sequence"]:
        assert row["sequence"]["adapter_status"] == "ok"
        assert row["sequence"]["proteins"]["animal"]["species"] == species
