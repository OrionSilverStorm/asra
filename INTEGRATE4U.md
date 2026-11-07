# ASRA integration handoff — Role 1 (Full-Stack & Integration)

## 1. Project context and scope

ASRA is a preclinical cross-species biological risk investigator. Role 3 has completed Ensembl orthologue retrieval, Biopython global sequence alignment, UniProt functional annotation analysis, nine-species compatibility testing, evidence adaptation and scientific validation. Your implementation task is to connect this scientific evidence to the application without losing measurements, provenance or uncertainty.

- **Source branch:** `feature/protein-bioinformatics`.
- **Integration target:** latest fetched `origin/master`, using a dedicated integration branch.
- **Inspected source commit:** `001d2324682d6eafbf6d5c5e145ff19a6831c41e` (`Complete Role 3 validation bundle`).
- **Inspection date:** 7 November 2026. Repository contents, rather than assumed APIs, underpin this handoff. Recheck signatures and contracts after fetching and reconciling master.
- This file was prepared as a documentation-only task on the source branch. No integration code, dependency changes, commits or pushes belong to its preparation. The implementation steps below are instructions for the subsequent Role 1 integration task.

Read these first:

1. `Backend/tools/sequence_integration_handoff.md` — public callable interfaces, adaptation and failure semantics.
2. `Backend/tools/sequence_milestone4.md` — validated results, transcript concerns, tied alignments and nine-species outcomes.
3. `Backend/tools/sequence.py`, `Backend/tools/resolver.py`, `Backend/tools/sequence_functional.py`, `Backend/tools/sequence_adapter.py` and their tests listed below.
4. `Backend/contract/models.py`, `Backend/contract/__init__.py`, `Frontend/lib/types.ts` and `claude.md` — actual shared contracts and naming rules.
5. Latest master orchestration, agents, frontend and Role 4 implementations. The inspected source branch still contains placeholder cellular modules; this does not describe newer teammate implementations.

## 2. Before integration: preserve the shared repository

Fetch the latest GitHub changes before choosing a base. Inspect `git status --short`, applicable `AGENTS.md` files, local and remote branch histories, and existing worktrees. Do not stash, overwrite or remove someone else's work to obtain a clean checkout. Never force-push, reset or discard teammate work.

Suggested preparation from the repository root; choose unused branch and directory names:

```sh
git status --short
git fetch origin
git log --oneline --left-right feature/protein-bioinformatics...origin/feature/protein-bioinformatics
git rev-parse origin/master
git rev-parse feature/protein-bioinformatics
git rev-parse origin/feature/protein-bioinformatics
git diff --stat origin/master...feature/protein-bioinformatics
git worktree add -b integration/role1-protein-bioinformatics /tmp/asra-role1-integration origin/master
```

The original worktree must remain on `feature/protein-bioinformatics`. Reconcile any source-branch divergence explicitly and record the exact source SHA selected; do not assume the remote contains all local work or that this document's inspected SHA is the newest source. In the dedicated worktree, inspect both sides before integrating that selected source commit. A reviewed `git merge --no-commit --no-ff <selected-source-SHA>` can stage the integration without automatically committing it; the placeholder must be replaced with the recorded SHA.

Resolve conflicts semantically, especially `Backend/tools/resolver.py` and `Backend/tools/sequence.py`. Preserve master changes to the Gemini agents, frontend, contracts, orchestration and cellular-team modules/adapters. Do not restore either whole file from a branch to resolve a conflict. Preserve Role 3's gene APIs and legacy sequence path alongside newer master behavior. Do not merge unrelated branches merely because they exist. Leave committing and pushing to the authorization for the integration task.

For provenance only, the local `origin/master` at documentation inspection was `51baf3582a6ba30da41ef0e6eca7f4d9d7c1c748`; it was **not refreshed during this documentation task** and must not be used as a claim of latest master. The inspected source history beyond that local reference includes:

