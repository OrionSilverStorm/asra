from __future__ import annotations
"""Layer 2, subcellular localisation: human vs animal UniProt annotations.

Run from Backend/: python -m tools.localisation SLC29A1 mouse

Two levels:
- ``compare_localisation(gene, species) -> dict`` is the detailed comparison
  (layer, status, observations, measurements, sources, limitations). Protein
  records and comparison details live in measurements.
- ``run_localisation(query) -> LayerResult`` is the pipeline layer: it maps
  that dict onto the universal contract (``to_layer_result``) and appends the
  curated literature evidence from tools/literature.py.

``complete`` means both reviewed records have cited experimental location evidence;
``partial`` means records/evidence are incomplete; ``unavailable`` means no record
can be resolved; ``error`` means invalid input or API failure prevents analysis.
Completeness never implies that a biological species difference is established.

Only the standard library is required. Searches are bounded and ambiguous matches
are rejected. Each selected accession is fetched again and its gene/taxon checked.
No results are invented or substituted when a request fails.
"""

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from contract import LayerResult, Observation, SourceRecord
from tools.base import unavailable
from tools.fixtures import fixture
from tools.literature import literature
from tools.resolver import OrthologueResolutionError, ResolvedQuery, resolve_orthologue


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


def _same_ensembl_id(expected: str, returned: object) -> bool:
    """Match an unversioned Ensembl ID from homology against a versioned UniProt xref."""
    return isinstance(returned, str) and (
        expected == returned or ("." not in expected and expected == returned.split(".")[0])
    )


def _validate_ensembl_record(
    record: dict, protein_id: str, gene_id: str, taxon: int, url: str, accession: str | None = None
) -> None:
    """Verify primary accession, taxonomy ID, and Ensembl protein/gene cross-reference."""
    found = record.get("primaryAccession")
    if not isinstance(found, str) or not _ACCESSION.fullmatch(found):
        raise _DataError("invalid_response", "UniProt record has no valid primary accession.", url)
    if accession is not None and found != accession:
        raise _DataError("record_mismatch", f"Requested {accession}, received {found}.", url)
    organism = record.get("organism")
    if not isinstance(organism, dict) or organism.get("taxonId") != taxon:
        raise _DataError("record_mismatch", f"Accession {found} does not match requested taxon {taxon}.", url)
    xrefs = _objects(record.get("uniProtKBCrossReferences", []), "uniProtKBCrossReferences")
    matched = False
    for ref in xrefs:
        if ref.get("database") != "Ensembl":
            continue
        props = {
            p.get("key"): p.get("value")
            for p in _objects(ref.get("properties", []), "Ensembl xref properties")
        }
        if _same_ensembl_id(protein_id, props.get("ProteinId")) and _same_ensembl_id(gene_id, props.get("GeneId")):
            matched = True
            break
    if not matched:
        raise _DataError(
            "record_mismatch",
            f"Accession {found} has no verified Ensembl cross-reference for {gene_id} / {protein_id}.",
            url,
        )


def _resolve_via_orthologue(
    gene: str, species: str, taxon: int, sources: list[dict], limitations: list[str]
) -> tuple[dict, dict, str]:
    """Resolve a unique animal UniProt record via its verified 1-to-1 Ensembl orthologue protein ID."""
    orth = resolve_orthologue(gene, species)
    target = orth["target"]
    protein_id = target["protein_id"].split(".")[0]
    gene_id = target["gene_id"].split(".")[0]
    query = f"xref:ensembl-{protein_id} AND organism_id:{taxon}"
    url = API_ROOT + "/search?" + urlencode({
        "query": query, "format": "json", "size": 100,
        "fields": "accession,gene_names,organism_id,reviewed,xref_ensembl",
    })
    payload, headers = _request_json(url)
    results = _objects(payload.get("results"), "search results")
    sources.append({"id": f"ensembl:{gene_id}", "database": "Ensembl", "url": orth["source_url"],
                    "kind": "orthology_resolution", "gene_id": gene_id, "protein_id": protein_id})
    sources.append({"id": f"search:{taxon}:ensembl:{protein_id}", "database": "UniProt", "url": url,
                    "kind": "resolution_search", "release": headers.get("x-uniprot-release")})
    if 'rel="next"' in headers.get("link", ""):
        raise _DataError("ambiguous_record", "UniProt Ensembl xref search has additional pages; resolution is ambiguous.", url)
    candidates = {}
    for record in results:
        _validate_ensembl_record(record, protein_id, gene_id, taxon, url)
        candidates[record["primaryAccession"]] = record
    if not candidates:
        raise _DataError("record_not_found", f"No UniProt record cross-referencing Ensembl {protein_id} in taxon {taxon}.", url)
    if len(candidates) != 1:
        raise _DataError("ambiguous_record", "Multiple UniProt accessions for Ensembl " + protein_id + ": " + ", ".join(sorted(candidates)), url)
    accession = next(iter(candidates))
    record_url = f"{API_ROOT}/{accession}.json"
    record, headers = _request_json(record_url)
    _validate_ensembl_record(record, protein_id, gene_id, taxon, record_url, accession)
    limitations.append(
        f"animal ({accession}): resolved via verified Ensembl one-to-one orthologue {gene_id} / {protein_id} "
        f"because exact UniProt gene-symbol lookup did not resolve a unique record."
    )
    return record, headers, url


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


