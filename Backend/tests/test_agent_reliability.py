from __future__ import annotations
"""Gemini failure visibility and experiment recommendations (all Gemini calls mocked)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents import interpreter, llm
from agents.interpreter import API_FAILED, NOT_CONFIGURED, Draft, FindingDraft, interpret
from agents.orchestrator import REVISION_FAILED, run_agents
from agents.sceptic import rests_on_missing_annotation
from contract import AssessmentRequest, Finding, LayerResult, Observation, SequenceStats, SourceRecord
from report.builder import build_report

# Frozen GAPDH-vs-mouse benchmark report (read-only here).
GAPDH = Path(__file__).resolve().parents[2] / "tests" / "frozen" / "03_gapdh.json"


def layer(status="ok") -> LayerResult:
    """One citable localisation layer with a shared and a human-only observation."""
    return LayerResult(
        species="mus_musculus", layer="localisation", status=status,
        observations=[
            Observation(field="shared_compartments", value="Nucleus", source_record_id="s1"),
            Observation(field="human_only_compartments", value="Membrane", source_record_id="s1"),
        ],
        source_records=[SourceRecord(id="s1", source="UniProt")],
    )


def finding(fid="f1", cited="localisation.shared_compartments", claim="c") -> Finding:
    """A finding citing an observation of `layer()`."""
    return Finding(id=fid, claim=claim, mechanism="m", concern="high",
                   cited_field=cited, source_record_id="s1")


@pytest.fixture
def no_sceptic_llm(monkeypatch):
    """Keep Gemini off for the Sceptic; tests then control `interpret` directly."""
    monkeypatch.setattr(llm, "available", lambda: False)


def script_interpret(monkeypatch, *drafts: Draft):
    """Make the orchestrator's successive `interpret` calls return `drafts` in order."""
    calls = iter(drafts)
    monkeypatch.setattr("agents.orchestrator.interpret", lambda *_a, **_k: next(calls))


# ── Task 1: Gemini failures are visible ────────────────────────────────────


def test_missing_key_is_reported_as_not_configured(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    draft = interpret([layer()])
    assert draft.findings == [] and draft.failure == NOT_CONFIGURED


def test_api_failure_is_reported_without_leaking_details(monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("429 quota exceeded for key AIza-SECRET-KEY")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "ask_json", boom)
    draft = interpret([layer()])
    assert draft.findings == [] and draft.failure == API_FAILED.format(kind="RuntimeError")
    # Neither the key nor the raw message may reach the report.
    assert "SECRET" not in draft.failure and "429" not in draft.failure


def test_successful_empty_answer_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "ask_json", lambda *_a, **_k: [])
    draft = interpret([layer()])
    assert draft.findings == [] and draft.failure == ""


def test_no_evidence_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    assert interpret([]).failure == ""


