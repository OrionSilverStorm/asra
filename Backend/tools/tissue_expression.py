from __future__ import annotations
"""Layer 4, tissue expression: GTEx (human) beside Bgee calls (animal).

- Human: GTEx v8 median TPM per tissue site (open-access summary data only).
- Animal: Bgee present/absent expression calls with an expression score, for
  the Ensembl one-to-one orthologue of the human gene.
- Tissues are matched on UBERON IDs: exact first, else the explicit
  organ-level map below (GTEx samples sub-sites, e.g. "right lobe of liver").
  Every match states which kind it is.

Design-doc rule: never divide GTEx by Bgee to claim a fold difference. TPM and
Bgee scores use different methods and scales, so they are shown side by side
and nothing is computed across them.
"""

from datetime import date

import httpx

from contract import LayerResult, Observation, SourceRecord
from tools.base import unavailable
from tools.fixtures import fixture
from tools.resolver import OrthologueResolutionError, ResolvedQuery, orthologue_gene_id

GTEX = "https://gtexportal.org/api/v2"
GTEX_DATASET = "gtex_v8"  # pairs with GENCODE v26 IDs from /reference/gene
BGEE = "https://www.bgee.org/api/"
TIMEOUT = 30.0
EXPRESSED_TPM = 1.0  # conventional "expressed" threshold for listing GTEx sites
SHOWN = 10  # matched tissues reported as observations (highest human TPM first)

# NCBI taxonomy IDs Bgee uses for each comparison species.
TAXON = {"mus_musculus": 10090, "rattus_norvegicus": 10116, "macaca_mulatta": 9544,
         "macaca_fascicularis": 9541, "canis_lupus_familiaris": 9615, "sus_scrofa": 9823,
         "oryctolagus_cuniculus": 9986, "cavia_porcellus": 10141, "danio_rerio": 7955}

# GTEx sub-site UBERON -> organ UBERON, used only when the exact ID has no Bgee call.
ORGAN = {
    "UBERON:0001114": "UBERON:0002107",  # right lobe of liver -> liver
    "UBERON:0008952": "UBERON:0002048",  # upper lobe of left lung -> lung
    "UBERON:0013756": "UBERON:0000178",  # venous blood -> blood
    "UBERON:0006566": "UBERON:0000948",  # left ventricle myocardium -> heart
    "UBERON:0006631": "UBERON:0000948",  # right atrium auricular region -> heart
    "UBERON:0001225": "UBERON:0002113",  # cortex of kidney -> kidney
    "UBERON:0001293": "UBERON:0002113",  # outer medulla of kidney -> kidney
    "UBERON:0001157": "UBERON:0001155",  # transverse colon -> colon
    "UBERON:0001159": "UBERON:0001155",  # sigmoid colon -> colon
    "UBERON:0001211": "UBERON:0002108",  # Peyer's patch (terminal ileum) -> small intestine
    "UBERON:0036149": "UBERON:0002097",  # suprapubic skin -> skin of body
    "UBERON:8480050": "UBERON:0002097",  # lower leg skin -> skin of body
    "UBERON:0006920": "UBERON:0001043",  # esophagus squamous epithelium -> esophagus
    "UBERON:0004648": "UBERON:0001043",  # esophagus muscularis mucosa -> esophagus
    "UBERON:0004550": "UBERON:0001043",  # gastroesophageal sphincter -> esophagus
    "UBERON:0001150": "UBERON:0001264",  # body of pancreas -> pancreas
    "UBERON:0002190": "UBERON:0001013",  # subcutaneous adipose -> adipose tissue
    "UBERON:0010414": "UBERON:0001013",  # omental fat pad -> adipose tissue
    "UBERON:0007610": "UBERON:0001637",  # tibial artery -> artery
    "UBERON:0001621": "UBERON:0001637",  # coronary artery -> artery
    "UBERON:0008367": "UBERON:0001911",  # breast epithelium -> mammary gland
}
BRAIN = "UBERON:0000955"  # every GTEx "Brain_*" site falls back to whole brain

LIMITATIONS = [
    "GTEx TPM and Bgee expression scores come from different methods and scales; they are shown side "
    "by side and must not be divided or ranked against each other.",
    "Bgee is queried for present (expressed) calls; a tissue without a call has no evidence either way, "
    "which is not evidence of absence.",
    "Organ-level matches compare a GTEx sub-site with a whole-organ animal term, so regional "
    "differences can be hidden.",
    "GTEx samples are post-mortem adult tissue; Bgee aggregates heterogeneous studies, stages and "
    "strains, so conditions are not matched.",
]


def _get(url: str, **params) -> dict:
    """GET JSON with a bounded timeout; HTTP errors propagate to the caller."""
    response = httpx.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _gtex(symbol: str) -> tuple[str, list[dict]]:
    """(GENCODE id, median TPM rows) for a human gene symbol; ValueError if unknown."""
    genes = [g for g in _get(f"{GTEX}/reference/gene", geneId=symbol)["data"]
             if g["geneSymbol"].upper() == symbol.upper()]
    if len(genes) != 1:
        raise ValueError(f"GTEx resolves {symbol} to {len(genes)} genes; expected exactly one.")
    gencode = genes[0]["gencodeId"]
    return gencode, _get(f"{GTEX}/expression/medianGeneExpression", gencodeId=gencode, datasetId=GTEX_DATASET)["data"]


