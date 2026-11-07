"""The universal JSON contract shared by every pipeline stage and the frontend.

Import from here (`from contract import LayerResult`) rather than from
contract.models, so the module layout can change without touching callers.
"""

from contract.models import (
    AssessmentRequest,
    Concern,
    Finding,
    LayerName,
    LayerResult,
    LayerStatus,
    Observation,
    Report,
    ResidueFraction,
    SequenceStats,
    SourceRecord,
    SpeciesId,
)

__all__ = [
    "AssessmentRequest",
    "Concern",
    "Finding",
    "LayerName",
    "LayerResult",
    "LayerStatus",
    "Observation",
    "Report",
    "ResidueFraction",
    "SequenceStats",
    "SourceRecord",
    "SpeciesId",
]
