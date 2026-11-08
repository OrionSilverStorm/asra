from __future__ import annotations
"""Resolver tests use synthetic API fixtures; live verification is opt-in."""

from copy import deepcopy
import os
from unittest.mock import patch

import httpx
import pytest

from contract import AssessmentRequest
from tools import resolver


@pytest.fixture
def payload():
    # Deliberately short, synthetic sequences: these are not biological evidence.
    return {"data": [{"id": "ENSG_TEST", "homologies": [{
        "type": "ortholog_one2one",
        "taxonomy_level": "Synthetic test ancestor",
        "dn_ds": None,
        "source": {"id": "ENSG_TEST", "protein_id": "ENSP_TEST",
                   "species": "homo_sapiens", "seq": "MACK", "perc_id": 75.0},
        "target": {"id": "ENSMUSG_TEST", "protein_id": "ENSMUSP_TEST",
                   "species": "mus_musculus", "seq": "MACKT", "perc_id": 60.0},
    }]}]}


@pytest.fixture
def api():
    # Mock the HTTP boundary, keeping real response decoding and status checks.
    with patch.object(resolver.httpx, "get") as get:
        yield get


def respond(api, payload, status=200):
    api.return_value = httpx.Response(
        status, json=payload,
        request=httpx.Request("GET", "https://rest.ensembl.org/mock"),
    )


@pytest.mark.parametrize("species", [
    "mus_musculus", "oryctolagus_cuniculus", "cavia_porcellus",
    "macaca_mulatta", "macaca_fascicularis", "canis_lupus_familiaris",
    "felis_catus",  # Valid identifiers are not restricted by the frontend enum.
])
def test_success_and_request_parameters(api, payload, species):
    relationship = payload["data"][0]["homologies"][0]
    relationship["target"]["species"] = species
    respond(api, payload)
    result = resolver.resolve_orthologue(" SLC29A1 ", species)
    assert result["gene"] == "SLC29A1"
    assert result["species"] == species
    assert result["source"] == {
        "gene_id": "ENSG_TEST", "protein_id": "ENSP_TEST",
        "species": "homo_sapiens", "sequence": "MACK",
        "metadata": {"perc_id": 75.0},
    }
    assert result["target"]["gene_id"] == "ENSMUSG_TEST"
    assert result["target"]["protein_id"] == "ENSMUSP_TEST"
    assert result["target"]["species"] == species
    assert result["target"]["sequence"] == "MACKT"
    assert result["orthology"] == {
        "type": "ortholog_one2one", "taxonomy_level": "Synthetic test ancestor", "dn_ds": None,
    }
    assert result["source_url"] == str(api.return_value.url)
    api.assert_called_once_with(
        "https://rest.ensembl.org/homology/symbol/homo_sapiens/SLC29A1",
        params={"target_species": species, "type": "orthologues",
                "sequence": "protein", "aligned": 0, "format": "full"},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=resolver.REQUEST_TIMEOUT,
    )


@pytest.mark.parametrize("gene,species", [
    (None, "mus_musculus"), (123, "mus_musculus"), ("", "mus_musculus"),
    ("  ", "mus_musculus"), ("SLC29A1?x=y", "mus_musculus"),
    ("../SLC29A1", "mus_musculus"), ("SLC29A1", None),
    ("SLC29A1", 123), ("SLC29A1", ""), ("SLC29A1", "mouse"),
    ("SLC29A1", "Mus musculus"), ("SLC29A1", "mus_musculus&x=y"),
    ("SLC29A1", "homo_sapiens"),
])
def test_invalid_inputs_do_not_call_api(api, gene, species):
    with pytest.raises(ValueError):
        resolver.resolve_orthologue(gene, species)
    api.assert_not_called()


@pytest.mark.parametrize("status", [400, 404, 429, 500, 503])
def test_http_failures(api, status):
    respond(api, {"error": "Synthetic failure"}, status)
    with pytest.raises(resolver.EnsemblAPIError, match=f"HTTP {status}"):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


@pytest.mark.parametrize("error,match", [
    (httpx.ReadTimeout("slow response"), "timed out"),
    (httpx.ConnectTimeout("slow connection"), "timed out"),
    (httpx.ConnectError("connection refused"), "request failed"),
])
def test_transport_failures(api, error, match):
    api.side_effect = error
    with pytest.raises(resolver.EnsemblAPIError, match=match) as caught:
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")
    assert caught.value.__cause__ is error


