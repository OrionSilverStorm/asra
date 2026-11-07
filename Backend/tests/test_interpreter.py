"""Interpreter tests with Gemini mocked out, so they run without an API key."""

from agents import interpreter, llm
from agents.interpreter import FindingDraft, interpret
from contract import LayerResult, Observation, SourceRecord

# One citable layer, shaped like a real layer result.
EVIDENCE = [LayerResult(
    species="mus_musculus", layer="sequence", status="ok",
    observations=[Observation(field="animal_length", value="66 aa", source_record_id="user_input")],
    source_records=[SourceRecord(id="user_input", source="Submitted sequence")],
)]


def test_no_key_means_no_findings(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    assert interpret(EVIDENCE).findings == []


def test_drafts_become_findings_with_our_ids(monkeypatch):
    draft = FindingDraft(claim="c", mechanism="m", concern="low",
                         cited_field="sequence.animal_length", source_record_id="user_input",
                         experiment="Measure it")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda prompt, schema, agent: [draft])
    out = interpret(EVIDENCE)
    [finding] = out.findings
    assert finding.id == "f1" and finding.source_record_id == "user_input"
    # The experiment is kept against the finding's id, not inside the Finding.
    assert out.experiments == {"f1": "Measure it"}


def test_model_failure_is_contained(monkeypatch):
    def boom(*_, **__):  # accept any args so the RuntimeError is what's raised
        raise RuntimeError("quota exceeded")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "ask_json", boom)
    assert interpret(EVIDENCE).findings == []


def test_prompt_contains_evidence_and_feedback():
    prompt = interpreter._build_prompt(EVIDENCE, ["Rejected 'x'"])
    assert "animal_length" in prompt and "Rejected 'x'" in prompt
