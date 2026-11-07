# Test cases — ASRA

Committed before any results were generated.

> **Read this first.** ASRA is tested on whether it surfaces a documented interspecies
> difference that sequence identity alone would miss — **not** on whether it "would have
> predicted" a clinical failure. In the historical cases the accepted mechanistic
> explanation was published years after the failure. Keep that wording everywhere:
> report, dashboard, pitch.

---

## Case 1: fialuridine

| Field | Value |
|---|---|
| Drug | Fialuridine (FIAU) |
| Gene | SLC29A1 (ENT1) |
| Human reference | human |
| Comparison species | mouse (*Mus musculus*) |
| Expected layer | localisation |
| Why this case | Tests **subcellular localisation**: the two proteins are orthologues, so sequence identity alone cannot distinguish them on this axis. |

**What the system should find**

Human ENT1 is present and functional in the mitochondrial membrane, whereas the mouse
transporter is not; mitochondrial ENT1 carries fialuridine into the mitochondrion, where
its triphosphate metabolite inhibits mitochondrial DNA polymerase γ, depletes mtDNA and
causes multisystem mitochondrial toxicity.

**Outcomes**

- **Pass** — names the human mitochondrial localisation of ENT1 as the difference AND attaches a `source_record` (UniProt annotation and/or the literature evidence for the mitochondrial targeting signal)
- **Partial** — flags localisation as the relevant layer but without evidence, OR returns `status: incomplete` for localisation while saying what is missing
- **Fail** — no mention of mitochondrial localisation, OR asserts a different mechanism as the explanation, OR treats the absence of a mouse annotation as proven biological absence

**Sceptic check**

Must flag that **a missing mouse annotation is not evidence of absence**. If the
localisation layer infers "mouse ENT1 is not mitochondrial" purely from an empty UniProt
field, the Sceptic should downgrade that to "not annotated" and point to the literature
evidence as the real support.

**Evidence behind the expected finding**

| Claim | Source | Year | Strength | Known before the failure (1993)? |
|---|---|---|---|---|
| 15 patients with chronic hepatitis B received fialuridine at 0.10 or 0.25 mg/kg/day; the trial was stopped in week 13 after one patient developed lactic acidosis and liver failure. 7 of 15 developed severe hepatotoxicity; 5 died and 2 survived only after liver transplant. Toxicity was multisystem: hepatic failure, lactic acidosis, pancreatitis, neuropathy, myopathy | McKenzie R, Fried MW, Sallie R, et al. *N Engl J Med* 1995;333(17):1099–105. PMID 7565947 · DOI 10.1056/NEJM199510263331702 | 1995 | Strong (clinical, primary report) | — (is the failure) |
| Toxicity is attributed to FIAU triphosphate inhibiting mitochondrial DNA polymerase γ, depleting mtDNA | Review literature, widely accepted | — | Strong | No |
| hENT1 is expressed and functional in the human mitochondrial membrane, and this expression enhances the mitochondrial toxicity of fialuridine | Lai Y, Tse CM, Unadkat JD. *J Biol Chem* 2004;279(6):4490–7. DOI 10.1074/jbc.M307938200 · PMID 14607828 | 2004 | Strong (experimental) | **No — 11 years after** |
| The mitochondrial targeting signal of hENT1 is identified, explicitly framed as explaining interspecies differences in FIAU mitochondrial toxicity; ENT1 is mitochondrial in humans but not in mice | Lee EW, Lai Y, Zhang H, Unadkat JD, "Identification of the mitochondrial targeting signal of the human equilibrative nucleoside transporter 1 (hENT1)", *J Biol Chem* 2006 (volume and pages *to confirm*). DOI 10.1074/jbc.M513825200 | 2006 | Strong (experimental) | **No — 13 years after** |
| Silencing ENT1 only modestly protected primary human hepatocyte spheroids from fialuridine toxicity; silencing TK2 gave substantial protection; silencing both gave near-complete protection. ENT1 is contributory, not sufficient. | Hendriks DFG, Hurrell T, Riede J, van der Horst M, Tuovinen S, Ingelman-Sundberg M. *Toxicol Sci* 2019;171(2):385–95. DOI 10.1093/toxsci/kfz195 · PMID 31505000 | 2019 | Moderate | No |
| Fialuridine is described as an excellent ENT1 substrate; its mitochondrial toxicity is "not predictable in certain species like rodents" | Review: "Addressing the clinical importance of equilibrative nucleoside transporters (ENTs) in drug discovery and development", PMC11347013 | 2022 | Review | No |

