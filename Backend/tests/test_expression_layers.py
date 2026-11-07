"""Offline tests for the three Role 4 pipeline layers (no network).

Each test replaces the HTTP helpers with small fakes and checks the contract
rules from CLAUDE.md: every observation cites a returned source record,
missing data is never reported as empty-but-ok, and nothing is computed
across GTEx and Bgee.
"""

import pytest

from contract import LayerResult
from tools import cell_expression, localisation, tissue_expression
from tools.resolver import AmbiguousOrthologueError, ResolvedQuery


def _query(gene="SLC29A1", species="mus_musculus") -> ResolvedQuery:
    """A resolved query with a gene, as the pipeline builds it."""
    return ResolvedQuery(species=species, sequence="", sequence_label=gene, gene=gene)


def _cited(result: LayerResult) -> bool:
    """True when every observation cites a source record the layer returned."""
    ids = {s.id for s in result.source_records}
    return all(o.source_record_id in ids for o in result.observations)


@pytest.fixture(autouse=True)
def _no_fixtures(monkeypatch):
    """Demo fixtures must not shadow the live code paths under test."""
    monkeypatch.setenv("ASRA_FIXTURES", "0")


# ── Localisation adapter ───────────────────────────────────────────────────


def _protein(acc: str, support: str) -> dict:
    """Minimal protein record in compare_localisation's measurements shape."""
    loc = {"id": "SL-0039", "name": "Cell membrane", "evidence_support": support, "evidence": []}
    return {"accession": acc, "scientific_name": "x", "reviewed": True, "entry_version": 1,
            "source_url": f"https://www.uniprot.org/uniprotkb/{acc}/entry", "release": "2026_04",
            "locations": [loc]}


def test_localisation_maps_partial_to_incomplete_and_adds_literature(monkeypatch):
    detail = {"status": "partial", "limitations": ["a", "a", "b"], "measurements": {
        "proteins": {"human": _protein("Q99808", "experimental"), "animal": _protein("Q9JIM1", "by_similarity")},
        "comparison": {"status": "overlap_only", "human_only_annotations": [], "animal_only_annotations": [],
                       "overlapping_locations": [{"id": "SL-0039", "name": "Cell membrane"}]}}}
    monkeypatch.setattr(localisation, "compare_localisation", lambda gene, species: detail)
    result = localisation.run_localisation(_query())
    fields = [o.field for o in result.observations]
    assert result.status == "incomplete" and result.data_version == "UniProt 2026_04"
    assert {"shared_compartments", "human_only_compartments", "literature_mitochondrial_targeting_signal"} <= set(fields)
    assert result.limitations == ["a", "b"]  # repeated caveats collapse
    assert _cited(result)


def test_localisation_failure_is_unavailable_without_data(monkeypatch):
    detail = {"status": "error", "limitations": ["human: UniProt returned HTTP 500."],
              "measurements": {"proteins": {"human": None, "animal": None}, "comparison": {}}}
    monkeypatch.setattr(localisation, "compare_localisation", lambda gene, species: detail)
    result = localisation.run_localisation(_query())
    assert result.status == "unavailable" and result.observations == [] and result.source_records == []


def test_localisation_without_gene_is_unavailable():
    assert localisation.run_localisation(_query(gene=None)).status == "unavailable"


# ── Cell expression (CELLxGENE Discover) ───────────────────────────────────


def _pop(fraction: float, cells: int) -> dict:
    """One WMG population as cell_expression._query returns it."""
    return {"tissue": "liver", "cell_type": "hepatocyte", "fraction": fraction,
            "expressing": int(fraction * cells), "cells": cells}


@pytest.fixture
def wmg(monkeypatch):
    """Fake Discover: one shared liver population plus one too-small population."""
    data = {"NCBITaxon:9606": {("UBERON:0002107", "CL:0000182"): _pop(0.5, 5000),
                               ("UBERON:0002107", "CL:0000091"): _pop(0.9, 50)},
            "NCBITaxon:10090": {("UBERON:0002107", "CL:0000182"): _pop(0.1, 2000),
                                ("UBERON:0002107", "CL:0000091"): _pop(0.1, 2000)}}
    monkeypatch.setattr(cell_expression, "_human_gene_id", lambda symbol: "ENSG1")
    monkeypatch.setattr(cell_expression, "_indexed", lambda taxon, gene_id: True)
    monkeypatch.setattr(cell_expression, "_query", lambda taxon, gene_id: data[taxon])
    monkeypatch.setattr(cell_expression, "_snapshot", lambda: "123")
    monkeypatch.setattr(cell_expression, "orthologue_gene_id", lambda gene, species: ("ENSMUSG1", None))


