# CELLxGENE Census Feasibility Report: Human vs. Rhesus Macaque CD28 Expression in CD4+ Effector-Memory T Cells

- **Workstream:** Cellular and Tissue Biological Analysis (`feat/cellular-tissue`)
- **Benchmark Case:** `CD28` (*Homo sapiens* vs. *Macaca mulatta* in CD4+ effector-memory T cells)
- **Pinned Census Release Verified:** `2025-11-08` (`cellxgene_census` v1.18.0; SOMA schema `2.4.0`; dataset schema `7.0.0`)
- **Final Feasibility Decision:** **`not feasible`** (for a direct, scientifically defensible cross-species comparison in CELLxGENE Census; **human side is `feasible`**, **rhesus macaque side is `unavailable`**, requiring `status: "partial"` in the ASRA `cell_expression` contract)

---

## 1. Executive Summary & Final Feasibility Decision

**Final Verdict: `not feasible`** (cross-species CD4+ effector-memory T-cell comparison in CELLxGENE Census alone).

A direct, scientifically defensible comparison of `CD28` RNA expression between human (*Homo sapiens*) and rhesus macaque (*Macaca mulatta*) CD4+ effector-memory T-cell ($T_{\text{EM}}$) populations **cannot be performed using CELLxGENE Census (`2025-11-08`) or CELLxGENE Discover alone**, despite both organisms and both orthologous `CD28` genes being indexed in the `2025-11-08` release:

1. **Human side (`Homo sapiens`, `NCBITaxon:9606`) is well-powered (`feasible`):**
   - Pinned Census release `2025-11-08` contains **`1,730,577` total cells (`1,285,147` primary cells)** across **`38` datasets** and **`2,292` unique donors** annotated as CD4+ effector-memory T cells:
     - `effector memory CD4-positive, alpha-beta T cell` (`CL:0000905`): **`1,714,211` total cells (`1,276,259` primary cells)** across `38` datasets and `2,292` donors.
     - `effector memory CD4-positive, alpha-beta T cell, terminally differentiated` (`CL:0001087`, CD4+ $T_{\text{EMRA}}$): **`16,366` total cells (`8,888` primary cells)** across `3` datasets and `58` donors.
   - Multiple blood (`UBERON:0000178`) and lymphoid-tissue (`UBERON:0000029` lymph node, `UBERON:0007644` thoracic lymph node, `UBERON:0002509` mesenteric lymph node, `UBERON:0001542` inguinal lymph node, `UBERON:0002106` spleen, `UBERON:0002371` bone marrow) datasets explicitly distinguish `CL:0000905` and `CL:0001087` from naive CD4+ T cells (`CL:0000895`), central memory CD4+ T cells (`CL:0000904`), generic memory CD4+ T cells (`CL:0000897`), regulatory T cells (`CL:0000815` / `CL:0000792`), and generic CD4+ T cells (`CL:0000624`).
   - Human `CD28` (`ENSG00000178562`, `soma_joinid = 1995`) is measured across `158,034,458` cells (`97.5%` of all human Census cells) with `6,677,612` nonzero observations (`nnz`).

2. **Rhesus macaque side (`Macaca mulatta`, `NCBITaxon:9544`) lacks the required tissue, cell-type annotation, and gene measurement coverage (`unavailable`):**
   - **Zero blood or lymphoid-tissue datasets:** Across all `19` *Macaca mulatta* datasets in Census `2025-11-08` (`7,010,229` total cells; `2,929,014` primary cells) and CELLxGENE Discover (`2,269` total platform datasets), **`0` datasets** profile blood (`UBERON:0000178`), lymph node (`UBERON:0000029`), spleen (`UBERON:0002106`), bone marrow (`UBERON:0002371`), thymus (`UBERON:0002370`), or tonsil (`UBERON:0002372`). Eighteen datasets profile brain tissue via single-nucleus RNA-seq (`nucleus`), and one dataset (`2e877cd3-5587-4fc1-8667-a48fe9e2a695`) profiles late-embryonic lung via whole-cell scRNA-seq (`cell`).
   - **Zero CD4+ effector-memory or generic CD4+ T-cell annotations:** Across all `7,010,229` *Macaca mulatta* cells, **`0` cells** are annotated with `CL:0000905`, `CL:0001087`, `CL:0000904`, `CL:0000897`, `CL:0000895`, or `CL:0000624`. Only two datasets contain any T-lineage annotations, both limited to coarse `T cell` (`CL:0000084`) or `mucosal invariant T cell` (`CL:0000940`).
   - **Unmeasured `CD28` (`ENSMMUG00000057214`) in the only whole-cell macaque T-cell dataset:** Macaque `CD28` (`ENSMMUG00000057214`, `soma_joinid = 23595`) has `n_measured_obs = 6,890,187` out of `7,010,229` total macaque cells. The exact difference (`7,010,229 - 6,890,187 = 120,042` cells) equals the complete cell count of the late-embryonic lung scRNA-seq dataset `2e877cd3-5587-4fc1-8667-a48fe9e2a695` (`120,042` cells, which contains `4,058` `T cell` and `1,881` `mucosal invariant T cell` profiles). Consequently, querying `X["raw"]` for `ENSMMUG00000057214` in `2e877cd3-5587-4fc1-8667-a48fe9e2a695` returns `0` across all `4,058` T cells because the gene is **absent from that dataset's feature set**, not because `CD28` is biologically unexpressed.
   - **Only 185 cortical T-cell nuclei measure `CD28` in macaque:** The only *Macaca mulatta* T-lineage population in Census `2025-11-08` with measured `ENSMMUG00000057214` is `185` single-nucleus `T cell` (`CL:0000084`) profiles from adult dorsolateral prefrontal cortex (`fc6ef080-9e5f-4aea-b9c4-a45a208bd288`, `4` donors), where `17 / 185` nuclei (`9.19%`) have a raw UMI count of `1`. These `185` cortical nuclei do not distinguish CD4+ from CD8+ T cells or effector-memory from naive/central-memory subsets and cannot be compared to human peripheral blood/lymphoid whole-cell CD4+ $T_{\text{EM}}$ profiles.

---

## 2. Task 1: Dataset & Release Availability Verification

### 2.1 Pinned CELLxGENE Census Release (`2025-11-08`)

The pinned release `2025-11-08` was verified using `cellxgene_census` (`v1.18.0`) and direct S3/HTTPS inspection:

