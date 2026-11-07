# Role 3 — Milestone 3.5: frontend species compatibility

Inspected branch `feature/protein-bioinformatics` and preserved all pre-existing
Milestone 3 work, the untracked adapter tests and virtual environment. No frontend,
routes, agents, shared contracts or cellular modules were edited. No commit/push.

## Actual selectable values and identifier compatibility

`Frontend/components/assessment/SpeciesSelect.tsx` imports `SPECIES` and
`SPECIES_GROUPS` from `Frontend/lib/species.ts`. It renders every entry in those
groups with `<option value={s.id}>`. All nine entries belong to rendered groups.
`AssessmentForm.tsx` validates with `isSpeciesId` and submits the exact ID unchanged.
The placeholder has an empty value and is disabled; it is not an animal choice.

The live [Ensembl species catalogue](https://rest.ensembl.org/info/species?content-type=application/json)
returned **all nine exact IDs as canonical names**, not aliases. No species-name
adapter or resolver change is necessary. Existing syntactically valid non-frontend
Ensembl species also remain accepted by the resolver; the shared evidence contract
still restricts adapted results to its nine species.

| Exact frontend value = Ensembl name | Taxon | Assembly |
|---|---:|---|
| mus_musculus | 10090 | GRCm39 |
| rattus_norvegicus | 10116 | GRCr8 |
| cavia_porcellus | 10141 | Cavpor3.0 |
| macaca_mulatta | 9544 | Mmul_10 |
| macaca_fascicularis | 9541 | Macaca_fascicularis_6.0 |
| canis_lupus_familiaris | 9615 | ROS_Cfam_1.0 |
| sus_scrofa | 9823 | Sscrofa11.1 |
| oryctolagus_cuniculus | 9986 | OryCun2.0 |
| danio_rerio | 7955 | GRCz11 |

The catalogue reports release 116 for these species. This does not independently
version the homology responses; `run_sequence().data_version` remains null.
UniProt release headers report **2026_04**. The frontend labels “Dog (beagle)” and
“Minipig” submit species-level identifiers: this check establishes neither beagle
nor minipig strain/assembly/protein specificity.

## Live SLC29A1 matrix

Live evidence collected 7 November 2026. Both `resolve_orthologue()` and
`run_sequence(..., functional=True)` were called for **every** row, with independent
homology HTTP requests. Their orthology outcomes agreed. Successful sequence
results also passed `to_layer_result()`.

All successful rows used human **ENSG00000112759 / ENSP00000360820 / Q99808-1,
456 aa**, exact sequence SHA-256
`49bca4bf056d239c66207751c15e2f1bf5c5f810a8685932c00ef588360f46ae`.
Identity is matches/all alignment columns, including gaps. Coverage is paired
residues/full protein length. Display percentages below are rounded to two decimals;
the JSON evidence retains full precision. H/A denotes human/animal coverage.

| Exact frontend species | Animal gene ID | Animal protein ID | Verified UniProt displayed sequence | aa | Identity % | H/A coverage % | Sequence status; animal annotation extraction |
|---|---|---|---|---:|---:|---|---|
| mus_musculus | ENSMUSG00000023942 | ENSMUSP00000063096 | Q9JIM1-1 | 460 | 79.39 | 99.78 / 98.91 | ok; 16 selected features |
| rattus_norvegicus | ENSRNOG00000019752 | ENSRNOP00000082743 | A0ACJ1MV19 | 504 | 70.83 | 100 / 90.48 | incomplete: tied alignment; 13 selected features |
| cavia_porcellus | ENSCPOG00000005137 | ENSCPOP00000004621 | H0V4R7 | 461 | 86.12 | 100 / 98.92 | ok; 12 selected features |
| macaca_mulatta | — | — | — | — | — | — | orthologue_unavailable in both calls |
| macaca_fascicularis | ENSMFAG00000038090 | ENSMFAP00000060756 | A0A7N9D7I6 | 590 | 76.78 | 100 / 77.29 | incomplete: tied alignment; 13 selected features |
| canis_lupus_familiaris | ENSCAFG00845011282 | ENSCAFP00845016038 | A0A8I3NI33 | 522 | 76.44 | 100 / 87.36 | incomplete: tied alignment; 12 selected features |
| sus_scrofa | ENSSSCG00000001700 | ENSSSCP00000052412 | A0A287B8K5 | 548 | 72.63 | 100 / 83.21 | incomplete: tied alignment; 12 selected features |
| oryctolagus_cuniculus | ENSOCUG00000017891 | ENSOCUP00000003048 | G1SJV6 | 456 | 88.82 | 100 / 100 | ok; 12 selected features |
| danio_rerio | two candidates below | two candidates below | not selected | — | — | — | ambiguous_orthologue in both calls |

Zebrafish returned two `ortholog_one2many` relationships:

| Candidate gene | Candidate protein | Supplied sequence length |
|---|---|---:|
| ENSDARG00000101289 | ENSDARP00000137952 | 440 aa |
| ENSDARG00000054447 | ENSDARP00000142204 | 436 aa |

Both raw candidates are retained in the report. Neither is chosen for alignment
or UniProt annotation transfer. Rhesus has a successful empty homology response;
this is not an API failure, unsupported species or proof of biological gene absence.

## CD28 checks

Prioritised rhesus, then cynomolgus and mouse as a comparison. All three resolve
uniquely, align, verify UniProt sequences and pass the adapter. Human reference:
**ENSG00000178562 / ENSP00000324890 / P10747-1, 220 aa**.

| Exact frontend species | Animal gene ID | Animal protein ID | UniProt displayed sequence | aa | Identity % | H/A coverage % | Selected animal features |
|---|---|---|---|---:|---:|---|---:|
| macaca_mulatta | ENSMMUG00000057214 | ENSMMUP00000065245 | A0A5F7ZKV3 | 220 | 98.18 | 100 / 100 | 3 |
| macaca_fascicularis | ENSMFAG00000003864 | ENSMFAP00000034788 | A0ACM8QAJ6 | 220 | 98.18 | 100 / 100 | 3 |
| mus_musculus | ENSMUSG00000026012 | ENSMUSP00000027165 | P31041 | 218 | 68.92 | 98.18 / 99.08 | 9 |

Sequence observations cannot establish cell-population CD28 expression or a
TGN1412 response. No expression, altered function or toxicity inference is made.

## Annotation coverage and failure categories

Successful annotation extraction means selected feature records were returned
for an exactly verified protein, not that biological questions can be answered
equally well for each species. Human SLC29A1 has 53 selected annotations and
human CD28 has 14. Mouse SLC29A1 and CD28 are reviewed UniProt entries; the
other animal entries retrieved here are unreviewed.

In particular, the six non-mouse SLC29A1 animal entries contain only selected
transmembrane segments and regions (mostly disorder predictions). They have no
selected annotated active site, binding site, domain or motif. Those records
are insufficient for specific functional-residue or motif-effect conclusions,
despite successful mapping/extraction. The macaque CD28 entries each contain
one transmembrane segment, one domain and one region, far less than the human
residue/modification evidence. Absence of any annotation is not biological absence.

Machine-readable distinctions are preserved:

| Category | Meaning / observed result |
|---|---|
| orthologue_unavailable | Successful Ensembl response has no target: observed for rhesus SLC29A1 |
| ambiguous_orthologue | Multiple/non-one-to-one candidates: observed for zebrafish SLC29A1 |
| api_failure | Transport/HTTP failure: one UniProt ConnectTimeout, recovered on the single retry; no terminal API failures |
| missing_sequence | Resolved relationship has no valid protein sequence; not observed in this audit |
| missing_uniprot_mapping | Successful UniProt search returns zero mappings; not observed for uniquely resolved pairs |
| unverified_uniprot_mapping | Candidates exist but accession/isoform/organism/xref/full sequence cannot be uniquely verified; not observed here |
| insufficient_functional_annotations | A verified entry has no selected features or unsupported feature endpoints; distinct from missing mapping; covered by unit tests, not observed as an extraction failure here |
| incomplete / tied alignment | Rat, cynomolgus, dog and pig SLC29A1 mappings depend on the selected optimal traceback |

Sparse region-only annotations additionally limit interpretation as described
above; `status: ok` at extraction does not imply comprehensive annotation.

## Evidence and reproduction

`Backend/tests/fixtures/role3/species_compatibility/report.json` contains the
complete species catalogue matches, identifiers, hashes, measurements, source
URLs, annotation statuses, limitations and request events. `http.json` contains
all 50 actual HTTP attempts with timestamps, URLs, response bodies and relevant
headers, including the recovered failure. Successful UniProt responses are reused
within this audit to avoid repeatedly fetching the same human reference; cache
hits are explicit in request events. No homology requests were reused.

Requests were sequential, separated by at least 0.4 s, with 10 s connect / 20 s
operation timeouts and one retry on transport/transient HTTP errors. Long or
date-form Retry-After responses are surfaced without an early retry. No HTTP 429
was observed. Live collection does not replace pinned evidence with guesses on
failure. The normal replay makes no network calls and consumes the complete tape.

From `Backend/`:

```sh
# Reproduce against the captured live evidence, without modifying it:
../.venv/bin/python -m tools.sequence_species_audit --replay --output tests/fixtures/role3/species_compatibility

# Fresh live audit; use a new output directory to preserve the pinned run:
../.venv/bin/python -m tools.sequence_species_audit --live --output /tmp/asra-species-audit

# Optional fresh parameterised integrations (twelve gene/species pairs):
ASRA_LIVE_SPECIES=1 ../.venv/bin/pytest tests/test_sequence_species.py -k live_frontend_pair -q
```

The frontend source hash is recorded so additions to the dropdown cannot silently
escape the inventory tests. The independent unit inventory, shared species enum,
synthetic full resolver/alignment/annotation/adapter tests for all nine values,
real HTTP replay and optional live tests cover the complete current list.

## Changes and integration

- `Backend/tools/sequence_functional.py`: typed annotation retrieval/mapping
  failures and nested per-protein `reason_code`; no signature/schema change to
  the shared contracts or sequence entry points.
- `Backend/tools/sequence_species_audit.py`: live recorder, frontend inventory,
  independent resolver/sequence checks and offline replay.
- `Backend/tests/test_sequence_species.py`: parameterised compatibility,
  failure distinctions, recorded replay and optional live integrations.
- `Backend/tests/fixtures/role3/species_compatibility/`: captured live evidence.
- This Role 3 report.

No identifier conversion is needed. The backend integration still needs a
resolved human gene, `run_sequence(gene, exact_frontend_id, functional=True)` and
explicit `to_layer_result()`. The existing sequence-only `ResolvedQuery` path,
default two-argument `run_sequence()` and both adapter schemas remain compatible.
Consumers should decode JSON evidence, handle nested `reason_code`, surface
ambiguous/unavailable/incomplete states, and avoid promising annotation parity.
Routes still accept sequences only and have intentionally not been changed.

Only the current Ensembl representative proteins are checked. Different isoforms,
assemblies, strains and future API releases can change coverage/results. A unique
one-to-one relationship is not proof of functional equivalence. Stop at 3.5.

## Validation

- Focused Role 3 tests: **210 passed, 14 skipped**.
- Full backend regression suite: **219 passed, 14 skipped**. It ran outside
  the restricted sandbox because of the previously observed FastAPI TestClient
  sandbox hang; no test or application changes were made for that environment.
- The fourteen skips are twelve optional frontend-pair live tests and two
  existing optional live Ensembl tests. The independent live recorder actually
  exercised all twelve gene/species pairs; the captured fifty HTTP attempts
  replay successfully through current public interfaces in the normal tests.
- `git diff --check` and whitespace checks on the new Role 3 files passed.
- No frontend identifiers, shared enums/contracts, routes, agents, cellular
  modules, requirements, teammate files or pre-existing adapter tests changed.
