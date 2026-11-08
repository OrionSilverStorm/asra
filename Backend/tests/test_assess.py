from __future__ import annotations
"""End-to-end tests for the HTTP API and the contract it returns."""

from fastapi.testclient import TestClient

from agents.sceptic import review
from contract import Finding, LayerResult, Observation, SourceRecord
from main import app

client = TestClient(app)

# Made-up test sequence (not a real protein); 66 valid residues.
SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQ"


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_assess_returns_contract_shape():
    res = client.post("/assess", json={"species": "mus_musculus", "sequence": SEQ, "sequenceLabel": "demo"})
    assert res.status_code == 200
    body = res.json()
    # camelCase report fields, as the frontend expects
    assert {"id", "generatedAt", "origin", "sequenceStats", "layers", "findings"} <= body.keys()
    assert body["origin"] == "live"
    assert body["sequenceStats"]["length"] == len(SEQ)
    # four layers, in order, snake_case contract fields
    assert [l["layer"] for l in body["layers"]] == ["sequence", "localisation", "cell_expression", "tissue_expression"]
    assert "source_records" in body["layers"][0]
    # observations inside layers keep their camelCase alias
    assert body["layers"][0]["observations"][0]["sourceRecordId"] == "user_input"


def test_assess_rejects_bad_sequence():
    res = client.post("/assess", json={"species": "mus_musculus", "sequence": "MKTAYB1ZJO"})
    assert res.status_code == 422


def test_assess_rejects_unknown_species():
    res = client.post("/assess", json={"species": "felis_catus", "sequence": SEQ})
    assert res.status_code == 422


def test_sceptic_rejects_uncited_and_flags_incomplete():
    layers = [LayerResult(species="mus_musculus", layer="sequence", status="incomplete",
                          observations=[Observation(field="x", value="v", source_record_id="s1")],
                          source_records=[SourceRecord(id="s1", source="test")])]
    cited = Finding(id="a", claim="c", mechanism="m", concern="high", cited_field="sequence.x", source_record_id="s1")
    uncited = cited.model_copy(update={"id": "b", "source_record_id": "missing"})
    # use_llm=False: this test covers the deterministic pass only.
    accepted, feedback = review([cited, uncited], layers, use_llm=False)
    assert [f.id for f in accepted] == ["a"] and accepted[0].concern == "flagged"
    assert len(feedback) == 1
