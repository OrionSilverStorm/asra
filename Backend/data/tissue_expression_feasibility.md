# ASRA Phase 1 Feasibility Report: GTEx & Bgee Cross-Species Tissue Expression

**Date:** 2026-11-07  
**Repository:** `OrionSilverStorm/asra`  
**Branch:** `feat/cellular-tissue`  
**Workstream:** Cellular and tissue biological analysis (`tissue_expression` layer)

---

## 1. Executive Summary & Feasibility Verdict

| Benchmark | Human Source (GTEx v8) | Animal Source (Bgee v15.2) | Exact UBERON Matches | Organ-Level UBERON Correspondences | Layer Status | Feasibility Verdict |
|---|---|---|---|---|---|---|
| **`SLC29A1`** (`Homo sapiens` vs. `Mus musculus`) | `ENSG00000112759.16` (`54` tissues, median `TPM`) | `ENSMUSG00000023942` (`Slc29a1`, `215` expressed calls, `expressionScore` `0–100`) | **14 tissues** | **6 major organs** (liver, lung, colon, heart, small intestine, blood) | `ok` | **Feasible (qualitative presence & within-species rank comparison only)** |
| **`CD28`** (`Homo sapiens` vs. `Macaca mulatta`) | `ENSG00000178562.17` (`54` tissues, median `TPM`) | `ENSMMUG00000057214` (`CD28`, `7` expressed calls, `expressionScore` `0–100`) | **2 tissues** (`UBERON:0002106` spleen, `UBERON:0009834` dlPFC) | **3 organs** (colon, liver, lung; **blood, thymus, and lymph node unannotated in macaque**) | `incomplete` | **Partially feasible (sparse macaque tissue coverage; `incomplete`)** |

---

## 2. Verified APIs, Endpoints & Versions

### 2.1 Human Tissue Expression: GTEx Portal API v2
- **OpenAPI Specification:** `https://gtexportal.org/api/v2/openapi.json` (`GTEx Portal API`, version `2.0.0`)
- **Gene Resolution Endpoint:**
  - `GET https://gtexportal.org/api/v2/reference/gene?geneId={SYMBOL}`
  - Returns versioned GENCODE gene identifiers (`gencodeId`), `gencodeVersion` (`v26`), `genomeBuild` (`GRCh38/hg38`), `entrezGeneId`, and description.
  - Verified records:
    - `SLC29A1`: `gencodeId = "ENSG00000112759.16"`, `entrezGeneId = 2030`, `gencodeVersion = "v26"`, `genomeBuild = "GRCh38/hg38"`.
    - `CD28`: `gencodeId = "ENSG00000178562.17"`, `entrezGeneId = 940`, `gencodeVersion = "v26"`, `genomeBuild = "GRCh38/hg38"`.
- **Median Tissue Expression Endpoint:**
  - `GET https://gtexportal.org/api/v2/expression/medianGeneExpression?gencodeId={GENCODE_ID}&datasetId=gtex_v8&itemsPerPage=100`
  - Returns 54 non-diseased human tissue sites with `tissueSiteDetailId`, `ontologyId` (`UBERON:*` or `EFO:*`), `median`, and `unit = "TPM"` (Transcripts Per Million from bulk RNA-Seq).
- **Tissue Metadata Endpoint:**
  - `GET https://gtexportal.org/api/v2/dataset/tissueSiteDetail?itemsPerPage=100`
  - Returns sample counts (`rnaSeqSampleSummary`), anatomical descriptions (`samplingSite`), and ontology IRIs for all 54 tissues.

### 2.2 Animal Tissue Expression: Bgee REST API
- **Base Endpoint:** `https://www.bgee.org/api/` (`display_type=json`)
- **Species Coverage:** All 9 preclinical comparison species in ASRA's `SpeciesId` contract (plus human `9606`) are natively indexed in Bgee:
  - `homo_sapiens` (`9606`, `GRCh38.p13`)
  - `mus_musculus` (`10090`, `GRCm38.p6`)
  - `rattus_norvegicus` (`10116`, `Rnor_6.0`)
  - `macaca_mulatta` (`9544`, `Mmul_10`)
  - `macaca_fascicularis` (`9541`, `Macaca_fascicularis_5.0`)
  - `canis_lupus_familiaris` (`9615`, `CanFam3.1`)
  - `sus_scrofa` (`9823`, `Sscrofa11.1`)
  - `oryctolagus_cuniculus` (`9986`, `OryCun2.0`)
  - `cavia_porcellus` (`10141`, `Cavpor3.0`)
  - `danio_rerio` (`7955`, `GRCz11`)
- **Ortholog & Gene Resolution Endpoints:**
  1. `GET https://www.bgee.org/api/?display_type=json&page=gene&action=homologs&gene_id={HUMAN_ENSEMBL_ID}&species_id=9606`
     - Resolves curated orthologous Ensembl gene IDs across taxonomic clades (`orthologsByTaxon`).
  2. `GET https://www.bgee.org/api/?display_type=json&page=gene&action=gene_search&query={SYMBOL}`
     - Resolves gene symbols and synonyms across species when homology lookup is unavailable.
  3. `GET https://www.bgee.org/api/?display_type=json&page=gene&action=general_info&gene_id={GENE_ID}&species_id={TAX_ID}`
     - Returns `genomeVersion`, `expressionSummary`, and gene metadata.
