from __future__ import annotations
"""Layer 3, cell-type expression: detection fractions per cell population.

Sources, chosen per comparison species:
- Mouse: CELLxGENE Discover gene-expression API (WMG v2) for both species.
  Populations are matched on exact UBERON tissue + CL cell-type IDs, so a
  match is an ontology match, never a fuzzy label match. Always `incomplete`:
  Discover aggregates cannot name the datasets/assays behind each value.
- Other species (e.g. macaque, which Discover does not index): the CELLxGENE
  Census audit in tools/cell_census.py, run live when `cellxgene_census` is
  installed, else replayed from its recorded live run in data/benchmarks/.
  Without either, only the human side is reported and the layer is
  `incomplete`.

Python computes every value here; the curated literature from
tools/literature.py is appended as separate, labelled evidence.
"""

import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from statistics import median

import httpx

from contract import LayerResult, Observation, SourceRecord
from tools.base import unavailable
from tools.cell_census import run_census_expression
from tools.fixtures import fixture
from tools.literature import literature
from tools.resolver import OrthologueResolutionError, ResolvedQuery, orthologue_gene_id

WMG = "https://api.cellxgene.cziscience.com/wmg/v2"
EXPLORER_URL = "https://cellxgene.cziscience.com/gene-expression"
TIMEOUT = 60.0
TAXON = {"homo_sapiens": "NCBITaxon:9606", "mus_musculus": "NCBITaxon:10090"}
HEALTHY = "PATO:0000461"  # disease filter "normal": exclude diseased samples
MIN_CELLS = 500  # populations smaller than this (either side) are not reported or compared
SHOWN = 8  # matched populations reported as observations (largest differences first)
ROOT_CELL = "CL:0000000"  # the generic "cell" roll-up, not a population
BENCHMARKS = Path(__file__).resolve().parents[1] / "data" / "benchmarks"

LIMITATIONS = [
    "Detection fraction is the share of cells with at least one read for the gene; RNA detection is "
    "not protein abundance, and a zero is a technical non-detection, not biological absence.",
    "CELLxGENE Discover aggregates many datasets per tissue and cell type; dataset IDs, assays and "
    "donors behind each aggregate are not itemised by this API.",
    "Matched populations share exact Cell Ontology and UBERON IDs, but annotation practice differs "
    "between human and animal studies, so equivalent labels need not be equivalent cells.",
    "Values from independent experiments are descriptive only; no normalised cross-species fold "
    "change is computed.",
    "Genes with many pseudogenes or paralogues (e.g. mouse Gapdh) lose multi-mapping reads during "
    "alignment, which lowers detection for technical reasons in whole datasets.",
]


# ── CELLxGENE Discover (WMG) helpers ───────────────────────────────────────


