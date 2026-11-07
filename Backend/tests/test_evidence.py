"""Prompt compaction keeps every citation target while shrinking sequence evidence."""

import json

from agents.evidence import compact_for_prompt
from contract import LayerResult, Observation
from tools.sequence_adapter import to_layer_result
from tools.sequence_demo import demonstration


def _layer():
    # Offline SLC29A1 human-vs-mouse result with functional analysis (recorded data).
    return to_layer_result(demonstration())


def test_compacts_sequence_layer_below_budget():
    full = json.dumps(_layer().model_dump(mode="json"))
    compact = json.dumps(compact_for_prompt([_layer()]))
    assert len(full) > 100_000
    assert len(compact) < 20_000  # measured ~12.8k for SLC29A1


def test_citation_targets_unchanged():
    layer = _layer()
    [compact] = compact_for_prompt([layer])
    before = [(o.field, o.source_record_id) for o in layer.observations]
    after = [(o["field"], o["source_record_id"]) for o in compact["observations"]]
    assert before == after
    assert [s["id"] for s in compact["source_records"]] == [s.id for s in layer.source_records]


def test_keeps_measurements_and_motif_drops_maps():
    [compact] = compact_for_prompt([_layer()])
    values = {o["field"]: json.loads(o["value"]) for o in compact["observations"]}
    assert values["measurements"]["identity_percent"] > 79
    assert "E72A" in values["substitutions"]
    assert values["human_to_animal"].startswith("omitted from prompt")
    assert "sequence" not in values["human"]
    assert values["functional_analysis"]["slc29a1_motif"]["sequence_observation"]["human_window"] == "PERN"


def test_plain_string_layers_untouched():
    layer = LayerResult(gene="X", species="mus_musculus", layer="localisation", status="incomplete",
                        observations=[Observation(field="shared_compartments", value="Plasma membrane")])
    [compact] = compact_for_prompt([layer])
    assert compact == layer.model_dump(mode="json")


def test_tolerates_null_parts_from_live_data():
    # Live UniProt can leave identity/features null (unverified mapping); found in a live run.
    rich = demonstration()
    rich["functional_analysis"]["proteins"]["animal"]["identity"] = None
    rich["functional_analysis"]["proteins"]["animal"]["features"] = None
    [compact] = compact_for_prompt([to_layer_result(rich)])
    values = {o["field"]: json.loads(o["value"]) for o in compact["observations"]}
    assert values["functional_analysis"]["proteins"]["animal"]["identity"]["accession"] is None
    assert values["functional_analysis"]["proteins"]["animal"]["feature_count"] == 0
