"""Resolve human gene symbols to Ensembl animal orthologues.

The existing sequence-only pipeline adapter remains separate: a submitted
sequence alone does not identify a gene. No alignment is performed here.
"""

from dataclasses import dataclass
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


def resolve(request: AssessmentRequest) -> ResolvedQuery:
    """Build the shared query.

    A gene symbol is taken only from an explicit sequence_label; a bare
    sequence never yields a guessed gene (gene stays None).
    """
    gene: Optional[str] = None
    if request.sequence_label:
        candidate = request.sequence_label.strip().lstrip(">").strip()
        if candidate:
            # Extract first token, removing common FASTA delimiters like pipe or space
            gene = candidate.split()[0].split("|")[0].strip().upper()

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