| Commit | Purpose |
|---|---|
| `1fedc6cd894b2ce8bc5e211652afbf6c23c0c215` | Ensembl orthologue resolver |
| `56a6da880344047500e706b78c390b6ffc08c916` | Resolver and protein alignment |
| `3e5e9e48f5419f62df30baa4f2fda671175219c3` | Merge of earlier `origin/master` |
| `ccfdbce9a40e6593b67e42375a927c23bfd1db99` | Evidence/integration readiness |
| `08fe62d6df33207154a653650777d5a34f592dce` | Functional analysis and species validation |
| `7f84391355ffe6aa5ca50909b9fa8df30051c264` | Validation and handoff |
| `001d2324682d6eafbf6d5c5e145ff19a6831c41e` | Final Role 3 validation bundle |

These are source-history references, not a claim that any integration has happened or an instruction to cherry-pick every commit.

## 3. Gene resolution: establish the human identity explicitly

The current `AssessmentRequest` has `species`, required `sequence` and optional `sequence_label` (wire alias `sequenceLabel`), with **no gene field**. `tools.resolver.resolve(request: AssessmentRequest) -> ResolvedQuery` preserves the submitted sequence and label but leaves `gene=None`. `ResolvedQuery` is a frozen dataclass with `species`, `sequence`, `sequence_label`, `gene`. The present pipeline cannot reliably identify a gene from a submission.

Implement an explicit human gene symbol input and server-side validation, or a verified human UniProt header route. Extend the request contract compatibly and update the Python model, TypeScript type, form, client, mock and `claude.md` together. This is a proposed contract extension, not an existing request API. Keeping `sequence` required initially is the least disruptive option; accepting gene-only requests would also require deliberate changes to validation, sequence statistics, report rendering and exports. Do not fabricate a placeholder sequence to satisfy the contract.

- Treat `GN=SLC29A1` in a human UniProt FASTA header as a candidate that must be verified against the accession/organism and resolved human identity. Preserve how the gene was established and the original header. The current Role 3 resolver validates symbol syntax and retrieves Ensembl human homology; it is not a UniProt FASTA parser or a general symbol authority service.
- **Never parse `sp|Q99808|S29A1_HUMAN` as gene `SP`.** `sp` denotes the database header prefix, `Q99808` is an accession and `S29A1_HUMAN` is an entry name. Do not use a first-token heuristic.
- If explicit input, header, organism or accession conflict, report the conflict and require resolution. Do not silently choose one. Never infer a gene from arbitrary amino acid sequences.
- If unresolved, keep the gene unset and return explicit `incomplete` submitted-sequence evidence or `unavailable` database evidence with reasons. The remaining assessment must still run. Do not report successful orthologue comparison.
- Retrieved human/animal reference proteins are the basis of the gene-based comparison. A submitted sequence must not silently become a reference protein or be assumed identical to the retrieved human protein. Label submitted-sequence statistics separately from reference-protein lengths and identity.

`Frontend/lib/sequence.ts::parseSequence()` currently preserves a single FASTA label but normalizes residues and strips a terminal stop. The scientific alignment API instead validates unchanged proteins and rejects stops, whitespace, lowercase and unsupported residues. Do not transfer the frontend's cleaning policy to retrieved scientific sequences. Request validation accepts standard amino acids plus X and requires at least 10 residues; the aligner additionally accepts B/Z and has no minimum length. These are distinct interfaces; preserve compatibility deliberately.

## 4. Sequence integration and exact public interfaces

Verified interfaces, imported with `Backend/` as the working directory or on `PYTHONPATH`:

| Module | Interface and behavior |
|---|---|
| `tools.resolver` | `resolve_orthologue(gene: str, species: str) -> dict`; retrieves a unique human-to-animal one-to-one relationship or raises a typed error. |
| `tools.sequence` | `align_proteins(human: str, animal: str) -> dict`; global alignment and measurements, without retrieval. |
| `tools.sequence` | `run_sequence(gene: str \| ResolvedQuery, species: str \| None = None, *, functional: bool = False) -> dict \| LayerResult`; overloads described below. |
| `tools.sequence_functional` | `add_functional_analysis(result, *, retrieve=None)`; returns an enriched copy. Optional retrieval injection returns `(entry, provenance)` and is reverified. |
| `tools.sequence_adapter` | `to_layer_result(result: dict) -> LayerResult`; the public bridge from rich evidence to the shared contract. |