def test_unusable_model_reply_raises_instead_of_looking_empty(monkeypatch):
    """ask_json must not turn garbage/empty text into the 'no findings' answer."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.run_log.log_event", lambda *_a, **_k: None)
    reply = SimpleNamespace(text="not json at all", parsed=None)
    monkeypatch.setattr(llm, "_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: reply)))
    with pytest.raises(ValueError):
        llm.ask_json("p", FindingDraft, agent="interpreter")


def test_valid_empty_list_reply_is_returned_as_empty(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.run_log.log_event", lambda *_a, **_k: None)
    reply = SimpleNamespace(text="[]", parsed=[])
    monkeypatch.setattr(llm, "_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: reply)))
    assert llm.ask_json("p", FindingDraft, agent="interpreter") == []


def test_failure_becomes_a_report_limitation(monkeypatch, no_sceptic_llm):
    script_interpret(monkeypatch, Draft(failure=NOT_CONFIGURED))
    out = run_agents([layer()])
    assert out.findings == [] and NOT_CONFIGURED in out.limitations
    # ...and reaches the Report unchanged, with no contract change.
    report = build_report(
        AssessmentRequest(species="mus_musculus", sequence="MKTAYIAKQRQ"),
        SequenceStats(length=11, estimated_mass_k_da=1.0, composition=[]),
        [layer()], out)
    assert NOT_CONFIGURED in report.limitations


def test_clean_empty_run_adds_no_failure_limitation(monkeypatch, no_sceptic_llm):
    script_interpret(monkeypatch, Draft())
    assert run_agents([layer()]).limitations == []


def test_failed_revision_keeps_validated_findings(monkeypatch, no_sceptic_llm):
    good = finding("f1")
    bad = finding("f2", cited="localisation.invented")  # rejected -> triggers the revision
    script_interpret(
        monkeypatch,
        Draft(findings=[good, bad], experiments={"f1": "Run assay A", "f2": "Run assay B"}),
        Draft(failure=API_FAILED.format(kind="TimeoutError")),
    )
    out = run_agents([layer()])
    assert [f.id for f in out.findings] == ["f1"]
    assert out.recommended_experiments == ["Run assay A"]
    assert REVISION_FAILED in out.limitations


# ── Task 2: no experiments from missing annotations ────────────────────────


def test_gapdh_regression_no_fractionation_for_missing_mouse_annotation(monkeypatch, no_sceptic_llm):
    """The frozen GAPDH report recommended fractionation for 'not annotated in mouse'."""
    frozen = json.loads(GAPDH.read_text(encoding="utf-8"))
    layers = [LayerResult.model_validate(l) for l in frozen["layers"]]
    gapdh_finding = Finding.model_validate(frozen["findings"][0])
    experiment = frozen["recommendedExperiments"][0]
    # Pin the premise: this is the experiment the old pipeline emitted.
    assert "fractionation" in experiment
    script_interpret(monkeypatch, Draft(findings=[gapdh_finding], experiments={"f1": experiment}))
    out = run_agents(layers)
    # The finding stays (flagged, with the Sceptic's caveat) but spawns no experiment.
    assert [f.id for f in out.findings] == ["f1"] and out.findings[0].concern == "flagged"
    assert not any("fractionation" in e or "western" in e for e in out.recommended_experiments)
    # Gap-driven "obtain data" recommendations are unaffected.
    assert any(e.startswith("Obtain sequence data") for e in out.recommended_experiments)


def test_human_only_field_cannot_generate_an_experiment(monkeypatch, no_sceptic_llm):
    f = finding(cited="localisation.human_only_compartments")
    script_interpret(monkeypatch, Draft(findings=[f], experiments={"f1": "Fractionate cells"}))
    assert run_agents([layer()]).recommended_experiments == []


def test_supported_finding_keeps_its_experiment(monkeypatch, no_sceptic_llm):
    script_interpret(monkeypatch, Draft(findings=[finding()], experiments={"f1": "Run immunofluorescence"}))
    assert run_agents([layer()]).recommended_experiments == ["Run immunofluorescence"]


def test_only_the_annotation_gap_finding_loses_its_experiment(monkeypatch, no_sceptic_llm):
    gap = finding("f2", cited="localisation.human_only_compartments")
    script_interpret(monkeypatch, Draft(findings=[finding("f1"), gap],
                                        experiments={"f1": "Assay A", "f2": "Assay B"}))
    assert run_agents([layer()]).recommended_experiments == ["Assay A"]


@pytest.mark.parametrize("claim", [
    "Membrane is annotated for human but not annotated for mouse.",
    "The mouse entry lacks a nuclear annotation.",
    "Mouse has no annotation for the compartment.",
    "The compartment is unannotated in mouse.",
])
def test_annotation_gap_wording_is_detected(claim):
    assert rests_on_missing_annotation(finding(claim=claim))


@pytest.mark.parametrize("claim", [
    "Human and mouse annotate conflicting compartments with experimental evidence.",
    "Mouse shares 78% identity over the signal peptide.",
])
def test_positive_contrasts_are_not_treated_as_annotation_gaps(claim):
    assert not rests_on_missing_annotation(finding(claim=claim))


def test_prompt_tells_the_model_annotation_gaps_are_not_biology():
    assert "NOT a biological difference" in interpreter.PROMPT
