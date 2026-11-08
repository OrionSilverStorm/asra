from __future__ import annotations
"""Curated literature evidence that databases do not encode.

The design doc asks for published findings to sit beside database results as
*separate* evidence (e.g. the SLC29A1 mitochondrial targeting signal, which no
UniProt entry annotates). Each entry is a real publication, copied by hand
from the paper named in its source record; nothing here is computed.

`literature(layer, gene, species)` returns the observations and source records
for one layer, so a layer tool can append them without knowing the details.
A statement about a particular animal is only attached when that animal is
the comparison species; statements about human biology are always attached.
"""

from contract import LayerName, Observation, SourceRecord

# Prefix on every literature observation value, so it never reads as a database call.
TAG = "LITERATURE (curated, not a database record): "

# ── Publications (real DOIs / citations) ───────────────────────────────────

LAI_2004 = SourceRecord(
    id="doi:10.1074/jbc.M307938200",
    source="Lai Y, Tse CM, Unadkat JD. J Biol Chem 2004;279(6):4490-7",
    url="https://doi.org/10.1074/jbc.M307938200")
LEE_2006 = SourceRecord(
    id="doi:10.1074/jbc.M513825200",
    source="Lee EW, Lai Y, Zhang H, Unadkat JD. J Biol Chem 2006 (mitochondrial targeting signal of hENT1)",
    url="https://doi.org/10.1074/jbc.M513825200")
# No DOI is recorded for Eastwood 2010 in tests/test_cases.md, so none is
# guessed here; the citation itself is the record.
EASTWOOD_2010 = SourceRecord(
    id="pub:eastwood2010",
    source="Eastwood D, Findlay L, Poole S, et al. Br J Pharmacol 2010;161(3):512-26")

# ── Evidence, keyed by (layer, human gene symbol) ──────────────────────────
# Each item is (observation field, statement, source record, animal species it
# concerns or None for a human-only statement).

# Both macaques used in TGN1412 preclinical work.
_MACAQUES = ("macaca_mulatta", "macaca_fascicularis")

_EVIDENCE: dict[tuple[LayerName, str], list[tuple[str, str, SourceRecord, tuple[str, ...] | None]]] = {
    # Fialuridine benchmark: the mitochondrial evidence lives in papers, not UniProt.
    ("localisation", "SLC29A1"): [
        ("literature_human_mitochondrial_location",
         "Human ENT1 is reported in the mitochondrial membrane; this is NOT annotated in UniProt", LAI_2004, None),
        ("literature_mitochondrial_targeting_signal",
         "A mitochondrial targeting signal was identified in human ENT1; the authors frame it as "
         "explaining interspecies differences in fialuridine mitochondrial toxicity", LEE_2006, None),
    ],
    # TGN1412 benchmark: the cell-population difference was shown by flow cytometry.
    ("cell_expression", "CD28"): [
        ("literature_human_cd4_effector_memory",
         "Human CD4+ effector memory T cells (CCR7-) are CD28-positive", EASTWOOD_2010, None),
        ("literature_macaque_cd4_effector_memory",
         "Cynomolgus and rhesus CD4+ effector memory T cells are CD28-negative", EASTWOOD_2010, _MACAQUES),
        ("literature_cytokine_source",
         "CD4+ effector memory T cells are the predominant source of the cytokines released "
         "by TGN1412 in humans", EASTWOOD_2010, None),
    ],
}


def literature(layer: LayerName, gene: str | None, species: str) -> tuple[list[Observation], list[SourceRecord]]:
    """Observations and their (deduplicated) source records for one layer, gene and species."""
    items = [(f, text, src) for f, text, src, animals in _EVIDENCE.get((layer, (gene or "").upper()), [])
             if animals is None or species in animals]
    observations = [Observation(field=f, value=TAG + text, source_record_id=src.id) for f, text, src in items]
    # dict keeps first-seen order while dropping repeated publications.
    sources = list({src.id: src for _, _, src in items}.values())
    return observations, sources
