"""Resolve human gene symbols to Ensembl animal orthologues.

The existing sequence-only pipeline adapter remains separate: a submitted
sequence alone does not identify a gene. No alignment is performed here.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
import time
import re
from typing import Optional
from urllib.parse import quote

import httpx

from contract import AssessmentRequest, SpeciesId


@dataclass(frozen=True)
class ResolvedQuery:
    """Everything a layer may need, resolved once and shared by all layers."""

    species: SpeciesId
    sequence: str
    sequence_label: Optional[str]
    # A sequence-only request supplies no gene symbol; do not guess one.
    gene: Optional[str] = None


# HGNC-style human symbol: uppercase letter first, then uppercase/digits/hyphen.
_SYMBOL = re.compile(r"[A-Z][A-Z0-9-]{0,19}")


def gene_from_label(label: Optional[str]) -> Optional[str]:
    """Return a human gene symbol stated explicitly in a FASTA label, else None.

    Two routes only (see INTEGRATE4U.md §3), never a first-token guess, so
    `sp|Q99808|S29A1_HUMAN` does not become gene "SP":
    1. A UniProt header's `GN=<symbol>`, accepted only when the header says
       the organism is human (OS=Homo sapiens or an _HUMAN entry name) and
       does not name another organism.
    2. A label that is exactly one uppercase symbol, e.g. "SLC29A1".
    """
    if not label:
        return None
    text = label.strip().lstrip(">").strip()
    gn = re.search(r"\bGN=(\S+)", text)
    if gn:
        organism = re.search(r"\bOS=(.+?)(?:\s+[A-Z]{2}=|$)", text)
        human = (organism.group(1).strip() == "Homo sapiens") if organism else "_HUMAN" in text
        return gn.group(1) if human and _SYMBOL.fullmatch(gn.group(1)) else None
    # Route 2: the whole label is a bare symbol (case-sensitive, so "demo" is not one).
    return text if _SYMBOL.fullmatch(text) else None


def resolve(request: AssessmentRequest) -> ResolvedQuery:
    """Build the shared query.

    The gene comes only from an explicit statement in sequence_label
    (`gene_from_label`); a bare sequence never yields a guessed gene.
    """
    gene = gene_from_label(request.sequence_label)

    return ResolvedQuery(
        species=request.species,
        sequence=request.sequence,
        sequence_label=request.sequence_label,
        gene=gene,
    )


# BLOSUM62 supports these ambiguous residues, but not J/O/U or stops.
SUPPORTED_RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWYBZX")


def validate_protein_sequence(sequence: str, label: str) -> None:
    """Validate unchanged data; even terminal stop markers require review."""
    if not isinstance(sequence, str) or not sequence:
        raise ValueError(f"{label} must be a non-empty protein sequence.")
    if "*" in sequence:
        location = "terminal" if sequence.endswith("*") and "*" not in sequence[:-1] else "internal or repeated"
        raise ValueError(f"{label} contains a {location} stop symbol; stops are not aligned or stripped.")
    bad = sorted(set(sequence) - SUPPORTED_RESIDUES)
    if bad:
        raise ValueError(f"{label} has unsupported residue characters: {', '.join(bad)}")


ENSEMBL_URL = "https://rest.ensembl.org"
REQUEST_TIMEOUT = 30.0


class OrthologueResolutionError(RuntimeError):
    """Base class for retrieval or Ensembl response errors."""


class EnsemblAPIError(OrthologueResolutionError):
    """A timeout, transport failure or unsuccessful HTTP response."""


class InvalidEnsemblResponseError(OrthologueResolutionError):
    """The response is malformed or does not match the requested species."""


class OrthologueNotFoundError(OrthologueResolutionError):
    """Ensembl returned no orthologue for this query."""


class MissingSequenceError(OrthologueResolutionError):
    """The relationship has no usable unaligned protein sequence."""


class AmbiguousOrthologueError(OrthologueResolutionError):
    """No unique one-to-one relationship; candidates need scientific review."""

    def __init__(self, message: str, candidates: list[dict]):
        super().__init__(message)
        # Retain every raw relationship, including its identifiers and metadata.
        self.candidates = candidates


def _protein_record(record: object, expected_species: str) -> dict:
    """Validate identifiers and the actual Ensembl `seq` field."""
    if not isinstance(record, dict):
        raise InvalidEnsemblResponseError("Missing source or target record.")
    if record.get("species") != expected_species:
        raise InvalidEnsemblResponseError(
            f"Expected species {expected_species!r}, got {record.get('species')!r}."
        )
    for field in ("id", "protein_id"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise InvalidEnsemblResponseError(f"Missing {expected_species} {field}.")
    sequence = record.get("seq")
    if not isinstance(sequence, str) or not sequence.strip():
        raise MissingSequenceError(f"Missing {expected_species} protein sequence (seq).")
    try:
        validate_protein_sequence(sequence, expected_species)
    except ValueError as exc:
        raise MissingSequenceError(str(exc)) from exc
    return {
        "gene_id": record["id"],
        "protein_id": record["protein_id"],
        "species": record["species"],
        "sequence": sequence,
        # Preserve optional API evidence such as taxon_id, perc_id and perc_pos.
        "metadata": {key: value for key, value in record.items()
                     if key not in {"id", "protein_id", "species", "seq"}},
    }


def resolve_orthologue(gene: str, species: str) -> dict:
    """Retrieve one human-to-animal protein orthologue by human gene symbol.

    `species` is an Ensembl identifier, e.g. mus_musculus,
    oryctolagus_cuniculus, cavia_porcellus or macaca_mulatta. Identifiers
    are not limited to the frontend dropdown; Ensembl validates availability.

    Return a JSON-compatible dictionary with gene, species, source, target,
    orthology (unmodified relationship metadata), and source_url. Source and
    target contain gene_id, protein_id, species, sequence and optional metadata.
    No release, confidence score or biological annotation is manufactured.

    Invalid inputs raise ValueError before HTTP. Retrieval failures raise
    EnsemblAPIError; malformed data, absent orthologues and missing sequences
    have separate exceptions. Multiple source genes, multiple relationships,
    or a non-one-to-one relationship raise AmbiguousOrthologueError with all
    raw candidates, even when only one target was returned by the filter.
    A unique one-to-one call does not establish functional equivalence.
    """
    if not isinstance(gene, str) or not gene.strip():
        raise ValueError("gene must be a non-empty human gene symbol.")
    gene = gene.strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", gene) is None:
        raise ValueError("gene must be a gene symbol without whitespace or URL delimiters.")
    if not isinstance(species, str):
        raise ValueError("species must be an Ensembl species identifier.")
    species = species.strip()
    if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", species) is None:
        raise ValueError("species must be an Ensembl identifier such as mus_musculus.")
    if species == "homo_sapiens":
        raise ValueError("species must be an animal comparison species other than human.")

    url = f"{ENSEMBL_URL}/homology/symbol/homo_sapiens/{quote(gene, safe='')}"
    try:
        response = httpx.get(
            url,
            params={"target_species": species, "type": "orthologues",
                    "sequence": "protein", "aligned": 0, "format": "full"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise EnsemblAPIError(f"Ensembl timed out resolving {gene} to {species}.") from exc
    except httpx.HTTPStatusError as exc:
        raise EnsemblAPIError(
            f"Ensembl HTTP {exc.response.status_code} resolving {gene} to {species}."
        ) from exc
    except httpx.RequestError as exc:
        raise EnsemblAPIError(f"Ensembl request failed for {gene} to {species}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise InvalidEnsemblResponseError("Ensembl did not return valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise InvalidEnsemblResponseError("Ensembl response must contain a data list.")
    records = payload["data"]
    candidates = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("homologies"), list):
            raise InvalidEnsemblResponseError("Ensembl gene record must contain a homologies list.")
        for relationship in record["homologies"]:
            if not isinstance(relationship, dict):
                raise InvalidEnsemblResponseError("Invalid Ensembl homology record.")
            candidates.append(relationship)
    if not candidates:
        raise OrthologueNotFoundError(f"No Ensembl orthologue found for {gene} to {species}.")
    # Count first: neither confidence nor response order justifies picking one.
    if (len(records) != 1 or len(candidates) != 1
            or candidates[0].get("type") != "ortholog_one2one"):
        raise AmbiguousOrthologueError(
            f"{gene} to {species} is not a unique one-to-one orthologue "
            f"({len(records)} source records, {len(candidates)} relationships); "
            "a justified biological selection is required.",
            candidates,
        )
    relationship = candidates[0]
    return {
        "gene": gene,
        "species": species,
        "source": _protein_record(relationship.get("source"), "homo_sapiens"),
        "target": _protein_record(relationship.get("target"), species),
        "orthology": {key: value for key, value in relationship.items()
                      if key not in {"source", "target"}},
        "source_url": str(response.url),
    }


# Successful orthologue lookups, cached on first fetch (design doc: data/cache/)
# so the expression layers survive an Ensembl outage for genes seen before.
_GENE_ID_CACHE = Path(__file__).resolve().parents[1] / "data" / "cache" / "orthologue_gene_ids.json"
_cache_lock = Lock()  # layers run in parallel threads and may write together


def _with_retry(fn, *args):
    """Call fn once more after a short pause if Ensembl fails transiently (5xx/timeouts)."""
    try:
        return fn(*args)
    except EnsemblAPIError:
        time.sleep(2)
        return fn(*args)


def _symbol_gene_id(gene: str, species: str) -> str | None:
    """Ensembl gene ID for the same symbol in the animal (e.g. GAPDH -> mouse Gapdh), or None."""
    response = httpx.get(f"{ENSEMBL_URL}/lookup/symbol/{species}/{quote(gene, safe='')}",
                         headers={"Accept": "application/json"}, timeout=REQUEST_TIMEOUT)
    if response.status_code == 400:  # Ensembl's "symbol not found"
        return None
    if response.status_code >= 500:
        raise EnsemblAPIError(f"Ensembl HTTP {response.status_code} looking up {gene} in {species}.")
    response.raise_for_status()
    return response.json().get("id")


def _resolve_gene_id(gene: str, species: str) -> dict:
    """{'gene_id', 'note'}: the one-to-one orthologue, or a justified pick among candidates.

    When Ensembl lists several orthologues, a candidate is accepted only if it
    is also the animal gene with the identical symbol, so orthology and
    nomenclature agree; otherwise the ambiguity is raised unchanged.
    """
    try:
        return {"gene_id": _with_retry(resolve_orthologue, gene, species)["target"]["gene_id"], "note": None}
    except AmbiguousOrthologueError as exc:
        candidates = {c.get("target", {}).get("id") for c in exc.candidates}
        same = _with_retry(_symbol_gene_id, gene, species)
        if same not in candidates:
            raise
        kinds = ", ".join(sorted({str(c.get("type")) for c in exc.candidates}))
        return {"gene_id": same, "note": f"Ensembl lists {len(candidates)} {species} orthologues of {gene} ({kinds}); "
                                         f"{same} was used because it also carries the same gene symbol."}


def orthologue_gene_id(gene: str, species: str) -> tuple[str, str | None]:
    """(Ensembl gene ID, selection note or None) of a human symbol's animal orthologue.

    Shared by the expression layers, which need the animal gene rather than its
    protein. Hits come from the on-disk cache; misses query Ensembl and are then
    cached. Failures raise OrthologueResolutionError and are never cached.
    """
    key = f"{gene.upper()}|{species}"
    with _cache_lock:
        cache = json.loads(_GENE_ID_CACHE.read_text(encoding="utf-8")) if _GENE_ID_CACHE.exists() else {}
    if key not in cache:
        entry = _resolve_gene_id(gene, species)
        with _cache_lock:
            cache = json.loads(_GENE_ID_CACHE.read_text(encoding="utf-8")) if _GENE_ID_CACHE.exists() else {}
            cache[key] = entry
            _GENE_ID_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _GENE_ID_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return cache[key]["gene_id"], cache[key]["note"]
