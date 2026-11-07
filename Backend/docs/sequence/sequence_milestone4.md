# Role 3 — Milestone 4 validation and integration handoff

Validated 7 November 2026. Scope: Role 3 sequence tools, fixtures and tests only.
No routes, frontend, agents, shared contracts or teammate files changed. No commit
or push. Earlier reports and captured responses remain intact.

## Scientific findings

**SLC29A1 human/mouse:** fresh UniProt Q99808/Q9JIM1 sequences agree with the
pinned benchmark and Ensembl proteins. The displayed proteins are Q99808-1
(456 aa, ENSP00000360820) and Q9JIM1-1 (460 aa, ENSMUSP00000063096).
Coordinates are 1-based, inclusive, in the complete precursor/displayed sequence.
Human PERN71–74 maps to mouse PARS71–74: E72→A and N74→S, with P71/R73
identical. There is one optimal alignment under the documented scoring. Human
C414 maps to mouse C418 and remains C. Identity is 366/461 = 79.39262472885032%;
89 resolved substitutions include 42 selected-annotation overlaps and 47 without
selected overlap. These categories measure overlap, not functional effects.

[Lee et al., 2006, PMID 16595656](https://pubmed.ncbi.nlm.nih.gov/16595656/),
DOI 10.1074/jbc.M513825200, identifies P71/E72/N74 as important for mitochondrial
targeting in tagged ENT1 constructs imaged in MDCK cells. Its human/rodent pattern
notation PEXN/PAXS agrees with the concrete PERN/PARS windows; X is a wildcard.
Human-to-rodent motif replacement abolished mitochondrial localisation in the
assayed construct; the reverse mouse replacement gave partial localisation.
This supports the curated motif anchor, not localisation or toxicity predictions
for arbitrary animals. The publication postdates the 1993 clinical event.
The abstract was independently checked against PubMed; publisher full text
access returned HTTP 403 in this run. No new figure-level verification is claimed.

Sources: [human Q99808](https://rest.uniprot.org/uniprotkb/Q99808.json),
[mouse Q9JIM1](https://rest.uniprot.org/uniprotkb/Q9JIM1.json).
Fresh raw responses, headers, timestamps and SHA-256 hashes are preserved in
`Backend/tests/fixtures/role3/milestone4_live.json`, alongside independent searches.
All fresh responses report UniProt release 2026_04. This does not version Ensembl.

**CD28 human/rhesus:** fresh P10747/A0A5F7ZKV3 agree with the pinned sequences.
Human ENSP00000324890 / P10747-1 and rhesus ENSMMUP00000065245 / A0A5F7ZKV3
are each 220 aa. The unique optimum has 216 matches, four substitutions,
98.18181818181819% identity and 100% coverage of both proteins, with no gaps.
The differences are F11L, V155A, I175C and V179M in full-sequence coordinates.
Human has seven documented isoforms; only the displayed isoform was analysed.
Rhesus has no alternative-products comment in this entry.

Human has 14 selected features (one transmembrane, one domain, one region,
three modified residues, five glycosylations, three mutagenesis records).
Rhesus has three (transmembrane/domain/region only). Human is reviewed with
protein-level evidence; rhesus is **unreviewed, predicted**. Exact xref and full
sequence verification establish the coordinate-bearing record, not annotation
parity or independent experimental verification. No claim about T-cell population
expression, TGN1412 binding/response or safety follows from these results.
Sources: [P10747](https://rest.uniprot.org/uniprotkb/P10747.json),
[A0A5F7ZKV3](https://rest.uniprot.org/uniprotkb/A0A5F7ZKV3.json).

## Long animal proteins: independent review

The selected proteins match the exact UniProt displayed sequences and corresponding
Ensembl gene/protein xrefs. No demonstrated accession mismatch or unsupported
canonical-to-isoform coordinate transfer was found. However, a unique gene-level
orthology relationship does not choose the biologically representative transcript.

| SLC29A1 selection | Selected aa / accession | Selected alignment excess relative to human | Independent selection concern |
|---|---|---|---|
| Rat | 504 / A0ACJ1MV19 | 47 N-terminal + 1 internal residue | Reviewed O54698 is 457 aa at the same gene ENSRNOG00000019752, with protein ENSRNOP00000026831.7; other entries also exist. |
| Cynomolgus | 590 / A0A7N9D7I6 | 134 N-terminal residues | Unreviewed, homology evidence; no gene name or alternative-products comment. Fresh accession confirms 590 aa; gene/protein-name searches returned zero and do not inventory alternatives. |
| Dog | 522 / A0A8I3NI33 | 66 N-terminal residues | Unreviewed, homology evidence. A0A8I3NK92 is 456 aa at the same gene ENSCAFG00845011282, protein ENSCAFP00845015667.1. |
| Pig | 548 / A0A287B8K5 | 84 N-terminal + 7 + 1 internal residues | Unreviewed, protein-level evidence. A0A287B2T6 is 457 aa at the same gene ENSSSCG00000001700, protein ENSSSCP00000050560.2. |

These are gap runs in the selected alignment, not proven evolutionary insertions.
No sequence-caution or alternative-products comments were present in the four
selected entries. Lack of those comments does not validate extensions. Protein-level
existence evidence does not prove every residue of a selected translation.
The alternative entries are candidates for review, not substitutes selected by this
milestone. Resolve transcript/assembly/model suitability before attributing the
extensions or lower coverage to biology. The cynomolgus extension remains particularly
unresolved. No independent genomic/transcriptomic or experimental confirmation was
performed, and current Ensembl canonical-transcript selection was not revalidated.

## Tied optima

`sequence_validation.audit_tracebacks` independently enumerated **all** optimal
tracebacks for the ten successful recorded pairs. No cap was reached. All reported
identity, match/substitution counts and coverage values are invariant in these
specific pairs. That is an observed result, not a property of equal-score alignments.

| SLC29A1 | Optima | Human coordinates whose animal mapping varies |
|---|---:|---|
| Rat | 2 | 1 |
| Cynomolgus | 2 | 1 |
| Dog | 2 | 1 |
| Pig | 8 | 1, 71, 321 |

All other successful pairs have one optimum. Rat/cynomolgus/dog motif mappings
are invariant despite the conservative runtime `alignment_ambiguous` flag.
Pig P71 maps to position 155 or 162; E72/R73/N74 map invariantly to 163/164/165.
Thus pig motif contiguity and its four-residue window depend on traceback.
P71 is opposite A155 or T162: both the substituted residue and its animal
coordinate depend on traceback. Human position 321 maps to 412 or 413; features
covering varying coordinates must retain the same caveat. Gap placement and
per-residue overlap records describe the selected traceback. Full mapping options
and metric ranges are in `Backend/tests/fixtures/role3/milestone4.json`.
The runtime keeps conservative flags; it does not run exhaustive enumeration.
The default gene call now also returns `incomplete` for tied optima.

## Nine frontend species and failure semantics

Offline replay exercises the real resolver, sequence, functional and adapter APIs
against all recorded responses, not just summary JSON. SLC29A1 outcomes:

| State | Frontend identifiers |
|---|---|
| ok | mus_musculus, cavia_porcellus, oryctolagus_cuniculus |
| incomplete (tie) | rattus_norvegicus, macaca_fascicularis, canis_lupus_familiaris, sus_scrofa |
| orthologue_unavailable | macaca_mulatta |
| ambiguous_orthologue | danio_rerio (two raw candidates retained; neither chosen) |

Rhesus's empty homology response is not evidence of biological absence. Zebrafish
requires justified paralogue selection. `ok` means the requested computation
returned data, not complete functional annotation. Non-mouse SLC29A1 animal
annotations are transmembrane/region-only. Missing annotations do not establish
missing motifs, localisation, binding or activity. Dog/minipig IDs remain species-level;
no breed/strain specificity is established. This matrix is for SLC29A1, not every gene;
CD28 has real evidence for rhesus, cynomolgus and mouse only. Synthetic tests check
interface compatibility for all nine species. The sequence-only request path always
returns incomplete submitted-sequence evidence and does not identify a gene.

## Integration and validation

See [the callable integration handoff](../../tools/sequence_integration_handoff.md) for exact
arguments, schemas, dependencies, failure handling and reproduction commands.

Focused Role 3 validation: **220 passed, 14 skipped** (optional live tests).
`git diff --check` and new-file whitespace checks passed. The original pinned
tape was preserved. No full application/API suite was needed for these scoped
sequence changes; application integration itself remains outside Role 3 ownership.
