Protein sequence validation, 2026-11-08

Branch: fix/protein-sequence-validation. No push or merge performed.

Inspected tools/resolver.py, tools/sequence.py, sequence_layer.py,
sequence_adapter.py, contract/models.py, sequence tests and pytest.ini before editing.
The shared LayerResult accepts optional string data_version; the rich evidence
schema explicitly enumerates fields. No interface or schema fields were added.

The runtime fix replaces null data_version with
`Ensembl REST homology; source release unknown`. This is source provenance,
not a claimed database release. Existing protein IDs, exact-sequence SHA-256,
source URLs and retrieval timestamp remain available. UniProt annotation
releases do not establish the Ensembl sequence release.

Observed live results are saved in protein_sequence_validation_observed.json.
This file contains actual output and raw ambiguity candidates, not a raw HTTP
recording. Synthetic mocked tests are identified explicitly and do not establish
biological results. Live tests are opt-in and service failures fail the tests.

| Query | Human protein | Animal protein | Matches / alignment columns | Identity % | Paired columns | Coverage human / animal % |
| --- | --- | --- | --- | --- | --- | --- |
| SLC29A1 / mus_musculus | ENSP00000360820 | ENSMUSP00000063096 | 366 / 461 | 79.392625 | 455 | 99.780702 / 98.913043 |
| CD28 / macaca_mulatta (rhesus) | ENSP00000324890 | ENSMMUP00000065245 | 216 / 220 | 98.181818 | 220 | 100 / 100 |
| CD28 / macaca_fascicularis (cynomolgus) | ENSP00000324890 | ENSMFAP00000034788 | 216 / 220 | 98.181818 | 220 | 100 / 100 |
| CRBN / oryctolagus_cuniculus | ENSP00000231948 | ENSOCUP00000033173 | 395 / 518 | 76.254826 | 415 | 93.891403 / 84.521385 |

Identity uses all alignment columns including gaps; coverage uses paired columns
divided by each full protein length. API perc_id metadata is retained separately
and is not substituted for locally computed global identity. Live success checks
validate species, IDs/hashes, URLs, metric arithmetic and adapter provenance.
The deterministic tests additionally recount matches and paired columns directly
from the aligned strings.

GADPH / mouse returned Ensembl HTTP 400 and remains unavailable. GAPDH is a
plausible intended spelling, but user intent cannot be established from a database
query. A separate GAPDH query resolved human ENSG00000111640 / ENSP00000229239
but returned three ortholog_one2many relationships and remains ambiguous. There
is no resolver contract permitting a typo alias, so no correction was introduced.

CYP3A4 / mouse returned nine ortholog_many2many relationships (the actual live
classification, rather than the anticipated one-to-many). All candidates are
retained; none was selected or aligned. The existing strict resolver already
preserves both one-to-many and many-to-many ambiguity. No expression-layer
selection or cache behavior was changed.

Commands run from Backend (logs in /tmp):

```
../.venv/bin/pytest tests/test_protein_sequence_validation.py -q
../.venv/bin/pytest tests/test_sequence_validation.py tests/test_sequence.py tests/test_sequence_functional.py tests/test_sequence_adapter.py tests/test_sequence_species.py tests/test_sequence_layer.py tests/test_resolver.py tests/test_protein_sequence_validation.py -q
ASRA_LIVE_ENSEMBL=1 ../.venv/bin/pytest tests/test_protein_sequence_validation.py -k live_pair -q -s
../.venv/bin/pytest -q
../.venv/bin/pytest -q --continue-on-collection-errors
timeout --signal=INT 60s ../.venv/bin/pytest -q --continue-on-collection-errors
```

New tests alone: 6 passed, 7 skipped. Focused suite after final test edits:
244 passed, 21 skipped. Live integration: 7 passed, 6 deselected (including
expected unavailable/ambiguous outcomes; these are not seven biological successes).
Full backend: 2 collection errors, no tests executed. Existing tests/test_cell_census.py
and tests/test_cellxgene_discovery.py have misplaced future imports at line 4.
The first continue-on-collection-errors attempt was interrupted after producing
no output; it yielded no pass count. A bounded retry also produced no output
and was interrupted; neither supplemental attempt establishes a pass count.

The first live request inside the sandbox failed DNS resolution. An approved
outside-sandbox retry reached Ensembl, and all seven live checks completed there.
The database release is unresolved. User confirmation of the intended GADPH
identifier and a justified biological choice for ambiguous cases remain necessary
before making a confident comparison. No biological fallback results were added.

Final review

Reviewed tracked diffs and all three new files; changes remain confined to the
protein sequence layer, its tests and documentation. git diff --check is clean.
The offline demonstration also now sets data_version to
`Offline pinned Ensembl protein pair; source release unknown`; its regression
asserts this value rather than null. Historical saved fixtures are unchanged.

Recomputed alignments from all four successful recorded sequence pairs, independently
counted matching and paired columns, and checked every measurement against the
recorded JSON. Species, protein IDs/SHA-256 and exact citation paths/query parameters
all match. This offline verification makes no claim of a new live retrieval.

Reproduced census collection errors with:

```
../.venv/bin/pytest tests/test_cell_census.py tests/test_cellxgene_discovery.py --collect-only -q
```

Both fail at line 4 on the duplicate `from __future__ import annotations`, following
a string expression at line 2. Python reports `SyntaxError: from __future__ imports
must occur at the beginning of the file`. These are syntax errors before the census
module imports can execute, not missing census dependencies. Both complete files
are byte-for-byte identical to HEAD; census code and tests were not modified.
Result: no tests collected, two errors.

Repeated the focused command listed above after the offline demonstration fix:
244 passed, 21 skipped. Live checks were not rerun during final review; their
previous results remain separately recorded above.
