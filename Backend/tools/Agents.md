
# ASRA: Cellular and Tissue Analysis

## Project context

ASRA is an agentic research system investigating biological differences between humans and preclinical animal models.

The application uses:

- Python and FastAPI for the backend
- Next.js for the frontend
- Gemini for agent reasoning
- Ensembl, UniProt, CELLxGENE, GTEx and Bgee for biological evidence

## Workstream ownership

This workstream owns:

- tools/localisation.py
- tools/cell_expression.py
- tools/tissue_expression.py
- Corresponding tests

Do not modify Frontend/, Backend/main.py, API routes, or agent modules without coordination.

## Required interfaces

Expose:

run_localisation(gene: str, species: str) -> dict

run_cell_expression(gene: str, species: str) -> dict

run_tissue_expression(gene: str, species: str) -> dict

## Shared output contract

Return JSON-serializable dictionaries:

{
    "layer": "localisation",
    "status": "complete",
    "observations": [],
    "measurements": {},
    "sources": [],
    "limitations": []
}

Allowed statuses:
complete, partial, unavailable, error.

Confirm the contract with the integration lead before changing its fields.

## Scientific requirements

1. Use real scientific database records.
2. Preserve source identifiers, URLs and evidence provenance.
3. Never invent measurements or scientific citations.
4. Missing annotations do not establish biological absence.
5. RNA expression is not equivalent to protein abundance.
6. Do not directly compare incompatible expression measurements.
7. Distinguish observations from biological hypotheses.
8. Do not infer drug safety from these comparisons.

## Benchmark cases

SLC29A1:

- Human versus mouse
- Investigate the ENT1 mitochondrial localisation mechanism
- Do not assume UniProt alone documents the known difference

CD28:

- Human versus rhesus macaque
- Investigate comparable CD4 effector-memory T-cell populations
- Report limitations of cross-study RNA comparisons

## Engineering requirements

- Use Python 3.11-compatible code.
- Keep modules independent of FastAPI.
- Use request timeouts and explicit error handling.
- Avoid downloading entire expression atlases.
- Cache verified datasets where appropriate.
- Write pytest tests with mocked API responses.
- Include a manual live-API smoke test.
- Do not add fabricated fallback results.
- Do not change other workstreams' files.

## Development sequence

1. Implement and test localisation.
2. Handoff localisation for integration.
3. Investigate CELLxGENE dataset feasibility.
4. Implement cell-type expression.
5. Implement tissue expression using GTEx and Bgee.
6. Complete tests and scientific limitations.

## Definition of done

A module is complete when it:

- Accepts the agreed inputs.
- Returns compatible structured output.
- Uses real evidence.
- Handles missing data and API failures.
- Passes its tests.
- Can be called independently.
- Is ready for integration.