@lru_cache(maxsize=1)
def _dimensions() -> dict:
    """WMG gene/tissue index (~3.5 MB), fetched once per process."""
    response = httpx.get(f"{WMG}/primary_filter_dimensions", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _human_gene_id(symbol: str) -> str | None:
    """Ensembl ID of a human gene symbol in the WMG index, or None."""
    genes = _dimensions()["gene_terms"][TAXON["homo_sapiens"]]
    return next((gid for item in genes for gid, name in item.items() if name.upper() == symbol.upper()), None)


def _indexed(taxon: str, gene_id: str) -> bool:
    """True when WMG indexes this Ensembl gene ID for the organism."""
    return any(gene_id in item for item in _dimensions()["gene_terms"][taxon])


def _query(taxon: str, gene_id: str) -> dict[tuple[str, str], dict]:
    """{(tissue_id, cell_type_id): population} for one gene in healthy tissue."""
    empty: list = []
    response = httpx.post(f"{WMG}/query", timeout=TIMEOUT, json={"is_rollup": True, "filter": {
        "gene_ontology_term_ids": [gene_id], "organism_ontology_term_id": taxon,
        "disease_ontology_term_ids": [HEALTHY], "dataset_ids": empty,
        "development_stage_ontology_term_ids": empty, "self_reported_ethnicity_ontology_term_ids": empty,
        "sex_ontology_term_ids": empty, "publication_citations": empty}})
    response.raise_for_status()
    data = response.json()
    labels = data["term_id_labels"]["cell_types"]
    tissue_names = {tid: name for item in _dimensions()["tissue_terms"][taxon] for tid, name in item.items()}
    populations = {}
    for tissue, cells in data["expression_summary"].get(gene_id, {}).items():
        for cell, stats in cells.items():
            label = labels.get(tissue, {}).get(cell, {}).get("aggregated")
            # Skip tissue totals, the root "cell" roll-up and unlabelled entries.
            if cell in {"tissue_stats", ROOT_CELL} or label is None:
                continue
            populations[(tissue, cell)] = {
                "tissue": tissue_names.get(tissue, tissue), "cell_type": label["name"],
                "fraction": stats["aggregated"]["pc"], "expressing": stats["aggregated"]["n"],
                "cells": label["total_count"]}
    return populations


def _snapshot() -> str:
    """WMG data snapshot id, recorded as the layer's data version."""
    return str(_dimensions().get("snapshot_id", "unknown"))


def _source(organism: str, symbol: str, gene_id: str) -> SourceRecord:
    """One citable record per organism/gene query."""
    return SourceRecord(id=f"cellxgene-wmg:{gene_id}", url=EXPLORER_URL,
                        source=f"CELLxGENE Discover gene expression, {organism} {symbol} ({gene_id}), "
                               f"healthy tissue, snapshot {_snapshot()}")


def _describe(p: dict) -> str:
    """'7.38% (49,606 expressing of 672,233 cells)', omitting the denominator when total_count is from a broader cell pool."""
    if p["cells"] > 0 and round(p["fraction"] * p["cells"]) == p["expressing"] and abs(p["expressing"] / p["cells"] - p["fraction"]) < 1e-4:
        return f"{p['fraction']:.2%} ({p['expressing']:,} expressing of {p['cells']:,} cells)"
    return f"{p['fraction']:.2%} ({p['expressing']:,} expressing cells)"


def _field(key: tuple[str, str]) -> str:
    """Citable field name, e.g. 'detection_UBERON0000178_CL0000905'."""
    return "detection_" + "_".join(k.replace(":", "") for k in key)


def _top_human(human: dict, source: SourceRecord) -> Observation:
    """The five human populations where the gene is most often detected."""
    big = sorted((p for p in human.values() if p["cells"] >= MIN_CELLS), key=lambda p: -p["fraction"])[:5]
    value = "; ".join(f"{p['tissue']} / {p['cell_type']}: {_describe(p)}" for p in big) or "None reported"
    return Observation(field="human_top_populations", value=value, source_record_id=source.id)


# ── Comparisons ────────────────────────────────────────────────────────────


def _mouse(query: ResolvedQuery, human: dict, human_src: SourceRecord) -> LayerResult:
    """Human vs mouse on exactly matched (tissue, cell type) populations."""
    try:
        mouse_id, note = orthologue_gene_id(query.gene, "mus_musculus")  # Ensembl orthologue
    except OrthologueResolutionError as exc:
        return _human_only(query, human, human_src, f"Mouse orthologue unresolved: {exc}")
    if not _indexed(TAXON["mus_musculus"], mouse_id):
        return _human_only(query, human, human_src, f"Mouse orthologue {mouse_id} is not indexed by CELLxGENE Discover.")
    mouse = _query(TAXON["mus_musculus"], mouse_id)
    mouse_src = _source("Mus musculus", query.gene, mouse_id)
    shared = [k for k in human.keys() & mouse.keys() if min(human[k]["cells"], mouse[k]["cells"]) >= MIN_CELLS]
    # Largest absolute difference in detection fraction first (descriptive ordering only).
    shared.sort(key=lambda k: -abs(human[k]["fraction"] - mouse[k]["fraction"]))
    observations = [_top_human(human, human_src), Observation(
        field="matched_population_count", source_record_id=mouse_src.id,
        value=f"{len(shared)} populations with the same UBERON tissue and CL cell type and >= {MIN_CELLS} "
              f"cells in both species; the {min(SHOWN, len(shared))} with the largest difference are listed")]
    if shared:
        # Medians across ALL matched populations: a gap here that mirrors the
        # per-population gaps points to a technical (whole-dataset) offset, such
        # as reads lost to pseudogene multi-mapping, not a cell-type difference.
        med = {side: median(pops[k]["fraction"] for k in shared) for side, pops in (("human", human), ("mouse", mouse))}
        observations.append(Observation(field="median_detection_all_matched", source_record_id=mouse_src.id,
                                        value=f"median across the {len(shared)} matched populations: human "
                                              f"{med['human']:.2%}; mouse {med['mouse']:.2%}"))
    for key in shared[:SHOWN]:
        h, m = human[key], mouse[key]
        observations.append(Observation(field=_field(key), source_record_id=mouse_src.id,
                                        value=f"{h['tissue']} / {h['cell_type']} ({key[0]}, {key[1]}): "
                                              f"human {_describe(h)}; mouse {_describe(m)}"))
    # Always "incomplete": Discover cannot itemise the datasets, assays and donors
    # behind each aggregate, which the design doc requires before a cross-species
    # comparison is ranked. Findings resting on it are therefore flagged.
    provenance = ("Partial provenance: each population is a CELLxGENE Discover aggregate across unnamed "
                  "datasets and assays, so these comparisons cannot be ranked as concerns on their own.")
    return LayerResult(gene=query.gene, species=query.species, layer="cell_expression",
                       status="incomplete", observations=observations, source_records=[human_src, mouse_src],
                       limitations=[provenance] + ([note] if note else []) + LIMITATIONS
                       + ([] if shared else ["No matched populations had enough cells in both species."]),
                       data_version=f"CELLxGENE Discover WMG snapshot {_snapshot()}")


def _human_only(query: ResolvedQuery, human: dict, human_src: SourceRecord, reason: str) -> LayerResult:
    """Human detection only: the animal side could not be measured."""
    gap = Observation(field="animal_cell_expression", source_record_id=human_src.id,
                      value=f"Not measured for {query.species}: {reason}")
    return LayerResult(gene=query.gene, species=query.species, layer="cell_expression", status="incomplete",
                       observations=[_top_human(human, human_src), gap], source_records=[human_src],
                       limitations=[reason, *LIMITATIONS], data_version=f"CELLxGENE Discover WMG snapshot {_snapshot()}")


def _census(query: ResolvedQuery) -> LayerResult | None:
    """Census audit: recorded benchmark when available, else live when installed, else None."""
    recorded = BENCHMARKS / f"census_{query.gene}_{query.species}.json"
    if recorded.exists():
        result = LayerResult.model_validate(json.loads(recorded.read_text(encoding="utf-8")))
        note = (f"Replayed a recorded live CELLxGENE Census run ({recorded.name}) rather than "
                "running a live remote TileDB-SOMA scan.")
        return result.model_copy(update={"limitations": [note, *result.limitations],
                                         "data_version": f"{result.data_version} (recorded run)"})
    if importlib.util.find_spec("cellxgene_census"):
        return run_census_expression(query)
    return None


def _with_literature(result: LayerResult) -> LayerResult:
    """Append curated literature evidence (separate, labelled) to a result with data."""
    observations, sources = literature("cell_expression", result.gene, result.species)
    if not observations or result.status == "unavailable":
        return result
    return result.model_copy(update={"observations": result.observations + observations,
                                     "source_records": result.source_records + sources})


def run_cell_expression(query: ResolvedQuery) -> LayerResult:
    """Pipeline layer: (ResolvedQuery) -> LayerResult."""
    # Offline demo evidence first, only when ASRA_FIXTURES is on (tools/fixtures.py).
    demo = fixture("cell_expression", query)
    if demo:
        return demo
    if query.gene is None:
        return unavailable("cell_expression", query, "Needs a resolved gene identifier; none was supplied.")
    # Species Discover cannot cover go to the Census audit when one is available.
    if query.species != "mus_musculus":
        census = _census(query)
        if census is not None and census.status != "unavailable":
            return _with_literature(census)
    human_id = _human_gene_id(query.gene)
    if human_id is None:
        return unavailable("cell_expression", query, f"{query.gene} is not indexed by CELLxGENE Discover for human.")
    human = _query(TAXON["homo_sapiens"], human_id)
    human_src = _source("Homo sapiens", query.gene, human_id)
    if query.species == "mus_musculus":
        return _with_literature(_mouse(query, human, human_src))
    return _with_literature(_human_only(query, human, human_src,
                                        "CELLxGENE Discover indexes human and mouse only, and no CELLxGENE "
                                        "Census audit is available for this gene and species."))
