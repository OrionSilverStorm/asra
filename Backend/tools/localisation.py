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
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import json
import re
from typing import Any, Literal, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from contract import (
        LayerName,
        LayerResult,
        LayerStatus,
        Observation,
        SourceRecord,
        SpeciesId,
    )
except ImportError:
    try:
        from Backend.contract import (
            LayerName,
            LayerResult,
            LayerStatus,
            Observation,
            SourceRecord,
            SpeciesId,
        )
    except ImportError:
        from pydantic import BaseModel, ConfigDict, Field
        from pydantic.alias_generators import to_camel

        SpeciesId = Literal[
            "mus_musculus",
            "rattus_norvegicus",
            "macaca_mulatta",
            "macaca_fascicularis",
            "canis_lupus_familiaris",
            "sus_scrofa",
            "oryctolagus_cuniculus",
            "cavia_porcellus",
            "danio_rerio",
        ]
        LayerName = Literal[
            "sequence", "localisation", "cell_expression", "tissue_expression"
        ]
        LayerStatus = Literal["ok", "incomplete", "unavailable"]

        class _CamelModel(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel, populate_by_name=True
            )

        class SourceRecord(BaseModel):
            """A citation: where a piece of evidence came from."""

            id: str
            source: str
            url: Optional[str] = None

        class Observation(_CamelModel):
            """One measured fact inside a layer (field name + display value)."""

            field: str
            value: str
            source_record_id: Optional[str] = None

        class LayerResult(BaseModel):
            """What every layer returns. snake_case on the wire, per the contract."""

            gene: Optional[str] = None
            species: SpeciesId
            layer: LayerName
            status: LayerStatus
            observations: list[Observation] = Field(default_factory=list)
            source_records: list[SourceRecord] = Field(default_factory=list)
            limitations: list[str] = Field(default_factory=list)
            data_version: Optional[str] = None

            model_config = ConfigDict(serialize_by_alias=True)


try:
    from tools.resolver import ResolvedQuery
except ImportError:
    try:
        from Backend.tools.resolver import ResolvedQuery
    except ImportError:

        @dataclass(frozen=True)
        class ResolvedQuery:
            """Everything a layer may need, resolved once and shared by all layers."""

            species: SpeciesId
            sequence: str = ""
            sequence_label: Optional[str] = None
            gene: Optional[str] = None


try:
    from tools.base import unavailable as _base_unavailable
except ImportError:
    try:
        from Backend.tools.base import unavailable as _base_unavailable
    except ImportError:

        def _base_unavailable(
            layer: LayerName, query: ResolvedQuery, reason: str
        ) -> LayerResult:
            return LayerResult(
                gene=query.gene,
                species=query.species,
                layer=layer,
                status="unavailable",
                limitations=[reason],
            )



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


_MISSING = object()

_STATUS_TO_LAYER_STATUS: dict[str, LayerStatus] = {
    "complete": "ok",
    "partial": "incomplete",
    "unavailable": "unavailable",
    "error": "unavailable",
}