The required production gene call is:

```python
import json

from contract import LayerResult
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result

# gene has already been resolved/validated as a human symbol.
# species is a supported frontend Ensembl identifier.
rich = run_sequence(gene, species, functional=True)
layer = to_layer_result(rich)
wire = layer.model_dump(mode="json", by_alias=True)

# Validate the adapted contract, then recover typed observations.
restored = LayerResult.model_validate(wire)
observations = {o.field: json.loads(o.value) for o in restored.observations}
identity = observations["measurements"]["identity_percent"]
```

This fragment illustrates the successful evidence path; put retrieval, adaptation and typed failure handling inside the isolated layer boundary described below. **Never call `LayerResult.model_validate(rich)`**: the rich schema is not the layer contract, and unknown measurements can be ignored while default empty observations conceal the loss. Validating an already adapted wire object, as above, is appropriate.

`run_sequence(ResolvedQuery)` is the legacy, network-free submitted-sequence path. It returns `LayerResult(status="incomplete")` even if `query.gene` is populated. Merely adding a gene to `ResolvedQuery` will therefore not activate reference comparison. The registry currently assigns `LAYERS["sequence"] = run_sequence`; replace or wrap that registry entry at the orchestration boundary so a verified gene invokes the two-argument API and adapter, while older sequence-only callers retain explicit fallback behavior. Keep `LayerFn = Callable[[ResolvedQuery], LayerResult]` compatibility unless the latest shared architecture requires an agreed extension. Do not invent a new Role 3 scientific entry point.

Preserve every rich field through adaptation and report serialization:

- Direct fields: `gene`, `species`, `layer`, `status`, `source_records`, `limitations`, `data_version`.
- Required structured observations: `human`, `animal`, `orthology`, `retrieved_at`, `provenance`, `alignment`, `parameters`, `measurements`, `metric_definitions`, `human_to_animal`, `animal_to_human`, `substitutions`, `ambiguous_pairs`, `indels`.
- Optional structured observation: `functional_analysis`, including protein identity/isoforms, features, mapped human features, annotated differences, motif/literature evidence, nested status and limitations.

Observation `value` is a **JSON string**, not a display-formatted metric. Decode with `json.loads`/`JSON.parse` for consumers; retain original values for audit/export. Integers and floats survive decoding; coordinate-map keys become strings and mapping values can be null. Coordinates are 1-based inclusive. Never round stored evidence or discard accession IDs, hashes, source records, provenance, annotation evidence, limitations or residue mappings. Display rounding is acceptable when raw precision remains available.

The adapter rejects missing/unhandled top-level fields, source-record extensions, duplicate IDs and absent required citations. Treat rejection as an integration/schema issue to diagnose, not a reason to bypass the adapter or trim evidence. It requires `ensembl_orthology`; functional evidence additionally requires `sequence_functional_analysis`. Other observation fields cite `ensembl_orthology`, while `functional_analysis` cites `sequence_functional_analysis` and retains underlying UniProt/publication citations inside its JSON. A missing `SourceRecord.url` becomes null. Do not call `add_functional_analysis()` again on already enriched evidence; duplicate source IDs would result.

## 5. Scientific error handling and isolation

`LayerStatus` currently permits only `ok`, `incomplete`, `unavailable`; **there is no `ambiguous` enum**. Construct a normal shared-contract failure result with an explicit reason and, where relevant, JSON observations for candidate records. Do not pass exceptions or `sequence_species_audit.error_record()` dictionaries into `to_layer_result()`: audit categories are not rich sequence results or valid layer statuses.

