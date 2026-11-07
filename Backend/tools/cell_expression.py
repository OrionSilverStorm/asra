"""CELLxGENE Census cell-type expression module (Layer 3: ``cell_expression``).

Implements a bounded, scientifically defensible cell-type expression analysis
grounded in the pinned CELLxGENE Census release ``2025-11-08``:

1. Queries the pinned CELLxGENE Census release ``2025-11-08`` via ``cellxgene_census``.
2. Performs a bounded human ``CD28`` (``ENSG00000178562``) expression analysis in
   primary ``effector memory CD4-positive, alpha-beta T cell`` (``CL:0000905`` /
   ``CL:0001087``) populations from one well-characterised healthy human PBMC
   dataset (default: ``ed5d841d-6346-47d4-ab2f-7119ad7e3a35``, Hao et al.,
   *Cell* 2021, NYGC multimodal PBMC reference atlas).
3. Verifies dataset-level gene measurement in ``feature_dataset_presence_matrix``
   before reading or interpreting any ``X['raw']`` zero UMI counts.
4. For rhesus macaque (``macaca_mulatta``) ``CD28`` (``ENSMMUG00000057214``),
   verifies and reports the absence of comparable ``CD4+`` effector-memory T-cell
   (``CL:0000905`` / ``CL:0001087``) and blood/lymphoid datasets across all 19
   macaque datasets in release ``2025-11-08``, while auditing the two generic
   ``T cell`` (``CL:0000084``) datasets.
5. Explicitly distinguishes ``unmeasured`` (feature absent from a dataset's
   ``feature_dataset_presence_matrix``), ``undetected`` (``0`` UMI counts in a
   measured dataset/cell due to scRNA-seq/snRNA-seq dropout or low mRNA copy
   number), and ``biologically absent`` (true lack of functional expression).
6. Returns an inconclusive cross-species comparison (``status="incomplete"``)
   with traceable ``SourceRecord`` citations and explicit scientific limitations.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from statistics import median
from typing import Any, Literal, Optional, Union

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


log = logging.getLogger("asra.tools.cell_expression")

# ── Constants ───────────────────────────────────────────────────────────────

DEFAULT_CENSUS_VERSION = "2025-11-08"
# Bounded healthy human PBMC reference dataset in CELLxGENE Census 2025-11-08:
# Hao et al., Cell 2021 ("nygc multimodal pbmc", 161,764 primary blood cells
# across 8 normal donors, 10x 3' v3, distinguishes CL:0000905 CD4+ TEM from
# CL:0000904 CD4+ TCM, CL:0000895 CD4+ naive, and CL:0000624 CD4+ T cells).
DEFAULT_HUMAN_DATASET_ID = "ed5d841d-6346-47d4-ab2f-7119ad7e3a35"

TARGET_CD4_EM_ONTOLOGY_IDS: tuple[str, ...] = (
    "CL:0000905",  # effector memory CD4-positive, alpha-beta T cell
    "CL:0001087",  # effector memory CD4-positive, alpha-beta T cell, terminally differentiated
)
CD4_ONTOLOGY_IDS: tuple[str, ...] = (
    "CL:0000905",
    "CL:0001087",
    "CL:0000904",  # central memory CD4-positive, alpha-beta T cell
    "CL:0000897",  # CD4-positive, alpha-beta memory T cell
    "CL:0000895",  # naive thymus-derived CD4-positive, alpha-beta T cell
    "CL:0000624",  # CD4-positive, alpha-beta T cell
)
GENERIC_T_CELL_ONTOLOGY_IDS: tuple[str, ...] = (
    "CL:0000084",  # T cell
    "CL:0000940",  # mucosal invariant T cell
)
BLOOD_LYMPHOID_GENERAL_TISSUES: frozenset[str] = frozenset(
    {"blood", "lymph node", "spleen", "bone marrow", "thymus"}
)

KNOWN_ENSEMBL_GENE_IDS: dict[tuple[str, str], str] = {
    ("homo_sapiens", "CD28"): "ENSG00000178562",
    ("macaca_mulatta", "CD28"): "ENSMMUG00000057214",
}

CENSUS_DOCS_URL = "https://chanzuckerberg.github.io/cellxgene-census/"
CELLXGENE_EXPLORER_BASE_URL = "https://cellxgene.cziscience.com/e"
ENSEMBL_SPECIES_PATH: dict[str, str] = {
    "homo_sapiens": "Homo_sapiens",
    "macaca_mulatta": "Macaca_mulatta",
    "mus_musculus": "Mus_musculus",
}


# ── Internal SOMA Helpers ───────────────────────────────────────────────────


def _table_to_rows(concat_result: Any) -> list[dict[str, Any]]:
    """Convert a PyArrow Table or mocked reader result into a list of row dicts."""
    if hasattr(concat_result, "to_pylist"):
        return list(concat_result.to_pylist())
    if hasattr(concat_result, "to_pandas"):
        return list(concat_result.to_pandas().to_dict(orient="records"))
    return list(concat_result)


def _check_gene_presence_by_dataset(
    rna_measurement: Any,
    feature_soma_joinid: int,
    dataset_id_by_joinid: dict[int, str],
) -> set[str]:
    """Return the set of dataset_ids in which ``feature_soma_joinid`` is measured."""
    presence_concat = (
        rna_measurement["feature_dataset_presence_matrix"]
        .read(coords=(slice(None), [feature_soma_joinid]))
        .tables()
        .concat()
    )
    rows = _table_to_rows(presence_concat)
    measured_joinids = {
        int(r["soma_dim_0"]) for r in rows if float(r.get("soma_data", 0)) != 0.0
    }
    return {
        dataset_id_by_joinid[jid]
        for jid in measured_joinids
        if jid in dataset_id_by_joinid
    }


def _resolve_var_gene(
    rna_measurement: Any,
    gene_symbol: str,
    organism_key: str,
) -> Optional[dict[str, Any]]:
    """Find the target gene row in ``rna.var`` by symbol or Ensembl ID."""
    gene_upper = gene_symbol.strip().upper()
    expected_ensembl_id = KNOWN_ENSEMBL_GENE_IDS.get((organism_key, gene_upper))
    var_rows = _table_to_rows(rna_measurement.var.read().concat())
    for row in var_rows:
        feature_name = str(row.get("feature_name", "")).strip()
        feature_id = str(row.get("feature_id", "")).strip()
        if (
            feature_name.upper() == gene_upper
            or feature_id.upper() == gene_upper
            or (expected_ensembl_id and feature_id == expected_ensembl_id)
        ):
            return {
                "soma_joinid": int(row["soma_joinid"]),
                "feature_id": feature_id,
                "feature_name": feature_name,
                "feature_type": str(row.get("feature_type", "protein_coding")),
                "feature_length": int(row.get("feature_length", 0)),
                "nnz": int(row.get("nnz", 0)),
                "n_measured_obs": int(row.get("n_measured_obs", 0)),
            }
    return None


def _compute_raw_expression_stats(
    rna_measurement: Any,
    obs_rows: list[dict[str, Any]],
    feature_soma_joinid: int,
) -> dict[str, Any]:
    """Slice ``X['raw']`` for ``(obs_joinids, [feature_soma_joinid])`` and compute stats.

    Must only be called AFTER confirming the dataset is present in
    ``feature_dataset_presence_matrix`` for ``feature_soma_joinid``.
    """
    obs_joinids = [int(r["soma_joinid"]) for r in obs_rows]
    n_total = len(obs_joinids)
    if n_total == 0:
        return {
            "n_total": 0,
            "n_detected": 0,
            "n_undetected": 0,
            "detection_fraction": 0.0,
            "mean_raw_all": 0.0,
            "mean_raw_detected": 0.0,
            "max_raw": 0.0,
        }

    obs_id_set = set(obs_joinids)
    x_concat = (
        rna_measurement["X"]["raw"]
        .read(coords=(obs_joinids, [feature_soma_joinid]))
        .tables()
        .concat()
    )
    x_rows = _table_to_rows(x_concat)

    detected_values: dict[int, float] = {}
    for row in x_rows:
        obs_jid = int(row["soma_dim_0"])
        val = float(row.get("soma_data", 0.0))
        if obs_jid in obs_id_set and val > 0.0:
            detected_values[obs_jid] = val

    n_detected = len(detected_values)
    n_undetected = n_total - n_detected
    total_umi = sum(detected_values.values())
    detection_fraction = n_detected / n_total
    mean_raw_all = total_umi / n_total
    mean_raw_detected = (total_umi / n_detected) if n_detected > 0 else 0.0
    max_raw = max(detected_values.values()) if detected_values else 0.0

    return {
        "n_total": n_total,
        "n_detected": n_detected,
        "n_undetected": n_undetected,
        "detection_fraction": detection_fraction,
        "mean_raw_all": mean_raw_all,
        "mean_raw_detected": mean_raw_detected,
        "max_raw": max_raw,
    }


def _dataset_source_record(
    dataset_id: str,
    dataset_info: dict[str, Any],
    default_label: str,
) -> SourceRecord:
    """Build a verifiable SourceRecord for a CELLxGENE dataset."""
    title = str(dataset_info.get("dataset_title") or "").strip()
    collection = str(dataset_info.get("collection_name") or "").strip()
    doi = str(dataset_info.get("collection_doi") or "").strip()

    label_parts = ["CELLxGENE Census dataset"]
    if title:
        label_parts.append(f"'{title}'")
    if collection and collection.lower() != title.lower():
        label_parts.append(f"({collection})")
    if doi:
        label_parts.append(f"DOI: {doi}")
    source_desc = " ".join(label_parts) if len(label_parts) > 1 else default_label
    url = (
        f"https://doi.org/{doi}"
        if doi and not doi.startswith("http")
        else f"{CELLXGENE_EXPLORER_BASE_URL}/{dataset_id}.cxg/"
    )
    return SourceRecord(
        id=f"cellxgene-dataset-{dataset_id}",
        source=source_desc,
        url=url,
    )


def _ensembl_source_record(organism_key: str, feature_id: str, feature_name: str) -> SourceRecord:
    """Build a verifiable SourceRecord for an Ensembl gene identifier."""
    species_path = ENSEMBL_SPECIES_PATH.get(organism_key, organism_key.capitalize())
    return SourceRecord(
        id=f"ensembl-{feature_id}",
        source=f"Ensembl {species_path} gene {feature_name} ({feature_id})",
        url=f"https://www.ensembl.org/{species_path}/Gene/Summary?g={feature_id}",
    )


def _coerce_query(
    query_or_gene: Union[ResolvedQuery, str, None],
    species: Optional[SpeciesId] = None,
) -> ResolvedQuery:
    """Accept either a canonical ``ResolvedQuery`` or ``(gene, species)`` arguments."""
    if hasattr(query_or_gene, "species") and hasattr(query_or_gene, "gene"):
        return query_or_gene  # type: ignore[return-value]

    target_species: SpeciesId = species or "macaca_mulatta"
    gene_str: Optional[str] = None
    if isinstance(query_or_gene, str) and query_or_gene.strip():
        gene_str = query_or_gene.strip().upper()
    return ResolvedQuery(
        species=target_species,
        sequence="",
        sequence_label=gene_str,
        gene=gene_str,
    )


# ── Public Entrypoint ───────────────────────────────────────────────────────


def run_cell_expression(
    query: Union[ResolvedQuery, str, None],
    species: Optional[SpeciesId] = None,
    *,
    census_version: str = DEFAULT_CENSUS_VERSION,
    human_dataset_id: str = DEFAULT_HUMAN_DATASET_ID,
) -> LayerResult:
    """Run bounded CELLxGENE Census cell-type expression comparison.

    Can be invoked either with the canonical pipeline ``ResolvedQuery``:
        ``run_cell_expression(query)``
    or directly with ``(gene, species)``:
        ``run_cell_expression("CD28", "macaca_mulatta")``
    """
    resolved = _coerce_query(query, species)
    if resolved.gene is None or not str(resolved.gene).strip():
        return _base_unavailable(
            "cell_expression",
            resolved,
            "Needs a resolved gene identifier; none was supplied.",
        )

    gene_symbol = str(resolved.gene).strip().upper()
    target_species: SpeciesId = resolved.species

    try:
        import cellxgene_census
    except ImportError as exc:
        return _base_unavailable(
            "cell_expression",
            resolved,
            f"cellxgene_census package is not installed: {exc}",
        )

    try:
        with cellxgene_census.open_soma(census_version=census_version) as census:
            return _evaluate_census_expression(
                census=census,
                gene_symbol=gene_symbol,
                target_species=target_species,
                census_version=census_version,
                human_dataset_id=human_dataset_id,
            )
    except Exception as exc:
        log.exception("CELLxGENE Census query failed for gene=%s species=%s", gene_symbol, target_species)
        return _base_unavailable(
            "cell_expression",
            resolved,
            f"CELLxGENE Census query failed ({type(exc).__name__}): {exc}",
        )


def _evaluate_census_expression(
    *,
    census: Any,
    gene_symbol: str,
    target_species: SpeciesId,
    census_version: str,
    human_dataset_id: str,
) -> LayerResult:
    """Core SOMA evaluation logic separated for deterministic unit testing."""
    summary_rows = _table_to_rows(census["census_info"]["summary"].read().concat())
    summary_map = {str(r["label"]): str(r["value"]) for r in summary_rows}
    schema_ver = summary_map.get("census_schema_version", "unknown")
    data_version = f"CELLxGENE Census {census_version} (schema {schema_ver})"

    census_source = SourceRecord(
        id=f"cellxgene-census-{census_version}",
        source=(
            f"CZ CELLxGENE Census release {census_version} "
            f"(census_schema_version={schema_ver})"
        ),
        url=CENSUS_DOCS_URL,
    )

    datasets_rows = _table_to_rows(census["census_info"]["datasets"].read().concat())
    dataset_by_id = {str(r["dataset_id"]): r for r in datasets_rows}
    dataset_id_by_joinid = {
        int(r["soma_joinid"]): str(r["dataset_id"]) for r in datasets_rows
    }

    # ── 1. Resolve human gene & verify dataset-level measurement ───────────
    hs_rna = census["census_data"]["homo_sapiens"].ms["RNA"]
    hs_gene = _resolve_var_gene(hs_rna, gene_symbol, "homo_sapiens")
    if hs_gene is None:
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="cell_expression",
            status="unavailable",
            observations=[],
            source_records=[census_source],
            limitations=[
                f"Gene '{gene_symbol}' was not found in Homo sapiens RNA var table "
                f"of CELLxGENE Census release {census_version}."
            ],
            data_version=data_version,
        )

    hs_measured_datasets = _check_gene_presence_by_dataset(
        hs_rna, hs_gene["soma_joinid"], dataset_id_by_joinid
    )
    hs_ensembl_source = _ensembl_source_record(
        "homo_sapiens", hs_gene["feature_id"], hs_gene["feature_name"]
    )
    hs_ds_info = dataset_by_id.get(human_dataset_id, {})
    hs_ds_source = _dataset_source_record(
        human_dataset_id,
        hs_ds_info,
        f"CELLxGENE Census Homo sapiens PBMC dataset {human_dataset_id}",
    )

    source_records: list[SourceRecord] = [
        census_source,
        hs_ds_source,
        hs_ensembl_source,
    ]
    observations: list[Observation] = [
        Observation(
            field="census_release",
            value=(
                f"CELLxGENE Census release {census_version} "
                f"(schema {schema_ver}; {len(datasets_rows)} total datasets)"
            ),
            source_record_id=census_source.id,
        ),
        Observation(
            field="human_gene_identifier",
            value=(
                f"{hs_gene['feature_name']} ({hs_gene['feature_id']}; "
                f"soma_joinid={hs_gene['soma_joinid']}; "
                f"measured in {len(hs_measured_datasets)} Homo sapiens Census datasets)"
            ),
            source_record_id=hs_ensembl_source.id,
        ),
    ]

    # Guard: never interpret 0 expression values if the gene is unmeasured in the dataset
    if human_dataset_id not in hs_measured_datasets:
        observations.append(
            Observation(
                field="human_gene_measurement_status",
                value=(
                    f"unmeasured in dataset {human_dataset_id}: "
                    f"{hs_gene['feature_id']} ({hs_gene['feature_name']}) is absent from "
                    "feature_dataset_presence_matrix; zero expression values cannot be inferred"
                ),
                source_record_id=hs_ds_source.id,
            )
        )
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="cell_expression",
            status="unavailable",
            observations=observations,
            source_records=source_records,
            limitations=[
                f"{hs_gene['feature_name']} ({hs_gene['feature_id']}) is unmeasured "
                f"(feature_dataset_presence_matrix == 0) in selected human dataset "
                f"{human_dataset_id}; refusing to interpret missing feature rows as "
                "zero expression or biological absence."
            ],
            data_version=data_version,
        )

    # ── 2. Bounded human PBMC CD4+ effector-memory T-cell analysis ─────────
    hs_obs_cols = [
        "soma_joinid",
        "dataset_id",
        "assay",
        "assay_ontology_term_id",
        "cell_type",
        "cell_type_ontology_term_id",
        "development_stage",
        "disease",
        "donor_id",
        "is_primary_data",
        "suspension_type",
        "tissue",
        "tissue_ontology_term_id",
        "tissue_general",
        "raw_sum",
        "nnz",
    ]
    ont_list_literal = ", ".join(f"'{cid}'" for cid in TARGET_CD4_EM_ONTOLOGY_IDS)
    hs_value_filter = (
        f"dataset_id == '{human_dataset_id}' and "
        "is_primary_data == True and "
        f"cell_type_ontology_term_id in [{ont_list_literal}]"
    )
    hs_obs_rows = _table_to_rows(
        census["census_data"]["homo_sapiens"]
        .obs.read(value_filter=hs_value_filter, column_names=hs_obs_cols)
        .concat()
    )

    if not hs_obs_rows:
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="cell_expression",
            status="unavailable",
            observations=observations,
            source_records=source_records,
            limitations=[
                f"No primary CD4+ effector-memory T cells ({', '.join(TARGET_CD4_EM_ONTOLOGY_IDS)}) "
                f"found in human dataset {human_dataset_id}."
            ],
            data_version=data_version,
        )

    hs_stats = _compute_raw_expression_stats(
        hs_rna, hs_obs_rows, hs_gene["soma_joinid"]
    )
    hs_donors = sorted({str(r["donor_id"]) for r in hs_obs_rows})
    hs_tissues = sorted(
        {f"{r['tissue']} ({r['tissue_ontology_term_id']})" for r in hs_obs_rows}
    )
    hs_assays = sorted(
        {f"{r['assay']} ({r['assay_ontology_term_id']})" for r in hs_obs_rows}
    )
    hs_suspensions = sorted({str(r["suspension_type"]) for r in hs_obs_rows})
    hs_diseases = sorted({str(r["disease"]) for r in hs_obs_rows})
    hs_cell_types = sorted(
        {
            f"{r['cell_type']} ({r['cell_type_ontology_term_id']})"
            for r in hs_obs_rows
        }
    )
    hs_median_raw_sum = float(median(float(r["raw_sum"]) for r in hs_obs_rows))
    hs_median_nnz = float(median(float(r["nnz"]) for r in hs_obs_rows))

    ds_title = str(hs_ds_info.get("dataset_title") or "PBMC dataset").strip()
    ds_doi = str(hs_ds_info.get("collection_doi") or "n/a").strip()

    observations.extend(
        [
            Observation(
                field="human_dataset_provenance",
                value=(
                    f"dataset_id={human_dataset_id}; title='{ds_title}'; "
                    f"DOI={ds_doi}; tissue={', '.join(hs_tissues)}; "
                    f"assay={', '.join(hs_assays)}; "
                    f"suspension_type={', '.join(hs_suspensions)}"
                ),
                source_record_id=hs_ds_source.id,
            ),
            Observation(
                field="human_gene_measurement_status",
                value=(
                    f"measured in dataset {human_dataset_id} "
                    f"(feature_dataset_presence_matrix=1 for {hs_gene['feature_id']}); "
                    f"{hs_stats['n_detected']} cells detected (X['raw'] > 0) and "
                    f"{hs_stats['n_undetected']} cells undetected (X['raw'] == 0)"
                ),
                source_record_id=hs_ds_source.id,
            ),
            Observation(
                field="human_cd4_effector_memory_population",
                value=(
                    f"{', '.join(hs_cell_types)}; "
                    f"primary_cells={hs_stats['n_total']}; "
                    f"unique_donors={len(hs_donors)}; "
                    f"disease_status={', '.join(hs_diseases)}; "
                    f"median_raw_umi_per_cell={hs_median_raw_sum:.1f}; "
                    f"median_detected_genes_per_cell={hs_median_nnz:.1f}"
                ),
                source_record_id=hs_ds_source.id,
            ),
            Observation(
                field="human_cd28_detection_fraction",
                value=(
                    f"{hs_stats['detection_fraction']:.4f} "
                    f"({hs_stats['detection_fraction'] * 100:.2f}%; "
                    f"{hs_stats['n_detected']} / {hs_stats['n_total']} primary cells "
                    f"with X['raw'] > 0 across {len(hs_donors)} donors; "
                    f"mean_raw_umi_all_cells={hs_stats['mean_raw_all']:.4f}; "
                    f"mean_raw_umi_detected_cells={hs_stats['mean_raw_detected']:.4f}; "
                    f"max_raw_umi={hs_stats['max_raw']:.1f})"
                ),
                source_record_id=hs_ds_source.id,
            ),
        ]
    )

    # ── 3. Comparison species evaluation ───────────────────────────────────
    census_data = census["census_data"]
    available_species = (
        set(census_data.keys()) if hasattr(census_data, "keys") else set()
    )
    if target_species not in available_species:
        observations.extend(
            [
                Observation(
                    field="animal_species_availability",
                    value=(
                        f"Species '{target_species}' is not indexed in CELLxGENE Census "
                        f"release {census_version} (available organisms: "
                        f"{', '.join(sorted(available_species))})"
                    ),
                    source_record_id=census_source.id,
                ),
                Observation(
                    field="measurement_state_distinction",
                    value=(
                        "unmeasured = gene or species absent from dataset/atlas feature matrix; "
                        "undetected = 0 UMI in a measured cell/dataset due to technical dropout; "
                        "biologically absent = true absence of expression in vivo (cannot be "
                        "inferred from missing atlas datasets or sparse 3' scRNA-seq zeros)"
                    ),
                    source_record_id=census_source.id,
                ),
                Observation(
                    field="cross_species_comparison",
                    value=(
                        f"inconclusive: {target_species} is absent from CELLxGENE Census "
                        f"release {census_version}; human CD4+ effector-memory T-cell "
                        f"{gene_symbol} detection is {hs_stats['detection_fraction']:.4f}, "
                        "but no animal single-cell comparator is available"
                    ),
                    source_record_id=census_source.id,
                ),
            ]
        )
        return LayerResult(
            gene=gene_symbol,
            species=target_species,
            layer="cell_expression",
            status="incomplete",
            observations=observations,
            source_records=source_records,
            limitations=_build_limitations(
                gene_symbol=gene_symbol,
                target_species=target_species,
                census_version=census_version,
                unmeasured_animal_datasets=[],
                measured_animal_t_datasets=[],
            ),
            data_version=data_version,
        )

    animal_rna = census_data[target_species].ms["RNA"]
    animal_gene = _resolve_var_gene(animal_rna, gene_symbol, target_species)
    animal_measured_datasets: set[str] = set()
    if animal_gene is not None:
        animal_measured_datasets = _check_gene_presence_by_dataset(
            animal_rna, animal_gene["soma_joinid"], dataset_id_by_joinid
        )
        animal_ensembl_source = _ensembl_source_record(
            target_species, animal_gene["feature_id"], animal_gene["feature_name"]
        )
        source_records.append(animal_ensembl_source)
        observations.append(
            Observation(
                field="animal_gene_identifier",
                value=(
                    f"{animal_gene['feature_name']} ({animal_gene['feature_id']}; "
                    f"soma_joinid={animal_gene['soma_joinid']}; "
                    f"measured in {len(animal_measured_datasets)} {target_species} Census datasets)"
                ),
                source_record_id=animal_ensembl_source.id,
            )
        )
    else:
        observations.append(
            Observation(
                field="animal_gene_identifier",
                value=(
                    f"unmeasured: gene '{gene_symbol}' was not found in "
                    f"{target_species} RNA var table in CELLxGENE Census {census_version}"
                ),
                source_record_id=census_source.id,
            )
        )

    animal_obs_cols = [
        "soma_joinid",
        "dataset_id",
        "assay",
        "assay_ontology_term_id",
        "cell_type",
        "cell_type_ontology_term_id",
        "development_stage",
        "disease",
        "donor_id",
        "is_primary_data",
        "suspension_type",
        "tissue",
        "tissue_ontology_term_id",
        "tissue_general",
    ]
    animal_obs_rows = _table_to_rows(
        census_data[target_species]
        .obs.read(column_names=animal_obs_cols)
        .concat()
    )

    animal_by_ds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in animal_obs_rows:
        animal_by_ds[str(row["dataset_id"])].append(row)

    n_animal_datasets = len(animal_by_ds)
    n_animal_total_cells = len(animal_obs_rows)
    n_animal_primary_cells = sum(
        1 for r in animal_obs_rows if bool(r.get("is_primary_data"))
    )
    animal_cd4_em_rows = [
        r
        for r in animal_obs_rows
        if str(r.get("cell_type_ontology_term_id")) in TARGET_CD4_EM_ONTOLOGY_IDS
    ]
    animal_cd4_any_rows = [
        r
        for r in animal_obs_rows
        if str(r.get("cell_type_ontology_term_id")) in CD4_ONTOLOGY_IDS
    ]
    animal_blood_lymphoid_rows = [
        r
        for r in animal_obs_rows
        if str(r.get("tissue_general", "")).strip().lower()
        in BLOOD_LYMPHOID_GENERAL_TISSUES
    ]
    animal_tissues_general = sorted(
        {str(r.get("tissue_general", "")) for r in animal_obs_rows if r.get("tissue_general")}
    )

    observations.append(
        Observation(
            field="animal_cd4_effector_memory_availability",
            value=(
                f"{len(animal_cd4_em_rows)} CD4+ effector-memory T cells "
                f"({', '.join(TARGET_CD4_EM_ONTOLOGY_IDS)}), "
                f"{len(animal_cd4_any_rows)} total CD4-annotated T cells, and "
                f"{len(animal_blood_lymphoid_rows)} blood/lymphoid cells across "
                f"{n_animal_datasets} {target_species} datasets "
                f"({n_animal_primary_cells} primary / {n_animal_total_cells} total cells; "
                f"available general tissues: {', '.join(animal_tissues_general) or 'none'}) "
                f"in CELLxGENE Census {census_version}"
            ),
            source_record_id=census_source.id,
        )
    )

    # Audit generic T-cell datasets in the comparison species
    unmeasured_animal_datasets: list[str] = []
    measured_animal_t_datasets: list[str] = []
    for ds_id in sorted(animal_by_ds.keys()):
        ds_rows = animal_by_ds[ds_id]
        t_rows = [
            r
            for r in ds_rows
            if str(r.get("cell_type_ontology_term_id")) in GENERIC_T_CELL_ONTOLOGY_IDS
            and bool(r.get("is_primary_data"))
        ]
        if not t_rows:
            continue

        ds_info = dataset_by_id.get(ds_id, {})
        ds_source = _dataset_source_record(
            ds_id,
            ds_info,
            f"CELLxGENE Census {target_species} dataset {ds_id}",
        )
        source_records.append(ds_source)

        t_ct_counts: dict[str, int] = defaultdict(int)
        for r in t_rows:
            t_ct_counts[
                f"{r['cell_type']} ({r['cell_type_ontology_term_id']})"
            ] += 1
        ct_summary = ", ".join(
            f"{label}: {count}" for label, count in sorted(t_ct_counts.items())
        )
        tissues_str = ", ".join(
            sorted({f"{r['tissue']} ({r['tissue_ontology_term_id']})" for r in t_rows})
        )
        assays_str = ", ".join(
            sorted({f"{r['assay']} ({r['assay_ontology_term_id']})" for r in t_rows})
        )
        susp_str = ", ".join(sorted({str(r["suspension_type"]) for r in t_rows}))
        donors_count = len({str(r["donor_id"]) for r in t_rows})
        dev_str = ", ".join(sorted({str(r["development_stage"]) for r in t_rows}))

        is_measured = (
            animal_gene is not None and ds_id in animal_measured_datasets
        )
        if not is_measured:
            gene_id_label = (
                animal_gene["feature_id"] if animal_gene is not None else gene_symbol
            )
            unmeasured_animal_datasets.append(ds_id)
            observations.append(
                Observation(
                    field=f"animal_noncomparable_t_cell_dataset_{ds_id[:8]}",
                    value=(
                        f"dataset_id={ds_id} ({tissues_str}; {dev_str}; {assays_str}; "
                        f"suspension_type={susp_str}; donors={donors_count}; {ct_summary}): "
                        f"{gene_symbol} ({gene_id_label}) is UNMEASURED "
                        "(feature_dataset_presence_matrix=0; absent from dataset feature space, "
                        "NOT detected-as-zero or biologically absent)"
                    ),
                    source_record_id=ds_source.id,
                )
            )
        else:
            assert animal_gene is not None
            measured_animal_t_datasets.append(ds_id)
            # Filter strictly to generic T cell (CL:0000084) if present, else all t_rows
            cl0000084_rows = [
                r
                for r in t_rows
                if str(r.get("cell_type_ontology_term_id")) == "CL:0000084"
            ]
            eval_rows = cl0000084_rows if cl0000084_rows else t_rows
            t_stats = _compute_raw_expression_stats(
                animal_rna, eval_rows, animal_gene["soma_joinid"]
            )
            observations.append(
                Observation(
                    field=f"animal_noncomparable_t_cell_dataset_{ds_id[:8]}",
                    value=(
                        f"dataset_id={ds_id} ({tissues_str}; {dev_str}; {assays_str}; "
                        f"suspension_type={susp_str}; donors={donors_count}; {ct_summary}): "
                        f"{gene_symbol} ({animal_gene['feature_id']}) is MEASURED "
                        f"(feature_dataset_presence_matrix=1), with "
                        f"{t_stats['n_detected']} / {t_stats['n_total']} generic T-cell "
                        f"({eval_rows[0]['cell_type_ontology_term_id']}) {susp_str} records "
                        f"detected ({t_stats['detection_fraction']:.4f} / "
                        f"{t_stats['detection_fraction'] * 100:.2f}%) and "
                        f"{t_stats['n_undetected']} / {t_stats['n_total']} undetected "
                        f"(mean_raw_umi={t_stats['mean_raw_all']:.4f}; max_raw_umi={t_stats['max_raw']:.1f}); "
                        "not comparable to human blood whole-cell CD4+ effector-memory T cells"
                    ),
                    source_record_id=ds_source.id,
                )
            )

    observations.extend(
        [
            Observation(
                field="measurement_state_distinction",
                value=(
                    "Explicit 3-state classification enforced: "
                    "(1) unmeasured = feature absent from dataset feature_dataset_presence_matrix "
                    f"(e.g. {gene_symbol} in macaque fetal lung dataset "
                    f"{', '.join(unmeasured_animal_datasets) or 'none'}); "
                    "(2) undetected = 0 captured UMI counts (X['raw'] == 0) in a dataset where "
                    "feature_dataset_presence_matrix == 1 "
                    f"({hs_stats['n_undetected']} / {hs_stats['n_total']} human blood CD4+ TEM cells "
                    "reflecting 3' droplet scRNA-seq capture dropout / low transcript copy number); "
                    "(3) biologically absent = true absence of functional gene/protein expression in "
                    "the population, which cannot be inferred from sparse scRNA-seq zero counts or "
                    "from missing atlas cell types/tissues"
                ),
                source_record_id=census_source.id,
            ),
            Observation(
                field="cross_species_comparison",
                value=(
                    f"inconclusive: Homo sapiens blood CD4+ effector-memory T cells "
                    f"(CL:0000905) in dataset {human_dataset_id} show {gene_symbol} "
                    f"({hs_gene['feature_id']}) detection fraction "
                    f"{hs_stats['detection_fraction']:.4f} "
                    f"({hs_stats['n_detected']} / {hs_stats['n_total']} cells across "
                    f"{len(hs_donors)} donors), whereas {target_species} has 0 comparable "
                    "CD4+ effector-memory T-cell (CL:0000905 / CL:0001087) or blood/lymphoid "
                    f"datasets in CELLxGENE Census {census_version}; no cross-species "
                    "biological equivalence or divergence can be claimed from this source"
                ),
                source_record_id=census_source.id,
            ),
        ]
    )

    limitations = _build_limitations(
        gene_symbol=gene_symbol,
        target_species=target_species,
        census_version=census_version,
        unmeasured_animal_datasets=unmeasured_animal_datasets,
        measured_animal_t_datasets=measured_animal_t_datasets,
    )

    return LayerResult(
        gene=gene_symbol,
        species=target_species,
        layer="cell_expression",
        status="incomplete",
        observations=observations,
        source_records=source_records,
        limitations=limitations,
        data_version=data_version,
    )


def _build_limitations(
    *,
    gene_symbol: str,
    target_species: str,
    census_version: str,
    unmeasured_animal_datasets: list[str],
    measured_animal_t_datasets: list[str],
) -> list[str]:
    """Construct scientific and technical limitations for the LayerResult."""
    limitations = [
        (
            f"Missing comparable animal population in CELLxGENE Census {census_version}: "
            f"{target_species} contains 0 blood or lymphoid-tissue datasets and 0 cells "
            "annotated as CD4+ effector-memory T cells (CL:0000905 / CL:0001087) or "
            "CD4+ T cells (CL:0000624), rendering the cross-species comparison inconclusive."
        ),
        (
            "Explicit distinction between unmeasured, undetected, and biologically absent: "
            "features absent from a dataset's feature_dataset_presence_matrix are unmeasured "
            f"(e.g. {gene_symbol} in macaque dataset "
            f"{', '.join(unmeasured_animal_datasets) if unmeasured_animal_datasets else 'with missing feature annotation'}); "
            "zero UMI counts (X['raw'] == 0) in a measured dataset are undetected due to "
            "sparse 3' droplet capture efficiency (~5-15% mRNA capture); neither establishes "
            "that the protein is biologically absent."
        ),
        (
            "RNA transcript detection versus cell-surface protein abundance: CELLxGENE Census "
            "stores single-cell/single-nucleus RNA UMI counts (X['raw']) and does not expose "
            "paired CITE-seq ADT surface-protein abundance or post-translational surface "
            "density, which govern functional receptor engagement (such as CD28 superagonist "
            "binding in CD4+ effector-memory T cells)."
        ),
        (
            "Cell-type annotation and suspension-type non-equivalence: generic 'T cell' "
            "(CL:0000084) annotations in non-lymphoid parenchyma or single-nucleus RNA-seq "
            f"({', '.join(measured_animal_t_datasets) if measured_animal_t_datasets else 'snRNA-seq'}) "
            "pool CD4+, CD8+, gamma-delta, and regulatory T cells and sample only nuclear "
            "pre-mRNA/mRNA, making them biologically and technically incomparable to "
            "whole-cell peripheral blood CD4+ effector-memory T cells."
        ),
        (
            "Cross-dataset normalisation and batch effects: CELLxGENE Census release "
            f"{census_version} provides raw UMI counts (X['raw']) without a cross-species "
            "batch-corrected expression layer; direct numerical comparison across independent "
            "studies, chemistries, and reference genome builds (GRCh38 vs Mmul_10) is "
            "confounded without matched experimental design."
        ),
    ]
    return limitations


# ── CLI Entrypoint ──────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded CELLxGENE Census cell-type expression analysis and "
            "emit a canonical LayerResult JSON object."
        )
    )
    parser.add_argument(
        "gene",
        nargs="?",
        default="CD28",
        help="Target gene symbol (default: CD28).",
    )
    parser.add_argument(
        "species",
        nargs="?",
        default="macaca_mulatta",
        help="Comparison species Ensembl ID (default: macaca_mulatta).",
    )
    parser.add_argument(
        "--census-version",
        default=DEFAULT_CENSUS_VERSION,
        help=f"Pinned CELLxGENE Census release (default: {DEFAULT_CENSUS_VERSION}).",
    )
    parser.add_argument(
        "--human-dataset-id",
        default=DEFAULT_HUMAN_DATASET_ID,
        help=f"Human PBMC dataset ID (default: {DEFAULT_HUMAN_DATASET_ID}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the LayerResult JSON output.",
    )
    args = parser.parse_args(argv)

    result = run_cell_expression(
        args.gene,
        args.species,  # type: ignore[arg-type]
        census_version=args.census_version,
        human_dataset_id=args.human_dataset_id,
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