def _slugify_token(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "term"


def _format_evidence_list(evidence_items: list[dict[str, Any]]) -> str:
    if not evidence_items:
        return "none"
    parts: list[str] = []
    for ev in evidence_items:
        code = ev.get("evidenceCode") or "unknown_code"
        src = ev.get("source")
        ident = ev.get("id")
        if src and ident:
            parts.append(f"{code}/{src}:{ident}")
        elif src:
            parts.append(f"{code}/{src}")
        else:
            parts.append(str(code))
    return ", ".join(parts)


def _format_location_entry(loc: dict[str, Any]) -> str:
    loc_id = loc.get("id") or "no-id"
    details = [
        f"id={loc_id}",
        f"support={loc.get('evidence_support', 'missing')}",
        f"evidence={_format_evidence_list(loc.get('evidence', []))}",
    ]
    if loc.get("molecule"):
        details.append(f"molecule={loc['molecule']}")
    if isinstance(loc.get("topology"), dict) and loc["topology"].get("name"):
        details.append(f"topology={loc['topology']['name']}")
    if isinstance(loc.get("orientation"), dict) and loc["orientation"].get("name"):
        details.append(f"orientation={loc['orientation']['name']}")
    return f"{loc['name']} ({'; '.join(details)})"


def to_layer_result(
    raw: dict[str, Any],
    query: Optional[ResolvedQuery] = None,
) -> LayerResult:
    """Convert the 6-field localisation dict into a canonical ``LayerResult``."""
    measurements = raw.get("measurements") or {}
    proteins = measurements.get("proteins") or {"human": None, "animal": None}
    errors = measurements.get("errors") or []
    comparison = measurements.get("comparison") or {}

    gene_val: Optional[str] = measurements.get("gene") or (
        query.gene if query is not None else None
    )
    species_val: SpeciesId = (
        measurements.get("species")
        or (query.species if query is not None else "mus_musculus")
    )
    layer_status: LayerStatus = _STATUS_TO_LAYER_STATUS.get(
        str(raw.get("status", "unavailable")), "unavailable"
    )

    # Build deduplicated SourceRecord list from protein records and evidence citations
    source_records: list[SourceRecord] = []
    seen_source_ids: set[str] = set()
    releases: list[str] = []

    for src in raw.get("sources") or []:
        rel = src.get("release")
        if isinstance(rel, str) and rel and rel not in releases:
            releases.append(rel)
        if src.get("kind") == "protein_record":
            acc = str(src["id"])
            if acc not in seen_source_ids:
                seen_source_ids.add(acc)
                side_protein = next(
                    (p for p in proteins.values() if p and p.get("accession") == acc),
                    None,
                )
                sci_name = (
                    side_protein.get("scientific_name")
                    if isinstance(side_protein, dict)
                    else None
                )
                reviewed_label = (
                    "reviewed (Swiss-Prot)"
                    if isinstance(side_protein, dict) and side_protein.get("reviewed")
                    else "unreviewed (TrEMBL)"
                )
                version_str = (
                    f", version={src.get('entry_version')}"
                    if src.get("entry_version") is not None
                    else ""
                )
                release_str = f", release={rel}" if rel else ""
                source_records.append(
                    SourceRecord(
                        id=acc,
                        source=(
                            f"UniProtKB {reviewed_label} {acc} "
                            f"({sci_name or 'taxon ' + str(src.get('taxon_id'))}"
                            f"{version_str}{release_str})"
                        ),
                        url=src.get("url"),
                    )
                )

    for side in ("human", "animal"):
        protein = proteins.get(side)
        if not isinstance(protein, dict):
            continue
        for loc in protein.get("locations") or []:
            for ev in loc.get("evidence") or []:
                ev_src = ev.get("source")
                ev_id = ev.get("id")
                ev_code = ev.get("evidenceCode") or "evidence"
                if isinstance(ev_src, str) and isinstance(ev_id, str) and ev_id:
                    rec_id = f"{ev_src}:{ev_id}"
                    if rec_id not in seen_source_ids:
                        seen_source_ids.add(rec_id)
                        source_records.append(
                            SourceRecord(
                                id=rec_id,
                                source=f"{ev_src} {ev_id} (UniProt {protein['accession']} {ev_code})",
                                url=ev.get("url"),
                            )
                        )

    observations: list[Observation] = []
    used_fields: set[str] = set()

    def _unique_field(base_field: str) -> str:
        candidate = base_field
        idx = 2
        while candidate in used_fields:
            candidate = f"{base_field}_{idx}"
            idx += 1
        used_fields.add(candidate)
        return candidate

    # 1. Per-species protein metadata, subcellular locations, and notes
    for side in ("human", "animal"):
        protein = proteins.get(side)
        if not isinstance(protein, dict):
            continue
        acc = protein["accession"]
        observations.append(
            Observation(
                field=_unique_field(f"{side}_protein"),
                value=(
                    f"{acc} ({protein.get('scientific_name') or side}; "
                    f"taxon_id={protein['taxon_id']}; "
                    f"reviewed={protein['reviewed']}; "
                    f"entry_version={protein.get('entry_version')})"
                ),
                source_record_id=acc,
            )
        )
        locs = protein.get("locations") or []
        if locs:
            locs_formatted = "; ".join(_format_location_entry(loc) for loc in locs)
        else:
            locs_formatted = (
                f"No structured SUBCELLULAR LOCATION annotations in UniProt record {acc}; "
                "localisation is unannotated/unknown (does not establish biological absence)"
            )
        observations.append(
            Observation(
                field=_unique_field(f"{side}_subcellular_locations"),
                value=locs_formatted,
                source_record_id=acc,
            )
        )
        notes = protein.get("notes") or []
        if notes:
            notes_formatted = "; ".join(
                f"{n.get('text', '')} (evidence={_format_evidence_list(n.get('evidence', []))})"
                for n in notes
                if n.get("text")
            )
            if notes_formatted:
                observations.append(
                    Observation(
                        field=_unique_field(f"{side}_location_notes"),
                        value=notes_formatted,
                        source_record_id=acc,
                    )
                )

    # 2. Convert legacy observations into canonical Observation objects
    for obs in raw.get("observations") or []:
        obs_type = obs.get("type") or "observation"
        loc_id = obs.get("location_id")
        src_ids = [
            str(sid) for sid in (obs.get("source_ids") or []) if str(sid) in seen_source_ids
        ]
        if not src_ids:
            continue

        if obs_type == "overlapping_annotation":
            token = _slugify_token(loc_id or obs.get("statement", "location"))
            observations.append(
                Observation(
                    field=_unique_field(f"overlapping_location_{token}"),
                    value=(
                        f"{obs['statement']} "
                        f"(location_id={loc_id}; sources={', '.join(src_ids)})"
                    ),
                    source_record_id=src_ids[0],
                )
            )
        elif obs_type == "annotation_difference":
            token = _slugify_token(loc_id or obs.get("statement", "location"))
            ev_support = obs.get("evidence_support") or {}
            # Cite the specific protein record carrying the positive annotation
            annotated_side = next(iter(ev_support.keys()), None)
            cited_acc = src_ids[0]
            if (
                annotated_side in proteins
                and isinstance(proteins[annotated_side], dict)
                and proteins[annotated_side]["accession"] in seen_source_ids
            ):
                cited_acc = proteins[annotated_side]["accession"]
            support_summary = ", ".join(
                f"{side}={','.join(codes)}" for side, codes in sorted(ev_support.items())
            )
            observations.append(
                Observation(
                    field=_unique_field(f"annotation_difference_{token}"),
                    value=(
                        f"{obs['statement']} "
                        f"(location_id={loc_id}; evidence_support: {support_summary})"
                    ),
                    source_record_id=cited_acc,
                )
            )
        elif obs_type == "incomplete_evidence":
            observations.append(
                Observation(
                    field=_unique_field("evidence_completeness"),
                    value=str(obs["statement"]),
                    source_record_id=src_ids[0],
                )
            )

    # 3. Overall comparison summary
    primary_protein = proteins.get("human") or proteins.get("animal")
    if isinstance(primary_protein, dict) and comparison:
        observations.append(
            Observation(
                field=_unique_field("comparison_summary"),
                value=(
                    f"comparison_status={comparison.get('status')}; "
                    f"overlapping_locations={len(comparison.get('overlapping_locations', []))}; "
                    f"human_only_annotations={len(comparison.get('human_only_annotations', []))}; "
                    f"animal_only_annotations={len(comparison.get('animal_only_annotations', []))}; "
                    f"supported_annotation_differences={len(comparison.get('supported_annotation_differences', []))}; "
                    f"biological_difference_supported={comparison.get('biological_difference_supported', False)} "
                    "(missing annotations never establish biological absence)"
                ),
                source_record_id=primary_protein["accession"],
            )
        )

    # Preserve all scientific limitations and append any top-level error messages
    limitations = list(raw.get("limitations") or [])
    for err in errors:
        msg = err.get("message")
        side = err.get("side")
        formatted_err = f"{side}: {msg}" if side else str(msg)
        if msg and formatted_err not in limitations and str(msg) not in limitations:
            limitations.append(formatted_err)

    data_version: Optional[str] = None
    if releases:
        data_version = f"UniProtKB release {', '.join(releases)}"
    elif source_records:
        data_version = "UniProtKB REST API"

    return LayerResult(
        gene=gene_val,
        species=species_val,
        layer="localisation",
        status=layer_status,
        observations=observations,
        source_records=source_records,
        limitations=limitations,
        data_version=data_version,
    )


def _run_localisation_dict(gene: str, species: str) -> dict:
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


def run_localisation_layer(
    query: Union[ResolvedQuery, str, None],
    species: Optional[SpeciesId] = None,
) -> LayerResult:
    """Always return a canonical ``LayerResult`` from either ``ResolvedQuery`` or ``(gene, species)``."""
    if hasattr(query, "species") and hasattr(query, "gene"):
        resolved: ResolvedQuery = query  # type: ignore[assignment]
    else:
        target_species: SpeciesId = species or "mus_musculus"
        gene_str: Optional[str] = (
            query.strip() if isinstance(query, str) and query.strip() else None
        )
        resolved = ResolvedQuery(
            species=target_species,
            sequence="",
            sequence_label=gene_str,
            gene=gene_str,
        )

    if resolved.gene is None or not str(resolved.gene).strip():
        return _base_unavailable(
            "localisation",
            resolved,
            "Needs a resolved gene identifier; none was supplied.",
        )

    raw = _run_localisation_dict(str(resolved.gene), str(resolved.species))
    return to_layer_result(raw, resolved)


def run_localisation(
    gene: Union[ResolvedQuery, str, None],
    species: Any = _MISSING,
) -> Union[LayerResult, dict]:
    """Run UniProt subcellular localisation comparison.

    - When called by the canonical ASRA pipeline with a single ``ResolvedQuery``
      (``run_localisation(query: ResolvedQuery) -> LayerResult``), returns a
      validated ``LayerResult`` with ``status`` mapped to ``ok | incomplete | unavailable``
      and traceable ``Observation`` / ``SourceRecord`` objects.
    - When called with two arguments ``run_localisation(gene, species) -> dict``,
      returns the six-field standalone dictionary contract.
    """
    if species is _MISSING and (
        hasattr(gene, "species") and hasattr(gene, "gene")
    ):
        return run_localisation_layer(gene)  # type: ignore[arg-type]
    return _run_localisation_dict(gene, species)  # type: ignore[arg-type]


def _main() -> int:
    """Manual live-API smoke test; JSON is printed even when an API call fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol, for example SLC29A1")
    parser.add_argument("species", help="Animal species, for example mouse or mus_musculus")
    parser.add_argument(
        "--layer-result",
        action="store_true",
        help="Emit the canonical pipeline LayerResult JSON schema instead of the standalone 6-field dict.",
    )
    args = parser.parse_args()
    if args.layer_result:
        layer_res = run_localisation_layer(args.gene, args.species)
        payload = layer_res.model_dump(mode="json", by_alias=True)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1 if layer_res.status == "unavailable" else 0
    result = run_localisation(args.gene, args.species)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] in {"error", "unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(_main())
