# Role 4 Overnight Biological Validation Report

**Date:** 8 November 2026  
**Branch:** `audit/role4-biological-validation`  
**Base Commit (`origin/master`):** `3bbf30e2984173b69749858393b316eb8daf9565`  
**Scope:** Role 4 Biological Layers (`localisation`, `cell_expression`, `cell_census`, `tissue_expression`, `literature`) and cross-layer benchmark validation.

---

## A. Baseline

| Item | Value |
|---|---|
| Repository | `OrionSilverStorm/asra` |
| Validation Branch | `audit/role4-biological-validation` |
| Starting `origin/master` Commit | `3bbf30e2984173b69749858393b316eb8daf9565` |
| Baseline Role 4 Biological Suite (after fixing duplicate `__future__` imports in 2 test files) | **53 passed in 0.06s** |
| Post-Fix Role 4 Biological Suite (`test_expression_layers.py`, `test_localisation.py`, `test_cell_census.py`) | **57 passed in 0.08s** |
| Post-Fix Full Backend Suite (`Backend/tests/`) | **328 passed, 14 skipped in 0.52s** |

---

## B. Findings: Confirmed Bugs vs Expected Limitations

### B.1 Confirmed Software Bugs

| ID | Component | Status | Description & Live Evidence |
|---|---|---|---|
| **BUG-1** | `Backend/tests/test_cell_census.py`, `Backend/tests/test_cellxgene_discovery.py` | **FIXED** | Commit `640fe5f` inserted a duplicate `from __future__ import annotations` before the module docstring while line 4 already had one, raising `SyntaxError` during pytest collection. |
| **BUG-2** | `Backend/tools/cell_expression.py` (`_describe`) | **FIXED** | **WMG v2 percentage/denominator mismatch:** `stats["aggregated"]["pc"]` (`n / n_measured_cells`) was always paired with `label["total_count"]` (`n_all_cells` across all datasets in that tissue + cell type, including datasets that did not measure the gene). Across live WMG v2 (`snapshot_id = 1762972271`), `|pc - n / total_count| > 1e-4` in **666 / 4,183 (15.9%)** of human `SLC29A1` populations and **154 / 1,259 (12.2%)** of mouse `SLC29A1` populations (e.g. `SLC29A1` human `pancreas / progenitor cell` emitted `"28.89% (128 expressing of 876 cells)"` where `128 / 876 = 14.61% = tpc`, because only `443` of the `876` cells were in datasets measuring `SLC29A1`). `_describe()` now displays the `of {cells:,} cells` denominator only when it corresponds to `fraction` (`pc`). |
| **BUG-3** | `Backend/tools/cell_expression.py` (`_census`) | **FIXED** | **Census live SOMA routing latency on `CD28` / `macaca_mulatta`:** `_census()` previously checked `find_spec("cellxgene_census")` before checking `Backend/data/benchmarks/census_{gene}_{species}.json`, triggering a **408.38s** remote TileDB-SOMA scan on hosts with `cellxgene_census` installed. `_census()` now replays the verified recorded benchmark first when available, clearly labelling `data_version` with `(recorded run)` and adding a `Replayed a recorded live CELLxGENE Census run...` note to `limitations`. |
| **BUG-4** | `Backend/tools/localisation.py` (`_resolve_via_orthologue`) | **FIXED** | **UniProt gene-symbol-only lookup failed on rabbit `CRBN` and macaque `CD28`:** Rabbit `CRBN` (`A0A5F9CHQ0`) has `"genes": null` in UniProt (`gene_exact:CRBN` returns 0 hits), and rhesus/cynomolgus `CD28` have multiple unreviewed TrEMBL entries matching `gene_exact:CD28` (`A0A5F7ZKV3, Q0PDN4` and `Q0PDN3, Q0PEU6`). Added a verified fallback (`_resolve_via_orthologue`) using the 1-to-1 Ensembl orthologue (`xref:ensembl-{target_protein_id} AND organism_id:{taxon}`) and checking `uniProtKBCrossReferences` for exact `ProteinId` + `GeneId` agreement, while preserving `status = "partial"` (`LayerResult.status = "incomplete"`). |
| **BUG-5** | `Backend/agents/sceptic.py` (lines 169, 228–236) & `Backend/agents/investigator.py` (lines 34–39) | **Documented for Role 2** | `sceptic._check()` maps every `SourceRecord.id` in a layer to `layer.status` (`status_by_source = {s.id: l.status ...}`) and downgrades any claim citing a source in an `incomplete` layer to `concern = "flagged"` (`"Rests on incomplete data; downgraded."`). Consequently, curated peer-reviewed experimental literature (`Lai 2004`, `Lee 2006`, `Eastwood 2010`) attached to `incomplete` `localisation` or `cell_expression` layers is automatically downgraded. Additionally, `investigator.select_evidence()` drops `ambiguous_candidates` observations from `sequence` when `sequence.status == "unavailable"`. |
| **BUG-6** | `Backend/tools/resolver.py` (`resolve_orthologue`, `_symbol_gene_id`) & `Backend/tools/sequence_layer.py` | **Documented for Role 1/3** | (a) `resolve_orthologue()` lacks the gene-symbol tie-breaker used by `orthologue_gene_id()`, causing `sequence` to return `status = "unavailable"` on the `GAPDH` conserved control (`ENSMUSG00000057666` + 2 pseudogene paralogues). (b) `_symbol_gene_id()` does not catch `httpx.HTTPError` to raise `EnsemblAPIError` for `_with_retry()`. (c) `sequence_layer.py` returns `data_version = None` when `status = "ok"`. |

