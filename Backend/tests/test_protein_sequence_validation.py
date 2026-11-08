"""Synthetic regressions; live biological checks require explicit opt-in."""
import json
import os
from hashlib import sha256
from unittest.mock import patch
import httpx
import pytest
from tools import resolver, sequence
from tools.sequence_adapter import to_layer_result

PAIRS = [("SLC29A1", "mus_musculus"), ("CD28", "macaca_mulatta"),
         ("CD28", "macaca_fascicularis"), ("CRBN", "oryctolagus_cuniculus")]


def verify(result, gene, species):
    assert result["gene"] == gene
    assert result["human"]["species"] == "homo_sapiens"
    assert result["animal"]["species"] == result["species"] == species
    m = result["measurements"]
    h, a = result["alignment"]["human"], result["alignment"]["animal"]
    assert len(h) == len(a) == m["alignment_columns"]
    assert m["exact_matches"] == sum(x == y and x in sequence.STANDARD_RESIDUES for x, y in zip(h, a))
    assert m["paired_columns"] == sum(x != "-" and y != "-" for x, y in zip(h, a))
    assert m["identity_percent"] == 100 * m["exact_matches"] / m["alignment_columns"]
    for side in ("human", "animal"):
        assert m[f"{side}_coverage_percent"] == 100 * m["paired_columns"] / len(result[side]["sequence"])
        assert result["provenance"][side] == {
            "protein_id": result[side]["protein_id"],
            "sequence_sha256": sha256(result[side]["sequence"].encode("ascii")).hexdigest()}
    assert result["source_records"][0]["url"].startswith("https://rest.ensembl.org/")
    assert result["data_version"] == "Ensembl REST homology; source release unknown"
    assert result["provenance"]["source_release"] == "unknown"
    assert to_layer_result(result).data_version == result["data_version"]


@pytest.mark.parametrize("gene,species", PAIRS)
def test_synthetic_pairs(gene, species):
    # Synthetic identifiers/sequences do not establish biological results.
    rel = {"type": "ortholog_one2one", "source": {
        "id": "H_TEST", "protein_id": "HP_TEST", "species": "homo_sapiens", "seq": "ACDEFGHIK"},
        "target": {"id": "A_TEST", "protein_id": "AP_TEST", "species": species, "seq": "ACDEFGHIKL"}}
    response = httpx.Response(200, json={"data": [{"homologies": [rel]}]},
        request=httpx.Request("GET", f"https://rest.ensembl.org/homology/symbol/homo_sapiens/{gene}"))
    with patch.object(resolver.httpx, "get", return_value=response):
        result = sequence.run_sequence(gene, species)
    assert result["human"]["protein_id"] == "HP_TEST"
    assert result["animal"]["protein_id"] == "AP_TEST"
    assert result["measurements"]["exact_matches"] == 9
    assert result["measurements"]["alignment_columns"] == 10
    assert result["measurements"]["paired_columns"] == 9
    verify(result, gene, species)


def test_cyp3a4_ambiguity_prevents_alignment():
    candidates = [{"type": "ortholog_one2many", "target": {"id": name, "species": "mus_musculus"}}
                  for name in ("TEST_MOUSE_1", "TEST_MOUSE_2")]
    response = httpx.Response(200, json={"data": [{"homologies": candidates}]},
                              request=httpx.Request("GET", "https://rest.ensembl.org/mock"))
    with patch.object(resolver.httpx, "get", return_value=response), patch.object(sequence, "align_proteins") as align:
        with pytest.raises(resolver.AmbiguousOrthologueError) as exc:
            sequence.run_sequence("CYP3A4", "mus_musculus")
    assert exc.value.candidates == candidates
    align.assert_not_called()


def test_gadph_is_never_rewritten():
    response = httpx.Response(400, json={"error": "synthetic unknown symbol"},
                              request=httpx.Request("GET", "https://rest.ensembl.org/mock"))
    with patch.object(resolver.httpx, "get", return_value=response) as get:
        with pytest.raises(resolver.EnsemblAPIError, match="GADPH"):
            sequence.run_sequence("GADPH", "mus_musculus")
    assert get.call_args.args[0].endswith("/GADPH")
    assert get.call_count == 1


@pytest.mark.skipif(os.getenv("ASRA_LIVE_ENSEMBL") != "1", reason="Opt-in live Ensembl check")
@pytest.mark.parametrize("gene,species", PAIRS + [("CYP3A4", "mus_musculus"), ("GADPH", "mus_musculus"), ("GAPDH", "mus_musculus")])
def test_live_pair(gene, species):
    try:
        result = sequence.run_sequence(gene, species)
    except resolver.AmbiguousOrthologueError as exc:
        print(json.dumps({"gene": gene, "species": species, "status": "ambiguous", "candidates": exc.candidates}))
        assert gene in {"CYP3A4", "GAPDH"}
        return
    except resolver.EnsemblAPIError as exc:
        if gene == "GADPH" and "HTTP 400" in str(exc):
            print(json.dumps({"gene": gene, "species": species, "status": "unavailable", "reason": str(exc)}))
            return
        raise
    assert gene not in {"CYP3A4", "GADPH"}
    verify(result, gene, species)
    print(json.dumps({k: result[k] for k in ("gene", "species", "status", "human", "animal", "measurements", "data_version", "provenance", "source_records")}))
