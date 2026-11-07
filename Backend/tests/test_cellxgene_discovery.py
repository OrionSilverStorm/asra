"""Mocked tests for CELLxGENE Census metadata discovery (`cellxgene_discovery.py`)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
import unittest

from Backend.tools import cellxgene_discovery


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def read(self, column_names=None, value_filter=None, coords=None):
        rows = [dict(r) for r in self._rows]
        if value_filter:
            if "'CL:0000905'" in value_filter and "'CL:0000624'" not in value_filter:
                rows = [
                    r for r in rows
                    if r.get("cell_type_ontology_term_id") in ("CL:0000905", "CL:0001087")
                ]
            elif "'CL:0000624'" in value_filter:
                rows = [
                    r for r in rows
                    if r.get("cell_type_ontology_term_id")
                    in (
                        "CL:0000905",
                        "CL:0001087",
                        "CL:0000904",
                        "CL:0000897",
                        "CL:0000895",
                        "CL:0000624",
                        "CL:0000084",
                    )
                ]
        if coords is not None:
            feature_ids = set(coords[1])
            rows = [r for r in rows if r.get("soma_dim_1") in feature_ids]
        if column_names is not None:
            rows = [{k: r.get(k) for k in column_names} for r in rows]
        return self._wrap(rows)

    def _wrap(self, rows: list[dict]):
        class _Reader:
            def tables(self_inner):
                return self_inner

            def concat(self_inner):
                return self_inner

            def to_pylist(self_inner):
                return list(rows)

        return _Reader()


def _build_fake_census():
    summary_rows = [
        {"soma_joinid": 0, "label": "census_schema_version", "value": "2.4.0"},
        {"soma_joinid": 1, "label": "census_build_date", "value": "2025-11-08"},
        {"soma_joinid": 2, "label": "dataset_schema_version", "value": "7.0.0"},
        {"soma_joinid": 3, "label": "total_cell_count", "value": "217768036"},
        {"soma_joinid": 4, "label": "unique_cell_count", "value": "125463259"},
    ]
    organisms_rows = [
        {
            "soma_joinid": 0,
            "organism_ontology_term_id": "NCBITaxon:9606",
            "organism_label": "Homo sapiens",
            "organism": "homo_sapiens",
        },
        {
            "soma_joinid": 3,
            "organism_ontology_term_id": "NCBITaxon:9544",
            "organism_label": "Macaca mulatta",
            "organism": "macaca_mulatta",
        },
    ]
    scc_rows = [
        {
            "soma_joinid": 81,
            "organism": "homo_sapiens",
            "category": "all",
            "label": "na",
            "ontology_term_id": "na",
            "total_cell_count": 162025130,
            "unique_cell_count": 99633637,
        },
        {
            "soma_joinid": 1820,
            "organism": "macaca_mulatta",
            "category": "all",
            "label": "na",
            "ontology_term_id": "na",
            "total_cell_count": 7010229,
            "unique_cell_count": 2929014,
        },
    ]
    datasets_rows = [
        {
            "soma_joinid": 10,
            "dataset_id": "3faad104-2ab8-4434-816d-474d8d2641db",
            "dataset_version_id": "1e44db10-b572-46cc-adae-dcc7acd44ca6",
            "collection_id": "dde06e0f-ab3b-46be-96a2-a8082383c4a1",
            "collection_name": "OneK1K",
            "collection_doi": "10.1126/science.abf3041",
            "dataset_title": "OneK1K PBMC",
            "dataset_total_cell_count": 1248980,
        },
        {
            "soma_joinid": 20,
            "dataset_id": "2e877cd3-5587-4fc1-8667-a48fe9e2a695",
            "dataset_version_id": "3e2a52fb-1237-4009-89f7-7e580cb74bd2",
            "collection_id": "6e067060-f7e4-466c-86f3-ec3dd33c0381",
            "collection_name": "Preterm Rhesus Lung",
            "collection_doi": "10.1126/scitranslmed.abl8574",
            "dataset_title": "Inflammatory blockade in premature Rhesus macaques",
            "dataset_total_cell_count": 120042,
        },
        {
            "soma_joinid": 21,
            "dataset_id": "fc6ef080-9e5f-4aea-b9c4-a45a208bd288",
            "dataset_version_id": "4ff87ad3-c44a-4b72-acf0-291999d6b675",
            "collection_id": "e1fa9900-3fc9-4b57-9dce-c95724c88716",
            "collection_name": "Primate dlPFC",
            "collection_doi": "10.1126/science.abo7257",
            "dataset_title": "Single-nucleus transcriptome data from the dlPFC: Rhesus",
            "dataset_total_cell_count": 131032,
        },
    ]

    hs_var = _FakeTable(
        [
            {
                "soma_joinid": 1995,
                "feature_id": "ENSG00000178562",
                "feature_name": "CD28",
                "feature_type": "protein_coding",
                "feature_length": 2920,
                "nnz": 6677612,
                "n_measured_obs": 158034458,
            }
        ]
    )
    hs_presence = _FakeTable([{"soma_dim_0": 10, "soma_dim_1": 1995, "soma_data": 1}])
    hs_obs = _FakeTable(
        [
            {
                "dataset_id": "3faad104-2ab8-4434-816d-474d8d2641db",
                "assay": "10x 3' v2",
                "assay_ontology_term_id": "EFO:0009899",
                "cell_type": "effector memory CD4-positive, alpha-beta T cell",
                "cell_type_ontology_term_id": "CL:0000905",
                "disease": "normal",
                "donor_id": "donor_1",
                "is_primary_data": True,
                "suspension_type": "cell",
                "tissue": "blood",
                "tissue_ontology_term_id": "UBERON:0000178",
                "tissue_general": "blood",
                "raw_sum": 2845.0,
                "nnz": 873,
            },
            {
                "dataset_id": "3faad104-2ab8-4434-816d-474d8d2641db",
                "assay": "10x 3' v2",
                "assay_ontology_term_id": "EFO:0009899",
                "cell_type": "CD4-positive, alpha-beta T cell",
                "cell_type_ontology_term_id": "CL:0000624",
                "disease": "normal",
                "donor_id": "donor_1",
                "is_primary_data": True,
                "suspension_type": "cell",
                "tissue": "blood",
                "tissue_ontology_term_id": "UBERON:0000178",
                "tissue_general": "blood",
                "raw_sum": 2900.0,
                "nnz": 890,
            },
        ]
    )

    mm_var = _FakeTable(
        [
            {
                "soma_joinid": 23595,
                "feature_id": "ENSMMUG00000057214",
                "feature_name": "CD28",
                "feature_type": "protein_coding",
                "feature_length": 3611,
                "nnz": 5325,
                "n_measured_obs": 6890187,
            }
        ]
    )
    # Dataset 20 (fetal lung) does NOT measure CD28; dataset 21 (dlPFC) DOES measure CD28
    mm_presence = _FakeTable([{"soma_dim_0": 21, "soma_dim_1": 23595, "soma_data": 1}])
    mm_obs = _FakeTable(
        [
            {
                "dataset_id": "2e877cd3-5587-4fc1-8667-a48fe9e2a695",
                "assay": "10x 3' v3",
                "assay_ontology_term_id": "EFO:0009922",
                "cell_type": "T cell",
                "cell_type_ontology_term_id": "CL:0000084",
                "development_stage": "late embryonic stage",
                "disease": "normal",
                "donor_id": "507",
                "is_primary_data": True,
                "suspension_type": "cell",
                "tissue": "lung",
                "tissue_ontology_term_id": "UBERON:0002048",
                "tissue_general": "lung",
                "raw_sum": 3823.0,
                "nnz": 1123,
            },
            {
                "dataset_id": "fc6ef080-9e5f-4aea-b9c4-a45a208bd288",
                "assay": "10x 3' v3",
                "assay_ontology_term_id": "EFO:0009922",
                "cell_type": "T cell",
                "cell_type_ontology_term_id": "CL:0000084",
                "development_stage": "prime adult stage",
                "disease": "normal",
                "donor_id": "RMB161",
                "is_primary_data": True,
                "suspension_type": "nucleus",
                "tissue": "dorsolateral prefrontal cortex",
                "tissue_ontology_term_id": "UBERON:0009834",
                "tissue_general": "brain",
                "raw_sum": 1180.0,
                "nnz": 946,
            },
        ]
    )

    class _FakeRNA:
        def __init__(self, var_tbl, presence_tbl):
            self.var = var_tbl
            self._items = {
                "X": {"raw": object(), "normalized": object()},
                "feature_dataset_presence_matrix": presence_tbl,
            }

        def __getitem__(self, key):
            return self._items[key]

    def _make_org(var_tbl, presence_tbl, obs_tbl):
        return SimpleNamespace(ms={"RNA": _FakeRNA(var_tbl, presence_tbl)}, obs=obs_tbl)

    class _FakeCensusContext:
        def __enter__(self):
            return {
                "census_info": {
                    "summary": _FakeTable(summary_rows),
                    "organisms": _FakeTable(organisms_rows),
                    "summary_cell_counts": _FakeTable(scc_rows),
                    "datasets": _FakeTable(datasets_rows),
                },
                "census_data": {
                    "homo_sapiens": _make_org(hs_var, hs_presence, hs_obs),
                    "macaca_mulatta": _make_org(mm_var, mm_presence, mm_obs),
                },
            }

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    return _FakeCensusContext()


class TestCellxGeneDiscovery(unittest.TestCase):
    def setUp(self):
        self._orig_module = sys.modules.get("cellxgene_census")
        fake_mod = SimpleNamespace(
            __version__="1.18.0",
            get_census_version_directory=lambda: {
                "2025-11-08": {"release_build": "2025-11-08", "flags": {"lts": True}}
            },
            open_soma=lambda census_version="2025-11-08": _build_fake_census(),
        )
        sys.modules["cellxgene_census"] = fake_mod

    def tearDown(self):
        if self._orig_module is None:
            sys.modules.pop("cellxgene_census", None)
        else:
            sys.modules["cellxgene_census"] = self._orig_module

    def test_run_census_discovery_reports_feasibility_and_presence(self):
        payload = cellxgene_discovery.run_census_discovery(
            census_version="2025-11-08",
            gene_symbol="CD28",
        )
        self.assertEqual(payload["census_version"], "2025-11-08")
        self.assertTrue(payload["pinned_version_in_directory"])
        self.assertEqual(payload["feasibility_assessment"]["verdict"], "not feasible")
        self.assertEqual(payload["feasibility_assessment"]["human_side_status"], "feasible")
        self.assertEqual(payload["feasibility_assessment"]["macaque_side_status"], "unavailable")

        # Verify gene metadata & presence counts
        hs_gene = payload["gene_metadata"]["homo_sapiens"]["gene_records"][0]
        mm_gene = payload["gene_metadata"]["macaca_mulatta"]["gene_records"][0]
        self.assertEqual(hs_gene["feature_id"], "ENSG00000178562")
        self.assertEqual(hs_gene["n_datasets_measuring_gene"], 1)
        self.assertEqual(mm_gene["feature_id"], "ENSMMUG00000057214")
        self.assertEqual(mm_gene["n_datasets_measuring_gene"], 1)

        # Verify macaque evaluation distinguishes unmeasured lung vs measured dlPFC
        mm_eval = payload["macaca_mulatta_evaluation"]
        self.assertEqual(mm_eval["cd4_effector_memory_cells"], 0)
        self.assertEqual(mm_eval["any_cd4_annotated_cells"], 0)
        self.assertEqual(mm_eval["blood_or_lymphoid_tissue_cells"], 0)
        by_ds = {d["dataset_id"]: d for d in mm_eval["all_datasets"]}
        self.assertFalse(by_ds["2e877cd3-5587-4fc1-8667-a48fe9e2a695"]["cd28_measured_in_dataset"])
        self.assertTrue(by_ds["fc6ef080-9e5f-4aea-b9c4-a45a208bd288"]["cd28_measured_in_dataset"])

        # Verify human evaluation captures CD4+ subtype distinction
        hs_eval = payload["homo_sapiens_evaluation"]
        self.assertEqual(hs_eval["total_cd4_em_datasets"], 1)
        top_ds = hs_eval["top_candidate_datasets"][0]
        self.assertTrue(top_ds["cd28_measured_in_dataset"])
        self.assertIn(
            "effector memory CD4-positive, alpha-beta T cell (CL:0000905)",
            top_ds["distinguished_cd4_t_subtypes"],
        )
        self.assertIn(
            "CD4-positive, alpha-beta T cell (CL:0000624)",
            top_ds["distinguished_cd4_t_subtypes"],
        )

    def test_cli_writes_json_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "discovery.json"
            rc = cellxgene_discovery.main(
                ["--census-version", "2025-11-08", "--gene", "CD28", "--output", str(out_path)]
            )
            self.assertEqual(rc, 0)
            written = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(written["feasibility_assessment"]["verdict"], "not feasible")


if __name__ == "__main__":
    unittest.main()
