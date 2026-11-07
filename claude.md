Comment on everything, however minor - as long as it is not redundant

Ensure all tools are modular and as concise as possible.

---

# Universal JSON format

Every part of ASRA (layer tools, agents, report builder, HTTP API, frontend) exchanges data in this one format. It is defined in two places that **must stay in sync**:

- Backend: `Backend/contract/models.py` (Pydantic, validates and serialises)
- Frontend: `Frontend/lib/types.ts` (TypeScript types)

If you change a field, update both files and this section.

## Rules
- **Naming:** `LayerResult` uses snake_case keys (the design-doc contract). All other objects use camelCase keys. Python code always uses snake_case attributes; `CamelModel` aliases them to camelCase on the wire.
- **Agents never produce a number.** Python computes every value; agents only add `Finding`s.
- **Never invent data.** A layer that can't run returns `status: "unavailable"` with a reason in `limitations`, never empty-but-"ok".
- **No claim without a source.** Every `Finding.sourceRecordId` must match a `SourceRecord.id` returned by a layer that ran.
- **No numeric risk score.** Concern is qualitative (`high | moderate | low | flagged`). Anything resting on `incomplete` data is `flagged`.
- **Layers fail independently.** One layer erroring becomes `unavailable`; the rest still run.

## Enumerations
| Name | Values |
|---|---|
| `SpeciesId` | `mus_musculus`, `rattus_norvegicus`, `macaca_mulatta`, `macaca_fascicularis`, `canis_lupus_familiaris`, `sus_scrofa`, `oryctolagus_cuniculus`, `cavia_porcellus`, `danio_rerio` |
| `LayerName` | `sequence`, `localisation`, `cell_expression`, `tissue_expression` |
| `LayerStatus` | `ok` (ran, has data) · `incomplete` (partial data) · `unavailable` (did not run / failed) |
| `Concern` | `high`, `moderate`, `low`, `flagged` |
| `DataOrigin` | `live` (backend) · `fixture` (backend, at least one layer served hand-entered demo data, `data_version` = `"fixture (hand-entered)"`) · `mock` (frontend-only stand-in) |

## AssessmentRequest (frontend → `POST /assess`)
```json
{
  "species": "mus_musculus",
  "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQ",
  "sequenceLabel": "test|DEMO1|Example protein"
}
```
- `sequence`: uppercase, letters `ACDEFGHIKLMNPQRSTVWYX` only, at least 10 residues. The frontend strips FASTA headers, whitespace and digits; the backend re-validates (invalid input → 422).
- `sequenceLabel`: the FASTA header without `>`, or `null`.

## LayerResult (what every layer tool returns), snake_case
```json
{
  "gene": "SLC29A1",
  "species": "mus_musculus",
  "layer": "localisation",
  "status": "incomplete",
  "observations": [
    { "field": "shared_compartments", "value": "plasma membrane", "sourceRecordId": "uniprot:EXAMPLE" }
  ],
  "source_records": [
    { "id": "uniprot:EXAMPLE", "source": "UniProt", "url": null }
  ],
  "limitations": ["Animal entry lacks a mitochondrial annotation; absence of annotation is not biological absence."],
  "data_version": "UniProt 2026_04"
}
```
- `observations[].field` is what findings cite as `"<layer>.<field>"`.
- `observations[]` objects themselves are camelCase (`sourceRecordId`).
- Calling pattern: every layer is a function `(ResolvedQuery) -> LayerResult`, registered in `Backend/tools/__init__.py` (`LAYERS`).

## Finding (agent output), camelCase
```json
{
  "id": "f1",
  "claim": "One-sentence statement of the cross-species difference.",
  "mechanism": "Interpreter's explanation of why it might matter.",
  "concern": "flagged",
  "citedField": "localisation.shared_compartments",
  "sourceRecordId": "uniprot:EXAMPLE",
  "scepticNote": "Rests on incomplete data; downgraded."
}
```

