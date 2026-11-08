from __future__ import annotations
"""Unit tests for Backend.tools.cell_expression (mocked SOMA fixtures)."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import patch

from tools.cell_census import (
    DEFAULT_CENSUS_VERSION,
    DEFAULT_HUMAN_DATASET_ID,
    LayerResult,
    ResolvedQuery,
    run_census_expression,
)


class _FakeTable:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def to_pylist(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _FakeRead:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def concat(self) -> _FakeTable:
        return _FakeTable(self._rows)

    def tables(self) -> "_FakeRead":
        return self


class _FakeSOMAArray:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.read_calls: list[dict[str, Any]] = []

    def read(self, **kwargs: Any) -> _FakeRead:
        self.read_calls.append(kwargs)
        coords = kwargs.get("coords")
        value_filter = kwargs.get("value_filter")
        rows = list(self._rows)

        if coords is not None and len(coords) == 2:
            dim0_sel, dim1_sel = coords
            if isinstance(dim0_sel, list):
                dim0_set = set(dim0_sel)
                rows = [r for r in rows if int(r.get("soma_dim_0", -1)) in dim0_set]
            if isinstance(dim1_sel, list):
                dim1_set = set(dim1_sel)
                rows = [r for r in rows if int(r.get("soma_dim_1", -1)) in dim1_set]

        if value_filter:
            if f"dataset_id == '{DEFAULT_HUMAN_DATASET_ID}'" in value_filter:
                rows = [
                    r
                    for r in rows
                    if r.get("dataset_id") == DEFAULT_HUMAN_DATASET_ID
                    and bool(r.get("is_primary_data"))
                    and r.get("cell_type_ontology_term_id")
                    in ("CL:0000905", "CL:0001087")
                ]

        return _FakeRead(rows)


class _FakeRNA:
    def __init__(
        self,
        var_rows: list[dict[str, Any]],
        presence_rows: list[dict[str, Any]],
        x_raw_rows: list[dict[str, Any]],
    ) -> None:
        self.var = _FakeSOMAArray(var_rows)
        self.presence_array = _FakeSOMAArray(presence_rows)
        self.x_raw_array = _FakeSOMAArray(x_raw_rows)
        self._items: dict[str, Any] = {
            "X": {"raw": self.x_raw_array},
            "feature_dataset_presence_matrix": self.presence_array,
        }

    def __getitem__(self, key: str) -> Any:
        return self._items[key]


def _build_fake_census(
    *,
    human_gene_measured: bool = True,
) -> tuple[dict[str, Any], _FakeRNA, _FakeRNA]:
    summary_rows = [
        {"label": "census_schema_version", "value": "2.4.0"},
        {"label": "census_build_date", "value": DEFAULT_CENSUS_VERSION},
        {"label": "dataset_schema_version", "value": "7.0.0"},
    ]
    datasets_rows = [
        {
            "soma_joinid": 10,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "dataset_version_id": "v1",
            "collection_id": "c-pbmc",
            "collection_name": "Multimodal PBMC reference atlas",
            "collection_doi": "10.1016/j.cell.2021.04.048",
            "dataset_title": "nygc multimodal pbmc",
            "dataset_total_cell_count": 161764,
        },
        {
            "soma_joinid": 20,
            "dataset_id": "2e877cd3-5587-4fc1-8667-a48fe9e2a695",
            "dataset_version_id": "v2",
            "collection_id": "c-lung",
            "collection_name": "Prenatal immunity in rhesus macaque",
            "collection_doi": "10.1126/scitranslmed.abl8574",
            "dataset_title": "Rhesus macaque prenatal lung immune cells",
            "dataset_total_cell_count": 120042,
        },
        {
            "soma_joinid": 21,
            "dataset_id": "fc6ef080-9e5f-4aea-b9c4-a45a208bd288",
            "dataset_version_id": "v3",
            "collection_id": "c-dlpfc",
            "collection_name": "Primate dlPFC evolution",
            "collection_doi": "10.1126/science.abo7257",
            "dataset_title": "Adult rhesus macaque dlPFC snRNA-seq",
            "dataset_total_cell_count": 131032,
        },
    ]

    hs_var_rows = [
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
    hs_presence_rows = (
        [{"soma_dim_0": 10, "soma_dim_1": 1995, "soma_data": 1}]
        if human_gene_measured
        else []
    )
    # 5 primary CD4+ effector-memory T cells in human PBMC dataset:
    # joinids 100, 101, 102 have CD28 counts > 0 (3 detected); 103, 104 have 0 (2 undetected)
    hs_obs_rows = [
        {
            "soma_joinid": 100,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "effector memory CD4-positive, alpha-beta T cell",
            "cell_type_ontology_term_id": "CL:0000905",
            "development_stage": "human adult stage",
            "disease": "normal",
            "donor_id": "donor_1",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "blood",
            "tissue_ontology_term_id": "UBERON:0000178",
            "tissue_general": "blood",
            "raw_sum": 4200.0,
            "nnz": 1500,
        },
        {
            "soma_joinid": 101,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "effector memory CD4-positive, alpha-beta T cell",
            "cell_type_ontology_term_id": "CL:0000905",
            "development_stage": "human adult stage",
            "disease": "normal",
            "donor_id": "donor_1",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "blood",
            "tissue_ontology_term_id": "UBERON:0000178",
            "tissue_general": "blood",
            "raw_sum": 4500.0,
            "nnz": 1600,
        },
        {
            "soma_joinid": 102,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "effector memory CD4-positive, alpha-beta T cell",
            "cell_type_ontology_term_id": "CL:0000905",
            "development_stage": "human adult stage",
            "disease": "normal",
            "donor_id": "donor_2",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "blood",
            "tissue_ontology_term_id": "UBERON:0000178",
            "tissue_general": "blood",
            "raw_sum": 3900.0,
            "nnz": 1400,
        },
        {
            "soma_joinid": 103,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "effector memory CD4-positive, alpha-beta T cell",
            "cell_type_ontology_term_id": "CL:0000905",
            "development_stage": "human adult stage",
            "disease": "normal",
            "donor_id": "donor_2",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "blood",
            "tissue_ontology_term_id": "UBERON:0000178",
            "tissue_general": "blood",
            "raw_sum": 3800.0,
            "nnz": 1350,
        },
        {
            "soma_joinid": 104,
            "dataset_id": DEFAULT_HUMAN_DATASET_ID,
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "effector memory CD4-positive, alpha-beta T cell",
            "cell_type_ontology_term_id": "CL:0000905",
            "development_stage": "human adult stage",
            "disease": "normal",
            "donor_id": "donor_2",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "blood",
            "tissue_ontology_term_id": "UBERON:0000178",
            "tissue_general": "blood",
            "raw_sum": 4100.0,
            "nnz": 1480,
        },
    ]
    hs_x_raw_rows = [
        {"soma_dim_0": 100, "soma_dim_1": 1995, "soma_data": 2.0},
        {"soma_dim_0": 101, "soma_dim_1": 1995, "soma_data": 1.0},
        {"soma_dim_0": 102, "soma_dim_1": 1995, "soma_data": 3.0},
    ]

    mm_var_rows = [
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
    # Dataset 21 (dlPFC) measures ENSMMUG00000057214; dataset 20 (fetal lung) does NOT
    mm_presence_rows = [
        {"soma_dim_0": 21, "soma_dim_1": 23595, "soma_data": 1}
    ]
    mm_obs_rows = [
        {
            "soma_joinid": 500,
            "dataset_id": "2e877cd3-5587-4fc1-8667-a48fe9e2a695",
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "T cell",
            "cell_type_ontology_term_id": "CL:0000084",
            "development_stage": "late embryonic stage",
            "disease": "normal",
            "donor_id": "mm_fetal_1",
            "is_primary_data": True,
            "suspension_type": "cell",
            "tissue": "lung",
            "tissue_ontology_term_id": "UBERON:0002048",
            "tissue_general": "lung",
        },
        {
            "soma_joinid": 600,
            "dataset_id": "fc6ef080-9e5f-4aea-b9c4-a45a208bd288",
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "T cell",
            "cell_type_ontology_term_id": "CL:0000084",
            "development_stage": "prime adult stage",
            "disease": "normal",
            "donor_id": "mm_adult_1",
            "is_primary_data": True,
            "suspension_type": "nucleus",
            "tissue": "dorsolateral prefrontal cortex",
            "tissue_ontology_term_id": "UBERON:0009834",
            "tissue_general": "brain",
        },
        {
            "soma_joinid": 601,
            "dataset_id": "fc6ef080-9e5f-4aea-b9c4-a45a208bd288",
            "assay": "10x 3' v3",
            "assay_ontology_term_id": "EFO:0009922",
            "cell_type": "T cell",
            "cell_type_ontology_term_id": "CL:0000084",
            "development_stage": "prime adult stage",
            "disease": "normal",
            "donor_id": "mm_adult_2",
            "is_primary_data": True,
            "suspension_type": "nucleus",
            "tissue": "dorsolateral prefrontal cortex",
            "tissue_ontology_term_id": "UBERON:0009834",
            "tissue_general": "brain",
        },
    ]
    mm_x_raw_rows = [
        {"soma_dim_0": 600, "soma_dim_1": 23595, "soma_data": 1.0}
    ]

    hs_rna = _FakeRNA(hs_var_rows, hs_presence_rows, hs_x_raw_rows)
    mm_rna = _FakeRNA(mm_var_rows, mm_presence_rows, mm_x_raw_rows)

    census = {
        "census_info": {
            "summary": _FakeSOMAArray(summary_rows),
            "datasets": _FakeSOMAArray(datasets_rows),
        },
        "census_data": {
            "homo_sapiens": SimpleNamespace(
                ms={"RNA": hs_rna},
                obs=_FakeSOMAArray(hs_obs_rows),
            ),
            "macaca_mulatta": SimpleNamespace(
                ms={"RNA": mm_rna},
                obs=_FakeSOMAArray(mm_obs_rows),
            ),
        },
    }
    return census, hs_rna, mm_rna


class TestCellExpressionModule(unittest.TestCase):
    def test_missing_gene_returns_unavailable(self) -> None:
        query = ResolvedQuery(
            species="macaca_mulatta",
            sequence="MLRLLLALNLFPSIQVTGNKILVKQSPMLVAYDNAVNLSCKYSYNLFSREFRASLHKGLDSAVEVCVVYGNYSQQLQVYSKTGFNCDGKLGNESVTFYLQNLYVNQTDIYFCKIEVMYPPPYLDNEKSNGTIIHVKGKHLCPSPLFPGPSKPFWVLVVVGGVLACYSLLVTVAFIIFWVRSKRSRLLHSDYMNMTPRRPGPTRKHYQPYAPPRDFAAYRS",
            sequence_label=None,
            gene=None,
        )
        result = run_census_expression(query)
        self.assertIsInstance(result, LayerResult)
        self.assertEqual(result.layer, "cell_expression")
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.gene)
        self.assertEqual(result.observations, [])
        self.assertTrue(
            any("Needs a resolved gene identifier" in lim for lim in result.limitations)
        )

    def test_cd28_human_vs_macaque_returns_incomplete_with_verified_evidence(self) -> None:
        fake_census, _, _ = _build_fake_census(human_gene_measured=True)
        opened_versions: list[str] = []

        @contextmanager
        def _fake_open_soma(census_version: str = DEFAULT_CENSUS_VERSION):
            opened_versions.append(census_version)
            yield fake_census

        fake_module = SimpleNamespace(
            __version__="1.18.0",
            open_soma=_fake_open_soma,
        )

        query = ResolvedQuery(
            species="macaca_mulatta",
            sequence="MLRLLLALNLFPSIQVTGNKILVKQSPMLVAYDNAVNLSCKYSYNLFSREFRASLHKGLDSAVEVCVVYGNYSQQLQVYSKTGFNCDGKLGNESVTFYLQNLYVNQTDIYFCKIEVMYPPPYLDNEKSNGTIIHVKGKHLCPSPLFPGPSKPFWVLVVVGGVLACYSLLVTVAFIIFWVRSKRSRLLHSDYMNMTPRRPGPTRKHYQPYAPPRDFAAYRS",
            sequence_label=">CD28",
            gene="CD28",
        )
        with patch.dict("sys.modules", {"cellxgene_census": fake_module}):
            result = run_census_expression(query)
            direct_result = run_census_expression("CD28", "macaca_mulatta")

        self.assertEqual(opened_versions, [DEFAULT_CENSUS_VERSION, DEFAULT_CENSUS_VERSION])
        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.layer, "cell_expression")
        self.assertEqual(result.gene, "CD28")
        self.assertEqual(result.species, "macaca_mulatta")
        self.assertEqual(result.data_version, "CELLxGENE Census 2025-11-08 (schema 2.4.0)")
        self.assertEqual(
            result.model_dump(mode="json", by_alias=True),
            direct_result.model_dump(mode="json", by_alias=True),
        )

        obs_by_field = {o.field: o for o in result.observations}
        # 1. Human detection fraction, cell counts, dataset ID, assay, tissue, donor info
        self.assertIn("human_cd28_detection_fraction", obs_by_field)
        self.assertIn("0.6000 (60.00%; 3 / 5 primary cells", obs_by_field["human_cd28_detection_fraction"].value)
        self.assertIn("across 2 donors", obs_by_field["human_cd28_detection_fraction"].value)

        self.assertIn("human_dataset_provenance", obs_by_field)
        self.assertIn(DEFAULT_HUMAN_DATASET_ID, obs_by_field["human_dataset_provenance"].value)
        self.assertIn("blood (UBERON:0000178)", obs_by_field["human_dataset_provenance"].value)
        self.assertIn("10x 3' v3 (EFO:0009922)", obs_by_field["human_dataset_provenance"].value)

        # 2. Rhesus macaque absence of comparable CD4+ effector-memory datasets
        self.assertIn("animal_cd4_effector_memory_availability", obs_by_field)
        self.assertIn(
            "0 CD4+ effector-memory T cells (CL:0000905, CL:0001087)",
            obs_by_field["animal_cd4_effector_memory_availability"].value,
        )
        self.assertIn(
            "0 blood/lymphoid cells",
            obs_by_field["animal_cd4_effector_memory_availability"].value,
        )

        # 3. Dataset-level measurement check on macaque generic T-cell datasets
        fetal_lung_obs = obs_by_field["animal_noncomparable_t_cell_dataset_2e877cd3"]
        self.assertIn("UNMEASURED", fetal_lung_obs.value)
        self.assertIn("feature_dataset_presence_matrix=0", fetal_lung_obs.value)

        dlpfc_obs = obs_by_field["animal_noncomparable_t_cell_dataset_fc6ef080"]
        self.assertIn("MEASURED", dlpfc_obs.value)
        self.assertIn("1 / 2 generic T-cell (CL:0000084) nucleus records detected (0.5000 / 50.00%)", dlpfc_obs.value)

        # 4. Explicit distinction between unmeasured, undetected, and biologically absent
        self.assertIn("measurement_state_distinction", obs_by_field)
        distinction_val = obs_by_field["measurement_state_distinction"].value
        self.assertIn("unmeasured", distinction_val)
        self.assertIn("undetected", distinction_val)
        self.assertIn("biologically absent", distinction_val)

        # 5. Inconclusive cross-species comparison (no invented biological difference)
        self.assertIn("cross_species_comparison", obs_by_field)
        self.assertTrue(
            obs_by_field["cross_species_comparison"].value.startswith("inconclusive:")
        )

        # 6. Every Observation.source_record_id resolves to a SourceRecord in result.source_records
        source_ids = {s.id for s in result.source_records}
        self.assertGreaterEqual(len(source_ids), 5)
        for obs in result.observations:
            self.assertIsNotNone(obs.source_record_id)
            self.assertIn(obs.source_record_id, source_ids)

        # 7. Wire format check: top-level snake_case, nested Observation sourceRecordId camelCase
        dumped = result.model_dump(mode="json", by_alias=True)
        self.assertIn("source_records", dumped)
        self.assertIn("data_version", dumped)
        self.assertIn("sourceRecordId", dumped["observations"][0])

    def test_unmeasured_human_gene_refuses_zero_interpretation(self) -> None:
        fake_census, hs_rna, _ = _build_fake_census(human_gene_measured=False)

        @contextmanager
        def _fake_open_soma(census_version: str = DEFAULT_CENSUS_VERSION):
            yield fake_census

        fake_module = SimpleNamespace(open_soma=_fake_open_soma)
        with patch.dict("sys.modules", {"cellxgene_census": fake_module}):
            result = run_census_expression("CD28", "macaca_mulatta")

        self.assertEqual(result.status, "unavailable")
        # X['raw'] must NOT have been read when feature_dataset_presence_matrix is 0
        self.assertEqual(len(hs_rna.x_raw_array.read_calls), 0)
        obs_by_field = {o.field: o for o in result.observations}
        self.assertIn("human_gene_measurement_status", obs_by_field)
        self.assertIn("unmeasured in dataset", obs_by_field["human_gene_measurement_status"].value)
        self.assertTrue(
            any("unmeasured" in lim for lim in result.limitations)
        )

    def test_species_not_in_census_returns_incomplete(self) -> None:
        fake_census, _, _ = _build_fake_census(human_gene_measured=True)

        @contextmanager
        def _fake_open_soma(census_version: str = DEFAULT_CENSUS_VERSION):
            yield fake_census

        fake_module = SimpleNamespace(open_soma=_fake_open_soma)
        with patch.dict("sys.modules", {"cellxgene_census": fake_module}):
            result = run_census_expression("CD28", "macaca_fascicularis")

        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.species, "macaca_fascicularis")
        obs_by_field = {o.field: o for o in result.observations}
        self.assertIn("human_cd28_detection_fraction", obs_by_field)
        self.assertIn("animal_species_availability", obs_by_field)
        self.assertIn("not indexed in CELLxGENE Census", obs_by_field["animal_species_availability"].value)
        self.assertTrue(
            obs_by_field["cross_species_comparison"].value.startswith("inconclusive:")
        )

    def test_soma_exception_returns_unavailable(self) -> None:
        @contextmanager
        def _failing_open_soma(census_version: str = DEFAULT_CENSUS_VERSION):
            raise RuntimeError("Simulated SOMA S3 timeout")
            yield {}

        fake_module = SimpleNamespace(open_soma=_failing_open_soma)
        with patch.dict("sys.modules", {"cellxgene_census": fake_module}):
            result = run_census_expression("CD28", "macaca_mulatta")

        self.assertEqual(result.status, "unavailable")
        self.assertTrue(
            any("Simulated SOMA S3 timeout" in lim for lim in result.limitations)
        )

    def test_live_smoke_output_artifact_contract(self) -> None:
        live_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "benchmarks"
            / "census_CD28_macaca_mulatta.json"
        )
        self.assertTrue(live_path.exists(), f"Expected live smoke output at {live_path}")
        raw = json.loads(live_path.read_text(encoding="utf-8"))
        validated = LayerResult.model_validate(raw)

        self.assertEqual(validated.gene, "CD28")
        self.assertEqual(validated.species, "macaca_mulatta")
        self.assertEqual(validated.layer, "cell_expression")
        self.assertEqual(validated.status, "incomplete")
        self.assertEqual(validated.data_version, "CELLxGENE Census 2025-11-08 (schema 2.4.0)")

        obs_map = {o.field: o for o in validated.observations}
        self.assertIn(
            "0.3337 (33.37%; 1429 / 4282 primary cells",
            obs_map["human_cd28_detection_fraction"].value,
        )
        self.assertIn(
            "0 CD4+ effector-memory T cells (CL:0000905, CL:0001087)",
            obs_map["animal_cd4_effector_memory_availability"].value,
        )
        self.assertIn(
            "UNMEASURED",
            obs_map["animal_noncomparable_t_cell_dataset_2e877cd3"].value,
        )
        self.assertIn(
            "17 / 185 generic T-cell (CL:0000084) nucleus records detected (0.0919 / 9.19%)",
            obs_map["animal_noncomparable_t_cell_dataset_fc6ef080"].value,
        )
        self.assertTrue(
            obs_map["cross_species_comparison"].value.startswith("inconclusive:")
        )

        source_ids = {s.id for s in validated.source_records}
        for obs in validated.observations:
            self.assertIn(obs.source_record_id, source_ids)


if __name__ == "__main__":
    unittest.main()