| Condition | Required integration behavior |
|---|---|
| `OrthologueNotFoundError` | Sequence layer unavailable with reason. Empty results do not prove biological absence. |
| `AmbiguousOrthologueError` | Unavailable comparison; preserve raw `.candidates` as JSON evidence for review. Never choose the first candidate or claim equivalence. |
| `MissingSequenceError`, `InvalidEnsemblResponseError` | Unavailable comparison with identifier/response reason; do not align fabricated or cleaned replacement sequences. |
| `EnsemblAPIError`, transport failures/timeouts | Contain failure in the layer; report retrieval failure separately from absent biology. |
| Invalid input (`ValueError`) | Validate at the API boundary; keep any remaining scientific-layer error isolated. Preserve existing 422 behavior for malformed requests. |
| Multiple optimal alignments | Retain `parameters.alternative_optimal_alignment_exists`, first-traceback policy, mappings and caveats; status remains incomplete. |
| Unsupported/non-displayed isoform or unverified UniProt mapping | Retain sequence evidence; annotation analysis stays partial/unavailable with its recorded reason. Never transfer canonical coordinates silently. |
| Missing/insufficient UniProt annotations or annotation API failure | Preserve measurements and available features; retain nested statuses, `reason_code` and limitations, with incomplete overall evidence. Absence of annotation is not absence of function. |

Annotation reason codes currently include `api_failure`, `missing_uniprot_mapping`, `unverified_uniprot_mapping`, `insufficient_functional_annotations`, `invalid_annotation_response`. `add_functional_analysis()` already contains supported annotation failures and preserves alignment evidence. Do not replace its partial result with a blank successful layer. `ok` means the requested computation returned data, not exhaustive annotation coverage or biological certainty.

`Backend/tools/base.py::run_isolated(layer, fn, query)` catches layer exceptions; `unavailable(layer, query, reason)` builds an unavailable result. Preserve this protection for all four layers and catch ambiguity specifically before the generic boundary loses its candidate payload. In `Backend/pipeline/runner.py::run_assessment(request)`, `resolve(request)` executes **before** the isolated layer loop. Do not introduce uncaught network lookup failures there; return an unresolved context with reasons or contain resolution failure explicitly so other layers and report generation continue.

Runtime Ensembl and UniProt reads use 30-second request timeouts. The species audit has its own pacing/retry/cache policy; it is not production middleware. Bound orchestration latency and report API failures honestly; do not claim a production retry/cache exists. Unknown Ensembl release stays `data_version=None`; UniProt release or retrieval date cannot fill it.

Sequence similarity, residue substitutions and feature overlaps alone do not establish altered function, toxicity, binding, localisation or safety. Tied optima and incomplete evidence must not become confident agent conclusions. Preserve Role 3's conservative runtime flags even when the independent audit found invariant aggregate metrics for particular recorded pairs.

## 6. Dependencies and clean installation

`Backend/requirements.txt` already contains `biopython==1.88`, `fastapi`, `uvicorn[standard]`, `google-genai`, `python-dotenv`, `pytest`, `httpx`. Pydantic v2 is currently supplied transitively by FastAPI; the code uses v2 APIs. Reconcile requirements against latest master without dropping teammates' dependencies, and verify a clean install actually supplies the required Pydantic behavior. Role 3 validated with Python 3.12; do not treat an existing developer virtualenv as clean-install proof.

Example commands from the integration repository root, using a new temporary environment:

```sh
python3.12 -m venv /tmp/asra-role1-clean-venv
/tmp/asra-role1-clean-venv/bin/python -m pip install -r Backend/requirements.txt
/tmp/asra-role1-clean-venv/bin/python -m pip check
```

From `Backend/`, verify imports, including the lazily loaded aligner dependency:

```sh
/tmp/asra-role1-clean-venv/bin/python -c 'import Bio, httpx, pydantic; from Bio.Align import PairwiseAligner; from contract import AssessmentRequest, LayerResult, Report; from tools.resolver import resolve_orthologue; from tools.sequence import run_sequence; from tools.sequence_adapter import to_layer_result; from main import app; print(Bio.__version__, pydantic.__version__); assert Bio.__version__ == "1.88"; assert int(pydantic.__version__.split(".")[0]) == 2'
```

