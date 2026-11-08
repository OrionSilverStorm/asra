# ASRA — Evaluation results

**All runs were made against commit `3bbf30e`, before the role4 fixes landed.**

All runs live against `/assess` (`Backend/pipeline/`), 2026-11-08. Raw responses in
`tests/frozen/`. Scored against criteria committed in `tests/test_cases.md` before any
result existed (commit 36d537d).

---

## Scoring table

| Case | Sequence-only caught it? | Did extra layers add evidence? | Did the Sceptic catch the unsupported claim? | Verdict |
|---|---|---|---|---|
| **SLC29A1 / mouse** | No | **Yes** — localisation returned Q99808 (entry v215) with experimental evidence for the human compartments | Yes — downgraded 2 of 3 findings | **Pass** |
| **CYP3A4 / mouse** | No — refused, correctly | **Yes** — named the one-to-many orthology and propagated it as an explicit limitation to all three other layers | Yes — downgraded the single finding, noting it doesn't assess the individual Cyp3a paralogues | **Pass** |
| **GAPDH / mouse** | No (layer failed) | Yes, but see below | Yes — flagged that missing mouse annotation isn't biological absence | **Partial** |
| **CD28 / macaque** | No | Yes — 15 observations, 7 source records, but from a **recorded** Census run, not live | Yes — noted the finding rests on curated literature, not primary single-cell concordance | **Partial** |

**Headline: in 4 of 4 cases the additional layers surfaced evidence that sequence
identity alone did not capture.** In three of those four the sequence layer failed
outright and the other layers still produced citable evidence — the layered design
degraded gracefully rather than collapsing.

---

## Why each verdict

### SLC29A1 — Pass
Run 2 retrieved UniProt Q99808 with experimental evidence for the human compartments
and produced 9 observations across 4 source records. The layer's limitations include,
unprompted:

> *The ENT1/fialuridine mitochondrial mechanism is not established by this annotation
> comparison. Additional literature is needed.*

The system declined to claim the mechanism it was being pointed at. That is the
Sceptic check from the contract, satisfied.

### CYP3A4 — Pass
The strongest result. The system identified that CYP3A4 has no unique one-to-one mouse
orthologue (9 relationships), refused to select one, stated that a justified biological
choice is required, propagated the unresolved orthology as an explicit limitation to
localisation, cell expression and tissue expression, and recommended a follow-up. No
identity figure was produced. Every pass criterion met.

### GAPDH — Partial
The conserved control produced a finding: human GAPDH annotated at membrane and
perinuclear region, mouse not annotated there. The Sceptic correctly downgraded it,
which satisfies one pass route. **But** the system also recommended subcellular
fractionation and a western blot — i.e. it recommended laboratory work on a housekeeping
gene on the strength of a missing annotation. The contract's fail criterion names
exactly that ("recommends follow-up experiments as if a concern exists").

Scored Partial rather than Fail because the Sceptic did its job and the limitation text
is honest; scored Partial rather than Pass because the output would still send a
researcher to the bench. **This is the most useful finding in the evaluation** and
belongs in the write-up: the Sceptic catches the claim but not the recommendation
downstream of it.

### CD28 — Partial
Partial by design, as the contract anticipated, but for a different reason than
expected. The cell-expression layer did not query Census live — it replayed a recorded
run, because `cellxgene_census` has no Windows wheels. The layer declares this in its
`data_version` as `(recorded run)`, which is honest labelling, but it is not evidence
obtained at query time.

The layer is otherwise the most explicit in the system: 0 blood/lymphoid datasets for
macaque, 0 cells annotated CD4+ effector-memory, and separate accounting for
*unmeasured* vs *undetected* vs *biologically absent*. The finding cites
`pub:eastwood2010` and the Sceptic correctly notes it rests on curated literature rather
than primary single-cell concordance.

Also unresolved: localisation reported multiple matching UniProt accessions
(A0A5F7ZKV3, Q0PDN4) for macaque without disambiguating.

---

## Issues found

| # | Issue | Severity | Evidence |
|---|---|---|---|
| 1 | **Network fragility.** Four runs, four different external failures: UniProt timeout, Ensembl timeout, Ensembl HTTP 500, plus one legitimate ambiguous-orthology stop. A different layer dropped each time. | **High — affects the live demo** | Runs 1–4 |
| 2 | **`sequence` returns `status: ok` with `data_version: null`**, reproducibly. The resolver doesn't supply the Ensembl release. Limitation text explains it honestly. | Medium | All runs |
| 3 | **CD28 cell layer is a recorded replay — a documented design decision, not a platform limitation.** Since the role4 fixes, a recorded benchmark is the preferred path whenever one exists, even with `cellxgene_census` installed; a live scan requires explicit `ASRA_LIVE_CENSUS=1`. Rationale is latency: the live TileDB-SOMA scan of CD28/`macaca_mulatta` took 408s against the frontend's 150s timeout, versus <1 ms for the replay. Labelled in `data_version` as `(recorded run)` and in the layer's limitations. Still not evidence obtained at query time. | Medium | `02_cd28.json`, `02_cd28_rerun.json`, `docs/role4_overnight_validation.md` |
| 4 | **GAPDH recommends bench work on a conserved gene** off a missing annotation. The Sceptic flags the claim; the recommendation survives. | Medium | `03_gapdh.json` |
| 5 | ~~**Unresolved UniProt accession ambiguity** for macaque CD28 (A0A5F7ZKV3, Q0PDN4).~~ **Closed.** Now resolved to `A0A5F7ZKV3` via a verified Ensembl one-to-one orthologue (`ENSMMUG00000057214` / `ENSMMUP00000065245`), stated in the layer's limitations, with the caveat that only an unreviewed UniProt record could be resolved. The human record `P10747` is also retrieved now, so compartments are actually compared. | ~~Low~~ Closed | `02_cd28_rerun.json` |
| 6 | **`functional_analysis` is a single 171 KB observation** in the SLC29A1 report. | Low — rendering | `01_slc29a1.json` |
| 7 | **`/assess/agent-pipeline` accepts evidence in the request body.** Anyone passing it `MOCK_EVIDENCE` gets a flawless report that proves nothing. Never demo this endpoint. | **High — reputational** | `api/routes.py` |

### Re-run on `51070ce`

CD28 / `macaca_mulatta` was re-run against the current HEAD after the role4 fixes
(`tests/frozen/02_cd28_rerun.json`). **The verdict is unchanged: Partial.** Same layer
statuses, same single finding, same Sceptic downgrade to `flagged`, same one recommended
experiment. Issue 5 closed; issue 3 reclassified above. Localisation gained five
observations and the human record. The scoring table above stands as run against
`3bbf30e`.

No misleading safety claims were produced. No wrong orthologue was silently selected.
No recorded data was presented as live without a label.

---

## Demo recommendation

**Do not do a cold live run on stage.** Every run so far has lost at least one layer to
an external failure, and it's a different layer each time.

Run live, with a frozen report loaded and ready. If a layer drops, say out loud that
you're loading a cached run — which is what the design doc already specifies.

Frozen reports available in `tests/frozen/`:
`01_slc29a1.json`, `01_slc29a1_run02.json`, `02_cd28.json`, `03_gapdh.json`, `04_cyp3a4.json`

**The strongest case to demo is CYP3A4.** It passes cleanly, it is the hardest result to
fake, and a system refusing to produce a number is more memorable to a judge than one
producing a good number.