def _bgee(gene_id: str, taxon: int) -> dict[str, dict]:
    """{UBERON id: Bgee call} of present-expression calls for one animal gene."""
    data = _get(BGEE, page="gene", action="expression", gene_id=gene_id, species_id=taxon,
                display_type="json", data_type="all", cond_param="anat_entity")["data"]
    return {c["condition"]["anatEntity"]["id"]: c for c in data["calls"]}


def _match(site: dict, calls: dict) -> tuple[str, str] | None:
    """(animal UBERON id, match kind) for one GTEx site, or None when unmatched."""
    exact = site["ontologyId"]
    if exact in calls:
        return exact, "exact UBERON match"
    organ = ORGAN.get(exact) or (BRAIN if site["tissueSiteDetailId"].startswith("Brain_") else None)
    return (organ, f"organ-level match from {exact}") if organ in calls else None


def _site(site: dict) -> str:
    """'Liver 25.1 TPM' for one GTEx site."""
    return f"{site['tissueSiteDetailId'].replace('_', ' ')} {site['median']:.1f} TPM"


def _call(call: dict) -> str:
    """'expressed, score 87.2 (gold; RNA-Seq, Affymetrix)' for one Bgee call."""
    score = call.get("expressionScore", {})
    return (f"{call['expressionState']}, score {score.get('expressionScore', '?')} "
            f"({call.get('expressionQuality', '?')}; {', '.join(call.get('dataTypesWithData', []))})")


def run_tissue_expression(query: ResolvedQuery) -> LayerResult:
    """Pipeline layer: (ResolvedQuery) -> LayerResult."""
    # Offline demo evidence first, only when ASRA_FIXTURES is on (tools/fixtures.py).
    demo = fixture("tissue_expression", query)
    if demo:
        return demo
    if query.gene is None:
        return unavailable("tissue_expression", query, "Needs a resolved gene identifier; none was supplied.")
    try:
        gencode, sites = _gtex(query.gene)
    except (ValueError, httpx.HTTPError) as exc:
        return unavailable("tissue_expression", query, f"GTEx lookup failed: {exc}")
    gtex_src = SourceRecord(id=f"gtex:{gencode}", url=f"https://gtexportal.org/home/gene/{query.gene}",
                            source=f"GTEx {GTEX_DATASET} median gene expression, {query.gene} ({gencode})")
    # Cell lines (EFO terms) are not tissues and have no animal counterpart.
    sites = sorted((s for s in sites if s["ontologyId"].startswith("UBERON:")), key=lambda s: -s["median"])
    observations = [Observation(field="human_top_tissues", source_record_id=gtex_src.id,
                                value="; ".join(_site(s) for s in sites[:5]) or "None reported")]
    version = f"GTEx {GTEX_DATASET} (GENCODE v26); Bgee API retrieved {date.today().isoformat()}"
    try:
        animal_id, note = orthologue_gene_id(query.gene, query.species)
        calls = _bgee(animal_id, TAXON[query.species])
    except (OrthologueResolutionError, httpx.HTTPError, KeyError) as exc:
        reason = f"Animal tissue expression unavailable: {type(exc).__name__}: {exc}"
        return LayerResult(gene=query.gene, species=query.species, layer="tissue_expression", status="incomplete",
                           observations=observations, source_records=[gtex_src],
                           limitations=[reason, *LIMITATIONS], data_version=version)
    bgee_src = SourceRecord(id=f"bgee:{animal_id}", url=f"https://www.bgee.org/gene/{animal_id}",
                            source=f"Bgee expression calls, {query.species} {animal_id} (orthologue of {query.gene})")
    # Group GTEx sites by the animal tissue they match (several brain sites -> brain).
    matched: dict[str, list[tuple[dict, str]]] = {}
    unmatched = []
    for site in sites:
        hit = _match(site, calls)
        if hit:
            matched.setdefault(hit[0], []).append((site, hit[1]))
        elif site["median"] >= EXPRESSED_TPM:
            unmatched.append(site)
    observations.append(Observation(field="matched_tissue_count", source_record_id=bgee_src.id,
                                    value=f"{len(matched)} animal tissues with a Bgee call match a GTEx site "
                                          f"({len(calls)} Bgee calls, {len(sites)} GTEx tissue sites)"))
    for uberon, pairs in list(matched.items())[:SHOWN]:  # sites were sorted, so highest TPM first
        call = calls[uberon]
        human = "; ".join(f"{_site(s)} [{kind}]" for s, kind in pairs)
        observations.append(Observation(field="tissue_" + uberon.replace(":", ""), source_record_id=bgee_src.id,
                                        value=f"{call['condition']['anatEntity']['name']} ({uberon}): human GTEx "
                                              f"{human}; {query.species} Bgee {_call(call)}"))
    if unmatched:
        observations.append(Observation(field="human_expressed_without_animal_call", source_record_id=gtex_src.id,
                                        value=f"{len(unmatched)} GTEx sites >= {EXPRESSED_TPM:g} TPM have no matching "
                                              "Bgee call (no evidence either way): "
                                              + "; ".join(_site(s) for s in unmatched[:6])))
    return LayerResult(gene=query.gene, species=query.species, layer="tissue_expression",
                       status="ok" if matched else "incomplete", observations=observations,
                       source_records=[gtex_src, bgee_src], limitations=([note] if note else []) + LIMITATIONS,
                       data_version=version)