Report dependency/network failures as blockers, not successful installation. Use a different unused temporary path if one already exists.

## 7. Validated benchmarks and scientific boundaries

### SLC29A1: human versus mouse (`mus_musculus`)

| Measurement/identity | Validated value |
|---|---|
| Human length | 456 amino acids |
| Mouse length | 460 amino acids |
| Exact matches / alignment columns | 366 / 461 |
| Identity | 79.39262472885032% (approximately 79.3926247%) |
| Human displayed UniProt isoform / Ensembl protein | Q99808-1 / ENSP00000360820 |
| Mouse displayed UniProt isoform / Ensembl protein | Q9JIM1-1 / ENSMUSP00000063096 |
| Human motif at residues 71–74 | PERN |
| Mouse motif at residues 71–74 | PARS |
| Computed motif substitutions | E72→A and N74→S; P71 and R73 unchanged |

Identity is `100 * exact_matches / alignment_columns`, including gap columns in the denominator. Paired identity is a separate measurement. Coverage is `100 * paired_columns / full_protein_length` for each protein. Alignment is global BLOSUM62, gap open -10, gap extension -0.5, equal terminal/internal penalties, epsilon 1e-6. This benchmark has one optimum. Never replace its measured identity with the older **78.4% mock value**, and never hardcode benchmark measurements as a substitute for computation.

Keep `functional_analysis.slc29a1_motif.sequence_observation` separate from its `literature` record. The computed PERN/PARS difference is an alignment observation. Lee et al. (2006), PMID 16595656 / DOI `10.1074/jbc.M513825200`, supplies the curated PEXN/PAXS targeting mechanism from tagged construct/cell experiments. It does not measure localisation or toxicity for the submitted sample or arbitrary species. X in that published motif notation is a wildcard. Preserve the paper's experimental scope and the limitation that it postdates the 1993 clinical event. Do not elevate abstract verification to newly verified full-text/figure evidence.

### CD28: human versus rhesus (`macaca_mulatta`)

The recorded pair has 220 amino acids on each side, 216 exact matches, no gaps, 100% coverage and 98.18181818181819% identity. Substitutions are F11L, V155A, I175C, V179M in full-sequence coordinates. Human identity is P10747-1 / ENSP00000324890; rhesus is A0A5F7ZKV3 / ENSMMUP00000065245. Human has seven documented isoforms; only the displayed sequence was analysed. Rhesus evidence is unreviewed/predicted with sparse annotations. Exact sequence/xref matching does not confer experimental annotation parity. Do not infer T-cell population expression, TGN1412 response or safety.

### Nine-species compatibility

All nine identifiers in `Frontend/lib/species.ts`, `Frontend/lib/types.ts` and `Backend/contract/models.py` must remain accepted or yield an explicit scientific unsupported/ambiguous outcome. Recorded **SLC29A1-specific** results are:

| Species ID | Recorded outcome |
|---|---|
| `mus_musculus` | ok |
| `rattus_norvegicus` | incomplete; tied optimal alignments |
| `macaca_mulatta` | orthologue unavailable for this recorded query |
| `macaca_fascicularis` | incomplete; tied optimal alignments |
| `canis_lupus_familiaris` | incomplete; tied optimal alignments |
| `sus_scrofa` | incomplete; tied optimal alignments |
| `oryctolagus_cuniculus` | ok |
| `cavia_porcellus` | ok |
| `danio_rerio` | ambiguous orthologue; two retained candidates |

These are replay expectations, not guarantees about future live data or every gene. In particular, SLC29A1 rhesus unavailability must not block the validated CD28 rhesus case. Zebrafish needs justified paralogue selection. Species IDs do not establish beagle breed or minipig strain specificity.