Sources to open: pubmed.ncbi.nlm.nih.gov/7565947 · pmc.ncbi.nlm.nih.gov/articles/PMC11347013
(the review cites Lai 2004 and Lee 2006 as refs 46–47 — pull both DOIs from there)

**Notes / caveats**

- Still open: the source for the mtDNA polymerase γ row (currently "review literature").
  Do not pitch a number without opening the source.
- Decide and document whether the transporter is presented as contributory or sufficient.

---

## Case 2: TGN1412

| Field | Value |
|---|---|
| Drug | TGN1412 (anti-CD28 superagonist; later TAB08) |
| Gene | CD28 |
| Human reference | human |
| Comparison species | macaque — cynomolgus dosed preclinically; CD28− effector-memory phenotype confirmed in both cynomolgus and rhesus (Eastwood 2010) |
| Expected layer | cell-type expression |
| Why this case | Tests **cell-type expression**: the protein is present in both species, so neither sequence identity nor bulk tissue expression would resolve a population-level difference. |

**What the system should find**

Human CD4+ effector memory T-cells (CCR7−) express high levels of CD28, whereas the
corresponding macaque CD4+ effector memory population is CD28−. That population is the
predominant source of the pro-inflammatory cytokines released in humans, so the macaque
could not reproduce the response.

**Outcomes**

- **Pass** — identifies the CD4+ effector memory population as the site of the difference AND attaches a `source_record` with dataset ID, cell counts and assay
- **Partial** — returns `status: incomplete` or `unavailable` for cell-type expression **and says the human and macaque cell-type labels are not reliably equivalent** (this is an honest pass-adjacent outcome; score it partial, not fail)
- **Fail** — reports the two CD28 proteins as equivalent with no caveat, OR asserts a cell-type difference without comparable data behind it

**Sceptic check**

Must flag that human and macaque cell-population labels are **not guaranteed equivalent**,
and that raw counts across experiments are not comparable without normalisation. If the
cell-type layer produces a fold difference from mismatched datasets, the Sceptic should
reject it.

**Evidence behind the expected finding**

| Claim | Source | Year | Strength | Known before the failure (2006)? |
|---|---|---|---|---|
| Six healthy male volunteers received a single IV dose of 0.1 mg/kg TGN1412; all six developed a systemic inflammatory response within ~90 minutes and multi-organ failure; two required mechanical ventilation, all received renal replacement therapy; **all six survived** | Suntharalingam G, Perry MR, Ward S, et al. *N Engl J Med* 2006;355(10):1018–28. PMID 16908486 · DOI 10.1056/NEJMoa063842 | 2006 | Strong (clinical, primary report) | — (is the failure) |
| The 0.1 mg/kg starting dose was 1/500th of the NOAEL of 50 mg/kg established in cynomolgus macaques | Suntharalingam et al. 2006, as cited in later literature | 2006 | Strong | — |
| Human CD4+ effector memory T-cells are CCR7−**CD28+**; cynomolgus **and** rhesus CD4+ effector memory T-cells are CCR7−**CD28−**, so they cannot be stimulated by a CD28 superagonist | Eastwood D, Findlay L, Poole S, Bird C, Wadhwa M, Moore M, Burns C, Thorpe R, Stebbings R. *Br J Pharmacol* 2010;161(3):512–26 | 2010 | Strong (experimental, both macaque species) | **No — 4 years after** |
| CD4+ effector memory T-cells are the predominant source of TGN1412-driven cytokines | Eastwood et al. 2010 | 2010 | Strong | No |
| Both human and macaque CD8+ effector memory T-cells lack CD28, which explains the CD4 bias of the human response | Pitcher et al. 2002; Moniuszko et al. 2004; Sallusto et al. 2004 | 2002–04 | Strong | Partly — published, but not connected to CD28-superagonist risk at the time |
| Competing/complementary factor: TGN1412 in aqueous phase did **not** trigger cytokine release from human PBMCs; high-density preculture was needed to reveal it | Stebbings et al.; Eastwood et al. *Br J Clin Pharmacol* 2013 | 2007–13 | Strong | No |

Sources to open: pubmed.ncbi.nlm.nih.gov/16908486 · the Eastwood 2010 paper in Br J Pharmacol
(open-access commentary: Pallardy & Hünig, "Primate testing of TGN1412: right target, wrong cell",
*Br J Pharmacol* 2010, DOI 10.1111/j.1476-5381.2010.00925.x)

**Notes / caveats**