| Property | Verified Value |
| --- | --- |
| Release tag | `2025-11-08` (present in `cellxgene_census.get_census_version_directory()`) |
| SOMA S3 URI | `s3://cellxgene-census-public-us-west-2/cell-census/2025-11-08/soma/` |
| HTTPS S3 bucket endpoint | `https://cellxgene-census-public-us-west-2.s3.us-west-2.amazonaws.com/?list-type=2&prefix=cell-census/2025-11-08/` |
| `census_schema_version` | `2.4.0` |
| `dataset_schema_version` | `7.0.0` |
| Total Census datasets (`census_info["datasets"]`) | `1,845` (out of `2,269` total datasets in CELLxGENE Discover Curation API) |
| Total Census cells (`total_cell_count`) | `217,768,036` |
| Unique primary Census cells (`unique_cell_count`) | `125,463,259` |
| Available `X` expression layers | `raw`, `normalized` |

### 2.2 Organism Support in Census `2025-11-08`

Contrary to older Census releases (`2023`–`2024`) that indexed only human and mouse, the `2025-11-08` release indexes **five organisms** in `census["census_data"]` and `census["census_info"]["organisms"]`:

| Organism Key | Scientific Name | Taxonomy ID | Total Cells (`total_cell_count`) | Unique Primary Cells (`unique_cell_count`) | Total Genes in `var` | Census Datasets |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `homo_sapiens` | *Homo sapiens* | `NCBITaxon:9606` | `162,025,130` | `99,633,637` | `61,497` | `1,636` (Discover) |
| `mus_musculus` | *Mus musculus* | `NCBITaxon:10090` | `46,299,127` | `21,029,771` | — | `499` (Discover) |
| `macaca_mulatta` | *Macaca mulatta* | `NCBITaxon:9544` | `7,010,229` | `2,929,014` | `34,676` | `19` |
| `callithrix_jacchus` | *Callithrix jacchus* | `NCBITaxon:9483` | `2,275,451` | `1,712,738` | — | `27` |
| `pan_troglodytes` | *Pan troglodytes* | `NCBITaxon:9598` | `158,099` | `158,099` | — | `1` |

*Note on Cynomolgus macaque (`Macaca fascicularis`, `NCBITaxon:9541`):* Neither CELLxGENE Census `2025-11-08` nor CELLxGENE Discover (`2,269` datasets) contains any datasets for *Macaca fascicularis* (`0` datasets).

---

## 3. Relevant Identifiers (Genes, Taxa, Cell Types, Tissues, Assays)

### 3.1 Species-Specific `CD28` Gene Identifiers

Verified via Ensembl REST API (`https://rest.ensembl.org/lookup/symbol/{species}/CD28`) and Census `2025-11-08` `census["census_data"][org].ms["RNA"].var`:

| Field | Human (*Homo sapiens*) | Rhesus Macaque (*Macaca mulatta*) |
| --- | --- | --- |
| **Taxonomy ID** | `NCBITaxon:9606` (`9606`) | `NCBITaxon:9544` (`9544`) |
| **Ensembl Gene ID (`feature_id`)** | `ENSG00000178562` (`.20`) | `ENSMMUG00000057214` (`.1`) |
| **Gene Symbol (`feature_name`)** | `CD28` | `CD28` |
| **Nomenclature Accession** | `HGNC:1653` | `VGNC:70759` |
| **Genome Assembly** | `GRCh38` (`chr2:203,706,475-203,738,912`, `+` strand) | `Mmul_10` (`chr12:63,115,347-63,146,858`, `+` strand) |
| **Biotype (`feature_type`)** | `protein_coding` | `protein_coding` |
| **Census `2025-11-08` `soma_joinid`** | `1995` | `23595` |
| **Census `feature_length` (bp)** | `2,920` | `3,611` |
| **Census `nnz` (nonzero cell observations)** | `6,677,612` | `5,325` |
| **Census `n_measured_obs` (cells where gene is in feature set)** | `158,034,458` / `162,025,130` (`97.54%`) | `6,890,187` / `7,010,229` (`98.29%`) |
| **Ensembl Source URL** | `https://rest.ensembl.org/lookup/id/ENSG00000178562?content-type=application/json` | `https://rest.ensembl.org/lookup/id/ENSMMUG00000057214?content-type=application/json` |

### 3.2 Relevant Ontology Identifiers

| Category | Ontology Term ID | Standard Label | Role in Investigation |
| --- | --- | --- | --- |
| **Target Cell Type (Primary)** | `CL:0000905` | `effector memory CD4-positive, alpha-beta T cell` | Primary target population ($T_{\text{EM}}$) |
| **Target Cell Type (Terminal)** | `CL:0001087` | `effector memory CD4-positive, alpha-beta T cell, terminally differentiated` | Terminally differentiated CD4+ $T_{\text{EMRA}}$ subset |
| **Comparator CD4+ Subset** | `CL:0000904` | `central memory CD4-positive, alpha-beta T cell` | Central memory CD4+ T cell ($T_{\text{CM}}$) |
| **Comparator CD4+ Subset** | `CL:0000897` | `CD4-positive, alpha-beta memory T cell` | Parent memory CD4+ T-cell term |
| **Comparator CD4+ Subset** | `CL:0000895` | `naive thymus-derived CD4-positive, alpha-beta T cell` | Naive CD4+ T cell ($T_{\text{N}}$) |
| **Generic CD4+ T Cell** | `CL:0000624` | `CD4-positive, alpha-beta T cell` | Unresolved / generic CD4+ $\alpha\beta$ T cell |
| **Generic T Cell** | `CL:0000084` | `T cell` | Coarse pan-T cell (pools CD4+, CD8+, $\gamma\delta$, naive, memory) |
| **Innate-like T Cell** | `CL:0000940` | `mucosal-associated invariant T cell` (Census: `mucosal invariant T cell`) | MAIT cell (present in macaque fetal lung) |
| **Tissue (Blood)** | `UBERON:0000178` | `blood` | Primary peripheral blood compartment |
| **Tissue (Lymphoid)** | `UBERON:0000029` / `UBERON:0007644` / `UBERON:0002509` / `UBERON:0001542` | `lymph node` / `thoracic` / `mesenteric` / `inguinal lymph node` | Secondary lymphoid organs |
| **Tissue (Lymphoid)** | `UBERON:0002106` / `UBERON:0002371` / `UBERON:0002370` | `spleen` / `bone marrow` / `thymus` | Primary and secondary lymphoid tissues |
| **Tissue (Macaque Only)** | `UBERON:0002048` / `UBERON:0009834` | `lung` / `dorsolateral prefrontal cortex` | Non-lymphoid tissues containing generic macaque T cells |
| **Assay** | `EFO:0009922` / `EFO:0009899` / `EFO:0009900` | `10x 3' v3` / `10x 3' v2` / `10x 5' v2` | Droplet-based single-cell/single-nucleus RNA-seq |
| **Assay** | `EFO:0030028` / `EFO:0022606` | `sci-RNA-seq3` / `10x gene expression flex` | Combinatorial indexing snRNA-seq / probe-based scRNA-seq |

---

## 4. Task 2: Verified Candidate Datasets & Biological Comparability

