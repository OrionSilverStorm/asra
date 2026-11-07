"""Gene-from-label rules and the pipeline sequence-layer wrapper (offline)."""

import json
from unittest.mock import patch

import pytest

from contract import AssessmentRequest
from tools import LAYERS
from tools.resolver import (AmbiguousOrthologueError, EnsemblAPIError, ResolvedQuery,
                            gene_from_label, resolve)
from tools.sequence_layer import run_sequence_layer

SEQ = "MACKMACKMACKMACK"


@pytest.mark.parametrize("label,gene", [
    # UniProt header with a human GN= -> that symbol, never the "sp" prefix
    ("sp|Q99808|S29A1_HUMAN Equilibrative nucleoside transporter 1 OS=Homo sapiens OX=9606 GN=SLC29A1 PE=1 SV=3", "SLC29A1"),
    # _HUMAN entry name counts as human when OS= is absent
    ("sp|P10747|CD28_HUMAN T-cell-specific surface glycoprotein CD28 GN=CD28", "CD28"),
    # Bare uppercase symbol
    ("SLC29A1", "SLC29A1"),
    # The case the old first-token rule got wrong
    ("sp|Q99808|S29A1_HUMAN Equilibrative nucleoside transporter 1", None),
    ("sp|P01308|INS_HUMAN Insulin", None),
    # Non-human organism: GN= is the animal's gene, not a human symbol
    ("sp|Q9JIM1|S29A1_MOUSE ENT1 OS=Mus musculus OX=10090 GN=Slc29a1", None),
    # Free text and lowercase labels are not symbols
    ("test|DEMO1|Example protein", None),
    ("demo", None),
    (None, None),
])
def test_gene_from_label(label, gene):
    assert gene_from_label(label) == gene


def test_resolve_never_guesses_sp():
    request = AssessmentRequest(species="mus_musculus", sequence=SEQ, sequence_label="sp|Q99808|S29A1_HUMAN")
    assert resolve(request).gene is None


def test_registry_uses_wrapper():
    assert LAYERS["sequence"] is run_sequence_layer


def test_no_gene_uses_legacy_fallback_without_network():
    with patch("tools.sequence.resolve_orthologue") as lookup:
        layer = run_sequence_layer(ResolvedQuery("mus_musculus", SEQ, None))
    lookup.assert_not_called()
    assert layer.status == "incomplete"
    assert layer.observations[0].field == "animal_length"


def test_gene_runs_full_comparison_and_adapter():
    resolved = {
        "gene": "SYNTHETIC", "species": "mus_musculus",
        "source": {"protein_id": "H", "sequence": "ACDEFGHIKLMNPQRSTVWY"},
        "target": {"protein_id": "A", "sequence": "ACDEFGHIKIMNPQRSTVWY"},
        "orthology": {"type": "ortholog_one2one"}, "source_url": "https://example.org/evidence",
    }
    # functional=True also calls UniProt (imported lazily from sequence_functional);
    # stub it to return the input unchanged so the test stays offline.
    with patch("tools.sequence.resolve_orthologue", return_value=resolved), \
         patch("tools.sequence_functional.add_functional_analysis", side_effect=lambda r, **_: r) as functional:
        layer = run_sequence_layer(ResolvedQuery("mus_musculus", SEQ, None, "SYNTHETIC"))
    functional.assert_called_once()
    fields = {o.field: json.loads(o.value) for o in layer.observations}
    assert layer.layer == "sequence"
    assert fields["measurements"]["identity_percent"] == pytest.approx(95.0)


def test_ambiguous_orthologue_keeps_candidates():
    candidates = [{"target": {"id": "A"}}, {"target": {"id": "B"}}]
    with patch("tools.sequence_layer.run_sequence", side_effect=AmbiguousOrthologueError("two", candidates)):
        layer = run_sequence_layer(ResolvedQuery("danio_rerio", SEQ, None, "SLC29A1"))
    assert layer.status == "unavailable"
    assert json.loads(layer.observations[0].value) == candidates
    assert layer.observations[0].source_record_id == layer.source_records[0].id


def test_api_failure_is_unavailable_with_reason():
    with patch("tools.sequence_layer.run_sequence", side_effect=EnsemblAPIError("timed out")):
        layer = run_sequence_layer(ResolvedQuery("mus_musculus", SEQ, None, "SLC29A1"))
    assert layer.status == "unavailable"
    assert "EnsemblAPIError" in layer.limitations[0]