@pytest.mark.parametrize("body", [
    None, [], {}, {"error": "bad request"}, {"data": None},
    {"data": [None]}, {"data": [{}]}, {"data": [{"homologies": {}}]},
    {"data": [{"homologies": [None]}]},
])
def test_malformed_payload(api, body):
    respond(api, body)
    with pytest.raises(resolver.InvalidEnsemblResponseError):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


def test_invalid_json(api):
    api.return_value = httpx.Response(
        200, text="<html>Not JSON</html>",
        request=httpx.Request("GET", "https://rest.ensembl.org/mock"),
    )
    with pytest.raises(resolver.InvalidEnsemblResponseError, match="valid JSON"):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


@pytest.mark.parametrize("body", [{"data": []}, {"data": [{"homologies": []}]}])
def test_no_orthologues(api, body):
    respond(api, body)
    with pytest.raises(resolver.OrthologueNotFoundError):
        resolver.resolve_orthologue("NONEXISTENT_TEST", "mus_musculus")


@pytest.mark.parametrize("side", ["source", "target"])
@pytest.mark.parametrize("sequence", [None, "", "   ", 123, "MA-CK", "MA CK"])
def test_missing_or_invalid_seq(api, payload, side, sequence):
    record = payload["data"][0]["homologies"][0][side]
    record["seq"] = sequence
    # An align_seq field must never mask a missing actual seq field.
    record["align_seq"] = "MACK"
    respond(api, payload)
    with pytest.raises(resolver.MissingSequenceError):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


def test_align_seq_alone_is_not_accepted(api, payload):
    target = payload["data"][0]["homologies"][0]["target"]
    target["align_seq"] = target.pop("seq")
    respond(api, payload)
    with pytest.raises(resolver.MissingSequenceError):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


@pytest.mark.parametrize("side", ["source", "target"])
@pytest.mark.parametrize("field,value", [
    ("id", None), ("protein_id", ""), ("species", "wrong_species"),
])
def test_invalid_identifiers(api, payload, side, field, value):
    payload["data"][0]["homologies"][0][side][field] = value
    respond(api, payload)
    with pytest.raises(resolver.InvalidEnsemblResponseError):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


@pytest.mark.parametrize("side", ["source", "target"])
def test_missing_protein_record(api, payload, side):
    del payload["data"][0]["homologies"][0][side]
    respond(api, payload)
    with pytest.raises(resolver.InvalidEnsemblResponseError):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


@pytest.mark.parametrize("kind", ["ortholog_one2many", "ortholog_many2many", None])
def test_single_non_one_to_one_target_requires_review(api, payload, kind):
    relationships = payload["data"][0]["homologies"]
    relationships[0]["type"] = kind
    respond(api, payload)
    with pytest.raises(resolver.AmbiguousOrthologueError) as caught:
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")
    assert caught.value.candidates == relationships


def test_multiple_orthologues_never_select_first(api, payload):
    relationships = payload["data"][0]["homologies"]
    alternative = deepcopy(relationships[0])
    alternative["target"]["id"] = "OTHER_TEST_GENE"
    alternative["target"]["seq"] = None
    relationships.append(alternative)
    respond(api, payload)
    with pytest.raises(resolver.AmbiguousOrthologueError) as caught:
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")
    assert caught.value.candidates == relationships
    assert len(caught.value.candidates) == 2


def test_multiple_source_genes_require_review(api, payload):
    # Even a second source with no target makes symbol resolution ambiguous.
    payload["data"].append({"id": "OTHER_HUMAN_GENE", "homologies": []})
    respond(api, payload)
    with pytest.raises(resolver.AmbiguousOrthologueError, match="2 source records"):
        resolver.resolve_orthologue("SLC29A1", "mus_musculus")


def test_preserves_sequence_only_pipeline_adapter(api):
    request = AssessmentRequest(species="mus_musculus", sequence="MACKMACKMACK")
    result = resolver.resolve(request)
    assert result == resolver.ResolvedQuery("mus_musculus", "MACKMACKMACK", None)
    assert result.gene is None
    api.assert_not_called()


@pytest.mark.skipif(os.getenv("ASRA_LIVE_ENSEMBL") != "1", reason="Opt-in live Ensembl check")
def test_live_slc29a1_mouse():
    # Live retrieval validates structure; fixed metrics belong to pinned fixtures.
    result = resolver.resolve_orthologue("SLC29A1", "mus_musculus")
    assert result["orthology"]["type"] == "ortholog_one2one"
    assert result["source"]["species"] == "homo_sapiens"
    assert result["target"]["species"] == "mus_musculus"
    assert result["source"]["sequence"]
    assert result["target"]["sequence"]