- **Anatomical Expression Calls Endpoint:**
  - `GET https://www.bgee.org/api/?display_type=json&page=gene&action=expression&gene_id={GENE_ID}&species_id={TAX_ID}`
  - Returns present expression calls (`requestedCallType = "EXPRESSED"`) across anatomical entities (`condition.anatEntity.id` in UBERON) with:
    - `expressionState`: `"expressed"`
    - `expressionScore.expressionScore`: non-parametric rank-normalised score on a `0–100` scale (`expressionScoreConfidence`: `"high"` / `"medium"` / `"low"`)
    - `expressionQuality`: `"gold"` or `"silver"`
    - `fdr`: false discovery rate p-value integrating bulk RNA-Seq, Affymetrix microarray, EST, in situ hybridization, and scRNA-seq data (`dataTypesWithData`).

---

## 3. Anatomical Ontology Matching (UBERON)

### 3.1 Exact UBERON ID Matching
GTEx v8 assigns 53 distinct ontology terms across its 54 tissue sites (`Brain_Cerebellum` and `Brain_Cerebellar_Hemisphere` both map to `UBERON:0002037`; two cell lines map to `EFO:0002009` and `EFO:0000572`).

- **`SLC29A1` (`Homo sapiens` vs. `Mus musculus` `ENSMUSG00000023942`):**
  14 tissues match by **exact UBERON ID** between GTEx v8 and Bgee mouse tissue-level calls (`cellType is None`):
  1. `UBERON:0001496` (`ascending aorta` / `Artery_Aorta`): GTEx `190.26 TPM` | Bgee mouse `expressed` (`score=41.08`, `gold`, `fdr=0.008`, `['Affymetrix']`)
  2. `UBERON:0002190` (`subcutaneous adipose tissue` / `Adipose_Subcutaneous`): GTEx `162.93 TPM` | Bgee mouse `expressed` (`score=68.79`, `gold`, `fdr=0.005`, `['Affymetrix']`)
  3. `UBERON:0002369` (`adrenal gland` / `Adrenal_Gland`): GTEx `117.56 TPM` | Bgee mouse `expressed` (`score=91.51`, `gold`, `fdr=7.72e-10`, `['Affymetrix', 'RNA-Seq']`)
  4. `UBERON:0000995` (`uterus` / `Uterus`): GTEx `94.16 TPM` | Bgee mouse `expressed` (`score=82.83`, `gold`, `fdr=5.05e-8`, `['Affymetrix', 'RNA-Seq']`)
  5. `UBERON:0000945` (`stomach` / `Stomach`): GTEx `89.06 TPM` | Bgee mouse `expressed` (`score=76.99`, `gold`, `fdr=3.93e-10`, `['Affymetrix', 'RNA-Seq']`)
  6. `UBERON:0000007` (`pituitary gland` / `Pituitary`): GTEx `70.06 TPM` | Bgee mouse `expressed` (`score=70.11`, `silver`, `fdr=0.01`, `['Affymetrix']`)
  7. `UBERON:0011907` (`gastrocnemius medialis` / `Muscle_Skeletal`): GTEx `54.68 TPM` | Bgee mouse `expressed` (`score=78.93`, `gold`, `fdr=0.005`, `['Affymetrix']`)
  8. `UBERON:0000992` (`ovary` / `Ovary`): GTEx `33.37 TPM` | Bgee mouse `expressed` (`score=74.60`, `gold`, `fdr=6.74e-7`, `['Affymetrix', 'RNA-Seq']`)
  9. `UBERON:0002106` (`spleen` / `Spleen`): GTEx `30.25 TPM` | Bgee mouse `expressed` (`score=87.23`, `gold`, `fdr=4.92e-13`, `['Affymetrix', 'RNA-Seq']`)
  10. `UBERON:0001225` (`cortex of kidney` / `Kidney_Cortex`): GTEx `23.54 TPM` | Bgee mouse `expressed` (`score=71.09`, `gold`, `fdr=9.39e-9`, `['Affymetrix', 'RNA-Seq']`)
  11. `UBERON:0001882` (`nucleus accumbens` / `Brain_Nucleus_accumbens_basal_ganglia`): GTEx `14.07 TPM` | Bgee mouse `expressed` (`score=53.68`, `silver`, `fdr=0.037`, `['Affymetrix']`)
  12. `UBERON:0001898` (`hypothalamus` / `Brain_Hypothalamus`): GTEx `13.94 TPM` | Bgee mouse `expressed` (`score=63.96`, `gold`, `fdr=2.98e-8`, `['Affymetrix', 'in situ hybridization', 'RNA-Seq']`)
  13. `UBERON:0001876` (`amygdala` / `Brain_Amygdala`): GTEx `5.68 TPM` | Bgee mouse `expressed` (`score=67.65`, `gold`, `fdr=0.007`, `['Affymetrix', 'in situ hybridization']`)
  14. `UBERON:0001954` (`Ammon's horn` / `Brain_Hippocampus`): GTEx `5.34 TPM` | Bgee mouse `expressed` (`score=68.48`, `gold`, `fdr=9.67e-7`, `['Affymetrix', 'in situ hybridization', 'RNA-Seq']`)

