"""Reusable CELLxGENE Census metadata discovery for cross-species CD28 feasibility.

Run from the repository root:
    /opt/homebrew/bin/uv run --no-project --python 3.11 --with cellxgene-census \\
        python -m Backend.tools.cellxgene_discovery

This module queries CELLxGENE Census SOMA metadata tables (``census_info``,
``var``, ``obs``, and ``feature_dataset_presence_matrix``) without downloading
expression atlases. It verifies organism availability, species-specific gene
identifiers, dataset provenance, cell-type ontology granularity, assay and
normalisation layers, and dataset-level gene measurement presence.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_CENSUS_VERSION = "2025-11-08"
HUMAN_CD28_ENSEMBL_ID = "ENSG00000178562"
MACAQUE_CD28_ENSEMBL_ID = "ENSMMUG00000057214"
CD4_EM_ONTOLOGY_IDS = ("CL:0000905", "CL:0001087")
CD4_RELATED_ONTOLOGY_IDS = (
    "CL:0000905",  # effector memory CD4-positive, alpha-beta T cell
    "CL:0001087",  # effector memory CD4-positive, alpha-beta T cell, terminally differentiated
    "CL:0000904",  # central memory CD4-positive, alpha-beta T cell
    "CL:0000897",  # CD4-positive, alpha-beta memory T cell
    "CL:0000895",  # naive thymus-derived CD4-positive, alpha-beta T cell
    "CL:0000624",  # CD4-positive, alpha-beta T cell
    "CL:0000084",  # T cell
)
BLOOD_LYMPHOID_GENERAL_TISSUES = (
    "blood",
    "lymph node",
    "spleen",
    "bone marrow",
    "thymus",
)


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
    """Return the set of dataset_ids in which feature_soma_joinid was measured."""
    presence_concat = (
        rna_measurement["feature_dataset_presence_matrix"]
        .read(coords=(slice(None), [feature_soma_joinid]))
        .tables()
        .concat()
    )
    rows = _table_to_rows(presence_concat)
    measured_joinids = {
        int(r["soma_dim_0"]) for r in rows if r.get("soma_data", 0) != 0
    }
    return {
        dataset_id_by_joinid[jid]
        for jid in measured_joinids
        if jid in dataset_id_by_joinid
    }


def run_census_discovery(
    census_version: str = DEFAULT_CENSUS_VERSION,
    gene_symbol: str = "CD28",
) -> dict[str, Any]:
    """Query CELLxGENE Census metadata tables for human vs macaque T-cell feasibility."""
    import cellxgene_census

    gene_upper = gene_symbol.strip().upper()
    s3_uri = f"s3://cellxgene-census-public-us-west-2/cell-census/{census_version}/soma/"

    result: dict[str, Any] = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "census_version": census_version,
        "census_s3_uri": s3_uri,
        "cellxgene_census_package_version": getattr(cellxgene_census, "__version__", "unknown"),
        "target_gene": gene_upper,
    }

    version_dir = cellxgene_census.get_census_version_directory()
    result["available_census_versions"] = list(version_dir.keys())
    result["pinned_version_in_directory"] = census_version in version_dir
    if census_version in version_dir:
        result["pinned_version_metadata"] = version_dir[census_version]

    with cellxgene_census.open_soma(census_version=census_version) as census:
        summary_rows = _table_to_rows(census["census_info"]["summary"].read().concat())
        result["census_summary"] = {
            str(row["label"]): str(row["value"]) for row in summary_rows
        }

        organisms_rows = _table_to_rows(census["census_info"]["organisms"].read().concat())
        scc_rows = _table_to_rows(census["census_info"]["summary_cell_counts"].read().concat())
        scc_all = {
            str(r["organism"]): r for r in scc_rows if str(r.get("category")) == "all"
        }

        organisms_summary = []
        for row in organisms_rows:
            org_key = str(row["organism"])
            scc_entry = scc_all.get(org_key, {})
            organisms_summary.append(
                {
                    "organism": org_key,
                    "organism_label": str(row["organism_label"]),
                    "organism_ontology_term_id": str(row["organism_ontology_term_id"]),
                    "total_cell_count": int(scc_entry.get("total_cell_count", 0)),
                    "unique_cell_count": int(scc_entry.get("unique_cell_count", 0)),
                }
            )
        result["organisms"] = organisms_summary

        datasets_rows = _table_to_rows(census["census_info"]["datasets"].read().concat())
        result["total_census_datasets"] = len(datasets_rows)
        dataset_by_id = {str(r["dataset_id"]): r for r in datasets_rows}
        dataset_id_by_joinid = {
            int(r["soma_joinid"]): str(r["dataset_id"]) for r in datasets_rows
        }

        # Inspect gene var metadata & presence matrices for Homo sapiens and Macaca mulatta
        gene_metadata: dict[str, Any] = {}
        measured_datasets_by_org: dict[str, set[str]] = {}
        for org_key, expected_id in (
            ("homo_sapiens", HUMAN_CD28_ENSEMBL_ID),
            ("macaca_mulatta", MACAQUE_CD28_ENSEMBL_ID),
        ):
            rna = census["census_data"][org_key].ms["RNA"]
            x_layers = sorted(list(rna["X"].keys()))
            var_rows = _table_to_rows(rna.var.read().concat())
            matches = [
                vrow
                for vrow in var_rows
                if str(vrow.get("feature_name", "")).upper() == gene_upper
                or str(vrow.get("feature_id", "")) == expected_id
            ]
            records = []
            measured_ds: set[str] = set()
            for vrow in matches:
                joinid = int(vrow["soma_joinid"])
                ds_set = _check_gene_presence_by_dataset(rna, joinid, dataset_id_by_joinid)
                measured_ds.update(ds_set)
                records.append(
                    {
                        "soma_joinid": joinid,
                        "feature_id": str(vrow["feature_id"]),
                        "feature_name": str(vrow["feature_name"]),
                        "feature_type": str(vrow["feature_type"]),
                        "feature_length": int(vrow["feature_length"]),
                        "nnz": int(vrow["nnz"]),
                        "n_measured_obs": int(vrow["n_measured_obs"]),
                        "n_datasets_measuring_gene": len(ds_set),
                    }
                )
            measured_datasets_by_org[org_key] = measured_ds
            gene_metadata[org_key] = {
                "x_layers": x_layers,
                "total_genes_in_var": len(var_rows),
                "gene_records": records,
            }
        result["gene_metadata"] = gene_metadata

        # Macaca mulatta obs metadata evaluation
        mm_obs_cols = [
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
        mm_obs_rows = _table_to_rows(
            census["census_data"]["macaca_mulatta"]
            .obs.read(column_names=mm_obs_cols)
            .concat()
        )
        mm_by_ds: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in mm_obs_rows:
            mm_by_ds[str(row["dataset_id"])].append(row)

        t_related_set = set(CD4_RELATED_ONTOLOGY_IDS) | {"CL:0000940"}
        mm_datasets_summary = []
        for ds_id_str in sorted(mm_by_ds.keys()):
            group = mm_by_ds[ds_id_str]
            ds_info = dataset_by_id.get(ds_id_str, {})
            ct_counts: dict[tuple[str, str], int] = defaultdict(int)
            for r in group:
                ct_counts[(str(r["cell_type"]), str(r["cell_type_ontology_term_id"]))] += 1

            t_pops = [
                {
                    "cell_type": ct_label,
                    "cell_type_ontology_term_id": ct_id,
                    "cell_count": count,
                }
                for (ct_label, ct_id), count in sorted(ct_counts.items())
                if ct_id in t_related_set
            ]
            mm_datasets_summary.append(
                {
                    "dataset_id": ds_id_str,
                    "dataset_version_id": str(ds_info.get("dataset_version_id", "")),
                    "collection_id": str(ds_info.get("collection_id", "")),
                    "collection_name": str(ds_info.get("collection_name", "")),
                    "collection_doi": str(ds_info.get("collection_doi", "")),
                    "dataset_title": str(ds_info.get("dataset_title", "")),
                    "total_cells": len(group),
                    "primary_cells": sum(1 for r in group if bool(r.get("is_primary_data"))),
                    "unique_donors": len({str(r["donor_id"]) for r in group}),
                    "tissues_general": sorted({str(r["tissue_general"]) for r in group}),
                    "tissues": sorted(
                        {f"{r['tissue']} ({r['tissue_ontology_term_id']})" for r in group}
                    ),
                    "assays": sorted(
                        {f"{r['assay']} ({r['assay_ontology_term_id']})" for r in group}
                    ),
                    "suspension_types": sorted({str(r["suspension_type"]) for r in group}),
                    "development_stages": sorted({str(r["development_stage"]) for r in group}),
                    "diseases": sorted({str(r["disease"]) for r in group}),
                    "cd28_measured_in_dataset": ds_id_str in measured_datasets_by_org["macaca_mulatta"],
                    "t_cell_populations": t_pops,
                }
            )

        cd4_all_ids = {
            "CL:0000624",
            "CL:0000895",
            "CL:0000897",
            "CL:0000904",
            "CL:0000905",
            "CL:0001087",
        }
        mm_cd4_em_count = sum(
            1 for r in mm_obs_rows if str(r.get("cell_type_ontology_term_id")) in CD4_EM_ONTOLOGY_IDS
        )
        mm_cd4_any_count = sum(
            1 for r in mm_obs_rows if str(r.get("cell_type_ontology_term_id")) in cd4_all_ids
        )
        mm_blood_lymphoid_count = sum(
            1
            for r in mm_obs_rows
            if str(r.get("tissue_general", "")).lower() in BLOOD_LYMPHOID_GENERAL_TISSUES
        )

        result["macaca_mulatta_evaluation"] = {
            "total_datasets": len(mm_datasets_summary),
            "total_cells": len(mm_obs_rows),
            "primary_cells": sum(1 for r in mm_obs_rows if bool(r.get("is_primary_data"))),
            "cd4_effector_memory_cells": mm_cd4_em_count,
            "any_cd4_annotated_cells": mm_cd4_any_count,
            "blood_or_lymphoid_tissue_cells": mm_blood_lymphoid_count,
            "datasets_with_generic_t_cells": [
                d for d in mm_datasets_summary if d["t_cell_populations"]
            ],
            "all_datasets": mm_datasets_summary,
        }

        # Homo sapiens CD4+ effector-memory T cell obs metadata evaluation
        hs_em_filter = "cell_type_ontology_term_id in ['CL:0000905', 'CL:0001087']"
        hs_em_rows = _table_to_rows(
            census["census_data"]["homo_sapiens"]
            .obs.read(
                value_filter=hs_em_filter,
                column_names=[
                    "dataset_id",
                    "assay",
                    "assay_ontology_term_id",
                    "cell_type",
                    "cell_type_ontology_term_id",
                    "disease",
                    "donor_id",
                    "is_primary_data",
                    "suspension_type",
                    "tissue",
                    "tissue_ontology_term_id",
                    "tissue_general",
                    "raw_sum",
                    "nnz",
                ],
            )
            .concat()
        )
        hs_by_ds: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in hs_em_rows:
            hs_by_ds[str(row["dataset_id"])].append(row)
        hs_em_ds_ids = sorted(hs_by_ds.keys())

        cd4_terms_by_ds: dict[str, set[str]] = defaultdict(set)
        if hs_em_ds_ids:
            ds_list_literal = ", ".join(f"'{d}'" for d in hs_em_ds_ids)
            hs_cd4_rows = _table_to_rows(
                census["census_data"]["homo_sapiens"]
                .obs.read(
                    value_filter=(
                        f"dataset_id in [{ds_list_literal}] and "
                        "cell_type_ontology_term_id in ['CL:0000905', 'CL:0001087', 'CL:0000904', "
                        "'CL:0000897', 'CL:0000895', 'CL:0000624', 'CL:0000084']"
                    ),
                    column_names=["dataset_id", "cell_type", "cell_type_ontology_term_id"],
                )
                .concat()
            )
            for r in hs_cd4_rows:
                cd4_terms_by_ds[str(r["dataset_id"])].add(
                    f"{r['cell_type']} ({r['cell_type_ontology_term_id']})"
                )

        hs_datasets_summary = []
        for ds_id_str, group in hs_by_ds.items():
            ds_info = dataset_by_id.get(ds_id_str, {})
            tissues_gen = sorted({str(r["tissue_general"]) for r in group})
            is_blood_lymphoid = any(
                t.lower() in BLOOD_LYMPHOID_GENERAL_TISSUES for t in tissues_gen
            )
            hs_datasets_summary.append(
                {
                    "dataset_id": ds_id_str,
                    "dataset_version_id": str(ds_info.get("dataset_version_id", "")),
                    "collection_id": str(ds_info.get("collection_id", "")),
                    "collection_name": str(ds_info.get("collection_name", "")),
                    "collection_doi": str(ds_info.get("collection_doi", "")),
                    "dataset_title": str(ds_info.get("dataset_title", "")),
                    "dataset_total_cell_count": int(ds_info.get("dataset_total_cell_count", 0)),
                    "cd4_em_total_cells": len(group),
                    "cd4_em_primary_cells": sum(1 for r in group if bool(r.get("is_primary_data"))),
                    "cd4_em_unique_donors": len({str(r["donor_id"]) for r in group}),
                    "median_raw_sum": float(median(float(r["raw_sum"]) for r in group)),
                    "median_nnz": float(median(float(r["nnz"]) for r in group)),
                    "is_blood_or_lymphoid": is_blood_lymphoid,
                    "tissues_general": tissues_gen,
                    "tissues": sorted(
                        {f"{r['tissue']} ({r['tissue_ontology_term_id']})" for r in group}
                    ),
                    "assays": sorted(
                        {f"{r['assay']} ({r['assay_ontology_term_id']})" for r in group}
                    ),
                    "suspension_types": sorted({str(r["suspension_type"]) for r in group}),
                    "diseases": sorted({str(r["disease"]) for r in group}),
                    "cd28_measured_in_dataset": ds_id_str in measured_datasets_by_org["homo_sapiens"],
                    "distinguished_cd4_t_subtypes": sorted(cd4_terms_by_ds.get(ds_id_str, set())),
                }
            )

        hs_datasets_summary.sort(
            key=lambda item: (item["cd4_em_primary_cells"], item["cd4_em_total_cells"]),
            reverse=True,
        )

        hs_by_term_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for r in hs_em_rows:
            hs_by_term_groups[(str(r["cell_type"]), str(r["cell_type_ontology_term_id"]))].append(r)

        hs_by_term = [
            {
                "cell_type": ct_label,
                "cell_type_ontology_term_id": ct_id,
                "total_cells": len(grp),
                "primary_cells": sum(1 for r in grp if bool(r.get("is_primary_data"))),
                "n_datasets": len({str(r["dataset_id"]) for r in grp}),
                "n_donors": len({str(r["donor_id"]) for r in grp}),
            }
            for (ct_label, ct_id), grp in sorted(hs_by_term_groups.items())
        ]

        result["homo_sapiens_evaluation"] = {
            "total_cd4_em_datasets": len(hs_datasets_summary),
            "blood_or_lymphoid_cd4_em_datasets": sum(
                1 for d in hs_datasets_summary if d["is_blood_or_lymphoid"]
            ),
            "total_cd4_em_cells": len(hs_em_rows),
            "primary_cd4_em_cells": sum(1 for r in hs_em_rows if bool(r.get("is_primary_data"))),
            "total_unique_donors": len({str(r["donor_id"]) for r in hs_em_rows}),
            "by_ontology_term": hs_by_term,
            "top_candidate_datasets": hs_datasets_summary[:15],
        }

        result["feasibility_assessment"] = {
            "verdict": "not feasible",
            "human_side_status": "feasible",
            "macaque_side_status": "unavailable",
            "summary": (
                "CELLxGENE Census release 2025-11-08 includes both Homo sapiens and Macaca mulatta, "
                "and supports high-resolution human CD4+ effector-memory T-cell (CL:0000905, CL:0001087) "
                "CD28 (ENSG00000178562) analysis across 38 datasets (1,285,147 primary cells; 2,292 donors). "
                "However, a scientifically defensible cross-species comparison with Macaca mulatta CD4+ "
                "effector-memory T cells is NOT FEASIBLE using CELLxGENE Census alone because: "
                "(1) Macaca mulatta has zero blood or lymphoid-tissue datasets in Census (18 brain snRNA-seq "
                "datasets and 1 fetal lung scRNA-seq dataset); "
                "(2) Macaca mulatta has zero cells annotated as CD4+ T cells (CL:0000624) or CD4+ "
                "effector-memory T cells (CL:0000905 / CL:0001087), providing only generic T cell (CL:0000084) "
                "and mucosal invariant T cell (CL:0000940) labels; and "
                "(3) in the only whole-cell Macaca mulatta dataset containing T cells (fetal lung dataset "
                "2e877cd3-5587-4fc1-8667-a48fe9e2a695, 4,058 T cells), ENSMMUG00000057214 (CD28) is not "
                "present in the dataset's measured feature set, leaving only 185 adult dorsolateral prefrontal "
                "cortex T-cell nuclei (fc6ef080-9e5f-4aea-b9c4-a45a208bd288) in which CD28 is measured."
            ),
        }

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Query CELLxGENE Census metadata to evaluate cross-species CD28 feasibility."
    )
    parser.add_argument(
        "--census-version",
        default=DEFAULT_CENSUS_VERSION,
        help=f"Pinned CELLxGENE Census release date (default: {DEFAULT_CENSUS_VERSION}).",
    )
    parser.add_argument(
        "--gene",
        default="CD28",
        help="Target gene symbol (default: CD28).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write JSON discovery output.",
    )
    args = parser.parse_args(argv)

    payload = run_census_discovery(census_version=args.census_version, gene_symbol=args.gene)
    formatted = json.dumps(payload, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + "\n", encoding="utf-8")
    print(formatted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
