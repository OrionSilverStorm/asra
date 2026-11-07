"""Compare human and animal UniProt subcellular-location annotations.

Run from the repository root: python3 -m Backend.tools.localisation SLC29A1 mouse

The shared contract is exactly: layer, status, observations, measurements,
sources, limitations. Protein records and comparison details live in measurements.
``complete`` means both reviewed records have cited experimental location evidence;
``partial`` means records/evidence are incomplete; ``unavailable`` means no record
can be resolved; ``error`` means invalid input or API failure prevents analysis.
Completeness never implies that a biological species difference is established.

Only the standard library is required. Searches are bounded and ambiguous matches
are rejected. Each selected accession is fetched again and its gene/taxon checked.
No results are invented or substituted when a request fails.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://rest.uniprot.org/uniprotkb"
REQUEST_TIMEOUT = 20.0
_ACCESSION = re.compile(
    r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})"
)
# Explicit taxonomy IDs prevent similarly named organisms being interchanged.
_SPECIES = {
    "mus_musculus": (10090, "Mus musculus", ("mouse", "mice")),
    "rattus_norvegicus": (10116, "Rattus norvegicus", ("rat", "rats")),
    "macaca_mulatta": (9544, "Macaca mulatta", ("rhesus", "rhesus macaque")),
    "macaca_fascicularis": (9541, "Macaca fascicularis", ("cynomolgus", "cynomolgus macaque")),
    "canis_lupus_familiaris": (9615, "Canis lupus familiaris", ("dog", "canis familiaris")),
    "sus_scrofa": (9823, "Sus scrofa", ("pig", "pigs")),
    "oryctolagus_cuniculus": (9986, "Oryctolagus cuniculus", ("rabbit",)),
    "cavia_porcellus": (10141, "Cavia porcellus", ("guinea pig",)),
    "danio_rerio": (7955, "Danio rerio", ("zebrafish",)),
}
_BASE_LIMITATIONS = [
    "Missing localisation annotations do not establish biological absence from a compartment.",
    "Matching gene symbols and taxonomy resolve candidate counterparts, not independently verified orthology; renamed genes and one-to-many orthologues need an orthology resource.",
    "Comparisons use exact location IDs (or unambiguous normalized labels when IDs are missing), without ontology ancestor expansion. Broad and specific membrane terms need not conflict.",
    "Annotations may concern different tissues, conditions or isoforms. Their overlap does not establish identical localisation, and annotation differences do not establish biological differences.",
    "UniProt annotations alone do not establish a drug mechanism or drug safety; additional comparative literature and experimental evidence are required.",
]


class _DataError(Exception):
    """A recoverable remote-data or resolution failure, retained in the result."""

    def __init__(self, kind: str, message: str, url: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.url = url


def _objects(value: object, field: str) -> list[dict]:
    """Validate collection shape so malformed data cannot masquerade as absence."""
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise _DataError("invalid_response", f"Expected an array of objects for {field}.")
    return value


def _request_json(url: str) -> tuple[dict, dict]:
    """Use bounded requests, retain release headers, and classify API failures."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ASRA-localisation/1.0"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read())
            headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        raise _DataError("api_error", f"UniProt returned HTTP {exc.code}.", url) from exc
    except (TimeoutError, URLError, OSError, HTTPException) as exc:
        raise _DataError("api_error", f"UniProt request failed: {exc}", url) from exc
    except (ValueError, UnicodeError) as exc:
        raise _DataError("invalid_response", "UniProt returned invalid JSON.", url) from exc
    if not isinstance(payload, dict):
        raise _DataError("invalid_response", "UniProt JSON is not an object.", url)
    return payload, headers