Rat, cynomolgus, dog and pig SLC29A1 selected proteins have unresolved transcript/model suitability concerns and long alignment extensions. Do not silently substitute the alternative accessions discussed in `sequence_milestone4.md` or label extensions as established evolutionary changes. Pig motif contiguity/P71 mapping varies between optimal tracebacks. Keep these caveats visible even where aggregate identity is invariant in the recorded audit.

## 8. Frontend, Gemini and report integration

Required flow:

```text
AssessmentForm / AssessmentWorkspace
  -> submitAssessment -> submitAssessmentHttp -> POST /assess
  -> run_assessment -> resolved human gene + species
  -> isolated sequence wrapper -> run_sequence(gene, species, functional=True)
  -> to_layer_result -> four-layer evidence list
  -> run_agents -> build_report -> ReportView + exports
```

Relevant existing locations and responsibilities:

- `Frontend/components/assessment/AssessmentForm.tsx` constructs the request; `AssessmentWorkspace.tsx` manages submission and errors. Add verified gene collection and show unresolved/conflicting identity clearly.
- `Frontend/lib/api/index.ts::submitAssessment()` selects the real backend unless `NEXT_PUBLIC_USE_MOCK` is exactly `"true"`. `Frontend/lib/api/http.ts::submitAssessmentHttp()` posts to `/assess` at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Check build-time environment values when validating the real path.
- `Backend/api/routes.py::assess(request)` calls `pipeline.run_assessment`; `Backend/tools/__init__.py::LAYERS` supplies the four layer functions. Keep routes thin and the layer boundary isolated.
- `Backend/agents/orchestrator.py::run_agents()` calls `investigator.select_evidence()`, `interpreter.interpret()`, then `sceptic.review()`, with at most one revision. Supply the adapted scientific layer, including partial evidence, rather than submitted-length-only or mock evidence.
- Investigator retains non-unavailable layers with sources. Interpreter serializes layers into the prompt using `Backend/agents/prompts/interpreter.md`; JSON-encoded observations must remain readable as evidence with their definitions and caveats. Verify the actual measurements and motif evidence reach the prompt and influence supported interpretations.
- Current Sceptic checks source existence and downgrades incomplete evidence to `flagged`; it does **not** validate that `cited_field` exists or that the cited source supports that particular observation. Coordinate with Role 2 to validate layer/field/source relationships and nested publication attribution. Valid existing citations include `sequence.measurements` and `sequence.functional_analysis`; do not invent dotted nested fields unless validation is explicitly extended to support them.
- `Backend/agents/llm.py` uses `GEMINI_API_KEY` and optional `GEMINI_MODEL`. Missing credentials or model failure yields no findings; this is not proof of a successful Gemini review. Preserve that fallback and label/report the review limitation. Never fabricate findings to satisfy an end-to-end test.
- `Backend/report/builder.py::build_report()` assembles the response; `_limitations()` currently adds status-based summaries, not every detailed layer limitation. Preserve layer and nested caveats in the report and present material caveats alongside conclusions.
- `Frontend/components/report/LayerPanel.tsx` currently prints `o.value` verbatim. Add sequence-aware rendering that decodes the known JSON observations safely and shows identity/coverage definitions, reference lengths, accessions, motif residues, annotated differences, statuses, source links and limitations. Keep other layers and legacy plain-string observations working. Do not leave scientific evidence as raw JSON strings.
- Preserve precision and complete evidence in JSON export. Update readable Markdown/print output through `Frontend/lib/export.ts` and report components so source citations, limitations, input/reference distinctions and provenance survive download as well as on-screen rendering.

### Live versus replay: required contract reconciliation

The current backend `DataOrigin` and frontend type accept only `"mock" | "live"`; `build_report()` hardcodes `origin="live"`. `ReportHeader.tsx` labels every non-mock report Live, and Markdown export only labels mock reports specially. There is **no existing replay report origin**. Fix this mismatch coherently in the implementation: agree an explicit replay origin/provenance representation across Python, TypeScript, `claude.md`, builder, UI, exports and tests. A new enum value is a proposed change, not an implemented API in this branch.

