# Localisation integration handoff

[localisation.py](./localisation.py) exposes `compare_localisation(gene: str, species: str) -> dict` (the detailed comparison below) and the pipeline layer `run_localisation(query: ResolvedQuery) -> LayerResult`, which maps it onto the universal contract and appends curated literature (see CLAUDE.md). It uses only the Python standard library and is tested with Python 3.11. No routes, frontend code, other biological modules, or dependency manifests were changed.

The checkout's [Agents.md](./Agents.md) was empty. This implementation follows the six-field contract supplied by the workstream owner, without adding top-level fields:

```python
from tools.localisation import compare_localisation  # run from Backend/

result = compare_localisation("SLC29A1", "mus_musculus")
# layer, status, observations, measurements, sources, limitations
```

Integration note: the existing [frontend layer type](../../Frontend/lib/types.ts) still uses different status names and fields, including `ok`, `incomplete` and `source_records`. The integration lead will need to reconcile that interface separately before direct UI consumption; this module follows the supplied backend contract.

Run these commands from the repository root:

```bash
python -m tools.localisation SLC29A1 mouse      # from Backend/
python -m pytest tests/test_localisation.py -q
```

The commands used in this checkout, whose existing virtual environment was not executable in the session, are:

```bash
/opt/homebrew/bin/uv run --no-project --python 3.11 python -m Backend.tools.localisation SLC29A1 mouse
/opt/homebrew/bin/uv run --no-project --python 3.11 --with pytest python -m pytest Backend/tests/test_localisation.py -q
```

`pytest` is a test dependency only. The CLI writes JSON to stdout and returns a nonzero exit code for `error` or `unavailable`. A `partial` result must be inspected for errors and evidence limitations; exit code zero alone does not certify a complete comparison.

## Result interpretation

| Field | Meaning |
| --- | --- |
| `layer` | Always `localisation`. |
| `status` | `complete`, `partial`, `unavailable`, or `error`, as described below. |
| `observations` | Traceable annotation summaries, explicitly separated from biological hypotheses. |
| `measurements.proteins` | Human and animal accessions, verified taxonomy, review status, entry versions, release, URLs, structured locations, evidence, topology, orientation, isoform context and notes. A failed side is `null`. |
| `measurements.comparison` | Overlap, annotations reported only in each retrieved record, and positive experimental support for annotation differences. |
| `measurements.errors` | Per-species failures with kind, message and request URL. Invalid input uses `side: null`. |
| `sources` | UniProt resolution searches and fetched protein records, including URLs, accessions and available release/version metadata. Publication URLs remain attached to their exact location or note evidence. |
| `limitations` | Missing evidence, resolution limits and constraints on scientific interpretation. |

- `complete`: both reviewed records were resolved, with location IDs and cited experimental evidence attached to every reported location. This describes the available annotation evidence, not an exhaustive map of cellular localisation.
- `partial`: at least one record was retrieved, but a record, annotation, location ID or experimental evidence is missing; similarity-only or unreviewed evidence also qualifies.
- `unavailable`: neither protein can be unambiguously resolved from successful searches.
- `error`: invalid input, or an API/record-validation failure prevents retrieval of either usable protein. One failed side with a usable counterpart is `partial` and retains its error details.

`supported_annotation_differences` means that a positive annotation reported in only one retrieved record has attached experimental PubMed evidence. It **never** means the protein is absent from that compartment in the other species. `biological_difference_supported` remains false because this module does not assess comparative experiments or negative evidence. When either record or its structured annotations are missing, one-sided difference lists are withheld.

The resolver queries exact gene symbols/synonyms and numeric species taxonomy, prefers a unique reviewed record, fetches its stable primary accession, and rechecks accession, taxonomy and gene identity. It refuses ambiguous or paginated search results. A unique unreviewed record is retained as partial evidence. Supported animals are mouse, rat, rhesus macaque, cynomolgus macaque, dog, pig, rabbit, guinea pig and zebrafish; common names, scientific names, Ensembl-style names and their taxonomy ID strings are accepted.

## Live SLC29A1 smoke test

The [complete saved JSON output](./localisation_slc29a1_example.json) is a live UniProt response-derived result, not a fallback fixture. It records retrieval time, UniProt release `2026_04`, human entry version 215 and mouse entry version 170. Both requests resolved successfully with no errors; the scientific result is `partial`.

| Finding | Human | Mouse |
| --- | --- | --- |
| Resolved protein | [Q99808](https://www.uniprot.org/uniprotkb/Q99808/entry), Homo sapiens, taxon 9606 | [Q9JIM1](https://www.uniprot.org/uniprotkb/Q9JIM1/entry), Mus musculus, taxon 10090 |
| Shared structured locations | Apical cell membrane (`SL-0015`), basolateral cell membrane (`SL-0026`), cell membrane (`SL-0039`) | Same three terms |
| Location evidence | `ECO:0000269` with PubMed identifiers | `ECO:0000250`, transferred by similarity from Q99808 |
| Structured mitochondrial annotation in retrieved records | None | None |

The supported finding is overlap in reported membrane annotations. The mouse evidence is inferred from the human record, so this overlap is **not independent experimental confirmation across species**. There are no annotation differences in the retrieved pair, and no supported biological localisation difference.

The absence of a mitochondrial annotation in either entry does not establish mitochondrial absence. The retrieved UniProt data do not reproduce the ENT1/fialuridine mechanism. Additional primary literature and comparative experiments are needed to evaluate mitochondrial targeting, drug transport and toxicity; no drug-safety conclusion is made.

## Validation and remaining limitations

The [mocked pytest suite](../tests/test_localisation.py) passes **38 tests**, including missing annotations, overlap, evidence strength and provenance, conservative positive differences, ambiguous/wrong-species records, accession revalidation, invalid inputs, HTTP failures, timeouts, truncated responses, malformed annotations and missing location IDs. Normal tests make no network requests; the CLI command above is the separate manual live smoke test.

- Matching gene symbols is not independent orthology validation. Renamed counterparts and duplicated genes require an orthology resource; ambiguous cases are refused.
- Comparison uses exact location IDs and unambiguous label fallback. It does not expand ontology ancestors or infer that differently specific membrane terms conflict.
- Locations are compared at protein-record level. Tissue, condition and isoform context is retained where UniProt supplies it but is not experimentally matched between species.
- Evidence codes and publications are preserved, but publication contents are not automatically reviewed. Similarity and other evidence cannot substitute for a comparative experiment.
- Only structured `SUBCELLULAR LOCATION` terms define compartments. Free-text notes and topology are retained separately; GO annotations and external localisation datasets are not merged.
- Each HTTP request has a 20-second socket timeout. Search size is bounded, but this is not a total wall-clock deadline. API outages/rate limits produce explicit errors; there are no automatic retries or persistent caches.
- A `complete` annotation result cannot establish a drug mechanism, clinical safety, or biological absence. Literature validation remains necessary for the fialuridine benchmark.

The callable and its contract are ready for integration review. Route wiring and expression work remain separate workstreams.
