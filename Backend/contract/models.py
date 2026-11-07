"""The universal JSON contract, as Pydantic models.

Every stage of the pipeline reads and writes these types, and FastAPI uses
them to validate requests and serialise responses. They mirror
Frontend/lib/types.ts field-for-field. If you change one, change the other
(and the spec in claude.md).

Naming on the wire:
- LayerResult uses snake_case (`source_records`, `data_version`), exactly as
  in the design doc's contract.
- Everything else uses camelCase (`generatedAt`, `sequenceStats`, ...), which
  is what the frontend expects. Python code always uses snake_case attributes;
  `CamelModel` converts them to camelCase aliases automatically.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

# ── Enumerations (kept as Literals so they serialise as plain strings) ──────

# Ensembl-style species IDs offered by the frontend dropdown.
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

# The four evidence layers, in display order.
LayerName = Literal["sequence", "localisation", "cell_expression", "tissue_expression"]

# ok = ran with data; incomplete = partial data; unavailable = did not run / failed.
LayerStatus = Literal["ok", "incomplete", "unavailable"]

# Qualitative concern on a finding. Deliberately not a number (no risk scores).
Concern = Literal["high", "moderate", "low", "flagged"]

# Whether a report came from the real pipeline or the frontend's mock.
DataOrigin = Literal["mock", "live"]

# The 20 standard amino acids plus X (unknown), shared with tools/sequence_stats.
VALID_RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWYX")
MIN_SEQUENCE_LENGTH = 10


class CamelModel(BaseModel):
    """Base for models serialised in camelCase.

    `populate_by_name` lets Python code construct models with snake_case
    names while JSON input/output uses the camelCase aliases.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ── Request ────────────────────────────────────────────────────────────────


class AssessmentRequest(CamelModel):
    """Body of POST /assess, sent by the frontend form."""

    species: SpeciesId
    # Normalised sequence: uppercase residues only (the frontend strips FASTA
    # headers, whitespace and digits before sending).
    sequence: str
    # FASTA header without ">", or null for a raw sequence.
    sequence_label: Optional[str] = None

    @field_validator("sequence")
    @classmethod
    def _check_sequence(cls, value: str) -> str:
        """Re-validate on the server; never trust the client alone."""
        value = value.strip().upper()
        bad = sorted(set(value) - VALID_RESIDUES)
        if bad:
            raise ValueError(f"Invalid residue characters: {', '.join(bad)}")
        if len(value) < MIN_SEQUENCE_LENGTH:
            raise ValueError(f"Sequence must be at least {MIN_SEQUENCE_LENGTH} residues.")
        return value


# ── Layer contract (design doc, "The contract") ────────────────────────────


class SourceRecord(BaseModel):
    """A citation: where a piece of evidence came from."""

    id: str  # stable ID, e.g. a UniProt accession or dataset ID
    source: str  # database / publication name
    url: Optional[str] = None


class Observation(CamelModel):
    """One measured fact inside a layer (field name + display value)."""

    field: str
    value: str
    # Points at SourceRecord.id so every value is traceable.
    source_record_id: Optional[str] = None


class LayerResult(BaseModel):
    """What every layer returns. snake_case on the wire, per the design doc."""

    gene: Optional[str] = None
    species: SpeciesId
    layer: LayerName
    status: LayerStatus
    observations: list[Observation] = Field(default_factory=list)
    source_records: list[SourceRecord] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_version: Optional[str] = None

    # Observations are CamelModels nested inside a snake_case model; this makes
    # sure they still serialise with their camelCase alias.
    model_config = ConfigDict(serialize_by_alias=True)


# ── Agent output ───────────────────────────────────────────────────────────


class Finding(CamelModel):
    """A claim from the agents. Must always cite a layer field and a source."""

    id: str
    claim: str
    mechanism: str
    concern: Concern
    cited_field: str  # "<layer>.<field>"
    source_record_id: str
    sceptic_note: Optional[str] = None


# ── Report ─────────────────────────────────────────────────────────────────


class ResidueFraction(BaseModel):
    """One row of the composition table."""

    residue: str
    fraction: float


class SequenceStats(CamelModel):
    """Basic statistics computed from the submitted sequence."""

    length: int
    # Explicit alias: the "kDa" unit doesn't camel-case cleanly by rule.
    estimated_mass_k_da: float = Field(alias="estimatedMassKDa")
    composition: list[ResidueFraction]


class Report(CamelModel):
    """The full response of POST /assess, rendered by the frontend's ReportView."""

    id: str
    generated_at: str  # ISO-8601 UTC timestamp
    origin: DataOrigin
    request: AssessmentRequest
    sequence_stats: SequenceStats
    layers: list[LayerResult]
    findings: list[Finding] = Field(default_factory=list)
    recommended_experiments: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
