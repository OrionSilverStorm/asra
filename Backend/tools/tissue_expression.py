"""GTEx and Bgee tissue expression module (Layer 4: ``tissue_expression``).

Implements a scientifically defensible human-versus-animal tissue-expression
analysis grounded in verified APIs:

1. Queries the GTEx Portal API v2 (``https://gtexportal.org/api/v2``, dataset
   ``gtex_v8``, GENCODE ``v26``, ``GRCh38/hg38``) for human gene metadata and
   bulk RNA-Seq median tissue expression (in ``TPM``) across 54 non-diseased
   human tissue sites annotated with ``UBERON`` / ``EFO`` ontology IDs.
2. Queries the Bgee REST API (``https://www.bgee.org/api/``, ``display_type=json``)
   to resolve the animal orthologous Ensembl gene identifier (via curated
   homology ``page=gene&action=homologs`` and ``action=gene_search``), species
   genome metadata (``action=general_info``), and ``FDR``-controlled anatomical
   expression calls (``action=expression``, reporting ``expressionState``,
   rank-normalised ``expressionScore`` on ``0-100``, ``expressionQuality``,
   ``fdr``, and ``dataTypesWithData``).
3. Aligns human and animal tissues using anatomical ontology identifiers
   (``UBERON:*``), separating **exact UBERON ID matches** from **curated
   biopsy-subpart to whole-organ UBERON correspondences** (e.g. GTEx ``Liver``
   ``UBERON:0001114`` *right lobe of liver* vs. Bgee ``UBERON:0002107`` *liver*).
4. Never computes cross-species fold changes or ratios between GTEx ``TPM`` and
   Bgee ``expressionScore`` (incompatible scales and experimental platforms),
   and explicitly distinguishes unannotated/unsampled animal tissues from
   biological absence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Union
import urllib.error
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# ── Shared Contract & Resolver Imports (with standalone fallback) ───────────

try:
    from contract import (
        LayerName,
        LayerResult,
        LayerStatus,
        Observation,
        SourceRecord,
        SpeciesId,
    )
except ImportError:
    try:
        from Backend.contract import (
            LayerName,
            LayerResult,
            LayerStatus,
            Observation,
            SourceRecord,
            SpeciesId,
        )
    except ImportError:
        SpeciesId = Literal[
            "mus_musculus",
            "rattus_norvegicus",
            "macaca_mulatta",
            "macaca_fascicularis",
            "canis_lupus_familiaris",
            "sus_scrofa",
            "oryctolagus_cuniculus",
            "cavia_porcellus",
            "danio_rerio",
        ]
        LayerName = Literal[
            "sequence", "localisation", "cell_expression", "tissue_expression"
        ]
        LayerStatus = Literal["ok", "incomplete", "unavailable"]

        class _CamelModel(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel, populate_by_name=True
            )

        class SourceRecord(BaseModel):
            """A citation: where a piece of evidence came from."""

            id: str
            source: str
            url: Optional[str] = None

        class Observation(_CamelModel):
            """One measured fact inside a layer (field name + display value)."""

            field: str
            value: str
            source_record_id: Optional[str] = None

        class LayerResult(BaseModel):
            """What every layer returns. snake_case on the wire, per the contract."""

            gene: Optional[str] = None
            species: SpeciesId
            layer: LayerName
            status: LayerStatus
            observations: list[Observation] = Field(default_factory=list)
            source_records: list[SourceRecord] = Field(default_factory=list)
            limitations: list[str] = Field(default_factory=list)
            data_version: Optional[str] = None

            model_config = ConfigDict(serialize_by_alias=True)


try:
    from tools.resolver import ResolvedQuery
except ImportError:
    try:
        from Backend.tools.resolver import ResolvedQuery
    except ImportError:

        @dataclass(frozen=True)
        class ResolvedQuery:
            """Everything a layer may need, resolved once and shared by all layers."""

            species: SpeciesId
            sequence: str = ""
            sequence_label: Optional[str] = None
            gene: Optional[str] = None


try:
    from tools.base import unavailable as _base_unavailable
except ImportError:
    try:
        from Backend.tools.base import unavailable as _base_unavailable
    except ImportError:

        def _base_unavailable(
            layer: LayerName, query: ResolvedQuery, reason: str
        ) -> LayerResult:
            return LayerResult(
                gene=query.gene,
                species=query.species,
                layer=layer,
                status="unavailable",
                limitations=[reason],
            )


log = logging.getLogger("asra.tools.tissue_expression")

# ── Constants ───────────────────────────────────────────────────────────────

GTEX_API_BASE = "https://gtexportal.org/api/v2"
DEFAULT_GTEX_DATASET_ID = "gtex_v8"
BGEE_API_BASE = "https://www.bgee.org/api/"
HUMAN_TAX_ID = 9606
DEFAULT_HTTP_TIMEOUT_SECONDS = 25.0
MIN_EXACT_MATCHES_FOR_OK = 5

SPECIES_TO_TAX_ID: dict[str, int] = {
    "homo_sapiens": 9606,
    "mus_musculus": 10090,
    "rattus_norvegicus": 10116,
    "macaca_mulatta": 9544,
    "macaca_fascicularis": 9541,
    "canis_lupus_familiaris": 9615,
    "sus_scrofa": 9823,
    "oryctolagus_cuniculus": 9986,
    "cavia_porcellus": 10141,
    "danio_rerio": 7955,
}

# Curated anatomical granularity mappings where GTEx annotates a surgical biopsy
# sub-structure UBERON ID while Bgee annotates the whole-organ UBERON ID.
# Reported separately from exact UBERON matches so granularity differences are
# always transparent.
SUBPART_TO_ORGAN_UBERON_MAP: tuple[dict[str, Any], ...] = (
    {
        "organ_label": "liver",
        "gtex_ontology_ids": ("UBERON:0001114",),  # right lobe of liver
        "bgee_ontology_ids": ("UBERON:0002107",),  # liver
        "relationship": "GTEx biopsy sub-structure (right lobe of liver, UBERON:0001114) <-> Bgee whole organ (liver, UBERON:0002107)",
    },
    {
        "organ_label": "lung",
        "gtex_ontology_ids": ("UBERON:0008952",),  # lower lobe of left lung
        "bgee_ontology_ids": ("UBERON:0002048",),  # lung
        "relationship": "GTEx biopsy sub-structure (lower lobe of left lung, UBERON:0008952) <-> Bgee whole organ (lung, UBERON:0002048)",
    },
    {
        "organ_label": "colon",
        "gtex_ontology_ids": ("UBERON:0001159", "UBERON:0001157"),  # sigmoid / transverse colon
        "bgee_ontology_ids": ("UBERON:0001155",),  # colon
        "relationship": "GTEx biopsy sub-regions (sigmoid/transverse colon, UBERON:0001159/UBERON:0001157) <-> Bgee whole organ (colon, UBERON:0001155)",
    },
    {
        "organ_label": "small intestine",
        "gtex_ontology_ids": ("UBERON:0001211",),  # terminal ileum
        "bgee_ontology_ids": ("UBERON:0002108", "UBERON:0002116", "UBERON:0000160"),  # small intestine / ileum / intestine
        "relationship": "GTEx biopsy sub-region (terminal ileum, UBERON:0001211) <-> Bgee organ (small intestine/intestine, UBERON:0002108/UBERON:0000160)",
    },
    {
        "organ_label": "heart",
        "gtex_ontology_ids": ("UBERON:0006566", "UBERON:0006631"),  # myocardium of left ventricle / left cardiac atrium
        "bgee_ontology_ids": ("UBERON:0000948", "UBERON:0002084"),  # heart / heart left ventricle
        "relationship": "GTEx cardiac sub-chambers (UBERON:0006566/UBERON:0006631) <-> Bgee organ (heart/left ventricle, UBERON:0000948/UBERON:0002084)",
    },
    {
        "organ_label": "blood",
        "gtex_ontology_ids": ("UBERON:0013756",),  # venous blood
        "bgee_ontology_ids": ("UBERON:0000178",),  # blood
        "relationship": "GTEx venous blood (UBERON:0013756) <-> Bgee blood (UBERON:0000178)",
    },
)

HttpJsonFetcher = Callable[[str], dict[str, Any]]


# ── HTTP & Parsing Helpers ──────────────────────────────────────────────────


def _default_http_get_json(
    url: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Perform a GET request and decode a JSON object with explicit timeout."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ASRA-TissueExpression/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object from {url}, got {type(data).__name__}")
        return data


def _coerce_query(
    query_or_gene: Union[ResolvedQuery, str, None],
    species: Optional[SpeciesId] = None,
) -> ResolvedQuery:
    """Accept either a canonical ``ResolvedQuery`` or ``(gene, species)`` arguments."""
    if hasattr(query_or_gene, "species") and hasattr(query_or_gene, "gene"):
        return query_or_gene  # type: ignore[return-value]

    target_species: SpeciesId = species or "mus_musculus"
    gene_str: Optional[str] = None
    if isinstance(query_or_gene, str) and query_or_gene.strip():
        gene_str = query_or_gene.strip().upper()
    return ResolvedQuery(
        species=target_species,
        sequence="",
        sequence_label=gene_str,
        gene=gene_str,
    )


def _fetch_gtex_human_profile(
    gene_symbol: str,
    dataset_id: str,
    http_get_json: HttpJsonFetcher,
) -> Optional[dict[str, Any]]:
    """Resolve human gene in GTEx and fetch median tissue expression across all tissues."""
    gene_url = (
        f"{GTEX_API_BASE}/reference/gene"
        f"?geneId={urllib.parse.quote(gene_symbol)}"
    )
    gene_payload = http_get_json(gene_url)
    gene_list = gene_payload.get("data") or []
    if not gene_list:
        return None

    # Prefer exact case-insensitive symbol match if multiple entries are returned
    selected = gene_list[0]
    for item in gene_list:
        if str(item.get("geneSymbolUpper", "")).upper() == gene_symbol.upper():
            selected = item
            break

    gencode_id = str(selected.get("gencodeId", "")).strip()
    if not gencode_id:
        return None
    ensembl_id = gencode_id.split(".")[0]

    expr_url = (
        f"{GTEX_API_BASE}/expression/medianGeneExpression"
        f"?gencodeId={urllib.parse.quote(gencode_id)}"
        f"&datasetId={urllib.parse.quote(dataset_id)}"
        "&itemsPerPage=100"
    )
    expr_payload = http_get_json(expr_url)
    expr_items = expr_payload.get("data") or []

    tissues: list[dict[str, Any]] = []
    for row in expr_items:
        tissues.append(
            {
                "tissueSiteDetailId": str(row.get("tissueSiteDetailId", "")),
                "ontologyId": str(row.get("ontologyId", "")),
                "median": float(row.get("median", 0.0)),
                "unit": str(row.get("unit", "TPM")),
                "datasetId": str(row.get("datasetId", dataset_id)),
            }
        )

    tissues.sort(key=lambda item: (-item["median"], item["tissueSiteDetailId"]))
    for rank_idx, item in enumerate(tissues, start=1):
        item["human_rank"] = rank_idx

    return {
        "gene_symbol": str(selected.get("geneSymbol") or gene_symbol),
        "gencode_id": gencode_id,
        "ensembl_id": ensembl_id,
        "entrez_gene_id": selected.get("entrezGeneId"),
        "gencode_version": str(selected.get("gencodeVersion", "v26")),
        "genome_build": str(selected.get("genomeBuild", "GRCh38/hg38")),
        "description": str(selected.get("description", "")),
        "dataset_id": dataset_id,
        "gene_url": gene_url,
        "expr_url": expr_url,
        "tissues": tissues,
    }


def _resolve_bgee_animal_gene(
    human_ensembl_id: str,
    gene_symbol: str,
    target_species: str,
    target_tax_id: int,
    http_get_json: HttpJsonFetcher,
) -> Optional[dict[str, Any]]:
    """Resolve the orthologous animal Ensembl gene ID via Bgee homologs or gene_search."""
    homologs_url = (
        f"{BGEE_API_BASE}?display_type=json&page=gene&action=homologs"
        f"&gene_id={urllib.parse.quote(human_ensembl_id)}&species_id={HUMAN_TAX_ID}"
    )
    candidates: list[dict[str, Any]] = []
    resolution_method = "bgee_ortholog"

    try:
        hom_payload = http_get_json(homologs_url)
        hom_data = hom_payload.get("data") or {}
        seen_ids: set[str] = set()
        for group in hom_data.get("orthologsByTaxon") or []:
            taxon_info = group.get("taxon") or {}
            for gene_obj in group.get("genes") or []:
                sp_obj = gene_obj.get("species") or {}
                sp_id = int(sp_obj.get("id", 0))
                gid = str(gene_obj.get("geneId", "")).strip()
                if sp_id == target_tax_id and gid and gid not in seen_ids:
                    seen_ids.add(gid)
                    candidates.append(
                        {
                            "gene_id": gid,
                            "name": str(gene_obj.get("name") or gene_symbol),
                            "taxon_lca": str(taxon_info.get("scientificName", "")),
                        }
                    )
    except Exception as exc:
        log.warning("Bgee homologs lookup failed for %s: %s", human_ensembl_id, exc)

    if not candidates:
        resolution_method = "bgee_gene_search"
        search_url = (
            f"{BGEE_API_BASE}?display_type=json&page=gene&action=gene_search"
            f"&query={urllib.parse.quote(gene_symbol)}"
        )
        search_payload = http_get_json(search_url)
        matches = (
            ((search_payload.get("data") or {}).get("result") or {}).get("geneMatches")
            or []
        )
        for match in matches:
            gene_obj = match.get("gene") or {}
            sp_obj = gene_obj.get("species") or {}
            if int(sp_obj.get("id", 0)) == target_tax_id:
                gid = str(gene_obj.get("geneId", "")).strip()
                gname = str(gene_obj.get("name") or "").strip()
                # Guard against paralog prefix matches (e.g. CD28 matching CD80 via synonym)
                if gid and (
                    gname.upper() == gene_symbol.upper()
                    or gname.upper().startswith(gene_symbol.upper())
                ):
                    candidates.append(
                        {
                            "gene_id": gid,
                            "name": gname or gene_symbol,
                            "taxon_lca": "",
                        }
                    )

    if not candidates:
        return None

    # Prefer exact symbol match (case-insensitive) when multiple paralogs exist (e.g. zebrafish a/b)
    selected = candidates[0]
    for cand in candidates:
        if cand["name"].upper() == gene_symbol.upper():
            selected = cand
            break

    return {
        "gene_id": selected["gene_id"],
        "name": selected["name"],
        "taxon_lca": selected["taxon_lca"],
        "all_ortholog_ids": [c["gene_id"] for c in candidates],
        "resolution_method": resolution_method,
        "species": target_species,
        "tax_id": target_tax_id,
    }


def _fetch_bgee_animal_profile(
    animal_gene_meta: dict[str, Any],
    http_get_json: HttpJsonFetcher,
) -> dict[str, Any]:
    """Fetch Bgee general_info and anatomical expression calls for the resolved animal gene."""
    gene_id = animal_gene_meta["gene_id"]
    tax_id = animal_gene_meta["tax_id"]

    info_url = (
        f"{BGEE_API_BASE}?display_type=json&page=gene&action=general_info"
        f"&gene_id={urllib.parse.quote(gene_id)}&species_id={tax_id}"
    )
    expr_url = (
        f"{BGEE_API_BASE}?display_type=json&page=gene&action=expression"
        f"&gene_id={urllib.parse.quote(gene_id)}&species_id={tax_id}"
    )

    genome_version = "unknown"
    expression_summary = ""
    description = ""
    try:
        info_payload = http_get_json(info_url)
        genes_list = (info_payload.get("data") or {}).get("genes") or []
        if genes_list:
            g0 = genes_list[0]
            description = str(g0.get("description") or "")
            expression_summary = str(g0.get("expressionSummary") or "")
            sp_info = g0.get("species") or {}
            genome_version = str(sp_info.get("genomeVersion") or "unknown")
    except Exception as exc:
        log.warning("Bgee general_info failed for %s: %s", gene_id, exc)

    expr_payload = http_get_json(expr_url)
    expr_data = expr_payload.get("data") or {}
    raw_calls = expr_data.get("calls") or []

    tissue_calls: list[dict[str, Any]] = []
    cell_type_calls: list[dict[str, Any]] = []
    for call in raw_calls:
        cond = call.get("condition") or {}
        anat = cond.get("anatEntity") or {}
        cell_type = cond.get("cellType")
        anat_id = str(anat.get("id") or "").strip()
        anat_name = str(anat.get("name") or "").strip()
        score_obj = call.get("expressionScore") or {}
        score_str = str(score_obj.get("expressionScore") or "0")
        try:
            score_val = float(score_str)
        except ValueError:
            score_val = 0.0

        parsed_call = {
            "anat_id": anat_id,
            "anat_name": anat_name,
            "cell_type_id": str(cell_type.get("id", "")) if isinstance(cell_type, dict) else None,
            "cell_type_name": str(cell_type.get("name", "")) if isinstance(cell_type, dict) else None,
            "expression_state": str(call.get("expressionState") or "expressed"),
            "expression_score": score_val,
            "expression_score_str": score_str,
            "score_confidence": str(score_obj.get("expressionScoreConfidence") or "unknown"),
            "expression_quality": str(call.get("expressionQuality") or "unknown"),
            "fdr": str(call.get("fdr") or "n/a"),
            "data_types": [str(dt) for dt in (call.get("dataTypesWithData") or [])],
        }
        if cell_type is None and anat_id.startswith("UBERON:"):
            tissue_calls.append(parsed_call)
        else:
            cell_type_calls.append(parsed_call)

    tissue_calls.sort(key=lambda item: (-item["expression_score"], item["anat_id"]))
    for rank_idx, item in enumerate(tissue_calls, start=1):
        item["animal_rank"] = rank_idx

    return {
        **animal_gene_meta,
        "genome_version": genome_version,
        "description": description,
        "expression_summary": expression_summary,
        "info_url": info_url,
        "expr_url": expr_url,
        "total_calls_count": len(raw_calls),
        "tissue_calls": tissue_calls,
        "cell_type_calls": cell_type_calls,
    }


# ── Public Entrypoint ───────────────────────────────────────────────────────


def run_tissue_expression(
    query: Union[ResolvedQuery, str, None],
    species: Optional[SpeciesId] = None,
    *,
    gtex_dataset_id: str = DEFAULT_GTEX_DATASET_ID,
    http_get_json: Optional[HttpJsonFetcher] = None,
) -> LayerResult:
    """Run GTEx (human) and Bgee (animal) cross-species tissue expression comparison.

    Accepts either a canonical ``ResolvedQuery``:
        ``run_tissue_expression(query)``
    or ``(gene, species)`` arguments:
        ``run_tissue_expression("SLC29A1", "mus_musculus")``
    """
    resolved = _coerce_query(query, species)
    if resolved.gene is None or not str(resolved.gene).strip():
        return _base_unavailable(
            "tissue_expression",
            resolved,
            "Needs a resolved gene identifier; none was supplied.",
        )

    gene_symbol = str(resolved.gene).strip().upper()
    target_species: SpeciesId = resolved.species
    fetcher = http_get_json or _default_http_get_json

    try:
        return _evaluate_tissue_expression(
            gene_symbol=gene_symbol,
            target_species=target_species,
            gtex_dataset_id=gtex_dataset_id,
            http_get_json=fetcher,
        )
    except Exception as exc:
        log.exception(
            "Tissue expression evaluation failed for gene=%s species=%s",
            gene_symbol,
            target_species,
        )
        return _base_unavailable(
            "tissue_expression",
            resolved,
            f"Tissue expression query failed ({type(exc).__name__}): {exc}",
        )


def _evaluate_tissue_expression(
    *,
    gene_symbol: str,
    target_species: SpeciesId,
    gtex_dataset_id: str,
    http_get_json: HttpJsonFetcher,
) -> LayerResult:
    """Core GTEx + Bgee evaluation logic separated for deterministic unit testing."""
    gtex_profile = _fetch_gtex_human_profile(
        gene_symbol=gene_symbol,
        dataset_id=gtex_dataset_id,
        http_get_json=http_get_json,
    )
    if gtex_profile is None or not gtex_profile["tissues"]:
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="tissue_expression",
            status="unavailable",
            observations=[],
            source_records=[
                SourceRecord(
                    id=f"gtex-{gtex_dataset_id}",
                    source=f"GTEx Portal API v2 ({gtex_dataset_id})",
                    url="https://gtexportal.org/home/",
                )
            ],
            limitations=[
                f"Human gene '{gene_symbol}' could not be resolved or has no median "
                f"tissue expression records in GTEx dataset '{gtex_dataset_id}'."
            ],
            data_version=f"GTEx API v2 ({gtex_dataset_id})",
        )

    human_ensembl_id = gtex_profile["ensembl_id"]
    gencode_id = gtex_profile["gencode_id"]
    gtex_tissues: list[dict[str, Any]] = gtex_profile["tissues"]

    gtex_source = SourceRecord(
        id=f"gtex-{gtex_dataset_id}-{human_ensembl_id}",
        source=(
            f"GTEx Portal API v2 ({gtex_dataset_id}, GENCODE {gtex_profile['gencode_version']}, "
            f"{gtex_profile['genome_build']}) median gene expression for {gene_symbol} ({gencode_id})"
        ),
        url=f"https://gtexportal.org/home/gene/{human_ensembl_id}",
    )
    human_ensembl_source = SourceRecord(
        id=f"ensembl-{human_ensembl_id}",
        source=f"Ensembl Homo_sapiens gene {gene_symbol} ({human_ensembl_id})",
        url=f"https://www.ensembl.org/Homo_sapiens/Gene/Summary?g={human_ensembl_id}",
    )

    source_records: list[SourceRecord] = [gtex_source, human_ensembl_source]

    expressed_human_tissues = [t for t in gtex_tissues if t["median"] >= 1.0]
    top_human_str = "; ".join(
        f"{t['tissueSiteDetailId']} ({t['ontologyId']})={t['median']:.2f} {t['unit']}"
        for t in gtex_tissues[:5]
    )

    observations: list[Observation] = [
        Observation(
            field="human_gene_identifier",
            value=(
                f"{gtex_profile['gene_symbol']} (gencodeId={gencode_id}; "
                f"ensemblId={human_ensembl_id}; entrezGeneId={gtex_profile['entrez_gene_id']}; "
                f"gencodeVersion={gtex_profile['gencode_version']}; "
                f"genomeBuild={gtex_profile['genome_build']})"
            ),
            source_record_id=human_ensembl_source.id,
        ),
        Observation(
            field="human_gtex_tissue_summary",
            value=(
                f"dataset={gtex_dataset_id}; total_tissues={len(gtex_tissues)}; "
                f"tissues_with_median_ge_1_tpm={len(expressed_human_tissues)}; "
                f"unit=TPM (bulk RNA-Seq median); top_tissues: {top_human_str}"
            ),
            source_record_id=gtex_source.id,
        ),
    ]

    target_tax_id = SPECIES_TO_TAX_ID.get(target_species)
    if target_tax_id is None:
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="tissue_expression",
            status="incomplete",
            observations=observations,
            source_records=source_records,
            limitations=[
                f"Comparison species '{target_species}' has no configured NCBI Taxonomy ID for Bgee."
            ],
            data_version=f"GTEx API v2 ({gtex_dataset_id}, GENCODE {gtex_profile['gencode_version']})",
        )

    # Resolve animal ortholog and fetch Bgee expression calls
    animal_gene_meta = _resolve_bgee_animal_gene(
        human_ensembl_id=human_ensembl_id,
        gene_symbol=gene_symbol,
        target_species=target_species,
        target_tax_id=target_tax_id,
        http_get_json=http_get_json,
    )
    if animal_gene_meta is None:
        bgee_db_source = SourceRecord(
            id=f"bgee-species-{target_tax_id}",
            source=f"Bgee gene expression database ({target_species}, NCBITaxon:{target_tax_id})",
            url="https://www.bgee.org/",
        )
        source_records.append(bgee_db_source)
        observations.extend(
            [
                Observation(
                    field="animal_gene_identifier",
                    value=(
                        f"unmeasured/unresolved: no orthologous or symbol-matched gene for "
                        f"{gene_symbol} ({human_ensembl_id}) found in Bgee for "
                        f"{target_species} (NCBITaxon:{target_tax_id})"
                    ),
                    source_record_id=bgee_db_source.id,
                ),
                Observation(
                    field="scale_and_comparability_assessment",
                    value=(
                        f"inconclusive: human GTEx ({gtex_dataset_id}) expression is measured "
                        f"across {len(gtex_tissues)} tissues in TPM, but no Bgee animal "
                        f"gene expression profile could be resolved for {target_species}"
                    ),
                    source_record_id=bgee_db_source.id,
                ),
            ]
        )
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="tissue_expression",
            status="incomplete",
            observations=observations,
            source_records=source_records,
            limitations=_build_limitations(
                gene_symbol=gene_symbol,
                target_species=target_species,
                gtex_dataset_id=gtex_dataset_id,
                exact_match_count=0,
                animal_tissue_call_count=0,
            ),
            data_version=f"GTEx API v2 ({gtex_dataset_id}) + Bgee REST API (NCBITaxon:{target_tax_id})",
        )

    bgee_profile = _fetch_bgee_animal_profile(
        animal_gene_meta=animal_gene_meta,
        http_get_json=http_get_json,
    )
    animal_gene_id = bgee_profile["gene_id"]
    animal_gene_name = bgee_profile["name"]
    animal_genome = bgee_profile["genome_version"]
    animal_tissue_calls: list[dict[str, Any]] = bgee_profile["tissue_calls"]

    bgee_source = SourceRecord(
        id=f"bgee-{target_tax_id}-{animal_gene_id}",
        source=(
            f"Bgee REST API v15 ({target_species}, NCBITaxon:{target_tax_id}, "
            f"genome {animal_genome}) expression calls for {animal_gene_name} ({animal_gene_id})"
        ),
        url=f"https://www.bgee.org/gene/{animal_gene_id}",
    )
    source_records.append(bgee_source)

    gold_count = sum(
        1 for c in animal_tissue_calls if c["expression_quality"].lower() == "gold"
    )
    silver_count = sum(
        1 for c in animal_tissue_calls if c["expression_quality"].lower() == "silver"
    )
    top_animal_str = (
        "; ".join(
            f"{c['anat_name']} ({c['anat_id']}): state={c['expression_state']}, "
            f"score={c['expression_score_str']} ({c['score_confidence']}), "
            f"quality={c['expression_quality']}, fdr={c['fdr']}, "
            f"assays={'+'.join(c['data_types'])}"
            for c in animal_tissue_calls[:5]
        )
        if animal_tissue_calls
        else "none"
    )

    ortholog_note = ""
    if len(bgee_profile["all_ortholog_ids"]) > 1:
        ortholog_note = (
            f"; co_orthologs={','.join(bgee_profile['all_ortholog_ids'])}"
        )

    observations.extend(
        [
            Observation(
                field="animal_gene_identifier",
                value=(
                    f"{animal_gene_name} (geneId={animal_gene_id}; species={target_species}; "
                    f"taxId=NCBITaxon:{target_tax_id}; genomeVersion={animal_genome}; "
                    f"resolution={bgee_profile['resolution_method']}{ortholog_note})"
                ),
                source_record_id=bgee_source.id,
            ),
            Observation(
                field="animal_bgee_expression_summary",
                value=(
                    f"total_calls={bgee_profile['total_calls_count']}; "
                    f"tissue_level_uberon_calls={len(animal_tissue_calls)} "
                    f"(gold={gold_count}, silver={silver_count}); "
                    f"cell_type_qualified_calls={len(bgee_profile['cell_type_calls'])}; "
                    f"unit=Bgee non-parametric expressionScore (0-100) + FDR-controlled present call; "
                    f"top_tissues: {top_animal_str}"
                ),
                source_record_id=bgee_source.id,
            ),
        ]
    )

    # ── Ontology Alignment: (A) Exact UBERON ID matches ────────────────────
    gtex_by_ont: dict[str, list[dict[str, Any]]] = {}
    for t in gtex_tissues:
        gtex_by_ont.setdefault(t["ontologyId"], []).append(t)

    bgee_by_ont: dict[str, dict[str, Any]] = {
        c["anat_id"]: c for c in animal_tissue_calls
    }

    exact_matches: list[dict[str, Any]] = []
    for ont_id, g_list in gtex_by_ont.items():
        if ont_id in bgee_by_ont:
            g_best = max(g_list, key=lambda x: x["median"])
            b_call = bgee_by_ont[ont_id]
            exact_matches.append(
                {
                    "ontology_id": ont_id,
                    "anat_name": b_call["anat_name"],
                    "gtex_tissues": g_list,
                    "gtex_primary": g_best,
                    "bgee_call": b_call,
                }
            )

    exact_matches.sort(
        key=lambda m: (-m["gtex_primary"]["median"], m["ontology_id"])
    )

    if exact_matches:
        exact_summary_items = [
            f"{m['ontology_id']} ({m['anat_name']}): "
            f"GTEx {m['gtex_primary']['tissueSiteDetailId']}={m['gtex_primary']['median']:.2f} TPM "
            f"(human rank {m['gtex_primary']['human_rank']}/{len(gtex_tissues)}) vs "
            f"Bgee {target_species} {m['bgee_call']['expression_state']} "
            f"score={m['bgee_call']['expression_score_str']} "
            f"(quality={m['bgee_call']['expression_quality']}, fdr={m['bgee_call']['fdr']}, "
            f"assays={'+'.join(m['bgee_call']['data_types'])}, "
            f"animal rank {m['bgee_call']['animal_rank']}/{len(animal_tissue_calls)})"
            for m in exact_matches[:8]
        ]
        observations.append(
            Observation(
                field="exact_uberon_tissue_matches",
                value=(
                    f"{len(exact_matches)} tissues matched by identical UBERON ID between "
                    f"human GTEx ({gtex_dataset_id}) and {target_species} Bgee: "
                    + "; ".join(exact_summary_items)
                ),
                source_record_id=bgee_source.id,
            )
        )
        # Emit individual observations for the top 5 exact UBERON-matched tissues
        for match in exact_matches[:5]:
            ont_compact = match["ontology_id"].lower().replace(":", "_")
            g_item = match["gtex_primary"]
            b_call = match["bgee_call"]
            observations.append(
                Observation(
                    field=f"matched_tissue_{ont_compact}",
                    value=(
                        f"{match['ontology_id']} ({match['anat_name']}): "
                        f"human GTEx {g_item['tissueSiteDetailId']} median={g_item['median']:.2f} TPM "
                        f"(rank {g_item['human_rank']}/{len(gtex_tissues)}) | "
                        f"{target_species} Bgee state={b_call['expression_state']}, "
                        f"expressionScore={b_call['expression_score_str']}/100 "
                        f"({b_call['score_confidence']} confidence, {b_call['expression_quality']} quality, "
                        f"fdr={b_call['fdr']}, assays={'+'.join(b_call['data_types'])}, "
                        f"rank {b_call['animal_rank']}/{len(animal_tissue_calls)}); "
                        "scales (TPM vs 0-100 rank score) are not directly comparable for fold-change calculation"
                    ),
                    source_record_id=bgee_source.id,
                )
            )
    else:
        observations.append(
            Observation(
                field="exact_uberon_tissue_matches",
                value=(
                    f"0 tissues matched by identical UBERON ID between human GTEx "
                    f"({gtex_dataset_id}) and {target_species} Bgee"
                ),
                source_record_id=bgee_source.id,
            )
        )

    # ── Ontology Alignment: (B) Biopsy sub-structure <-> whole-organ mappings
    subpart_correspondences: list[str] = []
    matched_gtex_ont_ids = {m["ontology_id"] for m in exact_matches}
    for mapping in SUBPART_TO_ORGAN_UBERON_MAP:
        g_candidates = [
            t
            for oid in mapping["gtex_ontology_ids"]
            for t in gtex_by_ont.get(oid, [])
        ]
        b_candidates = [
            bgee_by_ont[oid]
            for oid in mapping["bgee_ontology_ids"]
            if oid in bgee_by_ont
        ]
        if g_candidates and b_candidates:
            for t in g_candidates:
                matched_gtex_ont_ids.add(t["ontologyId"])
            g_desc = ", ".join(
                f"{t['tissueSiteDetailId']} ({t['ontologyId']})={t['median']:.2f} TPM"
                for t in g_candidates
            )
            b_best = b_candidates[0]
            subpart_correspondences.append(
                f"{mapping['organ_label']} [{mapping['relationship']}]: "
                f"human GTEx [{g_desc}] <-> {target_species} Bgee "
                f"[{b_best['anat_name']} ({b_best['anat_id']}) "
                f"state={b_best['expression_state']}, score={b_best['expression_score_str']}, "
                f"quality={b_best['expression_quality']}, fdr={b_best['fdr']}]"
            )

    if subpart_correspondences:
        observations.append(
            Observation(
                field="granularity_mapped_organ_correspondences",
                value=(
                    f"{len(subpart_correspondences)} organs aligned via biopsy sub-structure "
                    "(GTEx) to whole-organ (Bgee) UBERON relationships: "
                    + "; ".join(subpart_correspondences)
                ),
                source_record_id=gtex_source.id,
            )
        )

    # ── Missing / Unannotated Animal Tissues Among Top Human Tissues ───────
    unannotated_top_human = [
        t
        for t in gtex_tissues[:10]
        if t["ontologyId"] not in matched_gtex_ont_ids
    ]
    if unannotated_top_human:
        unannotated_str = ", ".join(
            f"{t['tissueSiteDetailId']} ({t['ontologyId']}={t['median']:.2f} TPM)"
            for t in unannotated_top_human[:5]
        )
        observations.append(
            Observation(
                field="missing_animal_tissue_coverage",
                value=(
                    f"Top human GTEx tissues without a matched {target_species} Bgee call: "
                    f"{unannotated_str}; absence from Bgee's returned expression calls "
                    "reflects unannotated or unsampled anatomical structures in the animal "
                    "dataset, NOT biological absence of expression"
                ),
                source_record_id=bgee_source.id,
            )
        )

    # ── Status & Comparability Assessment ──────────────────────────────────
    has_rich_coverage = len(exact_matches) >= MIN_EXACT_MATCHES_FOR_OK
    layer_status: LayerStatus = "ok" if has_rich_coverage else "incomplete"

    observations.append(
        Observation(
            field="scale_and_comparability_assessment",
            value=(
                f"{'sufficient qualitative tissue overlap' if has_rich_coverage else 'incomplete animal tissue coverage'}: "
                f"{len(exact_matches)} exact UBERON matches and "
                f"{len(subpart_correspondences)} sub-structure-to-organ UBERON correspondences "
                f"between human GTEx ({len(gtex_tissues)} tissues, bulk RNA-Seq median TPM) "
                f"and {target_species} Bgee ({len(animal_tissue_calls)} tissue-level UBERON calls, "
                "non-parametric 0-100 expressionScore across heterogeneous assays). "
                "Cross-species fold changes are NOT computed because GTEx TPM and Bgee "
                "expressionScore use incompatible units, normalisation, and assay modalities"
            ),
            source_record_id=gtex_source.id,
        )
    )

    data_version = (
        f"GTEx API v2 ({gtex_dataset_id}, GENCODE {gtex_profile['gencode_version']}, "
        f"{gtex_profile['genome_build']}) + Bgee REST API v15 "
        f"({target_species} {animal_genome})"
    )

    return LayerResult(
        gene=gene_symbol,
        species=target_species,
        layer="tissue_expression",
        status=layer_status,
        observations=observations,
        source_records=source_records,
        limitations=_build_limitations(
            gene_symbol=gene_symbol,
            target_species=target_species,
            gtex_dataset_id=gtex_dataset_id,
            exact_match_count=len(exact_matches),
            animal_tissue_call_count=len(animal_tissue_calls),
        ),
        data_version=data_version,
    )


def _build_limitations(
    *,
    gene_symbol: str,
    target_species: str,
    gtex_dataset_id: str,
    exact_match_count: int,
    animal_tissue_call_count: int,
) -> list[str]:
    """Construct scientific and methodological limitations for the LayerResult."""
    limitations = [
        (
            f"Incompatible quantitative scales (no cross-species fold changes): human GTEx "
            f"({gtex_dataset_id}) reports bulk RNA-Seq median Transcripts Per Million (TPM), "
            f"whereas Bgee reports a non-parametric rank-normalised expressionScore (0-100) "
            "and FDR-controlled present calls integrated across RNA-Seq, Affymetrix microarrays, "
            "in situ hybridization, and ESTs. Ratios or fold changes between GTEx TPM and Bgee "
            "expressionScore are mathematically invalid and are never computed."
        ),
        (
            f"Missing animal tissue annotations do not establish biological absence: Bgee "
            f"returned {animal_tissue_call_count} tissue-level UBERON expression calls for "
            f"{gene_symbol} in {target_species} ({exact_match_count} exact UBERON matches with "
            "GTEx). Human tissues lacking a corresponding Bgee call represent unsampled or "
            "unannotated anatomical entities in Bgee for that species, not absence of expression."
        ),
        (
            "Anatomical ontology granularity differences: GTEx frequently annotates surgical "
            "biopsy sub-structures (e.g. right lobe of liver UBERON:0001114, lower lobe of left "
            "lung UBERON:0008952, venous blood UBERON:0013756, sigmoid/transverse colon "
            "UBERON:0001159/UBERON:0001157), whereas Bgee often aggregates calls at the parent "
            "organ level (liver UBERON:0002107, lung UBERON:0002048, blood UBERON:0000178, colon "
            "UBERON:0001155); sub-structure and whole-organ terms are reported separately."
        ),
        (
            "Bulk tissue homogenate confounding and mRNA-versus-protein gap: whole-tissue RNA "
            "measurements average across parenchymal, stromal, endothelial, and infiltrating "
            "immune cells (e.g. T-cell transcripts in bulk spleen, blood, lung, or gut) and "
            "do not measure translated protein abundance, cell-surface receptor density, or "
            "isoform-specific subcellular targeting (such as ENT1/SLC29A1 mitochondrial localisation)."
        ),
    ]
    return limitations


# ── CLI Entrypoint ──────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run GTEx + Bgee cross-species tissue expression analysis and "
            "emit a canonical LayerResult JSON object."
        )
    )
    parser.add_argument(
        "gene",
        nargs="?",
        default="SLC29A1",
        help="Target gene symbol (default: SLC29A1).",
    )
    parser.add_argument(
        "species",
        nargs="?",
        default="mus_musculus",
        help="Comparison species Ensembl ID (default: mus_musculus).",
    )
    parser.add_argument(
        "--gtex-dataset-id",
        default=DEFAULT_GTEX_DATASET_ID,
        help=f"GTEx dataset ID (default: {DEFAULT_GTEX_DATASET_ID}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the LayerResult JSON output.",
    )
    args = parser.parse_args(argv)

    result = run_tissue_expression(
        args.gene,
        args.species,  # type: ignore[arg-type]
        gtex_dataset_id=args.gtex_dataset_id,
    )
    payload = result.model_dump(mode="json", by_alias=True)
    formatted = json.dumps(payload, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + "\n", encoding="utf-8")
    print(formatted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
