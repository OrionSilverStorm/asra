# ASRA

Across-Species Risk Assessment.

## Data sources

| Source | Used for | Version / release | Licence | URL |
|---|---|---|---|---|
| Ensembl | Orthologues, gene models, sequence layer | to record at integration | Data: EMBL-EBI Terms of Use, CC BY 4.0. Code/API: Apache 2.0 | https://www.ensembl.org |
| UniProt | Subcellular localisation annotations and evidence codes | to record at integration | CC BY 4.0 | https://www.uniprot.org/help/license |
| CZ CELLxGENE Discover Census | Cell-type expression layer | to record at integration — census_version must be pinned | Data: CC BY 4.0. cellxgene-census package: MIT | https://chanzuckerberg.github.io/cellxgene-census/ |
| GTEx | Human tissue expression | to record at integration | Open-access summary data only; protected individual-level data is dbGaP-controlled and out of scope | https://gtexportal.org |
| Bgee | Cross-species tissue expression calls | to record at integration | to confirm on bgee.org | https://bgee.org |
| Biopython | Pairwise sequence alignment | from requirements.txt | Biopython License Agreement (BSD-style) | https://biopython.org |

No patient-level data is used. GTEx protected (dbGaP-controlled) data is out of scope. Each layer must record the release of the source it queried in its data_version field (not yet enforced).
