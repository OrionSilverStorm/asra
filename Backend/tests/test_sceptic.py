"""Sceptic tests: the deterministic checks, then the Gemini pass (mocked)."""

import pytest

from agents import llm
from agents.orchestrator import run_agents
from agents.sceptic import Verdict, review
from contract import Finding, LayerResult, Observation, SourceRecord


def layer(status="ok", field="shared_compartments"):
    """One citable layer carrying a single observation."""
    return LayerResult(
        species="mus_musculus", layer="localisation", status=status,
        observations=[Observation(field=field, value="plasma membrane", source_record_id="s1")],
        source_records=[SourceRecord(id="s1", source="UniProt")],
    )


def finding(**over):
    """A finding that cites the observation above, unless overridden."""
    base = dict(id="f1", claim="c", mechanism="m", concern="high",
                cited_field="localisation.shared_compartments", source_record_id="s1")
    return Finding(**{**base, **over})


# ── Deterministic pass ─────────────────────────────────────────────────────


def test_citation_must_match_an_observation():
    """The source exists, but no observation of that field is behind it."""
    accepted, feedback = review([finding(cited_field="localisation.invented")], [layer()], use_llm=False)
    assert accepted == [] and "no observation" in feedback[0]


def test_incomplete_evidence_is_flagged():
    accepted, _ = review([finding()], [layer(status="incomplete")], use_llm=False)
    assert accepted[0].concern == "flagged"


# ── Gemini pass ────────────────────────────────────────────────────────────


@pytest.fixture
def verdict(monkeypatch):
    """Make the Sceptic's model call return one chosen verdict."""
    def set_verdict(**kw):
        monkeypatch.setattr(llm, "available", lambda: True)
        monkeypatch.setattr(llm, "ask_json", lambda prompt, schema, agent: [Verdict(**kw)])
    return set_verdict


def test_downgrade_lowers_concern_and_records_the_note(verdict):
    verdict(finding_id="f1", verdict="downgrade", note="Absence of annotation is not absence.")
    [accepted], _ = review([finding()], [layer()])
    assert accepted.concern == "flagged"
    assert accepted.sceptic_note == "Absence of annotation is not absence."


def test_reject_drops_the_finding(verdict):
    verdict(finding_id="f1", verdict="reject", note="Unsupported.")
    accepted, feedback = review([finding()], [layer()])
    assert accepted == [] and "Unsupported." in feedback[0]


def test_accept_cannot_raise_concern(verdict):
    """A verdict never promotes a finding the deterministic pass flagged."""
    verdict(finding_id="f1", verdict="accept", note="Stands.")
    accepted, _ = review([finding()], [layer(status="incomplete")])
    assert accepted[0].concern == "flagged"


def test_model_failure_keeps_the_deterministic_result(monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("quota exceeded")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "ask_json", boom)
    accepted, feedback = review([finding()], [layer()])
    assert [f.id for f in accepted] == ["f1"] and feedback == []


# ── Orchestration ──────────────────────────────────────────────────────────


def test_toggle_off_skips_the_challenge(monkeypatch):
    """sceptic=False still interprets, but never asks the Sceptic."""
    calls = []
    monkeypatch.setattr(llm, "available", lambda: True)

    def ask_json(prompt, schema, agent):
        calls.append(agent)
        return [schema(claim="c", mechanism="m", concern="high",
                       cited_field="localisation.shared_compartments", source_record_id="s1")]

    monkeypatch.setattr(llm, "ask_json", ask_json)
    # The claim is properly cited, so the deterministic pass keeps it.
    assert [f.id for f in run_agents([layer()], sceptic=False).findings] == ["f1"]
    assert calls == ["interpreter"]


def test_revision_happens_at_most_once(monkeypatch):
    """Every claim rejected: the Interpreter is re-run once, then it stops."""
    calls = []
    monkeypatch.setattr(llm, "available", lambda: True)

    def ask_json(prompt, schema, agent):
        calls.append(agent)
        # The Interpreter always drafts an uncitable claim, so the Sceptic's
        # deterministic pass always rejects it and always returns feedback.
        return [schema(claim="c", mechanism="m", concern="high",
                       cited_field="localisation.x", source_record_id="missing")] if agent == "interpreter" else []

    monkeypatch.setattr(llm, "ask_json", ask_json)
    assert run_agents([layer()]).findings == []
    assert calls.count("interpreter") == 2


def test_unusable_layers_become_limitations_and_experiments(monkeypatch):
    """A layer that returned nothing is named, not silently dropped."""
    monkeypatch.setattr(llm, "available", lambda: False)
    out = run_agents([LayerResult(species="mus_musculus", layer="sequence", status="unavailable",
                                  limitations=["Ensembl timed out."])])
    assert "sequence" in out.limitations[0] and "Ensembl timed out." in out.limitations[0]
    assert "sequence" in out.recommended_experiments[0]