- **`CD28` (`Homo sapiens` vs. `Macaca mulatta` `ENSMMUG00000057214`):**
  Only **2 tissues** match by **exact UBERON ID** out of the 7 total macaque calls in Bgee:
  1. `UBERON:0002106` (`spleen` / `Spleen`): GTEx `6.06 TPM` (rank #1 of 54 human tissues in GTEx) | Bgee macaque `expressed` (`score=72.96`, `gold`, `fdr=1.83e-6`, `['RNA-Seq']`, rank #1 of 7 macaque tissues in Bgee).
  2. `UBERON:0009834` (`dorsolateral prefrontal cortex` / `Brain_Frontal_Cortex_BA9`): GTEx `0.03 TPM` | Bgee macaque `expressed` (`score=38.75`, `silver`, `fdr=0.044`, `['RNA-Seq']`).

### 3.2 Granularity Mismatch Between GTEx Biopsy Sub-Sites and Bgee Whole Organs
GTEx annotates several major organs using the specific surgical biopsy sub-structure UBERON ID rather than the parent organ UBERON ID used by Bgee:

| Organ | GTEx `tissueSiteDetailId` & Sub-Structure `ontologyId` | Bgee Whole-Organ `anatEntity.id` |
|---|---|---|
| Liver | `Liver` (`UBERON:0001114`, *right lobe of liver*) | `UBERON:0002107` (*liver*) |
| Lung | `Lung` (`UBERON:0008952`, *lower lobe of left lung*) | `UBERON:0002048` (*lung*) |
| Colon | `Colon_Sigmoid` (`UBERON:0001159`) & `Colon_Transverse` (`UBERON:0001157`) | `UBERON:0001155` (*colon*) |
| Small Intestine | `Small_Intestine_Terminal_Ileum` (`UBERON:0001211`, *terminal ileum*) | `UBERON:0002108` (*small intestine*) / `UBERON:0000160` (*intestine*) |
| Heart | `Heart_Left_Ventricle` (`UBERON:0006566`) & `Heart_Atrial_Appendage` (`UBERON:0006631`) | `UBERON:0000948` (*heart*) / `UBERON:0002084` (*heart left ventricle*) |
| Blood | `Whole_Blood` (`UBERON:0013756`, *venous blood*) | `UBERON:0000178` (*blood*) |

Our implementation reports **exact UBERON matches** separately from **curated sub-structure-to-organ UBERON correspondences** so anatomical granularity differences are never hidden.

---

## 4. Major Scientific & Methodological Limitations

1. **Incompatible Measurement Scales (No Cross-Species Fold Changes):**
   - GTEx reports bulk RNA-Seq **median `TPM` (Transcripts Per Million)** (`[0, \infty)`), whereas Bgee reports a **non-parametric rank-normalised `expressionScore`** (`[0, 100]`) and qualitative `expressed` call (`FDR`-controlled) aggregated across heterogeneous platforms (`Affymetrix`, `RNA-Seq`, `in situ hybridization`, `EST`, `scRNA-seq`).
   - Dividing or subtracting GTEx `TPM` and Bgee `expressionScore` is mathematically and biologically invalid. Only qualitative presence calls (`expressed` at a given `FDR` / `TPM`) and within-species relative tissue rankings may be compared.
2. **Missing Animal Tissue Annotations Are Not Biological Absence:**
   - The Bgee `page=gene&action=expression` endpoint returns curated `expressed` calls for sampled anatomical structures. If an organ (such as `Whole_Blood` `UBERON:0013756` / `blood` `UBERON:0000178` or `thymus` `UBERON:0002370` in rhesus macaque `CD28`) is absent from Bgee's returned calls, this reflects **unmeasured or uncalled tissue coverage** in Bgee for that species—**not** biological absence of the transcript or protein.
3. **Bulk Tissue Averaging vs. Resident Immune Cell Infiltration:**
   - Both GTEx bulk RNA-Seq and Bgee tissue-level calls measure whole-tissue homogenates. Low-level `CD28` detection in non-lymphoid tissues (such as lung, liver, colon, or brain cortex) primarily reflects infiltrating or tissue-resident T lymphocytes rather than parenchymal expression.
4. **RNA Abundance vs. Functional Protein & Subcellular Localization:**
   - Bulk tissue mRNA levels (`TPM` or `expressionScore`) do not measure translated protein abundance, cell-surface receptor density (`CD28`), or isoform-specific subcellular targeting (such as the human-specific mitochondrial targeting of `SLC29A1` / ENT1).