---

### B.2 Expected Biological & Database Limitations (Not Software Bugs)

| Case / Layer | Limitation | Scientific Justification |
|---|---|---|
| **Case 1 (`SLC29A1`, mouse) — `localisation`** | Canonical UniProt `Q99808` (human) lists only plasma membrane locations (`SL-0038`, `SL-0037`, `SL-0039`); mitochondrial membrane targeting (`Lai et al. 2004`, `Lee et al. 2006`) is absent from canonical UniProt comments, and mouse `Q9JIM1` is annotated `by_similarity` (`ECO:0000250`) from `Q99808`. | Returning `status: "incomplete"` and attaching curated experimental literature (`Lai 2004`, `Lee 2006`) accurately reflects both UniProt curation state and published experimental evidence. |
| **Case 2 (`CD28`, rhesus & cynomolgus macaque) — `cell_expression`** | CELLxGENE Census `2025-11-08` contains **0** `macaca_mulatta` `CD4+ effector-memory T cells (CL:0000905, CL:0001087)` and **0** blood/PBMC datasets, and does not index `macaca_fascicularis`. | Returning `status: "incomplete"` with human PBMC `CL:0000905` (`33.37%`, `1429 / 4282` cells across 8 donors, `ed5d841d-6346-47d4-ab2f-7119ad7e3a35`) and `Eastwood 2010` (`pub:eastwood2010`) avoids inventing animal scRNA-seq measurements. |
| **Case 3 (`GAPDH`, mouse) — `cell_expression`** | Specific mouse cell types show lower WMG detection (`brain / leptomeningeal cell: human 98.55%; mouse 0.58%`) despite conserved global median detection (`human 68.06%; mouse 67.87%` across 639 matched populations). | Known technical multi-mapping read loss across mouse `Gapdh` retrotransposed pseudogenes in 10x alignment pipelines, explicitly explained in `cell_expression.py` `limitations` and `median_detection_all_matched`. |
| **Case 4 (`CYP3A4`, mouse) — All layers** | Ensembl lists **9** mouse `ortholog_many2many` `Cyp3a` genes (`Cyp3a11`, `Cyp3a13`, `Cyp3a16`, `Cyp3a25`, `Cyp3a41a`, `Cyp3a41b`, `Cyp3a44`, `Cyp3a57`, `Cyp3a59`). | Refusing to pick an arbitrary mouse gene and reporting human-only expression with `status: "incomplete"` (and `sequence` `status: "unavailable"`) is required by the ASRA contract. |
| **Case 5 (`CRBN`, rabbit) — `localisation` & `cell_expression`** | Rabbit `A0A5F9CHQ0` is unreviewed (`TrEMBL`) with only automatic `ECO:0000256` (`ARBA`) annotations (`Cytoplasm SL-0086`, `Nucleus SL-0191`), and `oryctolagus_cuniculus` is not indexed in CELLxGENE. | `localisation` and `cell_expression` must remain `status: "incomplete"`. |
| **All Cases — `tissue_expression`** | Human GTEx reports quantitative median TPM (`gtex_v8`), whereas Bgee reports cross-experiment `expressionScore` (`0–100`) and qualitative calls. | Cross-platform fold changes are never computed across GTEx TPM and Bgee scores. |

---

## C. Changes Made on `audit/role4-biological-validation`

