from __future__ import annotations
"""Role 3 adapter must preserve evidence and fail on schema changes."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result, EVIDENCE_FIELDS


@pytest.fixture
def rich():
    resolved = {
        "gene": "SYNTHETIC", "species": "mus_musculus",
        "source": {"protein_id": "H", "sequence": "ACDEFGHIKLMNPQRSTVWY"},
        "target": {"protein_id": "A", "sequence": "ACDEFGHIKIMNPQRSTVWY"},
        "orthology": {"type": "ortholog_one2one"}, "source_url": "https://example.org/evidence",
    }
    with patch("tools.sequence.resolve_orthologue", return_value=resolved):
        return run_sequence("SYNTHETIC", "mus_musculus")


def test_adapter_roundtrip_preserves_all_evidence(rich):
    before = deepcopy(rich)
    layer = to_layer_result(rich)
    wire = json.loads(layer.model_dump_json(by_alias=True))
    recovered = {o["field"]: json.loads(o["value"]) for o in wire["observations"]}
    assert set(recovered) == EVIDENCE_FIELDS
    for key in EVIDENCE_FIELDS:
        assert recovered[key] == json.loads(json.dumps(rich[key]))
    assert isinstance(recovered["measurements"]["exact_matches"], int)
    assert isinstance(recovered["measurements"]["identity_percent"], float)
    assert recovered["substitutions"][0]["human_position"] == 10
    assert wire["source_records"] == rich["source_records"]
    assert wire["limitations"][:len(rich["limitations"])] == rich["limitations"]
    for key in ("gene", "species", "layer", "status", "data_version"):
        assert wire[key] == rich[key]
    assert all(o["sourceRecordId"] == "ensembl_orthology" for o in wire["observations"])
    assert rich == before


@pytest.mark.parametrize("key", sorted(EVIDENCE_FIELDS))
def test_missing_evidence_is_never_silently_dropped(rich, key):
    del rich[key]
    with pytest.raises(ValueError, match="missing"):
        to_layer_result(rich)


def test_new_fields_require_adapter_review(rich):
    rich["new_evidence"] = {"important": 123}
    with pytest.raises(ValueError, match="unhandled"):
        to_layer_result(rich)


def test_new_nested_evidence_is_preserved(rich):
    rich["measurements"]["new_metric"] = 1.23456789
    adapted = to_layer_result(rich)
    obs = next(o for o in adapted.observations if o.field == "measurements")
    assert json.loads(obs.value)["new_metric"] == 1.23456789


def test_source_extensions_are_not_discarded(rich):
    rich["source_records"][0]["release"] = "unknown"
    with pytest.raises(ValueError, match="source record"):
        to_layer_result(rich)


def test_unsupported_species_fails_shared_contract_validation(rich):
    rich["species"] = "felis_catus"
    with pytest.raises(ValueError):
        to_layer_result(rich)
