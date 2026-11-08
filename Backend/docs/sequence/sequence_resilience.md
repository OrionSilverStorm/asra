Sequence resilience

Scope: the pipeline sequence wrapper, typed Ensembl transport error metadata,
shared sequence evidence builder, a strictly limited snapshot loader, tests and
raw protein evidence. No routes, evidence schema fields, master merge or other
layers are changed. origin/master was fetched at b26bcbc; this work remains on
fix/protein-sequence-validation, retaining its existing commits.

Failure: origin/master:tests/frozen/01_slc29a1_run02.json records three Ensembl
timeouts and an unavailable sequence layer. The old retry wrapper used error text
and discarded Retry-After. It had no recorded-sequence recovery path.

Retry policy: at most three attempts; network timeout/connect/remote protocol/proxy
errors, HTTP 429 and 5xx only. Retry-After delta-seconds and HTTP-date are respected
with at most five seconds total scheduled sleep. If a server requests a wait beyond
the remaining budget, no early retry is made; retrying stops. Per-operation HTTP
timeouts remain 30 seconds; the sleep cap is not a whole-assessment deadline.
Legacy exception text still supports retries, but cannot alone authorize fallback.
Invalid input, permanent 4xx, local protocol errors, ambiguity, malformed records
and missing sequences do not authorize fallback.

Only exact SLC29A1 / mus_musculus may recover after confirmed transient failure.
A supplied UniProt header accession must be Q99808. The recovery loads runtime
copies of original evidence already stored in tests/fixtures/role3:
- homology.json: the successful raw HTTP record for this pair from
  species_compatibility/http.json (2026-11-07T19:16:29.540313+00:00).
- Q99808.json, Q9JIM1.json, manifest.json: byte-for-byte original UniProt snapshots.

The loader checks file SHA-256, unique one-to-one recorded orthology, exact human
and mouse gene/protein IDs, species, sequence hashes, UniProt accessions, full
sequence equality and authoritative Ensembl cross-references in UniProt. It fails
closed on missing/corrupt/mismatched evidence. No AI report or saved measurements
are consumed. The original Biopython algorithm aligns the raw sequences anew.

The existing evidence schema and string-valued adapter are preserved. Fallback
status is incomplete, source labels and provenance say pinned/recorded, the original
retrieval timestamp is retained, source citations and file/sequence hashes are
included. data_version identifies pinned Ensembl (release unknown) and the original
UniProt 2026_04 snapshots. UniProt's version does not establish an Ensembl release.
Functional annotations are not refreshed/projected; no functional equivalence or
fresh live evidence is claimed. Runtime deployment must include Backend/data/sequence.

Replayed the exact frozen request with mocked three consecutive HTTP read timeouts:
unavailable -> incomplete pinned evidence, 366/461 = 79.39262472885032% identity,
455/456 = 99.78070175438596% human coverage and
455/460 = 98.91304347826087% mouse coverage. Output is in
/tmp/asra-frozen-sequence-recovery.json. The original frozen report is unchanged.
This is a deterministic reproduction of its failure path, not a new live API run.

Commands from Backend:

```
../.venv/bin/pytest tests/test_sequence_validation.py tests/test_sequence.py tests/test_sequence_functional.py tests/test_sequence_adapter.py tests/test_sequence_species.py tests/test_sequence_layer.py tests/test_resolver.py tests/test_protein_sequence_validation.py tests/test_sequence_resilience.py -q
../.venv/bin/pytest -q
```

Full backend tests run outside the sandbox because earlier sandbox runs stalled in
FastAPI TestClient. Live API integration tests remain opt-in and are skipped here.

Final results: focused suite 281 passed, 21 skipped in 0.86s; full backend
373 passed, 21 skipped in 42.50s. No remaining failures. New deterministic
resilience coverage adds 37 cases. Earlier development checks caught a mistyped
manifest checksum constant; it was corrected to the original file's verified
SHA-256 before these final runs. git diff --check passed. Only protein sequence
code, tests, documentation and raw snapshot assets are changed.