| File | Purpose of Modification | Tests Added / Updated | Integration Status |
|---|---|---|---|
| `Backend/tests/test_cell_census.py` | Removed duplicate line-1 `from __future__ import annotations` before module docstring (`BUG-1`). | Restored collection of 6 existing Census unit tests. | **READY TO REVIEW AND INTEGRATE** |
| `Backend/tests/test_cellxgene_discovery.py` | Removed duplicate line-1 `from __future__ import annotations` before module docstring (`BUG-1`). | Restored collection of 7 existing discovery unit tests. | **READY TO REVIEW AND INTEGRATE** |
| `Backend/tools/cell_expression.py` | 1. `_describe()`: Only displays `of {cells:,} cells` denominator when `cells` corresponds to `fraction` (`pc`), omitting incompatible `total_count` denominators (`BUG-2`).<br>2. `_census()`: Prefers recorded Census benchmark (`census_{gene}_{species}.json`) when present—clearly labelled as `(recorded run)` in `data_version` and `limitations`—avoiding a 408s live SOMA scan during the `CD28`/`macaca_mulatta` demo (`BUG-3`). | Added `test_wmg_omits_denominator_when_total_count_does_not_match_reported_pc` and `test_census_routing_prefers_recorded_benchmark_even_when_census_installed` in `Backend/tests/test_expression_layers.py`. | **READY TO REVIEW AND INTEGRATE** |
| `Backend/tools/localisation.py` | Added verified Ensembl 1-to-1 orthologue cross-reference fallback (`_resolve_via_orthologue` + `_validate_ensembl_record`) when animal `gene_exact` search returns `record_not_found` (rabbit `CRBN` `A0A5F9CHQ0`, where UniProt `"genes"` is `null`) or `ambiguous_record` (macaque `CD28` unreviewed isoforms), citing the Ensembl orthologue IDs in `limitations` and `SourceRecord.source` and preserving `incomplete` status (`BUG-4`). | Added `test_rabbit_crbn_resolves_via_verified_ensembl_orthologue_when_uniprot_genes_missing` and `test_macaque_cd28_disambiguates_multiple_unreviewed_isoforms_via_ensembl_orthologue` in `Backend/tests/test_localisation.py`. | **READY TO REVIEW AND INTEGRATE** |
| `Backend/docs/role4_overnight_validation.md` | Full overnight biological validation report. | N/A (documentation) | **READY TO REVIEW AND INTEGRATE** |

### Before / After Results for Targeted Fixes

1. **WMG Denominator Mismatch (`Backend/tools/cell_expression.py`):**
   - **Before:** `"pancreas / progenitor cell: 28.89% (128 expressing of 876 cells)"` (`128 / 876 = 14.61%`, incompatible denominator) and `"mouse 39.94% (1,231 expressing of 3,159 cells)"` (`1,231 / 3,159 = 38.97%`).
   - **After:** `"pancreas / progenitor cell: 28.89% (128 expressing cells)"` and `"mouse 39.94% (1,231 expressing cells)"`, while compatible populations such as `"human 7.51% (1,622 expressing of 21,605 cells)"` (`1,622 / 21,605 = 7.51%`) retain their denominator.
2. **Census Routing (`Backend/tools/cell_expression.py`):**
   - **Before:** `run_cell_expression(ResolvedQuery(gene="CD28", species="macaca_mulatta"))` took **408.38s** when `cellxgene_census` was installed.
   - **After:** Replays `census_CD28_macaca_mulatta.json` in **< 1 ms**, setting `data_version = "CELLxGENE Census 2025-11-08 (schema 2.4.0) (recorded run)"` and prepending `"Replayed a recorded live CELLxGENE Census run (census_CD28_macaca_mulatta.json) rather than running a live remote TileDB-SOMA scan."` to `limitations`.
3. **Rabbit `CRBN` & Macaque `CD28` Localisation (`Backend/tools/localisation.py`):**
   - **Before (Rabbit `CRBN`):** `animal` protein was `None` with limitation `"animal: No exact UniProt gene match for CRBN in taxon 9986."`
   - **After (Rabbit `CRBN`):** Unambiguously resolves `A0A5F9CHQ0` via Ensembl 1-to-1 orthologue `ENSOCUG00000025795 / ENSOCUP00000033173`, reports `animal_compartments: Cytoplasm (SL-0086); Nucleus (SL-0191)` and `shared_compartments: Cytoplasm (SL-0086); Nucleus (SL-0191)`, cites `uniprot:A0A5F9CHQ0 (... resolved via Ensembl orthologue ENSOCUG00000025795 / ENSOCUP00000033173)`, and preserves `LayerResult.status = "incomplete"`.
   - **Before (Macaque `CD28`):** `animal` protein was `None` with limitation `"animal: Multiple matching UniProt accessions: A0A5F7ZKV3, Q0PDN4"`.
   - **After (Macaque `CD28`):** Disambiguates `A0A5F7ZKV3` (`macaca_mulatta`, via `ENSMMUG00000057214 / ENSMMUP00000065245`) and `A0ACM8QAJ6` (`macaca_fascicularis`, via `ENSMFAG00000003864 / ENSMFAP00000034788`), reports missing subcellular location annotations explicitly as `"No structured SUBCELLULAR LOCATION annotation (localisation unknown)"`, and preserves `LayerResult.status = "incomplete"`.