def _inputs(gene: str, species: str) -> tuple[str, str]:
    """Accept a gene symbol and supported common/scientific/Ensembl species name."""
    if not isinstance(gene, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", gene.strip()):
        raise _DataError("invalid_input", "gene must be a nonempty gene symbol (letters, digits, '.', '_' or '-').")
    if isinstance(species, str):
        name = " ".join(species.strip().lower().replace("_", " ").split())
        for canonical, (taxon, scientific, aliases) in _SPECIES.items():
            if name in (canonical.replace("_", " "), scientific.lower(), str(taxon), *aliases):
                return gene.strip().upper(), canonical
    raise _DataError("invalid_input", "species must identify a supported non-human animal: " + ", ".join(_SPECIES))


def _validate_record(record: dict, gene: str, taxon: int, url: str, accession: str | None = None) -> None:
    """Check accession, exact gene symbol/synonym, and numeric taxonomy ID."""
    found = record.get("primaryAccession")
    if not isinstance(found, str) or not _ACCESSION.fullmatch(found):
        raise _DataError("invalid_response", "UniProt record has no valid primary accession.", url)
    if accession is not None and found != accession:
        raise _DataError("record_mismatch", f"Requested {accession}, received {found}.", url)
    organism = record.get("organism")
    if not isinstance(organism, dict) or organism.get("taxonId") != taxon:
        raise _DataError("record_mismatch", f"Accession {found} does not match requested taxon {taxon}.", url)
    names = []
    for item in _objects(record.get("genes", []), "genes"):
        primary = item.get("geneName", {})
        if not isinstance(primary, dict):
            raise _DataError("invalid_response", "Invalid geneName object.", url)
        names.append(primary.get("value", ""))
        names.extend(synonym.get("value", "") for synonym in _objects(item.get("synonyms", []), "gene synonyms"))
    if not any(isinstance(name, str) and name.casefold() == gene.casefold() for name in names):
        raise _DataError("record_mismatch", f"Accession {found} does not match gene {gene}.", url)


def _resolve(gene: str, taxon: int, sources: list[dict]) -> tuple[dict, dict, str]:
    """Prefer a unique reviewed record; never pick the first of ambiguous hits."""
    for reviewed in (True, False):
        query = f"gene_exact:{gene} AND organism_id:{taxon} AND reviewed:{str(reviewed).lower()}"
        url = API_ROOT + "/search?" + urlencode({
            "query": query, "format": "json", "size": 100,
            "fields": "accession,gene_names,organism_id,reviewed",
        })
        payload, headers = _request_json(url)
        results = _objects(payload.get("results"), "search results")
        sources.append({"id": f"search:{taxon}:{reviewed}", "database": "UniProt", "url": url,
                        "kind": "resolution_search", "release": headers.get("x-uniprot-release")})
        # Do not silently resolve from a truncated result set.
        if 'rel="next"' in headers.get("link", ""):
            raise _DataError("ambiguous_record", "UniProt search has additional pages; resolution is ambiguous.", url)
        candidates = {}
        for record in results:
            _validate_record(record, gene, taxon, url)
            candidates[record["primaryAccession"]] = record
        if not candidates:
            continue
        if len(candidates) != 1:
            raise _DataError("ambiguous_record", "Multiple matching UniProt accessions: " + ", ".join(sorted(candidates)), url)
        accession = next(iter(candidates))
        record_url = f"{API_ROOT}/{accession}.json"
        record, headers = _request_json(record_url)
        _validate_record(record, gene, taxon, record_url, accession)
        if reviewed and record.get("entryType") != "UniProtKB reviewed (Swiss-Prot)":
            raise _DataError("record_mismatch", f"Accession {accession} is not the reviewed record requested.", record_url)
        return record, headers, url
    raise _DataError("record_not_found", f"No exact UniProt gene match for {gene} in taxon {taxon}.", url)


def _evidence(items: object) -> list[dict]:
    """Retain the original evidence codes/identifiers, adding only known URLs."""
    evidence = []
    for raw in _objects(items, "evidences"):
        item = dict(raw)
        source, identifier = item.get("source"), item.get("id")
        if isinstance(identifier, str) and identifier:
            if source == "PubMed" and identifier.isdigit():
                item["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"
            elif source == "UniProtKB" and _ACCESSION.fullmatch(identifier):
                item["url"] = f"https://www.uniprot.org/uniprotkb/{identifier}/entry"
        evidence.append(item)
    return evidence


def _support(evidence: list[dict]) -> str:
    """An experimental code requires a traceable publication, not just a label."""
    if any(item.get("evidenceCode") == "ECO:0000269" and item.get("source") == "PubMed"
           and isinstance(item.get("id"), str) and item["id"].isdigit() for item in evidence):
        return "experimental"
    if any(item.get("evidenceCode") == "ECO:0000250" for item in evidence):
        return "by_similarity"
    if any(item.get("evidenceCode") for item in evidence):
        return "other"
    return "missing"


def _term(raw: object) -> dict | None:
    """Keep topology/orientation separate from compartments and their evidence."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("value"), str) or not raw["value"].strip():
        raise _DataError("invalid_response", "Invalid subcellular location/topology/orientation term.")
    identifier = raw.get("id")
    if identifier is not None and not isinstance(identifier, str):
        raise _DataError("invalid_response", "Invalid subcellular location ID.")
    evidence = _evidence(raw.get("evidences", []))
    return {"id": identifier or None, "name": raw["value"], "evidence": evidence,
            "evidence_support": _support(evidence)}


def _protein(record: dict, headers: dict, resolution_url: str) -> dict:
    """Extract only structured SUBCELLULAR LOCATION comments and attached notes."""
    locations, notes = [], []
    for comment in _objects(record.get("comments", []), "comments"):
        if comment.get("commentType") != "SUBCELLULAR LOCATION":
            continue
        molecule = comment.get("molecule")
        for raw in _objects(comment.get("subcellularLocations", []), "subcellularLocations"):
            location = _term(raw.get("location"))
            if location is None:
                raise _DataError("invalid_response", "Subcellular annotation has no location term.")
            locations.append({**location, "topology": _term(raw.get("topology")),
                              "orientation": _term(raw.get("orientation")), "molecule": molecule})
        note = comment.get("note", {})
        if not isinstance(note, dict):
            raise _DataError("invalid_response", "Invalid subcellular location note.")
        for text in _objects(note.get("texts", []), "location notes"):
            notes.append({"text": text.get("value"), "evidence": _evidence(text.get("evidences", [])), "molecule": molecule})
    accession = record["primaryAccession"]
    audit = record.get("entryAudit", {})
    if not isinstance(audit, dict):
        raise _DataError("invalid_response", "Invalid UniProt entry audit.")
    return {
        "accession": accession, "taxon_id": record["organism"]["taxonId"],
        "scientific_name": record["organism"].get("scientificName"),
        "reviewed": record.get("entryType") == "UniProtKB reviewed (Swiss-Prot)",
        "source_url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
        "api_url": f"{API_ROOT}/{accession}.json", "resolution_url": resolution_url,
        "entry_version": audit.get("entryVersion"),
        "last_annotation_update": audit.get("lastAnnotationUpdateDate"),
        "release": headers.get("x-uniprot-release"), "locations": locations, "notes": notes,
    }


def _location_label(location: dict) -> str:
    """Normalize labels only for fallback matching when an ID is missing."""
    return " ".join(location["name"].casefold().split())


def _compare(proteins: dict) -> dict:
    """Report positive annotation differences, never negative biological evidence."""
    comparison = {
        "status": "not_comparable", "overlapping_locations": [],
        "human_only_annotations": [], "animal_only_annotations": [],
        "supported_annotation_differences": [], "biological_difference_supported": False,
    }
    if not all(proteins.values()):
        return comparison
    if not all(protein["locations"] for protein in proteins.values()):
        comparison["status"] = "incomplete_evidence"
        return comparison
    # A label-only term can match a known ID, but never arbitrarily choose among
    # multiple IDs with the same label. Isoform context stays in the raw records.
    ids_by_label = {}
    for protein in proteins.values():
        for location in protein["locations"]:
            if location["id"]:
                ids_by_label.setdefault(_location_label(location), set()).add(location["id"])
    grouped = {}
    for side, protein in proteins.items():
        grouped[side] = {}
        for location in protein["locations"]:
            label = _location_label(location)
            known_ids = ids_by_label.get(label, set())
            if not location["id"] and len(known_ids) > 1:
                comparison["status"] = "incomplete_evidence"
                comparison["reason"] = "A location without an ID matches multiple location IDs by label; differences cannot be resolved."
                return comparison
            key = location["id"] or next(iter(known_ids), "label:" + label)
            grouped[side].setdefault(key, []).append(location)
    human, animal = grouped["human"], grouped["animal"]
    for key in sorted(human.keys() | animal.keys()):
        representative = (human.get(key) or animal[key])[0]
        item = {"id": None if key.startswith("label:") else key, "name": representative["name"],
                "source_ids": [proteins[side]["accession"] for side in grouped if key in grouped[side]],
                "evidence_support": {side: sorted({loc["evidence_support"] for loc in grouped[side][key]})
                                     for side in grouped if key in grouped[side]}}
        if key in human and key in animal:
            comparison["overlapping_locations"].append(item)
        else:
            side = "human" if key in human else "animal"
            item["side"] = side
            comparison[f"{side}_only_annotations"].append(item)
            if "experimental" in item["evidence_support"][side]:
                comparison["supported_annotation_differences"].append(item)
    comparison["status"] = ("annotation_differences" if comparison["human_only_annotations"] or comparison["animal_only_annotations"] else "overlap_only")
    return comparison


def run_localisation(gene: str, species: str) -> dict:
    """Return the six-field shared contract for a human-versus-animal comparison.

    Invalid input and expected remote failures are returned as structured errors.
    ``supported_annotation_differences`` supports the positive annotation in the
    named species only; it is never evidence of absence in the other species.
    """
    result = {"layer": "localisation", "status": "error", "observations": [],
              "measurements": {"proteins": {"human": None, "animal": None}, "errors": []},
              "sources": [], "limitations": list(_BASE_LIMITATIONS)}
    measurements = result["measurements"]
    proteins, errors = measurements["proteins"], measurements["errors"]
    try:
        gene, species = _inputs(gene, species)
    except _DataError as exc:
        errors.append({"side": None, "kind": exc.kind, "message": str(exc), "url": exc.url})
        measurements["comparison"] = _compare(proteins)
        return result
    measurements.update({"gene": gene, "species": species,
                         "retrieved_at": datetime.now(timezone.utc).isoformat()})
    if gene in {"SLC29A1", "ENT1"}:
        result["limitations"].append(
            "The ENT1/fialuridine mitochondrial mechanism is not established by this annotation comparison. Additional literature is needed to assess species-specific mitochondrial targeting, drug transport and toxicity."
        )
    for side, taxon in (("human", 9606), ("animal", _SPECIES[species][0])):
        try:
            record, headers, search_url = _resolve(gene, taxon, result["sources"])
            try:
                protein = _protein(record, headers, search_url)
            except _DataError as exc:
                exc.url = f"{API_ROOT}/{record['primaryAccession']}.json"
                raise
            proteins[side] = protein
            result["sources"].append({
                "id": protein["accession"], "database": "UniProt", "kind": "protein_record",
                "url": protein["source_url"], "api_url": protein["api_url"],
                "taxon_id": taxon, "entry_version": protein["entry_version"], "release": protein["release"],
            })
        except _DataError as exc:
            errors.append({"side": side, "kind": exc.kind, "message": str(exc), "url": exc.url})
            result["limitations"].append(f"{side}: {exc}")
    comparison = _compare(proteins)
    measurements["comparison"] = comparison
    if comparison.get("reason"):
        result["limitations"].append(comparison["reason"])
    incomplete = bool(errors)
    for side, protein in proteins.items():
        if protein is None:
            continue
        if not protein["locations"]:
            incomplete = True
            result["limitations"].append(f"{side} ({protein['accession']}): no structured SUBCELLULAR LOCATION annotations; localisation is unknown.")
        if not protein["reviewed"]:
            incomplete = True
            result["limitations"].append(f"{side} ({protein['accession']}): only an unreviewed UniProt record could be resolved.")
        other = proteins["animal" if side == "human" else "human"]
        if other and any(
            evidence.get("evidenceCode") == "ECO:0000250"
            and evidence.get("source") == "UniProtKB"
            and evidence.get("id") == other["accession"]
            for location in protein["locations"] for evidence in location["evidence"]
        ):
            result["limitations"].append(
                f"{side}: some location evidence is transferred by similarity from {other['accession']}; it is not independent cross-species experimental confirmation."
            )
        for location in protein["locations"]:
            if location["evidence_support"] != "experimental":
                incomplete = True
                result["limitations"].append(f"{side} {location['name']}: evidence is {location['evidence_support']}; no attached experimental PubMed evidence was identified.")
            if location["id"] is None:
                incomplete = True
                result["limitations"].append(f"{side} {location['name']}: missing location ID; comparison uses the normalized label.")
    if any(proteins.values()):
        result["status"] = "partial" if incomplete else "complete"
    elif any(error["kind"] in {"api_error", "invalid_response", "record_mismatch"} for error in errors):
        result["status"] = "error"
    else:
        result["status"] = "unavailable"
    # Summaries are traceable to protein records; detailed evidence stays attached
    # to each raw location, topology and note in measurements.proteins.
    for item in comparison["overlapping_locations"]:
        result["observations"].append({"type": "overlapping_annotation", "location_id": item["id"],
            "statement": f"Both records annotate {item['name']}.", "source_ids": item["source_ids"]})
    for side in ("human", "animal"):
        for item in comparison[f"{side}_only_annotations"]:
            result["observations"].append({"type": "annotation_difference", "location_id": item["id"],
                "statement": f"{item['name']} is annotated in the {side} record only within the retrieved pair; this does not establish absence in the other species.",
                "evidence_support": item["evidence_support"],
                "source_ids": [protein["accession"] for protein in proteins.values() if protein]})
    if incomplete:
        result["observations"].append({"type": "incomplete_evidence",
            "statement": "The comparison has incomplete records or localisation evidence; inspect limitations and errors.",
            "source_ids": [protein["accession"] for protein in proteins.values() if protein]})
    return result


def _main() -> int:
    """Manual live-API smoke test; JSON is printed even when an API call fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol, for example SLC29A1")
    parser.add_argument("species", help="Animal species, for example mouse or mus_musculus")
    args = parser.parse_args()
    result = run_localisation(args.gene, args.species)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] in {"error", "unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(_main())