def compare_localisation(gene: str, species: str) -> dict:
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
            try:
                record, headers, search_url = _resolve(gene, taxon, result["sources"])
            except _DataError as primary_exc:
                if (
                    side != "animal"
                    or proteins["human"] is None
                    or primary_exc.kind not in {"record_not_found", "ambiguous_record"}
                ):
                    raise
                try:
                    record, headers, search_url = _resolve_via_orthologue(
                        gene, species, taxon, result["sources"], result["limitations"]
                    )
                except (_DataError, OrthologueResolutionError, ValueError):
                    raise primary_exc
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


# ── Contract adapter (pipeline layer) ──────────────────────────────────────

# Detailed status -> universal LayerStatus. "error" and "unavailable" both mean
# the layer could not produce usable evidence.
_STATUS = {"complete": "ok", "partial": "incomplete"}


def _record_id(protein: dict) -> str:
    """Source-record id for one UniProt entry, e.g. 'uniprot:Q99808'."""
    return f"uniprot:{protein['accession']}"


def _names(items: list[dict]) -> str:
    """'Cell membrane (SL-0039); ...' or 'None' for an empty list."""
    return "; ".join(f"{i['name']} ({i['id']})" if i.get("id") else i["name"] for i in items) or "None"


def _evidence_summary(protein: dict) -> str:
    """Per-location evidence strength plus any similarity-transfer source."""
    parts = [f"{loc['name']}: {loc['evidence_support']}" for loc in protein["locations"]]
    # ECO:0000250 items name the UniProt entry the annotation was copied from.
    copied = sorted({ev["id"] for loc in protein["locations"] for ev in loc["evidence"]
                     if ev.get("evidenceCode") == "ECO:0000250" and ev.get("source") == "UniProtKB"})
    if copied:
        parts.append("transferred by similarity from " + ", ".join(copied))
    return "; ".join(parts) or "No structured SUBCELLULAR LOCATION annotation"


def to_layer_result(detail: dict, query: ResolvedQuery) -> LayerResult:
    """Map the detailed comparison onto the universal LayerResult."""
    proteins = detail["measurements"]["proteins"]
    comparison = detail["measurements"].get("comparison", {})
    orth_src = next(
        (s for s in detail.get("sources", []) if isinstance(s, dict) and s.get("kind") == "orthology_resolution"),
        None,
    )
    observations, sources = [], []
    for side in ("human", "animal"):
        protein = proteins.get(side)
        if protein is None:
            continue  # a failed side is reported in limitations, never as empty data
        rid = _record_id(protein)
        review = "reviewed" if protein["reviewed"] else "unreviewed"
        orth_note = (
            f", resolved via Ensembl orthologue {orth_src['gene_id']} / {orth_src['protein_id']}"
            if side == "animal" and orth_src
            else ""
        )
        sources.append(SourceRecord(id=rid, url=protein["source_url"],
                                    source=f"UniProt {protein['accession']} ({protein['scientific_name']}, "
                                           f"{review}, entry v{protein['entry_version']}{orth_note})"))
        compartments = (
            _names(protein["locations"])
            if protein["locations"]
            else "No structured SUBCELLULAR LOCATION annotation (localisation unknown)"
        )
        observations += [
            Observation(field=f"{side}_compartments", value=compartments, source_record_id=rid),
            Observation(field=f"{side}_evidence", value=_evidence_summary(protein), source_record_id=rid),
        ]
    # Overlap/difference lists exist only when both sides were comparable.
    if comparison.get("status") in {"overlap_only", "annotation_differences"}:
        first = sources[0].id  # shared terms are cited to the human entry
        observations.append(Observation(field="shared_compartments",
                                        value=_names(comparison["overlapping_locations"]), source_record_id=first))
        for side in ("human", "animal"):
            rid = _record_id(proteins[side])
            only = _names(comparison[f"{side}_only_annotations"])
            note = "" if only == "None" else " (annotated in this record only; not evidence of absence in the other)"
            observations.append(Observation(field=f"{side}_only_compartments", value=only + note, source_record_id=rid))
    lit_obs, lit_sources = literature("localisation", query.gene, query.species)
    releases = sorted({p["release"] for p in proteins.values() if p and p.get("release")})
    return LayerResult(
        gene=query.gene, species=query.species, layer="localisation",
        status=_STATUS.get(detail["status"], "unavailable"),
        observations=observations + lit_obs if observations else [],
        source_records=sources + lit_sources if observations else [],
        # dict.fromkeys drops repeated caveats while keeping their order.
        limitations=list(dict.fromkeys(detail["limitations"])),
        data_version=("UniProt " + ", ".join(releases)) if releases else None,
    )


def run_localisation(query: ResolvedQuery) -> LayerResult:
    """Pipeline layer: (ResolvedQuery) -> LayerResult."""
    # Offline demo evidence first, only when ASRA_FIXTURES is on (tools/fixtures.py).
    demo = fixture("localisation", query)
    if demo:
        return demo
    if query.gene is None:
        return unavailable("localisation", query, "Needs a resolved gene identifier; none was supplied.")
    return to_layer_result(compare_localisation(query.gene, query.species), query)


def _main() -> int:
    """Manual live-API smoke test; JSON is printed even when an API call fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol, for example SLC29A1")
    parser.add_argument("species", help="Animal species, for example mouse or mus_musculus")
    args = parser.parse_args()
    result = compare_localisation(args.gene, args.species)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] in {"error", "unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(_main())