---

## D. Validation Summary & Benchmark Outcomes

### D.1 Commands Executed & Results
```bash
# Role 4 biological layer test suite:
/opt/homebrew/bin/uv run --no-project --python 3.11 --with pytest --with-requirements Backend/requirements.txt python -m pytest Backend/tests/test_expression_layers.py Backend/tests/test_localisation.py Backend/tests/test_cell_census.py -q
# -> 57 passed in 0.08s

# Full backend test suite:
/opt/homebrew/bin/uv run --no-project --python 3.11 --with pytest --with-requirements Backend/requirements.txt python -m pytest Backend/tests/ -q
# -> 328 passed, 14 skipped in 0.52s
```

### D.2 Five Benchmark Cases Evaluation Table

| Benchmark Case | `sequence` | `localisation` | `cell_expression` | `tissue_expression` | Overall Role 4 Outcome |
|---|---|---|---|---|---|
| **1. Fialuridine (`SLC29A1`, mouse)** | `ok` (`77.63%` identity; `PEXN` motif at 71–74 in human `Q99808` vs `PAXS` in mouse; note `data_version=None`) | `incomplete` (`UniProt 2026_04`; human `Q99808` plasma membrane vs mouse `Q9JIM1` `by_similarity`; attaches `Lai 2004` & `Lee 2006`) | `incomplete` (`WMG snapshot 1762972271`; 631 matched populations `>=500` cells; median human `1.23%` vs mouse `3.45%`; denominators verified) | `ok` (`GTEx gtex_v8; Bgee 2026-11-08`; 17 matched tissues including liver, kidney, heart, cortex, adrenal) | **PASS** |
| **2a. TGN1412 (`CD28`, `macaca_mulatta`)** | `ok` (`98.18%` identity; 4 substitutions `F11L, V155A, I175C, V179M`; `MYPPPY` conserved) | `incomplete` (`UniProt 2026_04`; human `P10747` Cell membrane/surface; rhesus `A0A5F7ZKV3` resolved via Ensembl orthologue `ENSMMUP00000065245`, localisation unknown) | `incomplete` (`Census 2025-11-08 (recorded run)`; human PBMC `CL:0000905` `33.37%` `[1429/4282, 8 donors]`; 0 rhesus blood/CD4+ TEM datasets; attaches `Eastwood 2010`) | `ok` (`GTEx gtex_v8; Bgee 2026-11-08`; 5 matched tissues: spleen, lung, colon, liver, dlPFC) | **PASS** |
| **2b. TGN1412 (`CD28`, `macaca_fascicularis` frontend preset)** | `ok` (`98.18%` identity; same 4 substitutions) | `incomplete` (`UniProt 2026_04`; human `P10747`; cynomolgus `A0ACM8QAJ6` resolved via Ensembl orthologue `ENSMFAP00000034788`, localisation unknown) | `incomplete` (Live Census: human `CL:0000905` `33.37%` + `Eastwood 2010` + cynomolgus absent from Census; without `cellxgene_census` installed: WMG `_human_only` + `Eastwood 2010`) | `ok` (`GTEx gtex_v8; Bgee 2026-11-08`; 4 matched tissues: spleen, lung, colon, liver) | **PARTIAL** (see P1-2 on `macaca_fascicularis` vs `macaca_mulatta` preset) |
| **3. Conserved Control (`GAPDH`, mouse)** | **`unavailable`** (`resolve_orthologue` raises `AmbiguousOrthologueError` across 3 mouse `ortholog_one2many` genes; see P1-1) | `incomplete` (`UniProt 2026_04`; shared cytoskeleton, cytosol, nucleus between `P04406` and `P16858`; mouse `by_similarity` from rat `P04797`) | `incomplete` (`WMG snapshot 1762972271`; resolves `ENSMUSG00000057666` via symbol tie-breaker; 639 matched populations; median human `68.06%` vs mouse `67.87%`) | `ok` (`GTEx gtex_v8; Bgee 2026-11-08`; 18 matched tissues, high ubiquitous expression in both species) | **PASS for Role 4 layers** (`sequence` needs P1-1 in `resolver.py`) |
| **4. Orthologue Failure (`CYP3A4`, mouse)** | `unavailable` (9 mouse `Cyp3a` `ortholog_many2many` candidates preserved in `ambiguous_candidates`) | `incomplete` (`UniProt 2026_04`; human `P08684` ER/microsome membrane; mouse `No exact UniProt gene match`) | `incomplete` (`WMG snapshot 1762972271`; human enterocytes/hepatocytes `51.8–68.3%`; mouse orthologue unresolved) | `incomplete` (`GTEx gtex_v8; Bgee 2026-11-08`; human Liver `335.3 TPM`, Ileum `48.2 TPM`; mouse orthologue unresolved) | **PASS** |
| **5. Thalidomide (`CRBN`, rabbit)** | `ok` (`95.18%` paired identity, `76.25%` global identity over 442 vs 491 aa; 20 substitutions mapped to `Q96SW2` & `A0A5F9CHQ0` features) | `incomplete` (`UniProt 2026_04`; human `Q96SW2` Cytoplasm/Nucleus/Membrane vs rabbit `A0A5F9CHQ0` Cytoplasm/Nucleus `ECO:0000256`, resolved via `ENSOCUP00000033173`) | `incomplete` (`WMG snapshot 1762972271`; human top populations reported; rabbit not indexed in CELLxGENE) | `ok` (`GTEx gtex_v8; Bgee 2026-11-08`; 8 matched tissues with gold RNA-Seq calls in rabbit `ENSOCUG00000025795`) | **PASS** |