def test_mouse_compares_only_matched_populations_with_enough_cells(wmg):
    result = cell_expression.run_cell_expression(_query())
    detection = [o for o in result.observations if o.field.startswith("detection_")]
    assert [o.field for o in detection] == ["detection_UBERON0002107_CL0000182"]  # 50-cell population dropped
    assert "human 50.00%" in detection[0].value and "mouse 10.00%" in detection[0].value
    # Discover aggregates lack dataset provenance, so the layer is never "ok".
    assert result.status == "incomplete" and result.limitations[0].startswith("Partial provenance")
    assert _cited(result)


def test_unresolved_mouse_orthologue_reports_human_side_only(wmg, monkeypatch):
    def ambiguous(gene, species):
        raise AmbiguousOrthologueError("not one-to-one", [])
    monkeypatch.setattr(cell_expression, "orthologue_gene_id", ambiguous)
    result = cell_expression.run_cell_expression(_query())
    assert result.status == "incomplete"
    assert any(o.field == "animal_cell_expression" and "not one-to-one" in o.value for o in result.observations)


def test_non_mouse_replays_recorded_census_run_with_literature(monkeypatch):
    monkeypatch.setattr(cell_expression.importlib.util, "find_spec", lambda name: None)  # no cellxgene_census
    result = cell_expression.run_cell_expression(_query("CD28", "macaca_mulatta"))
    assert "(recorded run)" in result.data_version and "Replayed" in result.limitations[0]
    assert any(o.field == "literature_macaque_cd4_effector_memory" for o in result.observations)
    assert _cited(result)


def test_macaque_literature_is_not_attached_to_other_species(wmg, monkeypatch):
    monkeypatch.setattr(cell_expression.importlib.util, "find_spec", lambda name: None)
    result = cell_expression.run_cell_expression(_query("CD28", "sus_scrofa"))
    fields = {o.field for o in result.observations}
    assert "literature_human_cd4_effector_memory" in fields
    assert "literature_macaque_cd4_effector_memory" not in fields


# ── Tissue expression (GTEx + Bgee) ────────────────────────────────────────


def _fake_get(url: str, **params) -> dict:
    """Fake GTEx/Bgee: liver matches at organ level, adrenal exactly, testis has no call."""
    if url.endswith("/reference/gene"):
        return {"data": [{"geneSymbol": "SLC29A1", "gencodeId": "ENSG1.1"}]}
    if url.endswith("/medianGeneExpression"):
        return {"data": [
            {"tissueSiteDetailId": "Liver", "ontologyId": "UBERON:0001114", "median": 20.0},
            {"tissueSiteDetailId": "Adrenal_Gland", "ontologyId": "UBERON:0002369", "median": 50.0},
            {"tissueSiteDetailId": "Testis", "ontologyId": "UBERON:0000473", "median": 5.0},
            {"tissueSiteDetailId": "Cells_Cultured_fibroblasts", "ontologyId": "EFO:0002009", "median": 99.0}]}
    call = lambda uid, name: {"condition": {"anatEntity": {"id": uid, "name": name}}, "expressionState": "expressed",
                              "expressionScore": {"expressionScore": "80"}, "expressionQuality": "gold",
                              "dataTypesWithData": ["RNA-Seq"]}
    return {"data": {"calls": [call("UBERON:0002107", "liver"), call("UBERON:0002369", "adrenal gland")]}}


@pytest.fixture
def gtex_bgee(monkeypatch):
    """Route tissue_expression's HTTP through the fake."""
    monkeypatch.setattr(tissue_expression, "_get", _fake_get)
    monkeypatch.setattr(tissue_expression, "orthologue_gene_id", lambda gene, species: ("ENSMUSG1", None))


def test_tissue_matches_exact_then_organ_level_and_never_divides(gtex_bgee):
    result = tissue_expression.run_tissue_expression(_query())
    values = {o.field: o.value for o in result.observations}
    assert "[exact UBERON match]" in values["tissue_UBERON0002369"]
    assert "[organ-level match from UBERON:0001114]" in values["tissue_UBERON0002107"]
    assert "Testis 5.0 TPM" in values["human_expressed_without_animal_call"]
    assert "fibroblasts" not in values["human_top_tissues"]  # cell lines are not tissues
    assert result.status == "ok" and _cited(result)
    assert not any("fold" in v.lower() or "ratio" in v.lower() for v in values.values())


def test_tissue_without_animal_gene_keeps_human_side_as_incomplete(gtex_bgee, monkeypatch):
    def ambiguous(gene, species):
        raise AmbiguousOrthologueError("not one-to-one", [])
    monkeypatch.setattr(tissue_expression, "orthologue_gene_id", ambiguous)
    result = tissue_expression.run_tissue_expression(_query())
    assert result.status == "incomplete" and [o.field for o in result.observations] == ["human_top_tissues"]
    assert "not one-to-one" in result.limitations[0]