- **Species label:** preclinical testing used **cynomolgus** macaques, with a NOAEL of
  50 mg/kg; the human starting dose of 0.1 mg/kg was 1/500th of that. Eastwood 2010 found
  the CD28− effector memory phenotype in **both** cynomolgus and rhesus, so running the
  benchmark against rhesus is defensible — but say "macaque" in the pitch and name
  cynomolgus as the species actually dosed.
- CELLxGENE is the stretch layer. If it does not land, this case resolves as **partial**
  by design — an honest outcome, not a broken benchmark. Decide with the team now whether
  to promote the layer.
- Record any competing or complementary factors (e.g. assay conditions) so the write-up
  says "most plausible accepted explanation", not "the cause".

---

## Case 3: conserved control (GAPDH)

| Field | Value |
|---|---|
| Drug | — (no drug; control) |
| Gene | GAPDH |
| Human reference | human |
| Comparison species | mouse |
| Expected layer | all |
| Why this case | Tests **specificity**: a conserved, heavily annotated housekeeping gene where no translational concern should be raised. Guards against a system that manufactures alarm from any input. |

**What the system should find**

Nothing of translational concern.

**Outcomes**

- **Pass** — raises no translational risk; any minor difference reported is explicitly described as not functionally relevant, or is downgraded by the Sceptic
- **Partial** — reports a minor difference neutrally but without saying whether it matters, leaving the reader to infer risk
- **Fail** — presents any finding as a translational risk, or recommends follow-up experiments as if a concern exists

**Sceptic check**

Should actively downgrade any flagged difference here. If the Sceptic stays silent while
the Interpreter raises a concern, that is a Sceptic failure and must be recorded as such
in the evaluation table.

**Evidence behind the expected finding**

| Claim | Source | Year | Strength | Known before the failure? |
|---|---|---|---|---|
| GAPDH is highly conserved between human and mouse and ubiquitously expressed | Ensembl orthologue record + UniProt entry — **record the accessions and the release version you used** | — | Strong | n/a |

**Notes / caveats**

- Pin and display the isoform accessions. Isoform choice changes the identity figure, and
  on a control case an unexplained identity drop looks like a bug.
- Consider ACTB as a second control if time allows.

---

## Case 4: missing data

| Field | Value |
|---|---|
| Drug | — |
| Gene | CYP3A4 |
| Human reference | human |
| Comparison species | mouse |
| Expected layer | sequence |
| Why this case | Tests **honesty under absence**: the system must refuse to guess. Human CYP3A4 has no one-to-one mouse orthologue — the mouse Cyp3a locus contains at least six genes (Cyp3a11, 3a13, 3a16, 3a25, 3a41, 3a44). The sequence layer therefore cannot return a meaningful identity figure without arbitrarily picking one paralogue. It is also the canonical example of species differences in drug metabolism, so a pharmacologist judge recognises it instantly. |

**What the system should find**

That the orthology is one-to-many and no single identity figure is defensible.

**Outcomes**

- **Pass** — flags the ambiguous orthology, returns `status: incomplete` or `unavailable` rather than a number, renders it as a **visible** panel rather than a blank, keeps the other layers running, and recommends what would be needed (a justified functional orthologue, or enzyme activity data)
- **Partial** — flags the ambiguity but recommends nothing, OR lets the failure stop the other layers
- **Fail** — returns a single identity figure by silently picking one paralogue, OR presents the comparison as if it were one-to-one

**Sceptic check**

Must state that any downstream conclusion rests on an arbitrary orthologue choice, and
must not rank it highly.

**Evidence behind the expected finding**

| Claim | Source | Year | Strength | Known before the failure? |
|---|---|---|---|---|
| n/a — this case tests system behaviour, not a biological claim | — | — | — | — |

**Notes / caveats**

- Verify the one-to-many relationship in the Ensembl release actually used, and record
  that release version.
- Also worth running: a nonexistent gene name and a misspelled one. Those belong in the
  adversarial tests, not here.

---

## Scoring sheet (fill after runs — leave blank until then)

| Case | Sequence-only caught it? | Did extra layers add evidence? | Did the Sceptic catch the unsupported claim? | Verdict |
|---|---|---|---|---|
| Fialuridine / SLC29A1 | | | | |
| TGN1412 / CD28 | | | | |
| GAPDH control | | | | |
| Missing data | | | | |

**Check on every case:** `data_version` is nullable and nothing enforces it, so a layer
returning `status: ok` with `data_version: null` would pass silently. **Check this
manually when scoring.**

**Headline for the write-up:** in ___ of 4 cases the additional layers surfaced evidence
that sequence identity alone did not capture.