---

## E. Outstanding Actions for Other Teammates (Ranked P0 / P1 / P2)

### P0 — Blocks Demonstration or Creates Materially Misleading Claims
- **P0-1 (Role 2 — `Backend/agents/sceptic.py` lines 169, 228–236):** Exempt `SourceRecord` entries with `s.kind == "literature"` from the automatic `status == "incomplete"` layer downgrade in `sceptic._check()`. Currently, `status_by_source = {s.id: l.status for l in layers for s in l.source_records}` forces `concern = "flagged"` (`"Rests on incomplete data; downgraded."`) on claims citing `Lai et al. 2004` (`doi:10.1074/jbc.M307938200`), `Lee et al. 2006` (`doi:10.1074/jbc.M513825200`), and `Eastwood et al. 2010` (`pub:eastwood2010`) solely because `localisation` (`SLC29A1`) and `cell_expression` (`CD28`) have `status = "incomplete"`.

### P1 — Important Correctness or Scientific Credibility Issues
- **P1-1 (Role 1/3 — `Backend/tools/resolver.py` lines 135–160):** Apply the same case-insensitive gene-symbol tie-breaker in `resolve_orthologue()` that `orthologue_gene_id()` already uses when Ensembl returns `ortholog_one2many` with a single exact symbol match (`Gapdh` → `ENSMUSG00000057666`), so the `sequence` layer succeeds (`status = "ok"`) on the `GAPDH` conserved control benchmark instead of returning `status = "unavailable"`.
- **P1-2 (Frontend / Role 4 — `Frontend/lib/caseStudies.ts` line 54):** The TGN1412 frontend preset specifies `species: "macaca_fascicularis"`, whereas the detailed recorded Census benchmark (`Backend/data/benchmarks/census_CD28_macaca_mulatta.json`) is for `macaca_mulatta`. Aligning the preset or adding a recorded `census_CD28_macaca_fascicularis.json` benchmark will ensure offline/Windows hosts without `cellxgene_census` still receive the Hao et al. 2021 human PBMC `CD4+ TEM (CL:0000905)` `33.37%` observation.
- **P1-3 (Role 1/3 — `Backend/tools/sequence_layer.py` line 138):** Populate `data_version` (instead of `None`) when `run_sequence()` returns `status = "ok"`, as noted in `tests/test_cases.md` line 218.
- **P1-4 (Role 1 — `Backend/tools/resolver.py` line 259):** Catch `httpx.HTTPError` in `_symbol_gene_id()` and raise `EnsemblAPIError` so `_with_retry()` retries transient timeouts on `/lookup/symbol/{species}/{gene}`.

### P2 — Optional Improvements
- **P2-1 (Role 2 — `Backend/agents/investigator.py` lines 34–39):** Include `Observation(field="ambiguous_candidates", ...)` from `unavailable` layers in `evidence.citable` so `sequence`'s candidate list reaches the Interpreter directly even when all other layers are unavailable.
