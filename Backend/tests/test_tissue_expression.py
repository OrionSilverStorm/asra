"""Unit tests for Backend.tools.tissue_expression and Backend.tools.tissue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import unittest

from Backend.tools.tissue import run_tissue_expression as run_tissue_wrapper
from Backend.tools.tissue_expression import (
    DEFAULT_GTEX_DATASET_ID,
    LayerResult,
    ResolvedQuery,
    run_tissue_expression,
)


def _make_mock_http_fetcher(
    *,
    include_homologs: bool = True,
    animal_found_in_search: bool = True,
    fail_gtex: bool = False,
) -> Any:
    """Build a deterministic HTTP JSON fetcher for GTEx v2 and Bgee REST endpoints."""

    def _fetcher(url: str) -> dict[str, Any]:
        if fail_gtex and "gtexportal.org" in url:
            raise RuntimeError("Simulated GTEx API timeout")

        # ── GTEx reference/gene ────────────────────────────────────────────
        if "gtexportal.org/api/v2/reference/gene" in url:
            if "geneId=SLC29A1" in url:
                return {
                    "data": [
                        {
                            "gencodeId": "ENSG00000112759.16",
                            "gencodeVersion": "v26",
                            "geneSymbol": "SLC29A1",
                            "geneSymbolUpper": "SLC29A1",
                            "entrezGeneId": 2030,
                            "genomeBuild": "GRCh38/hg38",
                            "description": "solute carrier family 29 member 1",
                        }
                    ]
                }
            if "geneId=CD28" in url:
                return {
                    "data": [
                        {
                            "gencodeId": "ENSG00000178562.17",
                            "gencodeVersion": "v26",
                            "geneSymbol": "CD28",
                            "geneSymbolUpper": "CD28",
                            "entrezGeneId": 940,
                            "genomeBuild": "GRCh38/hg38",
                            "description": "CD28 molecule",
                        }
                    ]
                }
            return {"data": []}

        # ── GTEx expression/medianGeneExpression ───────────────────────────
        if "gtexportal.org/api/v2/expression/medianGeneExpression" in url:
            if "ENSG00000112759.16" in url:
                return {
                    "data": [
                        {
                            "tissueSiteDetailId": "Artery_Aorta",
                            "ontologyId": "UBERON:0001496",
                            "median": 190.26,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Adipose_Subcutaneous",
                            "ontologyId": "UBERON:0002190",
                            "median": 162.93,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Adrenal_Gland",
                            "ontologyId": "UBERON:0002369",
                            "median": 117.56,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Uterus",
                            "ontologyId": "UBERON:0000995",
                            "median": 94.16,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Lung",
                            "ontologyId": "UBERON:0008952",
                            "median": 70.24,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Spleen",
                            "ontologyId": "UBERON:0002106",
                            "median": 30.25,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Liver",
                            "ontologyId": "UBERON:0001114",
                            "median": 25.30,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Kidney_Cortex",
                            "ontologyId": "UBERON:0001225",
                            "median": 23.54,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                    ]
                }
            if "ENSG00000178562.17" in url:
                return {
                    "data": [
                        {
                            "tissueSiteDetailId": "Spleen",
                            "ontologyId": "UBERON:0002106",
                            "median": 6.06,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Cells_EBV-transformed_lymphocytes",
                            "ontologyId": "EFO:0000572",
                            "median": 4.82,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Whole_Blood",
                            "ontologyId": "UBERON:0013756",
                            "median": 3.41,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Lung",
                            "ontologyId": "UBERON:0008952",
                            "median": 2.30,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Colon_Transverse",
                            "ontologyId": "UBERON:0001157",
                            "median": 1.15,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Liver",
                            "ontologyId": "UBERON:0001114",
                            "median": 0.25,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                        {
                            "tissueSiteDetailId": "Brain_Frontal_Cortex_BA9",
                            "ontologyId": "UBERON:0009834",
                            "median": 0.03,
                            "unit": "TPM",
                            "datasetId": DEFAULT_GTEX_DATASET_ID,
                        },
                    ]
                }
            return {"data": []}

        # ── Bgee homologs ──────────────────────────────────────────────────
        if "bgee.org/api/" in url and "action=homologs" in url:
            if not include_homologs:
                return {"code": 200, "status": "SUCCESS", "data": {"orthologsByTaxon": []}}
            if "gene_id=ENSG00000112759" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "orthologsByTaxon": [
                            {
                                "taxon": {"scientificName": "Euarchontoglires"},
                                "genes": [
                                    {
                                        "geneId": "ENSMUSG00000023942",
                                        "name": "Slc29a1",
                                        "species": {
                                            "id": 10090,
                                            "genus": "Mus",
                                            "speciesName": "musculus",
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                }
            if "gene_id=ENSG00000178562" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "orthologsByTaxon": [
                            {
                                "taxon": {"scientificName": "Catarrhini"},
                                "genes": [
                                    {
                                        "geneId": "ENSMMUG00000057214",
                                        "name": "CD28",
                                        "species": {
                                            "id": 9544,
                                            "genus": "Macaca",
                                            "speciesName": "mulatta",
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                }

        # ── Bgee gene_search fallback ──────────────────────────────────────
        if "bgee.org/api/" in url and "action=gene_search" in url:
            if not animal_found_in_search:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {"result": {"geneMatches": []}},
                }
            return {
                "code": 200,
                "status": "SUCCESS",
                "data": {
                    "result": {
                        "geneMatches": [
                            {
                                "gene": {
                                    "geneId": "ENSMUSG00000099999",
                                    "name": "Cd80",
                                    "species": {"id": 10090},
                                },
                                "match": "cd28lg",
                                "matchSource": "synonym",
                            },
                            {
                                "gene": {
                                    "geneId": "ENSMUSG00000023942",
                                    "name": "Slc29a1",
                                    "species": {"id": 10090},
                                },
                                "match": "Slc29a1",
                                "matchSource": "name",
                            },
                        ]
                    }
                },
            }

        # ── Bgee general_info ──────────────────────────────────────────────
        if "bgee.org/api/" in url and "action=general_info" in url:
            if "ENSMUSG00000023942" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "genes": [
                            {
                                "geneId": "ENSMUSG00000023942",
                                "name": "Slc29a1",
                                "description": "solute carrier family 29 member 1",
                                "expressionSummary": "Expressed in adrenal gland and 214 other tissues.",
                                "species": {
                                    "id": 10090,
                                    "genomeVersion": "GRCm38.p6",
                                },
                            }
                        ]
                    },
                }
            if "ENSMMUG00000057214" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "genes": [
                            {
                                "geneId": "ENSMMUG00000057214",
                                "name": "CD28",
                                "description": "CD28 molecule",
                                "expressionSummary": "Expressed in spleen and 6 other tissues.",
                                "species": {
                                    "id": 9544,
                                    "genomeVersion": "Mmul_10",
                                },
                            }
                        ]
                    },
                }

        # ── Bgee expression calls ──────────────────────────────────────────
        if "bgee.org/api/" in url and "action=expression" in url:
            if "ENSMUSG00000023942" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "calls": [
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002107", "name": "liver"}
                                },
                                "expressionScore": {
                                    "expressionScore": "93.09",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "<= 1.00e-14",
                                "dataTypesWithData": ["Affymetrix", "RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002369", "name": "adrenal gland"}
                                },
                                "expressionScore": {
                                    "expressionScore": "91.51",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "7.72e-10",
                                "dataTypesWithData": ["Affymetrix", "RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002106", "name": "spleen"}
                                },
                                "expressionScore": {
                                    "expressionScore": "87.23",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "4.92e-13",
                                "dataTypesWithData": ["Affymetrix", "RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0000995", "name": "uterus"}
                                },
                                "expressionScore": {
                                    "expressionScore": "82.83",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "5.05e-8",
                                "dataTypesWithData": ["Affymetrix", "RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0001225", "name": "cortex of kidney"}
                                },
                                "expressionScore": {
                                    "expressionScore": "71.09",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "9.39e-9",
                                "dataTypesWithData": ["Affymetrix", "RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {
                                        "id": "UBERON:0002190",
                                        "name": "subcutaneous adipose tissue",
                                    }
                                },
                                "expressionScore": {
                                    "expressionScore": "68.79",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "0.005",
                                "dataTypesWithData": ["Affymetrix"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {
                                        "id": "UBERON:0001496",
                                        "name": "ascending aorta",
                                    }
                                },
                                "expressionScore": {
                                    "expressionScore": "41.08",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "0.008",
                                "dataTypesWithData": ["Affymetrix"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                        ]
                    },
                }
            if "ENSMMUG00000057214" in url:
                return {
                    "code": 200,
                    "status": "SUCCESS",
                    "data": {
                        "calls": [
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002106", "name": "spleen"}
                                },
                                "expressionScore": {
                                    "expressionScore": "72.96",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "1.83e-6",
                                "dataTypesWithData": ["RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0001155", "name": "colon"}
                                },
                                "expressionScore": {
                                    "expressionScore": "53.69",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "7.06e-4",
                                "dataTypesWithData": ["RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002107", "name": "liver"}
                                },
                                "expressionScore": {
                                    "expressionScore": "53.30",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "9.80e-4",
                                "dataTypesWithData": ["RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "gold",
                            },
                            {
                                "condition": {
                                    "anatEntity": {"id": "UBERON:0002048", "name": "lung"}
                                },
                                "expressionScore": {
                                    "expressionScore": "44.97",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "0.013",
                                "dataTypesWithData": ["RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "silver",
                            },
                            {
                                "condition": {
                                    "anatEntity": {
                                        "id": "UBERON:0009834",
                                        "name": "dorsolateral prefrontal cortex",
                                    }
                                },
                                "expressionScore": {
                                    "expressionScore": "38.75",
                                    "expressionScoreConfidence": "high",
                                },
                                "fdr": "0.044",
                                "dataTypesWithData": ["RNA-Seq"],
                                "expressionState": "expressed",
                                "expressionQuality": "silver",
                            },
                        ]
                    },
                }

        raise AssertionError(f"Unexpected URL in mock fetcher: {url}")

    return _fetcher


class TestTissueExpressionModule(unittest.TestCase):
    def test_wrapper_reexports_same_function(self) -> None:
        self.assertIs(run_tissue_wrapper, run_tissue_expression)

    def test_missing_gene_returns_unavailable(self) -> None:
        query = ResolvedQuery(
            species="mus_musculus",
            sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
            sequence_label=None,
            gene=None,
        )
        result = run_tissue_expression(query)
        self.assertIsInstance(result, LayerResult)
        self.assertEqual(result.layer, "tissue_expression")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.observations, [])
        self.assertTrue(
            any("Needs a resolved gene identifier" in lim for lim in result.limitations)
        )

    def test_slc29a1_human_vs_mouse_returns_ok_with_uberon_matches(self) -> None:
        fetcher = _make_mock_http_fetcher()
        query = ResolvedQuery(
            species="mus_musculus",
            sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
            sequence_label=">SLC29A1",
            gene="SLC29A1",
        )
        result = run_tissue_expression(query, http_get_json=fetcher)
        direct_result = run_tissue_expression(
            "SLC29A1", "mus_musculus", http_get_json=fetcher
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.layer, "tissue_expression")
        self.assertEqual(result.gene, "SLC29A1")
        self.assertEqual(result.species, "mus_musculus")
        self.assertIn("GTEx API v2 (gtex_v8, GENCODE v26, GRCh38/hg38)", result.data_version or "")
        self.assertIn("Bgee REST API v15 (mus_musculus GRCm38.p6)", result.data_version or "")
        self.assertEqual(
            result.model_dump(mode="json", by_alias=True),
            direct_result.model_dump(mode="json", by_alias=True),
        )

        obs_map = {o.field: o for o in result.observations}
        self.assertIn("ENSG00000112759.16", obs_map["human_gene_identifier"].value)
        self.assertIn("ENSMUSG00000023942", obs_map["animal_gene_identifier"].value)
        self.assertIn(
            "6 tissues matched by identical UBERON ID",
            obs_map["exact_uberon_tissue_matches"].value,
        )
        self.assertIn("matched_tissue_uberon_0001496", obs_map)
        self.assertIn("Artery_Aorta median=190.26 TPM", obs_map["matched_tissue_uberon_0001496"].value)
        self.assertIn(
            "scales (TPM vs 0-100 rank score) are not directly comparable for fold-change calculation",
            obs_map["matched_tissue_uberon_0001496"].value,
        )

        # Sub-structure <-> whole-organ UBERON correspondence for liver
        self.assertIn("granularity_mapped_organ_correspondences", obs_map)
        self.assertIn("UBERON:0001114", obs_map["granularity_mapped_organ_correspondences"].value)
        self.assertIn("UBERON:0002107", obs_map["granularity_mapped_organ_correspondences"].value)

        # Every Observation.source_record_id resolves to a valid SourceRecord.id
        source_ids = {s.id for s in result.source_records}
        self.assertEqual(
            source_ids,
            {
                "gtex-gtex_v8-ENSG00000112759",
                "ensembl-ENSG00000112759",
                "bgee-10090-ENSMUSG00000023942",
            },
        )
        for obs in result.observations:
            self.assertIn(obs.source_record_id, source_ids)

    def test_cd28_human_vs_macaque_returns_incomplete_due_to_sparse_animal_tissues(
        self,
    ) -> None:
        fetcher = _make_mock_http_fetcher()
        result = run_tissue_expression(
            "CD28", "macaca_mulatta", http_get_json=fetcher
        )

        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.gene, "CD28")
        self.assertEqual(result.species, "macaca_mulatta")

        obs_map = {o.field: o for o in result.observations}
        self.assertIn("ENSMMUG00000057214", obs_map["animal_gene_identifier"].value)
        self.assertIn(
            "2 tissues matched by identical UBERON ID",
            obs_map["exact_uberon_tissue_matches"].value,
        )
        self.assertIn("matched_tissue_uberon_0002106", obs_map)
        self.assertIn("Spleen median=6.06 TPM", obs_map["matched_tissue_uberon_0002106"].value)
        self.assertIn("expressionScore=72.96/100", obs_map["matched_tissue_uberon_0002106"].value)

        # Whole_Blood (UBERON:0013756) is flagged as unannotated in macaque, NOT biologically absent
        self.assertIn("missing_animal_tissue_coverage", obs_map)
        self.assertIn("Whole_Blood (UBERON:0013756=3.41 TPM)", obs_map["missing_animal_tissue_coverage"].value)
        self.assertIn(
            "NOT biological absence of expression",
            obs_map["missing_animal_tissue_coverage"].value,
        )
        self.assertIn(
            "incomplete animal tissue coverage",
            obs_map["scale_and_comparability_assessment"].value,
        )

    def test_gene_search_fallback_and_unresolved_animal_gene(self) -> None:
        # 1. Fallback to gene_search when homologs is empty
        fallback_fetcher = _make_mock_http_fetcher(
            include_homologs=False, animal_found_in_search=True
        )
        res_fallback = run_tissue_expression(
            "SLC29A1", "mus_musculus", http_get_json=fallback_fetcher
        )
        self.assertEqual(res_fallback.status, "ok")
        obs_map = {o.field: o for o in res_fallback.observations}
        self.assertIn("resolution=bgee_gene_search", obs_map["animal_gene_identifier"].value)

        # 2. Unresolved animal gene returns incomplete with human GTEx preserved
        unresolved_fetcher = _make_mock_http_fetcher(
            include_homologs=False, animal_found_in_search=False
        )
        res_unresolved = run_tissue_expression(
            "CD28", "mus_musculus", http_get_json=unresolved_fetcher
        )
        self.assertEqual(res_unresolved.status, "incomplete")
        obs_unresolved = {o.field: o for o in res_unresolved.observations}
        self.assertIn("human_gtex_tissue_summary", obs_unresolved)
        self.assertTrue(
            obs_unresolved["animal_gene_identifier"].value.startswith(
                "unmeasured/unresolved:"
            )
        )

    def test_gtex_failure_or_unknown_gene_returns_unavailable(self) -> None:
        fetcher = _make_mock_http_fetcher()
        unknown_res = run_tissue_expression(
            "NONEXISTENT_GENE_XYZ", "mus_musculus", http_get_json=fetcher
        )
        self.assertEqual(unknown_res.status, "unavailable")

        failing_fetcher = _make_mock_http_fetcher(fail_gtex=True)
        err_res = run_tissue_expression(
            "SLC29A1", "mus_musculus", http_get_json=failing_fetcher
        )
        self.assertEqual(err_res.status, "unavailable")
        self.assertTrue(
            any("Simulated GTEx API timeout" in lim for lim in err_res.limitations)
        )

    def test_live_smoke_output_artifacts_contract(self) -> None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        slc_path = data_dir / "tissue_expression_slc29a1_live.json"
        cd28_path = data_dir / "tissue_expression_cd28_live.json"
        self.assertTrue(slc_path.exists(), f"Missing live output at {slc_path}")
        self.assertTrue(cd28_path.exists(), f"Missing live output at {cd28_path}")

        slc_res = LayerResult.model_validate(
            json.loads(slc_path.read_text(encoding="utf-8"))
        )
        self.assertEqual(slc_res.gene, "SLC29A1")
        self.assertEqual(slc_res.species, "mus_musculus")
        self.assertEqual(slc_res.layer, "tissue_expression")
        self.assertEqual(slc_res.status, "ok")
        slc_obs = {o.field: o for o in slc_res.observations}
        self.assertIn(
            "14 tissues matched by identical UBERON ID",
            slc_obs["exact_uberon_tissue_matches"].value,
        )
        slc_sources = {s.id for s in slc_res.source_records}
        for obs in slc_res.observations:
            self.assertIn(obs.source_record_id, slc_sources)

        cd28_res = LayerResult.model_validate(
            json.loads(cd28_path.read_text(encoding="utf-8"))
        )
        self.assertEqual(cd28_res.gene, "CD28")
        self.assertEqual(cd28_res.species, "macaca_mulatta")
        self.assertEqual(cd28_res.layer, "tissue_expression")
        self.assertEqual(cd28_res.status, "incomplete")
        cd28_obs = {o.field: o for o in cd28_res.observations}
        self.assertIn(
            "2 tissues matched by identical UBERON ID",
            cd28_obs["exact_uberon_tissue_matches"].value,
        )
        self.assertIn(
            "Whole_Blood (UBERON:0013756=3.41 TPM)",
            cd28_obs["missing_animal_tissue_coverage"].value,
        )
        cd28_sources = {s.id for s in cd28_res.source_records}
        for obs in cd28_res.observations:
            self.assertIn(obs.source_record_id, cd28_sources)


if __name__ == "__main__":
    unittest.main()
