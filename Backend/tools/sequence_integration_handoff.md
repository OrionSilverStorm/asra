# Role 3 — Milestone 4 integration handoff

Validated 7 November 2026. Scientific findings and unresolved transcript-selection
issues: [Milestone 4 report](sequence_milestone4.md).


Run with `Backend/` on `PYTHONPATH`, or use it as the working directory.
Dependencies: Python 3.12 used here, Biopython 1.88 (pinned in requirements), httpx,
Pydantic v2/shared `contract`; pytest only for validation. Gene calls require Ensembl
REST; functional mode additionally requires UniProt REST. Runtime requests have
30 s timeouts and no retry/cache policy; the audit recorder's retry/cache is audit-only.

```python
from tools.resolver import resolve_orthologue
from tools.sequence import align_proteins, run_sequence
from tools.sequence_functional import add_functional_analysis
from tools.sequence_adapter import to_layer_result

resolved = resolve_orthologue("CD28", "macaca_mulatta")
plain = run_sequence("CD28", "macaca_mulatta")
rich = run_sequence("CD28", "macaca_mulatta", functional=True)
# Equivalent enrichment of an existing plain result, without mutation:
enriched = add_functional_analysis(plain)
layer = to_layer_result(rich)
wire = layer.model_dump(mode="json", by_alias=True)
```

- `resolve_orthologue(gene: str, species: str) -> dict`: source/target records contain
  `gene_id, protein_id, species, sequence, metadata`; result adds `gene, species,
  orthology, source_url`. No automatic selection of multiple/non-one-to-one results.
- `align_proteins(human: str, animal: str) -> dict`: unchanged uppercase nonempty
  proteins, standard residues plus B/Z/X. Global BLOSUM62, gap open -10, extension
  -0.5, terminal gaps treated equally, epsilon 1e-6. Returns alignment/parameters,
  measurements/definitions, reciprocal maps, substitutions, ambiguous_pairs, indels,
  limitations. Unsupported symbols raise ValueError. No minimum length here.
- `run_sequence(gene: str, species: str, *, functional: bool=False) -> dict`:
  adds gene/species/layer/status, human/animal, orthology, sources, retrieved_at,
  provenance, data_version. Default adds no annotation requests. `functional=True`
  adds `functional_analysis`; UniProt failures retain sequence data as incomplete.
- `run_sequence(gene: ResolvedQuery) -> LayerResult`: legacy submitted-sequence
  evidence only, with no network access, even when the query has a gene field.
- `add_functional_analysis(result: dict, *, retrieve=None) -> dict`: enrich a plain
  result once; optional injected retrieval `(protein)->(entry, provenance)` is
  reverified. `functional_analysis` contains status, proteins (identity/features/
  status/reason_code), mapped_human_features, functional_substitutions,
  other_substitutions, unclassified_substitutions, slc29a1_motif and limitations.
  Do not re-enrich an already enriched result (source IDs would be duplicated).
- `to_layer_result(result: dict) -> LayerResult`: requires the rich schema;
  rejects missing/unhandled top-level fields, source extensions and duplicate IDs.
  Shared fields: `gene, species, layer, status, observations, source_records,
  limitations, data_version`. Observations are `field, value, sourceRecordId`.
  All evidence structures, including numbers, nested provenance and limitations,
  survive JSON encoding/decoding; numeric values are not rounded. Decode `value`
  with `json.loads`; coordinate-map keys become strings. SourceRecord missing URL
  is normalised to null. Annotation identities now retain entry_type and
  protein_existence alongside release, audit versions, xrefs, isoform and hashes.

```python
import json
observations = {o.field: json.loads(o.value) for o in layer.observations}
identity = observations["measurements"]["identity_percent"]  # float
```

Role 1 must supply a scientifically resolved human gene and call the adapter
explicitly; submitted sequences must not silently become reference proteins.
The present routes/registry still use the sequence-only path. No gene-based path
was wired into the application in this milestone. The shared contract supports
only ok/incomplete/unavailable, with no ambiguous enum. Resolver errors propagate:
`OrthologueNotFoundError`, `AmbiguousOrthologueError` (raw `.candidates`),
`MissingSequenceError`, `EnsemblAPIError`, `InvalidEnsemblResponseError`.
Integration must catch these, report unavailable with reasons, and retain ambiguity
candidates as JSON observations if needed; never pass an error_record to the rich
adapter or coerce an ambiguous choice to success. Invalid input raises ValueError.
Annotation `reason_code` distinguishes api_failure, missing_uniprot_mapping,
unverified_uniprot_mapping, insufficient_functional_annotations and invalid responses.
Unknown source release remains `data_version=None`; UniProt release cannot fill it.
Non-displayed isoform annotation transfer remains unsupported.

## Reproduction and validation

From `Backend/`:

```sh
../.venv/bin/python -m tools.sequence_demo
../.venv/bin/python -m tools.sequence_validation --output /tmp/asra-validation.json
../.venv/bin/pytest tests/test_sequence_validation.py tests/test_sequence.py tests/test_sequence_functional.py tests/test_sequence_adapter.py tests/test_sequence_species.py tests/test_resolver.py -q
```

The independent audit checks a full shared-contract serialisation roundtrip for
all ten successful recorded pairs, including every evidence field, numeric type,
source, limitation and citation. The fresh source test checks response hashes,
sequence agreement and alternative same-gene xrefs. Pinned replay is offline;
new runtime retrieval timestamps are not claimed as fresh biological retrievals.

Validation: **220 passed, 14 skipped** (opt-in live tests); `git diff --check` passed.