Fixture/replay reports must visibly identify recorded evidence and its original capture metadata and must never be labelled live. A new report timestamp or a fresh Gemini interpretation does not turn old biological evidence into a live retrieval. Keep fixture replay out of the default production path; do not silently fall back to fixture evidence on API failure. Distinguish biological evidence origin from whether Gemini was actually called. Preserve existing frontend mock labeling while adding an accurate replay label.

## 9. Integration tests and validation commands

Role 3's handoff records **220 passed, 14 skipped** for its focused validation; those are prior results, not newly executed checks for this document or full application integration. Live tests are opt-in. Run existing backend regressions and the Role 3 suites in the clean integration environment.

From `Backend/` (keep Gemini mocked/disabled for deterministic tests):

```sh
/tmp/asra-role1-clean-venv/bin/python -m pytest tests/test_assess.py tests/test_interpreter.py -q
/tmp/asra-role1-clean-venv/bin/python -m pytest tests/test_resolver.py tests/test_sequence.py tests/test_sequence_functional.py tests/test_sequence_adapter.py tests/test_sequence_species.py tests/test_sequence_validation.py -q
/tmp/asra-role1-clean-venv/bin/python -m pytest -q
/tmp/asra-role1-clean-venv/bin/python -m tools.sequence_demo
/tmp/asra-role1-clean-venv/bin/python -m tools.sequence_validation --output /tmp/asra-role1-validation.json
/tmp/asra-role1-clean-venv/bin/python -m tools.sequence_species_audit --replay --output tests/fixtures/role3/species_compatibility
```

The demo and audit above are **offline replay**. The replay audit reads the existing tape; do not overwrite fixtures. `Backend/tests/fixtures/role3/` contains the Q99808/Q9JIM1 snapshots and manifest, `species_compatibility/http.json` and `report.json`, `milestone4.json`, and captured `milestone4_live.json`. The last filename records a prior live capture; reading it today is replay validation. Write new live captures to a separate temporary directory.

Optional live Ensembl checks from `Backend/`:

```sh
ASRA_LIVE_ENSEMBL=1 /tmp/asra-role1-clean-venv/bin/python -m pytest tests/test_resolver.py::test_live_slc29a1_mouse tests/test_sequence.py::test_live_slc29a1_mouse -q
ASRA_LIVE_SPECIES=1 /tmp/asra-role1-clean-venv/bin/python -m pytest tests/test_sequence_species.py::test_live_frontend_pair -q
/tmp/asra-role1-clean-venv/bin/python -m tools.sequence_species_audit --live --output /tmp/asra-role1-live-audit
```

Live species tests may skip on service failures; a skip is not a passed live validation. Scientific tool audits do not exercise `/assess` or Gemini. Add application-level tests for the new wiring; existing API tests cover sequence-only behavior and must remain valid unless a documented contract change requires an update.

Required integration assertions:

