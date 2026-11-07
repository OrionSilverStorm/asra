"""Hand-entered demo evidence, so the agents have something to read before the
live integrations land.

This is NOT invented data. Every value below was copied from the UniProt entry
or the publication named in its source record (accessions checked against
rest.uniprot.org on 2026-11-07), and the cases are the benchmarks in
tests/test_cases.md. Nothing here is a number the system computed.

Three guards keep a fixture from passing as a live fetch:
- `status` is always "incomplete", never "ok";
- the first limitation says, in words, that the layer was not queried;
- `data_version` is "fixture (hand-entered)".

Switched on with ASRA_FIXTURES=1 in Backend/.env. All four layers now query
live sources, so this is an offline demo mode only (e.g. no network at a
venue); leave it off for real runs.
"""

import os
from typing import Optional

from contract import LayerName, LayerResult, Observation, SourceRecord, SpeciesId
from tools.literature import EASTWOOD_2010, LAI_2004, LEE_2006  # shared with the live layers
from tools.resolver import ResolvedQuery

# data_version stamped on every fixture layer. report/builder.py uses it to
# set the report origin to "fixture"; Frontend/lib/layers.ts mirrors it.
FIXTURE_VERSION = "fixture (hand-entered)"

# Prepended to every fixture layer's limitations.
FIXTURE_NOTE = (
    "FIXTURE DATA: copied by hand from the records cited here for demonstration. "
    "This layer did not query a live database."
)

# ── Source records (real accessions and publications) ──────────────────────

HUMAN_ENT1 = SourceRecord(id="uniprot:Q99808", source="UniProt Q99808 (S29A1_HUMAN)",
                          url="https://www.uniprot.org/uniprotkb/Q99808")
MOUSE_ENT1 = SourceRecord(id="uniprot:Q9JIM1", source="UniProt Q9JIM1 (S29A1_MOUSE)",
                          url="https://www.uniprot.org/uniprotkb/Q9JIM1")

HUMAN_CD28 = SourceRecord(id="uniprot:P10747", source="UniProt P10747 (CD28_HUMAN)",
                          url="https://www.uniprot.org/uniprotkb/P10747")
MACAQUE_CD28 = SourceRecord(id="uniprot:Q0PDN4", source="UniProt Q0PDN4 (CD28, Macaca mulatta, unreviewed)",
                            url="https://www.uniprot.org/uniprotkb/Q0PDN4")

HUMAN_GAPDH = SourceRecord(id="uniprot:P04406", source="UniProt P04406 (G3P_HUMAN)",
                           url="https://www.uniprot.org/uniprotkb/P04406")
MOUSE_GAPDH = SourceRecord(id="uniprot:P16858", source="UniProt P16858 (G3P_MOUSE)",
                           url="https://www.uniprot.org/uniprotkb/P16858")


def _layer(observations: list[Observation], sources: list[SourceRecord],
           limitations: list[str]) -> dict:
    """One fixture layer, minus the gene/species/layer filled in on lookup."""
    return {
        "observations": observations,
        "source_records": sources,
        "limitations": [FIXTURE_NOTE, *limitations],
    }


def _obs(field: str, value: str, source: SourceRecord) -> Observation:
    """Shorthand: an observation pointing at one source record."""
    return Observation(field=field, value=value, source_record_id=source.id)


# ── The cases, keyed by (gene symbol, comparison species) ──────────────────

