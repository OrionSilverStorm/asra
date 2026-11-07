# Role 3 — Milestone 3

Only sequence tooling and focused tests are changed. No shared contracts,
routes, agents, frontend or cellular modules are changed.

## Calling the analysis

From `Backend/`, with the existing requirements installed:

```python
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result

rich = run_sequence("SLC29A1", "mus_musculus", functional=True)
layer = to_layer_result(rich)
```

The existing two-argument call retains its Milestone 2 schema and network
behaviour. `run_sequence(ResolvedQuery)` still returns submitted-sequence-only
`LayerResult` evidence; it never guesses that a submitted sequence is a gene's
reference protein. Functional analysis is an explicit keyword option for the
gene API. `add_functional_analysis(rich)` also enriches an existing result without
mutating it. The adapter accepts both schemas and preserves the nested analysis
as JSON in the `functional_analysis` observation. That observation cites the
computed analysis source; individual identities, features, motif evidence and
substitution overlaps retain their underlying UniProt or publication source IDs.

## Reproducible demonstration

```sh
cd Backend
../.venv/bin/python -m tools.sequence_demo
../.venv/bin/pytest tests/test_sequence_functional.py tests/test_sequence.py tests/test_sequence_adapter.py tests/test_resolver.py -q
```

The demonstration is offline. Raw UniProt responses and HTTP headers are in
`Backend/tests/fixtures/role3/`; `manifest.json` records response SHA-256 hashes,
HTTP response dates, source URLs and release headers. These dates describe the
snapshot responses; the replay does not claim a new retrieval. UniProt data are
CC BY 4.0: https://www.uniprot.org/help/license . The protein sequences must also
match the exact SHA-256 hashes already pinned in the Milestone 2 Ensembl tests.
The replay does not independently revalidate the orthology relationship against
today's Ensembl API. The live path does use the existing orthologue resolver.

## Verified findings

UniProt release **2026_04**, released 4 November 2026, was returned in the HTTP
headers. The exact sequence, organism, Ensembl gene/protein cross-reference,
primary accession and displayed isoform agree:

| Protein | Ensembl protein cross-reference | UniProt isoform | Length |
|---|---|---|---|
| Human | ENSP00000360820.3 | Q99808-1 | 456 aa |
| Mouse | ENSMUSP00000063096.7 | Q9JIM1-1 | 460 aa |

The Ensembl resolver supplies unversioned IDs; matched versioned UniProt
cross-references are retained rather than claiming Ensembl verified a particular
version. If the caller supplies a version, it must agree exactly.

The selected alignment has 89 resolved substitutions, 366 exact matches and
461 columns (79.39262472885032% identity). There are **42 substitutions overlapping
selected annotations** on either protein (including the literature region),
**47 without selected annotation overlap**, and zero unclassified substitutions.
These counts depend on the documented feature selection, not on an assessment
of functional impact. The selected records contain 53 human and 16 mouse
annotations: functional sites, mutagenesis, modifications, glycosylation,
transmembrane segments and regions. Topological compartments, complete chains,
secondary-structure elements and natural variants are excluded; otherwise broad
chain/compartment annotations would trivially cover the entire protein.

The human C414 site, annotated as essential for nucleobase transport with
experimental evidence (PMID 21795683), maps to mouse C418 and is identical. This
is a mapped residue observation, not proof that transporter activity is equal.
The current entries have no selected `Domain`, `Binding site` or `Motif` feature
records. The implementation extracts those types when provided, retaining the
original feature object, ECO codes and publication references; it does not invent
such annotations for SLC29A1.

Sources: [human UniProt JSON](https://rest.uniprot.org/uniprotkb/Q99808.json),
[mouse UniProt JSON](https://rest.uniprot.org/uniprotkb/Q9JIM1.json),
[C414 experimental paper](https://pubmed.ncbi.nlm.nih.gov/21795683/).

## SLC29A1 motif: literature and computation

[Lee EW, Lai Y, Zhang H, Unadkat JD (2006), J Biol Chem 281(24):16700–16706,
DOI 10.1074/jbc.M513825200, PMID 16595656](https://doi.org/10.1074/jbc.M513825200)
identified Pro71, Glu72 and Asn74 in the human PEXN sequence as important for
mitochondrial targeting. Tagged truncation and point-mutant constructs were
studied by confocal microscopy in MDCK cells. Swapping human PEXN for the rodent
PAXS sequence removed mitochondrial localisation in the tested construct; the
reverse mouse swap produced partial localisation. Mouse liver mitochondrial
FIAU uptake was also tested. This is experimental support in the paper's
systems, published after the 1993 clinical failure, not a universal motif rule.
The earlier experimental context is
[Lai et al. (2004), DOI 10.1074/jbc.M307938200](https://doi.org/10.1074/jbc.M307938200).

Independently, this replay computes human **PERN71–74** aligned contiguously to
mouse **PARS71–74**. E72→A and N74→S overlap the literature motif; P71 and R73
are identical. `X` in the paper's pattern means an unspecified residue, not an
ambiguous X in these sequences. The curated check requires verified human
displayed Q99808, SLC29A1 and the expected P/E/N anchor at those coordinates.
It records gaps, noncontiguous positions and alternative optimal traceback
ambiguity. Other genes and unsupported anchors produce no motif finding.
The motif evidence is explicitly separate from UniProt feature annotations.

Sequence identity, motif presence and overlap do **not** establish mitochondrial
localisation, altered function or drug toxicity. Missing mouse annotations never
establish biological absence. This milestone does not generate drug-risk claims.

## Failure behaviour and integration needs

- No first-hit mapping: all UniProt search candidates are verified; multiple
  verified entries, pagination, mismatched accession/isoform, organism, gene,
  protein or sequence yield unavailable annotation evidence.
- Timeouts, HTTP errors, invalid JSON and malformed responses are reported with
  reasons. Existing sequence measurements survive as `incomplete` evidence.
- Non-displayed isoforms are unsupported. Canonical feature positions are never
  reused for them. Explicit isoform sequence retrieval/coordinate annotations
  remain future work. Species name synonyms also need curated taxonomy handling;
  a mismatch currently fails conservatively.
- Uncertain/out-of-range/foreign-isoform feature endpoints are preserved but
  excluded from projection and overlap. Human gaps map to null animal positions;
  B/Z/X pairs are ambiguous, not resolved substitutions. A tied optimum is marked
  incomplete because a different traceback may change overlaps.
- Substitutions overlapping a known selected feature remain reportable when the
  other annotations are unavailable. Remaining substitutions are unclassified
  whenever annotation coverage is incomplete.
- `data_version` remains null because the Ensembl release is unknown. UniProt
  release, entry/sequence versions and per-source provenance are recorded inside
  each verified identity; a UniProt release is not an Ensembl release.
- Role 1 must supply the resolved gene, explicitly opt in and call the adapter.
  Existing routes accept sequences only and do not call this path. Consumers
  must decode JSON observations, retain nested source citations and respect
  incomplete status. Cellular localisation integration is outside this milestone.

Stop at Milestone 3; no commit, push or integration changes are included.

Validation in this workspace: full backend suite **188 passed, 2 skipped**
(the existing opt-in live Ensembl tests). The existing FastAPI TestClient health
test stalled inside the restricted sandbox; the full suite passed outside it.
The offline demonstration and adapter round trip passed. `git diff --check`
and whitespace checks on the new files passed. The pre-existing untracked
`Backend/tests/test_sequence_adapter.py` and `.venv/` were left untouched.