1. **SLC29A1/mus_musculus through `POST /assess`:** submit a verified symbol (or verified GN/header route) and a valid actual sequence under the final request contract. Assert 456/460 lengths, 366/461 matches/columns, full-precision identity within numerical tolerance, coverage, accessions, PERN/PARS, mapped coordinates, provenance, sources and limitations in the returned sequence layer. Trace the same evidence into agent input, report and exports. Never assert an invented current JSON request field before implementing the contract extension.
2. **CD28/macaca_mulatta through `POST /assess`:** assert the recorded 220/220, 216 matches, four substitutions, sparse/unreviewed rhesus annotation caveats and citation continuity. Keep this distinct from SLC29A1 rhesus unavailability.
3. **Gene resolution failures:** missing symbol, arbitrary sequence, `sp|Q99808|S29A1_HUMAN` without a verified GN route, conflicting explicit/header identity, wrong organism and malformed input. No `SP` gene, guessed gene or successful fabricated comparison; preserve legacy fallback and ordinary request validation.
4. **Scientific/API failures:** absent orthologue, multiple candidates/non-one-to-one relationship, missing protein, tied alignment, unsupported isoform, missing/unverified/empty UniProt annotations, timeout/HTTP/malformed response. Preserve available measurements and raw ambiguity candidates where applicable; return an assessment with independent layer outcomes rather than an uncaught error.
5. **Serialization:** compare rich result to adapter, shared-contract JSON roundtrip, HTTP response and exported JSON. Decode observation values to check numeric types/precision, null gaps, string map keys, source IDs, nested evidence, statuses and limitations. Test adapter rejection rather than silent loss on schema drift.
6. **Agent interpretation and citations:** use a deterministic mocked Gemini response to verify the actual scientific prompt, valid citations, rejection of unsupported fields/sources, `flagged` concern for incomplete evidence and no function/toxicity inference from similarity alone. Keep measured motif differences distinct from reported experimental mechanisms. Separately report any real Gemini run and its model; mocked interpretation tests do not establish live review.
7. **Provenance:** replayed biological evidence never produces a Live badge/export label; fixture capture time remains distinct from report generation. Test missing credentials/model failure and explicit API failure without hidden fixture fallback.
8. **Frontend:** exercise all nine species IDs with supported or explicit unavailable/ambiguous outcomes, human-readable scientific evidence, graceful JSON-decoding failure, source links, limitations, legacy plain-string layers and report downloads.

From `Frontend/` in the integration worktree:

```sh
npm ci
npm run lint
npm run build
```

Inspect `Frontend/AGENTS.md` before frontend work. Run the latest master's additional required checks where feasible, then from the integration repository root run `git diff --check` and review the complete diff. Record any unrun check with its reason; do not conceal dependency, build, credential or network blockers.

## 10. Success criteria

A researcher can submit a verified human gene and animal species, obtain real sequence measurements and functional evidence, see scientific limitations and sources, and receive an agent-reviewed report without losing information or fabricating biological findings. Partial/unavailable outcomes remain explicit, scientific evidence survives every boundary, and live, replayed and mocked validation are distinguishable. A missing Gemini key does not meet the live agent-reviewed success criterion even when offline evidence tests pass.

## 11. Ownership and coordination

| Role | Ownership |
|---|---|
| Role 1 | Backend orchestration, API routes, shared application wiring and frontend integration. |
| Role 2 | Gemini reasoning, citation validation and agent evaluation. |
| Role 3 | Scientific sequence engine, orthologue/alignment/functional evidence and scientific validation. |
| Role 4 | Localisation, cell-type and tissue modules and their adapters. |

Avoid modifying other roles' scientific implementations without coordinating. Prefer application-boundary wrappers and existing public adapters. Preserve latest master cellular modules even though this inspected branch has placeholders. Coordinate any change to scientific selection, coordinate transfer, annotation meaning or conservative status rules with the owner; a merge conflict is not permission to replace their implementation.

## 12. Required implementation report

Integration Codex must finish with:

- Files changed, their purpose, and any contract additions/discrepancies resolved.
- Exact latest master base SHA, selected Role 3 source SHA, source commits actually integrated, merge/cherry-pick mapping if applicable, and resulting integration HEAD/worktree state. Distinguish incorporated commits from uncommitted integration edits; do not claim a merge was committed if it was not.
- Commands/checks run and actual passed/failed/skipped counts, frontend lint/build result, clean-install/import result and `git diff --check` result.
- Separate validation results for offline replay, synthetic/mocked tests, newly fetched biological evidence and real versus mocked Gemini review. Include capture dates/source provenance and model where applicable.
- Outstanding scientific limitations: isoform/transcript suitability, incomplete annotation, tied mappings, unknown source releases, organism/strain scope and the limits on functional/toxicity inference.
- Unresolved blockers with owner/next action, including unavailable APIs, missing credentials, failing checks or unagreed contract changes. State explicitly whether the full researcher workflow and live agent review were demonstrated.

Do not claim implementation or new live validation solely because this handoff and the prior Role 3 artifacts exist.