FIXTURES: dict[tuple[str, SpeciesId], dict[LayerName, dict]] = {
    # Case 1, fialuridine. The point: both UniProt entries show only plasma
    # membrane, and the mitochondrial evidence sits in the literature instead.
    ("SLC29A1", "mus_musculus"): {
        "localisation": _layer(
            observations=[
                _obs("human_compartments",
                     "Basolateral cell membrane; apical cell membrane; cell membrane", HUMAN_ENT1),
                _obs("animal_compartments",
                     "Basolateral cell membrane; apical cell membrane; cell membrane", MOUSE_ENT1),
                _obs("shared_compartments", "Plasma membrane (apical and basolateral)", MOUSE_ENT1),
                _obs("human_only_compartments",
                     "Mitochondrial membrane - reported in the literature; NOT annotated in UniProt", LAI_2004),
                _obs("mitochondrial_targeting_signal",
                     "Identified in human ENT1; the authors frame it as explaining interspecies "
                     "differences in fialuridine mitochondrial toxicity", LEE_2006),
                _obs("animal_evidence_codes",
                     "Every mouse compartment is ECO:0000250 (inferred by similarity from Q99808); "
                     "none is a direct observation in mouse", MOUSE_ENT1),
            ],
            sources=[HUMAN_ENT1, MOUSE_ENT1, LAI_2004, LEE_2006],
            limitations=[
                "Neither UniProt entry annotates a mitochondrial location; that evidence comes only "
                "from the two publications cited here.",
                "The mouse annotations are inferred by similarity from the human entry, so they are "
                "not independent evidence and their silence proves nothing about mouse biology.",
            ]),
    },
    # Case 2, TGN1412. Deliberately has no dataset IDs or cell counts: the
    # honest outcome here is 'partial', and the Sceptic should say why.
    ("CD28", "macaca_mulatta"): {
        "localisation": _layer(
            observations=[
                _obs("human_compartments", "Cell membrane; single-pass type I membrane protein", HUMAN_CD28),
                _obs("animal_compartments", "Cell membrane; single-pass type I membrane protein", MACAQUE_CD28),
                _obs("shared_compartments", "Cell membrane", MACAQUE_CD28),
                _obs("human_only_compartments", "None reported", HUMAN_CD28),
            ],
            sources=[HUMAN_CD28, MACAQUE_CD28],
            limitations=[
                "The macaque entry is unreviewed and its localisation is an automatic annotation "
                "(ECO:0000256/ARBA), not a curated experimental one.",
            ]),
        "cell_expression": _layer(
            observations=[
                _obs("human_cell_population",
                     "CD4+ effector memory T cells (CCR7-) are CD28-positive", EASTWOOD_2010),
                _obs("animal_cell_population",
                     "Cynomolgus and rhesus CD4+ effector memory T cells are CD28-negative", EASTWOOD_2010),
                _obs("cytokine_source",
                     "CD4+ effector memory T cells are the predominant source of the cytokines "
                     "released by TGN1412 in humans", EASTWOOD_2010),
            ],
            sources=[EASTWOOD_2010],
            limitations=[
                "No CELLxGENE dataset was queried, so there are no detection fractions, cell counts "
                "or assay identifiers behind these statements and no quantitative comparison is possible.",
                "Human and macaque cell-type labels are not guaranteed equivalent.",
            ]),
    },
    # Case 3, conserved control. Nothing here should alarm anyone.
    ("GAPDH", "mus_musculus"): {
        "localisation": _layer(
            observations=[
                _obs("human_compartments",
                     "Cytoplasm, cytosol; nucleus; cytoplasm, perinuclear region", HUMAN_GAPDH),
                _obs("animal_compartments",
                     "Cytoplasm, cytosol; cytoplasm, cytoskeleton; nucleus", MOUSE_GAPDH),
                _obs("shared_compartments", "Cytosol and nucleus", MOUSE_GAPDH),
                _obs("human_only_compartments", "None reported", HUMAN_GAPDH),
            ],
            sources=[HUMAN_GAPDH, MOUSE_GAPDH],
            limitations=[
                "The mouse annotations are inferred by similarity (ECO:0000250) from the rat entry P04797.",
            ]),
    },
}

# Gene symbols that have a fixture, longest first so "SLC29A1" wins over a
# shorter symbol that happens to be a substring of the same label.
_GENES = sorted({gene for gene, _ in FIXTURES}, key=len, reverse=True)


def enabled() -> bool:
    """True when ASRA_FIXTURES is set to 1/true in the environment."""
    return os.getenv("ASRA_FIXTURES", "").strip().lower() in {"1", "true", "yes"}


def _gene_in(query: ResolvedQuery) -> Optional[str]:
    """Find a fixture gene symbol in the resolved gene or the FASTA header.

    Searching the whole label as well as `query.gene` keeps this working for
    headers like ">sp|Q99808|S29A1_HUMAN", where the resolver's first token is
    the database prefix rather than the symbol.
    """
    text = f"{query.gene or ''} {query.sequence_label or ''}".upper()
    return next((gene for gene in _GENES if gene in text), None)


def fixture(layer: LayerName, query: ResolvedQuery) -> Optional[LayerResult]:
    """Return the demo evidence for this layer, or None to fall through."""
    if not enabled():
        return None
    gene = _gene_in(query)
    case = FIXTURES.get((gene, query.species)) if gene else None
    if not case or layer not in case:
        return None
    return LayerResult(
        gene=gene,
        species=query.species,
        layer=layer,
        # Never "ok": hand-entered evidence is partial by definition.
        status="incomplete",
        data_version=FIXTURE_VERSION,
        **case[layer],
    )