## Report (`POST /assess` response → frontend), camelCase
```json
{
  "id": "uuid",
  "generatedAt": "2026-11-07T17:55:36+00:00",
  "origin": "live",
  "request": { "...AssessmentRequest" : "" },
  "sequenceStats": {
    "length": 66,
    "estimatedMassKDa": 7.27,
    "composition": [{ "residue": "A", "fraction": 0.106 }]
  },
  "layers": ["...four LayerResult objects, in LayerName order"],
  "findings": ["...Finding objects (may be empty)"],
  "recommendedExperiments": ["plain-text suggestions (may be empty)"],
  "limitations": ["report-wide caveats"]
}
```
- `sequenceStats` is computed by Python from the input (`Backend/tools/sequence_stats.py`, mirrored in `Frontend/lib/sequence.ts`).
- Downloads (JSON export) add a top-level `"caveat"` string to this object.
- Error responses follow FastAPI: `{"detail": "text"}` or, for 422, `{"detail": [{"msg": "...", "loc": [...]}]}`.

## Pipeline order
`AssessmentRequest` → `tools/resolver.py` (ResolvedQuery) → 4 layers via `run_isolated` (in parallel threads, LayerName order kept) → `agents/` (Investigator → Interpreter ⇄ Sceptic, one revision) → `report/builder.py` → `Report`.

Gene resolution (`resolver.gene_from_label`): the gene comes only from a human UniProt header's `GN=` or a label that is exactly an uppercase symbol; never a first-token guess (`sp|Q99808|…` is not gene `SP`). No gene → `gene=None`.

Sequence layer (`tools/sequence_layer.py`): with a gene it runs Ensembl orthologue + alignment + UniProt features (`run_sequence(gene, species, functional=True)` → `to_layer_result`); its observation values are **JSON strings**. Without a gene it falls back to the submitted-length-only `incomplete` result. Orthologue errors become `unavailable` with the reason (ambiguous candidates kept as evidence).

Localisation (`tools/localisation.py`): `compare_localisation(gene, species)` returns the detailed UniProt comparison dict; `to_layer_result` maps it (`complete`→`ok`, `partial`→`incomplete`, `error`/`unavailable`→`unavailable`) to `human_/animal_compartments`, `human_/animal_evidence`, `shared_compartments`, `human_/animal_only_compartments`.

Cell expression (`tools/cell_expression.py`): mouse uses the CELLxGENE Discover API for both species (exact UBERON+CL matches, `detection_<tissue>_<cell>` fields, always `incomplete` because aggregates lack dataset provenance); other species use the Census audit (`tools/cell_census.py`) live when `cellxgene_census` is installed (not on Windows), else its recorded run in `Backend/data/benchmarks/census_<GENE>_<species>.json`, else human-only `incomplete`.

Tissue expression (`tools/tissue_expression.py`): GTEx v8 median TPM beside Bgee calls for the animal orthologue, matched on UBERON (exact, else the explicit organ-level `ORGAN` map; each match says which). Nothing is ever divided across GTEx and Bgee.

Shared: `resolver.orthologue_gene_id(gene, species)` → `(ensembl_gene_id, note)`, cached in `Backend/data/cache/orthologue_gene_ids.json`; among several Ensembl orthologues it accepts only the candidate that also has the same gene symbol, and the note becomes a limitation. `tools/literature.py` holds curated publications appended as separate `literature_*` observations (species-scoped). `tools/fixtures.py` is an offline demo mode only (`ASRA_FIXTURES=1`).

In the agent stage: the Investigator splits layers into citable evidence and excluded ones (its `gaps` become report limitations and "obtain this data" experiments); the Interpreter drafts findings, each with a suggested `experiment`; the Sceptic runs a deterministic pass (citation must match an observation; `incomplete` evidence is forced to `flagged`) and then a Gemini pass whose verdicts can only weaken a finding (`accept | downgrade | reject`), never promote one. An experiment is kept only while its finding survives. Each run is appended to `Backend/data/logs/runs.jsonl`.