### 4.1 Complete Inventory of *Macaca mulatta* Datasets in Census `2025-11-08` (19 Datasets)

Across the entire CELLxGENE Census `2025-11-08` release (and CELLxGENE Discover), there are exactly **19 datasets** (`5` collections) for *Macaca mulatta*:

| Dataset ID (Version ID) | Collection Title & Reference | Tissue(s) (`UBERON`) | Assay (`EFO`) & Suspension | Total Cells (Primary Cells) | Donors | T-Cell / Immune Labels (`CL`) | `CD28` (`ENSMMUG00000057214`) Status |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| **`2e877cd3-5587-4fc1-8667-a48fe9e2a695`** (`3e2a52fb-1237-4009-89f7-7e580cb74bd2`) | *Inflammatory blockade in premature Rhesus macaques exposed to intra-uterine inflammation* ([Senthamaraikannan et al., *Sci Transl Med* 2022](https://doi.org/10.1126/scitranslmed.abl8574))<br>Explorer: https://cellxgene.cziscience.com/e/2e877cd3-5587-4fc1-8667-a48fe9e2a695.cxg/<br>H5AD: https://datasets.cellxgene.cziscience.com/3e2a52fb-1237-4009-89f7-7e580cb74bd2.h5ad | `lung` (`UBERON:0002048`), late embryonic stage (`UBERON:0007220`) | `10x 3' v3` (`EFO:0009922`), **`cell`** | `120,042` (`120,042`) | `13` (`502`–`515B`) | `T cell` (`CL:0000084`): **`4,058` cells**<br>`mucosal invariant T cell` (`CL:0000940`): **`1,881` cells**<br>`B cell` (`CL:0000236`), `myeloid leukocyte` (`CL:0000766`), `mucosal type mast cell` (`CL:0000485`), `dendritic cell` (`CL:0000451`)<br>**No CD4+ or $T_{\text{EM}}$ labels** | **NOT MEASURED** (`0` in dataset feature set; `0 / 4,058` T cells detected) |
| **`fc6ef080-9e5f-4aea-b9c4-a45a208bd288`** (`4ff87ad3-c44a-4b72-acf0-291999d6b675`) | *Single-nucleus transcriptome data from the dlPFC: Rhesus* ([Ma et al., *Science* 2022](https://doi.org/10.1126/science.abo7257))<br>Explorer: https://cellxgene.cziscience.com/e/fc6ef080-9e5f-4aea-b9c4-a45a208bd288.cxg/<br>H5AD: https://datasets.cellxgene.cziscience.com/4ff87ad3-c44a-4b72-acf0-291999d6b675.h5ad | `dorsolateral prefrontal cortex` (`UBERON:0009834`), prime adult (`UBERON:0018241`) | `10x 3' v3` (`EFO:0009922`), **`nucleus`** | `131,032` (`131,032`) | `4` (`RMB161`, `RMB196`, `RMB295`, `RMB307`) | `T cell` (`CL:0000084`): **`185` nuclei**<br>`B cell` (`CL:0000236`), `macrophage` (`CL:0000235`), `microglial cell` (`CL:0000129`), `myeloid cell` (`CL:0000763`)<br>**No CD4+ or $T_{\text{EM}}$ labels** | **Measured:** `17 / 185` T-cell nuclei (`9.19%`) have `1` UMI (`mean_raw = 0.0919`, `max = 1`) |
| **`d87ba7ec-fddf-4141-abfd-1d69e8427a42`** (`5bd7d724-1f53-474f-8391-57aadfc24864`) + **14 non-primary subset datasets** (`f61d3b91-...`, `e25e50f8-...`, `def3f8fe-...`, `885d325f-...`, `6fedc2f9-...`, `6e2fbf86-...`, `693f1ad9-...`, `58be58d9-...`, `4af83f0b-...`, `3dd26fea-...`, `3cb0fbb6-...`, `361826be-...`, `228286c6-...`, `04613344-...`) | *A single-cell multi-omic atlas spanning the adult rhesus macaque brain* ([Chiou et al., *Sci Adv* 2023](https://doi.org/10.1126/sciadv.adh1914))<br>Collection: https://cellxgene.cziscience.com/collections/8c4bcf0d-b4df-45c7-888c-74fb0013e9e7 | `27` brain regions (`UBERON:0009834`, `UBERON:0001876`, etc.), juvenile & prime adult | `sci-RNA-seq3` (`EFO:0030028`), **`nucleus`** | `2,583,967` primary (`6,665,186` incl. 14 subsets) | `5` (`6J2`, `4I3`, `3I4`, `2C0`, `3R7`) | **`0` T cells** (`microglial cell` `CL:0000129` only immune class; note `basket cell` `CL:0000118` is a GABAergic interneuron) | Measured in brain nuclei, but **`0` T cells present** |
| **`e374c7eb-d99f-4196-adb3-726eb89a37d1`** (`261dd26f-1507-41a5-94e5-b96903de74a9`) | *Macaque: Great apes study* ([Jorstad et al., *Science* 2023](https://doi.org/10.1126/science.ade9516))<br>Explorer: https://cellxgene.cziscience.com/e/e374c7eb-d99f-4196-adb3-726eb89a37d1.cxg/ | `middle temporal gyrus` (`UBERON:0002771`), prime adult | `10x 3' v3` (`EFO:0009922`), **`nucleus`** | `89,136` (`89,136`) | `3` (`Q19.26.010`, `011`, `015`) | **`0` T cells** (`microglial cell` `CL:0000129` only) | Measured in cortical nuclei, **`0` T cells present** |
| **`1f59341c-a913-4ca3-b8af-1ea33df0e8d8`** (`180453b9-3bdd-4e84-9e1b-9ab71702e8d8`) | *Evolution of cellular diversity in primary motor cortex of monkey - macaque neurons* ([Bakken et al., *Nature* 2021](https://doi.org/10.1038/s41586-021-03465-8))<br>Explorer: https://cellxgene.cziscience.com/e/1f59341c-a913-4ca3-b8af-1ea33df0e8d8.cxg/ | `primary motor cortex` (`UBERON:0001384`), adult | `10x 3' v3` (`EFO:0009922`), **`nucleus`** | `4,837` (`4,837`) | `3` (`Q19.26.002`, `003`, `008`) | **`0` T cells** (`glutamatergic neuron` `CL:0000679` only) | Measured in neuron nuclei, **`0` T cells present** |

### 4.2 Verified Candidate *Homo sapiens* Blood & Lymphoid Datasets with CD4+ Effector-Memory T Cells

In Census `2025-11-08`, **`38` datasets** contain `CL:0000905` (`effector memory CD4-positive, alpha-beta T cell`) and/or `CL:0001087` (`effector memory CD4-positive, alpha-beta T cell, terminally differentiated`). Below are the primary blood and lymphoid-tissue reference datasets verified in Census `2025-11-08`:

| Dataset ID (Version ID) | Title, Collection & DOI | Tissue(s) (`UBERON`) | Assay (`EFO`) & Suspension | CD4+ $T_{\text{EM}}$ Cells (`CL:0000905` / `CL:0001087`) Total (Primary) | Donors ($T_{\text{EM}}$ / Total) | Median UMI / Median Genes in $T_{\text{EM}}$ | Distinguished CD4+ / T-Cell Subtypes (`CL`) |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| **`3faad104-2ab8-4434-816d-474d8d2641db`** (`1e44db10-b572-46cc-adae-dcc7acd44ca6`) | *Single-cell eQTL mapping identifies cell type specific genetic control of autoimmune disease* (OneK1K PBMC, [Yazar et al., *Science* 2022](https://doi.org/10.1126/science.abf3041))<br>Explorer: https://cellxgene.cziscience.com/e/3faad104-2ab8-4434-816d-474d8d2641db.cxg/<br>H5AD: https://datasets.cellxgene.cziscience.com/1e44db10-b572-46cc-adae-dcc7acd44ca6.h5ad | `blood` (`UBERON:0000178`) | `10x 3' v2` (`EFO:0009899`), `cell` | `31,261` (`31,261`) `CL:0000905` (out of `1,248,980` total cells) | `981` / `981` (all `normal` `PATO:0000461`) | `2,845.0` UMI / `873.0` genes | **Yes:** distinguishes `CL:0000905` ($T_{\text{EM}}$), `CL:0000904` ($T_{\text{CM}}$), `CL:0000895` ($T_{\text{N}}$), `CL:0000934` (CD4+ CTL), `CL:0000815` ($T_{\text{reg}}$), and generic `CL:0000624` (CD4+ T cell) |
| **`c838aec3-03ef-4398-b882-0e3912abfff0`** (`f89a12c2-7a3b-415b-ab87-bbc550fe17f4`) | *AIDA Phase 1 Data Freeze v2* (Asian Immune Diversity Atlas, [Kock et al., *Cell* 2025](https://doi.org/10.1016/j.cell.2025.02.017))<br>Explorer: https://cellxgene.cziscience.com/e/c838aec3-03ef-4398-b882-0e3912abfff0.cxg/<br>H5AD: https://datasets.cellxgene.cziscience.com/f89a12c2-7a3b-415b-ab87-bbc550fe17f4.h5ad | `blood` (`UBERON:0000178`) | `10x 5' v2` (`EFO:0009900`), `cell` | `25,012` (`25,012`) `CL:0000905` (out of `1,265,624` total cells) | `591` / `625` (all `normal` `PATO:0000461`) | `5,650.0` UMI / `1,961.0` genes | **Yes:** distinguishes `CL:0000905` ($T_{\text{EM}}$), `CL:0000904` ($T_{\text{CM}}$), `CL:0000895` ($T_{\text{N}}$), `CL:0000934` (CD4+ CTL), `CL:0000815` ($T_{\text{reg}}$), `CL:0000624` (CD4+ T), `CL:0000084` (T cell) |
| **`46104f0b-9af5-466a-ae0f-56b8dc1969a2`** (`dcce49e2-34bb-4615-8476-60c74a26330d`) + **7 Sound Life cohort datasets** (`aa32098f-...`, `47e00f43-...`, `420d0f5d-...`, `3cb646ab-...`, `0c0c49a2-...`, `0a8e3443-...`, `5fde5c9c-...`) | *Multi-omic profiling reveals age-related immune dynamics in healthy adults* (Sound Life cohort, [Thomson et al., *Nature* 2025](https://doi.org/10.1038/s41586-025-09686-5))<br>Collection: https://cellxgene.cziscience.com/collections/e9360edf-b0b7-4e01-bce8-e596814f13e7 | `blood` (`UBERON:0000178`) | `10x 3' v3` (`EFO:0009922`), `cell` | `193,452` (`193,452`) in `46104f0b-...`; **`1,091,711` (`1,091,711`)** across all 8 cohort splits | `18` in `46104f0b-...` (`96` across 8 splits; `normal` & `CMV+`) | `5,151.0` UMI / `1,584.0` genes | **Yes:** distinguishes `CL:0000905` ($T_{\text{EM}}$), `CL:0000904` ($T_{\text{CM}}$), `CL:0000897` (CD4+ memory), `CL:0000895` ($T_{\text{N}}$), `CL:0002677`/`CL:0002678` ($T_{\text{reg}}$), `CL:0000084` (T cell) |
| **`e522d2cd-7927-4e59-a4ed-064009569279`** (`c1ce03ce-4b71-4b8d-b695-c3cec99cdfc2`) | *Human Immune Health Atlas* ([Thomson et al., *Nature* 2025](https://doi.org/10.1038/s41586-025-09686-5))<br>Explorer: https://cellxgene.cziscience.com/e/e522d2cd-7927-4e59-a4ed-064009569279.cxg/ | `blood` (`UBERON:0000178`) | `10x 3' v3` (`EFO:0009922`), `cell` | `137,919` (`10,537` primary; overlaps Sound Life) `CL:0000905` | `108` / `108` | `5,344.0` UMI / `1,633.0` genes | **Yes:** distinguishes `CL:0000905`, `CL:0000904`, `CL:0000897`, `CL:0000895`, `CL:0000084` |
| **`1b350d0a-4535-4879-beb6-1142f3f94947`** (`589324ee-ce60-4295-843f-29a52894a522`) & T-cell subset **`960ecd06-e7c2-463d-9a5b-6832994376c6`** | *Multimodal profiling reveals tissue-directed signatures of human immune cells altered with age* ([Wells et al., *Nat Immunol* 2025](https://doi.org/10.1038/s41590-025-02241-4))<br>Explorer: https://cellxgene.cziscience.com/e/1b350d0a-4535-4879-beb6-1142f3f94947.cxg/ | `blood` (`UBERON:0000178`), `thoracic lymph node` (`UBERON:0007644`), `mesenteric lymph node` (`UBERON:0002509`), `inguinal lymph node` (`UBERON:0001542`), `spleen` (`UBERON:0002106`), `bone marrow` (`UBERON:0002371`), `lung`, `gut` | `10x 3' v3` (`EFO:0009922`) & `10x 5' v2` (`EFO:0009900`), `cell` | Includes both **`CL:0000905`** (`8,731` primary in thoracic LN alone) and **`CL:0001087`** ($T_{\text{EMRA}}$) across blood and lymphoid organs | `24` (`normal`) | `4,311.0` UMI / `1,563.0` genes (thoracic LN) | **Yes:** distinguishes both `CL:0000905` ($T_{\text{EM}}$) and `CL:0001087` ($T_{\text{EMRA}}$) from `CL:0000904` ($T_{\text{CM}}$), `CL:0000897` (CD4+ memory), `CL:0000895` ($T_{\text{N}}$), and `CL:0000792` ($T_{\text{reg}}$) |
| **`1b9d8702-5af8-4142-85ed-020eb06ec4f6`** (`09a381ce-feaf-48c8-a928-58f6768f4265`) & T/ILC subset **`ae29ebd0-1973-40a4-a6af-d15a5f77a80f`** | *Cross-tissue immune cell analysis reveals tissue-specific features in humans* ([Domínguez Conde et al., *Science* 2022](https://doi.org/10.1126/science.abl5197))<br>Explorer: https://cellxgene.cziscience.com/e/1b9d8702-5af8-4142-85ed-020eb06ec4f6.cxg/ | `blood`, `bone marrow`, `spleen`, `thymus`, `lymph nodes` (`17` tissues) | `10x 3' v3` (`EFO:0009922`), `10x 5' v1` (`EFO:0011025`), `10x 5' v2` (`EFO:0009900`), `cell` | Annotated `CL:0000905` across lymphoid & mucosal tissues (`329,762` total dataset cells) | `12` (`normal`) | ~`1,928` mean genes/cell | **Yes:** distinguishes `CL:0000905` ($T_{\text{EM}}$) from `CL:0000895` ($T_{\text{N}}$) and `CL:0000792` ($T_{\text{reg}}$) |
| **`cd2f23c1-aef1-48ae-8eb4-0bcf124e567d`** (`2cf4ad28-177f-4326-ab49-c4cb012c295d`) | *A Balanced Bone Marrow Reference Map of Hematopoietic Development* ([bone marrow atlas, *Blood Cancer Discov* 2025](https://doi.org/10.1158/2643-3230.BCD-24-0342))<br>Explorer: https://cellxgene.cziscience.com/e/cd2f23c1-aef1-48ae-8eb4-0bcf124e567d.cxg/ | `bone marrow` (`UBERON:0002371`) | `10x 3' v2` (`EFO:0009899`), `10x 3' v3` (`EFO:0009922`), `cell` | `6,843` (`6,843`) `CL:0000905` | `31` / `45` (`normal`) | `3,492.0` UMI / `916.0` genes | **Yes:** distinguishes `CL:0000905`, `CL:0000904`, `CL:0000895`, `CL:0000792`, `CL:0000084` |
| **`c7775e88-49bf-4ba2-a03b-93f00447c958`** (`fe2e847c-1602-4f1b-86a4-112e4dc7a8e3`) | *Single-cell multi-omics analysis of the immune response in COVID-19* ([Stephenson et al., *Nat Med* 2021](https://doi.org/10.1038/s41591-021-01329-2))<br>Explorer: https://cellxgene.cziscience.com/e/c7775e88-49bf-4ba2-a03b-93f00447c958.cxg/ | `blood` (`UBERON:0000178`) | `10x 3' transcription profiling` (`EFO:0030003`), `cell` | Annotated `CL:0000905` (`647,366` total dataset cells) | `120` (`normal`, `COVID-19`) | ~`1,322` mean genes/cell | **Yes:** distinguishes `CL:0000905`, `CL:0000904`, `CL:0000895`, `CL:0000815`, `CL:0000624` |

*(Note: Two additional recent Discover blood datasets—`ff4235bb-1cdf-4dcf-a13a-dc4f32244400` using `10x gene expression flex` `EFO:0022606` with `3,758,514` cells across `234` donors, and `789ad837-9bf5-436c-9b60-9f1153546e4c` with `2,029,864` cells across `89` donors—are indexed in the CELLxGENE Discover API post-`2025-11-08`.)*

### 4.3 Available Normalisation Information in Census `2025-11-08`

In CELLxGENE Census `2025-11-08`, both `census["census_data"]["homo_sapiens"].ms["RNA"]["X"]` and `census["census_data"]["macaca_mulatta"].ms["RNA"]["X"]` expose two sparse matrix layers:

1. **`X["raw"]`**: Integer raw UMI counts (for droplet/3'/5' UMI assays such as `10x 3' v2`/`v3`, `10x 5' v2`, `sci-RNA-seq3`) or raw read counts (for full-length plate assays such as `Smart-seq2` `EFO:0008931`).
2. **`X["normalized"]`**: Census-standardized normalized expression values, computed per cell by dividing `X["raw"]` by feature length (`var["feature_length"]`) **only** for full-length sequencing assays (e.g., `Smart-seq2`) and then normalizing each cell by its total sum (`obs["raw_sum"]`), stored in reduced-precision floating point. Note that `X["normalized"]` is **not log-transformed** (`log1p` is not applied in `X["normalized"]`) and is **not batch-corrected across datasets or species**.
3. **Per-cell normalisation covariates in `obs`**: `raw_sum` (total raw counts per cell/nucleus), `nnz` (number of nonzero detected genes per cell/nucleus), `raw_mean_nnz`, `raw_variance_nnz`, and `n_measured_vars` (number of genes measured in that cell's source dataset).

### 4.4 Cross-Species Comparability Assessment Matrix

| Comparability Dimension | *Homo sapiens* (Census `2025-11-08`) | *Macaca mulatta* (Census `2025-11-08`) | Suitable for Meaningful Comparison? |
| --- | --- | --- | --- |
| **Target Cell Population (`CL:0000905` / `CL:0001087`)** | `1,730,577` cells (`1,285,147` primary) across `38` datasets, `2,292` donors | **`0` cells** (`0` datasets) | **No** — target population is completely unannotated in macaque. |
| **Distinction of CD4+ $T_{\text{EM}}$ from Generic CD4+ T Cells** | **Yes** (`CL:0000905` and `CL:0001087` explicitly separated from `CL:0000904` $T_{\text{CM}}$, `CL:0000895` $T_{\text{N}}$, and `CL:0000624` CD4+ T) | **No** — not even generic `CD4-positive, alpha-beta T cell` (`CL:0000624`) is annotated (`0` cells); only pan-`T cell` (`CL:0000084`) and `mucosal invariant T cell` (`CL:0000940`) exist. | **No** — pooling naive, central-memory, effector-memory, CD4+, and CD8+ T cells into `CL:0000084` masks the exact subset-specific `CD28` loss that defines primate $T_{\text{EM}}$ biology. |
| **Tissue Equivalence (Blood / Lymphoid)** | Abundant `blood` (`UBERON:0000178`), `lymph node` (`UBERON:0000029`, `0007644`, `0002509`, `0001542`), `spleen` (`UBERON:0002106`), `bone marrow` (`UBERON:0002371`) | **`0` blood or lymphoid datasets**; T cells exist only in late-embryonic `lung` (`UBERON:0002048`) and adult `dorsolateral prefrontal cortex` (`UBERON:0009834`). | **No** — fetal lung and adult cerebral cortex T cells are not biologically equivalent to peripheral blood or secondary lymphoid CD4+ $T_{\text{EM}}$ cells. |
| **Developmental Stage Equivalence** | Primarily adult (`prime adult stage`, `middle aged stage`, `late adult stage`) | Whole-cell T cells (`2e877cd3-...`) are exclusively **late embryonic / premature fetal** (`UBERON:0007220`); adult T cells (`fc6ef080-...`) are `185` brain nuclei. | **No** — fetal/premature thymic emigrants have fundamentally different memory differentiation and `CD28` expression profiles than adult antigen-experienced $T_{\text{EM}}$ cells (Pitcher et al., *J Immunol* 2002). |
| **Suspension & Assay Modality** | Whole **`cell`** (`10x 3' v2`, `10x 3' v3`, `10x 5' v2`) | Adult dlPFC T cells (`fc6ef080-...`) are single **`nucleus`** (`10x 3' v3`); fetal lung T cells (`2e877cd3-...`) are whole **`cell`** (`10x 3' v3`) but lack `CD28` in their feature matrix. | **No** — comparing nuclear RNA (`nucleus`, median `1,180` UMI/nucleus) against whole-cell RNA (`cell`, median `2,845`–`5,650` UMI/cell) confounds cytoplasmic transcript abundance with nuclear retention. |
| **`CD28` Gene Measurement Coverage** | `ENSG00000178562` measured in `158,034,458` cells (`38 / 38` candidate $T_{\text{EM}}$ datasets) | `ENSMMUG00000057214` **not measured** in `2e877cd3-...` (`4,058` lung T cells); measured in only `185` dlPFC T-cell nuclei (`fc6ef080-...`). | **No** — the only whole-cell macaque T-cell dataset does not measure `ENSMMUG00000057214`. |

---

## 5. Task 3: Evaluation of Scientific and Technical Limitations

### 5.1 RNA Expression vs. Cell-Surface Protein Abundance
- Single-cell RNA-seq (`X["raw"]` and `X["normalized"]`) measures polyadenylated mRNA transcript capture, **not** cell-surface CD28 glycoprotein density, homodimerization state, or co-stimulatory signaling competence.
- In human and non-human primate T cells, surface CD28 protein has a longer half-life and much higher per-cell copy number than steady-state `CD28` mRNA. Even in bona fide surface-$\text{CD28}^+$ human CD4+ T cells profiled by CITE-seq (e.g., Hao et al., *Cell* 2021 `10.1016/j.cell.2021.04.048` and Thomson et al., *Nature* 2025 `10.1038/s41586-025-09686-5`), a large fraction of cells with robust anti-CD28 ADT (antibody-derived tag) protein signal exhibit `0` captured `CD28` mRNA UMIs due to low steady-state transcription and 3'/5' droplet capture inefficiency.
- Conversely, post-transcriptional regulation, splice isoform switching, and receptor shedding/internalization upon TCR/CD28 engagement alter surface CD28 protein independently of total gene-level mRNA counts.

### 5.2 Differences in Sequencing Methods, Suspension Types, and Sampling
- **Single-cell (`cell`) vs. Single-nucleus (`nucleus`):** The only adult macaque T-cell records in Census `2025-11-08` with measured `ENSMMUG00000057214` (`fc6ef080-9e5f-4aea-b9c4-a45a208bd288`, `185` cells) were generated by **single-nucleus RNA-seq** (`10x 3' v3`, `nucleus`) from frozen postmortem dorsolateral prefrontal cortex (`median_raw_sum = 1,180` UMI), whereas candidate human PBMC/lymphoid datasets use **whole-cell scRNA-seq** (`cell`, `median_raw_sum = 2,845`–`5,650` UMI). Mature spliced `CD28` mRNAs reside predominantly in the cytoplasm; snRNA-seq systematically under-samples short cytoplasmic transcripts relative to long nuclear/nascent transcripts.
- **3' vs. 5' Chemistry and Sequencing Depth:** Human candidate datasets span `10x 3' v2` (`EFO:0009899`, e.g., OneK1K `3faad104-...` with median `2,845` UMI and `873` genes per $T_{\text{EM}}$ cell), `10x 3' v3` (`EFO:0009922`, Sound Life `46104f0b-...` with median `5,151` UMI and `1,584` genes), and `10x 5' v2` (`EFO:0009900`, AIDA `c838aec3-...` with median `5,650` UMI and `1,961` genes). Comparing 3' and 5' capture efficiencies or different sequencing depths across species without matched reference annotations introduces severe technical bias, especially when 3' UTR annotation lengths differ between `GRCh38` (`ENSG00000178562`, `feature_length = 2,920` bp) and `Mmul_10` (`ENSMMUG00000057214`, `feature_length = 3,611` bp).

### 5.3 Cell-Type Annotation Consistency and Biological Non-Equivalence
- **Asymmetric Ontology Granularity:** Human immune atlases in CELLxGENE annotate T-cell subsets using fine-grained Cell Ontology terms (`CL:0000895` naive, `CL:0000904` central memory, `CL:0000905` effector memory, `CL:0001087` terminally differentiated effector memory $T_{\text{EMRA}}$), often informed by multimodal CITE-seq surface markers (CD45RA, CD45RO, CCR7, CD27, CD28). In contrast, the two macaque datasets with T cells were annotated by neurobiology (`fc6ef080-...`) or pulmonary biology (`2e877cd3-...`) pipelines that collapsed all non-MAIT T lymphocytes into a single pan-`T cell` (`CL:0000084`) cluster.
- **Species-Specific Phenotypic Gating of Primate $T_{\text{EM}}$ Cells:** Even when identical labels are applied in external studies, human and macaque CD4+ effector-memory T cells are defined by different canonical surface markers:
  - In **humans**, CD4+ $T_{\text{EM}}$ (`CL:0000905`) are typically defined as $\text{CD4}^+\text{CD45RA}^-\text{CCR7}^-$ (or $\text{CD45RO}^+\text{CCR7}^-$), the majority of which **retain $\text{CD28}^+$ expression** ($\sim 80\text{--}95\%$ $\text{CD28}^+$ in healthy young adults, with $\text{CD28}^-$ cells concentrated in CMV-driven late-differentiated/senescent $T_{\text{EM}}$ and $T_{\text{EMRA}}$ `CL:0001087`; note that 4 of the 8 Sound Life datasets in Census specifically stratify by `cytomegalovirus infection` `MONDO:0005132`).
  - In **rhesus macaques** (*Macaca mulatta*), memory CD4+ T-cell subsets are canonically gated using **CD28 and CD95** (Pitcher et al., *J Immunol* 2002): central memory ($T_{\text{CM}}$) cells are defined as $\text{CD95}^+\text{CD28}^+$, whereas effector memory ($T_{\text{EM}}$) cells are defined as **$\text{CD95}^+\text{CD28}^-$** (or stratified by CCR7 and CD28 into $\text{CCR7}^-\text{CD28}^+$ transitional memory $T_{\text{TM}}$ and $\text{CCR7}^-\text{CD28}^-$ effector memory $T_{\text{EM}}$). This fundamental difference in CD28 retention on effector-memory CD4+ T cells explains why rhesus and cynomolgus macaques failed to predict the catastrophic human CD4+ $T_{\text{EM}}$ cytokine storm induced by the CD28 superagonist antibody **TGN1412** (Eastwood et al., *Br J Pharmacol* 2010).

### 5.4 Gene Detection, Dropout, and Reference Annotation Quality
- `CD28` is a moderately to lowly expressed transcript in resting T cells, subject to high Poisson/negative-binomial dropout in droplet scRNA-seq (`nnz = 6,677,612` across `158,034,458` measured human cells in Census `2025-11-08`).
- In *Macaca mulatta*, 3'-end capture (`10x 3' v3`) is additionally sensitive to incomplete 3' UTR annotation in `Mmul_10` (`ENSMMUG00000057214`) compared with extensively curated human `GRCh38`/GENCODE annotations (`ENSG00000178562`). Lower 3' read mapping efficiency in non-human primates can artificially depress UMI counts and detection rates even when true transcript abundance is comparable.

### 5.5 Batch Effects and Multi-Study Confounding
- CELLxGENE Census aggregates independently generated datasets (`1,845` datasets in `2025-11-08`) without cross-dataset batch correction in `X["raw"]` or `X["normalized"]`.
- Any human vs. macaque comparison across Census datasets is 100% confounded with study, laboratory, tissue dissociation protocol, donor age/pathogen history (e.g., CMV serostatus in human PBMC cohorts), reference genome build (`GRCh38` vs. `Mmul_10`), and Cell Ranger / alignment pipeline version.

### 5.6 Critical Pitfall: Misinterpreting Non-Detection or Non-Measurement as Biological Absence
- **Empirical proof from Census `2025-11-08`:** In *Macaca mulatta* dataset `2e877cd3-5587-4fc1-8667-a48fe9e2a695` (`120,042` fetal lung cells, including `4,058` `T cell` `CL:0000084` and `1,881` `mucosal invariant T cell` `CL:0000940`), querying `X["raw"]` for `ENSMMUG00000057214` (`CD28`) yields **`0` counts in `100%` of cells (`0 / 4,058` T cells)**.
- Inspection of `var["n_measured_obs"]` (`6,890,187` vs. `7,010,229` total macaque cells; difference = `120,042` cells) and `feature_dataset_presence_matrix` proves that **`ENSMMUG00000057214` was not present in the submitted feature matrix of `2e877cd3-5587-4fc1-8667-a48fe9e2a695`**. Because CELLxGENE Census stores a unified organism-level sparse matrix `X` padded with zeros for unmeasured dataset-feature pairs, a naive query that does not check `feature_dataset_presence_matrix` would falsely report `0.0%` `CD28` expression across `4,058` rhesus macaque T cells and misinterpret **technical non-measurement** as **biological absence of `CD28` in macaque T cells**—ironically arriving at the TGN1412 literature conclusion via a completely invalid data artifact.
- Similarly, in the `185` adult macaque dlPFC T-cell nuclei (`fc6ef080-9e5f-4aea-b9c4-a45a208bd288`), the `90.81%` zero rate (`168 / 185` nuclei with `0` UMI; `17 / 185` with `1` UMI) reflects nuclear RNA sparsity (`median_raw_sum = 1,180` UMI) and unseparated CD4+/CD8+ T-cell identity rather than verified absence of CD28 in CD4+ $T_{\text{EM}}$ cells.

---

## 6. Smallest Defensible Implementation Plan for `Backend/tools/cell_expression.py`

Because the cross-species CD4+ effector-memory T-cell comparison is **`not feasible`** in CELLxGENE Census `2025-11-08` (human side `feasible`, macaque side `unavailable`), `Backend/tools/cell_expression.py` must **not** fabricate a cross-species statistical comparison or compare human blood CD4+ $T_{\text{EM}}$ (`CL:0000905`) against macaque brain snRNA-seq pan-`T cell` (`CL:0000084`) or unmeasured fetal lung T cells (`2e877cd3-5587-4fc1-8667-a48fe9e2a695`).

Instead, the smallest scientifically defensible implementation of `run_cell_expression(gene: str, species: str) -> dict` under the shared 6-field contract (`layer`, `status`, `observations`, `measurements`, `sources`, `limitations`) should:

1. **Pin and verify Census release `2025-11-08`** (`DEFAULT_CENSUS_VERSION = "2025-11-08"`), recording the Census build date, schema version, and `cellxgene_census` version in `sources`.
2. **Resolve species-specific gene metadata in `var` and validate dataset-level measurement via `feature_dataset_presence_matrix`:**
   - Resolve `CD28` to `ENSG00000178562` (`soma_joinid = 1995`) in `homo_sapiens` and `ENSMMUG00000057214` (`soma_joinid = 23595`) in `macaca_mulatta`.
   - Explicitly filter out any dataset where `feature_dataset_presence_matrix` is `0` for the target `soma_joinid` so unmeasured zeros (such as `2e877cd3-5587-4fc1-8667-a48fe9e2a695` in macaque) are never aggregated as zero expression.
3. **Enforce strict biological comparability filters before computing expression summaries:**
   - Require matched target cell-type ontology terms (`CL:0000905` `effector memory CD4-positive, alpha-beta T cell` and `CL:0001087` `effector memory CD4-positive, alpha-beta T cell, terminally differentiated`, with comparator context from `CL:0000904` $T_{\text{CM}}$, `CL:0000895` $T_{\text{N}}$, and `CL:0000624` CD4+ T cell), matched suspension type (`cell`), and relevant blood/lymphoid tissues (`UBERON:0000178`, `UBERON:0000029`, `UBERON:0002106`, `UBERON:0002371`, `UBERON:0002370`), restricted to `is_primary_data == True` and `disease == 'normal'`.
   - On the **human side**, query a bounded, verified reference dataset (e.g., OneK1K PBMC `3faad104-2ab8-4434-816d-474d8d2641db`, $N = 981$ healthy donors, `31,261` primary `CL:0000905` cells, or AIDA `c838aec3-03ef-4398-b882-0e3912abfff0`, $N = 591$ donors, `25,012` primary `CL:0000905` cells) to report human CD4+ $T_{\text{EM}}$ vs. naive/central-memory `CD28` detection rate and normalized expression without downloading the entire 162M-cell human atlas.
   - On the **rhesus macaque side**, report from `obs` and `feature_dataset_presence_matrix` metadata that `0` `CL:0000905` / `CL:0001087` / `CL:0000624` cells and `0` blood/lymphoid datasets exist in Census `2025-11-08`, and document why the two datasets containing generic `T cell` (`CL:0000084`) records (`2e877cd3-5587-4fc1-8667-a48fe9e2a695` unmeasured fetal lung; `fc6ef080-9e5f-4aea-b9c4-a45a208bd288` `185` adult dlPFC nuclei) are excluded from direct cross-species comparison.
4. **Return `status: "partial"` with `comparison.comparable: false` and `comparison.biological_difference_supported: false`:**
   - Clearly separate measured human observations and macaque metadata coverage in `observations` and `measurements` from any biological hypothesis about TGN1412/CD28 species differences, and include all six limitation categories in `limitations`.

---

## 7. Supporting References & Data Provenance

1. **CELLxGENE Census (`2025-11-08`):** CZ CELLxGENE Discover Census, SOMA schema `2.4.0`, dataset schema `7.0.0`, `s3://cellxgene-census-public-us-west-2/cell-census/2025-11-08/soma/` ([Programmatic documentation](https://chanzuckerberg.github.io/cellxgene-census/)).
2. **CELLxGENE Discover Curation API:** `https://api.cellxgene.cziscience.com/curation/v1/datasets` (2,269 curated datasets inspected).
3. **Ensembl Comparative / Gene Lookup (`Release 115`):**
   - Human `CD28`: [`ENSG00000178562`](https://rest.ensembl.org/lookup/id/ENSG00000178562?content-type=application/json) (`GRCh38`, `HGNC:1653`).
   - Rhesus macaque `CD28`: [`ENSMMUG00000057214`](https://rest.ensembl.org/lookup/id/ENSMMUG00000057214?content-type=application/json) (`Mmul_10`, `VGNC:70759`).
4. **Verified *Macaca mulatta* Datasets with T-Lineage Annotations in Census `2025-11-08`:**
   - Senthamaraikannan P et al. (2022). *Inflammatory blockade prevents injury to the developing pulmonary gas exchange surface in preterm primates.* **Science Translational Medicine**, `10.1126/scitranslmed.abl8574`. Dataset ID: `2e877cd3-5587-4fc1-8667-a48fe9e2a695` ([CELLxGENE Explorer](https://cellxgene.cziscience.com/e/2e877cd3-5587-4fc1-8667-a48fe9e2a695.cxg/)).
   - Ma S et al. (2022). *Molecular and cellular evolution of the primate dorsolateral prefrontal cortex.* **Science**, `10.1126/science.abo7257`. Dataset ID: `fc6ef080-9e5f-4aea-b9c4-a45a208bd288` ([CELLxGENE Explorer](https://cellxgene.cziscience.com/e/fc6ef080-9e5f-4aea-b9c4-a45a208bd288.cxg/)).
   - Chiou KL et al. (2023). *A single-cell multi-omic atlas spanning the adult rhesus macaque brain.* **Science Advances**, `10.1126/sciadv.adh1914`. Primary Dataset ID: `d87ba7ec-fddf-4141-abfd-1d69e8427a42` ([CELLxGENE Collection](https://cellxgene.cziscience.com/collections/8c4bcf0d-b4df-45c7-888c-74fb0013e9e7)).
5. **Verified *Homo sapiens* Blood & Lymphoid Reference Datasets with `CL:0000905` / `CL:0001087` in Census `2025-11-08`:**
   - Yazar S et al. (2022). *Single-cell eQTL mapping identifies cell type–specific genetic control of autoimmune disease.* **Science**, `10.1126/science.abf3041`. Dataset ID: `3faad104-2ab8-4434-816d-474d8d2641db` ([CELLxGENE Explorer](https://cellxgene.cziscience.com/e/3faad104-2ab8-4434-816d-474d8d2641db.cxg/)).
   - Kock KH et al. (2025). *Asian Immune Diversity Atlas (AIDA) Phase 1 Data Freeze v2.* **Cell**, `10.1016/j.cell.2025.02.017`. Dataset ID: `c838aec3-03ef-4398-b882-0e3912abfff0` ([CELLxGENE Explorer](https://cellxgene.cziscience.com/e/c838aec3-03ef-4398-b882-0e3912abfff0.cxg/)).
   - Thomson Z et al. (2025). *Multi-omic profiling reveals age-related immune dynamics in healthy adults / Human Immune Health Atlas.* **Nature**, `10.1038/s41586-025-09686-5`. Dataset IDs: `46104f0b-9af5-466a-ae0f-56b8dc1969a2`, `aa32098f-f7b0-43f2-a00a-601d190aae94`, `e522d2cd-7927-4e59-a4ed-064009569279` ([CELLxGENE Collection](https://cellxgene.cziscience.com/collections/e9360edf-b0b7-4e01-bce8-e596814f13e7)).
   - Wells SB et al. (2025). *Multimodal profiling reveals tissue-directed signatures of human immune cells altered with age.* **Nature Immunology**, `10.1038/s41590-025-02241-4`. Dataset IDs: `1b350d0a-4535-4879-beb6-1142f3f94947`, `960ecd06-e7c2-463d-9a5b-6832994376c6` ([CELLxGENE Collection](https://cellxgene.cziscience.com/collections/cc431242-35ea-41e1-a100-41e0dec2665b)).
   - Domínguez Conde C et al. (2022). *Cross-tissue immune cell analysis reveals tissue-specific features in humans.* **Science**, `10.1126/science.abl5197`. Dataset IDs: `1b9d8702-5af8-4142-85ed-020eb06ec4f6`, `ae29ebd0-1973-40a4-a6af-d15a5f77a80f` ([CELLxGENE Collection](https://cellxgene.cziscience.com/collections/62ef75e4-cbea-454e-a0ce-998ec40223d3)).
6. **Immunological & Translational Benchmark Literature:**
   - Pitcher CJ et al. (2002). *Development and homeostasis of T cell memory in rhesus macaque.* **Journal of Immunology**, `10.4049/jimmunol.168.1.29` (defines rhesus macaque CD4+ $T_{\text{CM}}$ as $\text{CD95}^+\text{CD28}^+$ and $T_{\text{EM}}$ as $\text{CD95}^+\text{CD28}^-$).
   - Suntharalingam G et al. (2006). *Cytokine storm in a phase 1 trial of the anti-CD28 monoclonal antibody TGN1412.* **New England Journal of Medicine**, `10.1056/NEJMoa063842`.
   - Eastwood D et al. (2010). *Monoclonal antibody TGN1412 trial failure explained by species differences in CD28 expression on CD4+ effector memory T-cells.* **British Journal of Pharmacology**, `10.1111/j.1476-5381.2010.00922.x`.
