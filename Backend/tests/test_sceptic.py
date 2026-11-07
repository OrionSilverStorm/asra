"""Sceptic tests: the deterministic checks, then the Gemini pass (mocked)."""

import pytest

from agents import llm
from agents.orchestrator import run_agents
from agents.sceptic import Verdict, review
from contract import Finding, LayerResult, Observation, SourceRecord


def layer(status="ok"):
    """One citable layer, matching the finding below."""
    return LayerResult(
        species="mus_musculus",
        layer="localisation",
        status=status,
        observations=[Observation(field="shared_compartments", value="plasma membrane", source_record_id="s1")],
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


# ── Strengthened Scientific Audit Checks ───────────────────────────────────


def _make_fixture_layers() -> list[LayerResult]:
    """Create a realistic set of 4 layer results with known sources and observations."""
    seq_obs = [
        Observation(field="global_identity", value="78.4%", source_record_id="seq_rec"),
        Observation(field="mitochondrial_motif", value="Human 1-24; Mouse absent", source_record_id="seq_rec"),
    ]
    seq_records = [SourceRecord(id="seq_rec", source="Ensembl v1.0")]

    loc_records = [SourceRecord(id="loc_rec", source="UniProtKB")]

    cell_obs = [
        Observation(field="fraction_expressing", value="0.45", source_record_id="cell_rec"),
    ]
    cell_records = [SourceRecord(id="cell_rec", source="CELLxGENE Census")]

    tissue_obs = [
        Observation(field="tpm", value="12.5", source_record_id="tissue_rec"),
    ]
    tissue_records = [SourceRecord(id="tissue_rec", source="GTEx v8")]

    return [
        LayerResult(
            species="mus_musculus",
            layer="sequence",
            status="ok",
            observations=seq_obs,
            source_records=seq_records,
        ),
        LayerResult(
            species="mus_musculus",
            layer="localisation",
            status="incomplete",
            observations=[],
            source_records=loc_records,
            limitations=["Mouse subcellular compartment unannotated in UniProt"],
        ),
        LayerResult(
            species="mus_musculus",
            layer="cell_expression",
            status="ok",
            observations=cell_obs,
            source_records=cell_records,
        ),
        LayerResult(
            species="mus_musculus",
            layer="tissue_expression",
            status="ok",
            observations=tissue_obs,
            source_records=tissue_records,
        ),
    ]


def test_sceptic_rejects_missing_citation():
    """Finding citing a non-existent source record must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Human and mouse differ at residue 42.",
        mechanism="Possible conformational change.",
        concern="moderate",
        cited_field="sequence.global_identity",
        source_record_id="non_existent_source",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "not in the evidence" in feedback[0]


def test_sceptic_rejects_invalid_cited_field():
    """Finding citing a field that does not exist in the layer must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Human and mouse differ at non-existent metric.",
        mechanism="Mechanism claim.",
        concern="moderate",
        cited_field="sequence.non_existent_field",
        source_record_id="seq_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "no observation" in feedback[0]


def test_sceptic_rejects_clinical_safety_prediction():
    """Claims using 'safe', 'safety', or predicting lack of toxicity must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="The compound is expected to be safe in humans based on mouse homology.",
        mechanism="Will not cause toxicity because mouse model tolerated it.",
        concern="low",
        cited_field="sequence.global_identity",
        source_record_id="seq_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "unsupported clinical safety prediction" in feedback[0]


def test_sceptic_rejects_missing_annotation_treated_as_biological_absence():
    """Claiming biological absence based on incomplete UniProt annotation must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Mouse ENT1 is absent in mitochondrial membrane.",
        mechanism="Does not localize to mitochondria because UniProt lacks annotation.",
        concern="high",
        cited_field="localisation.compartment",
        source_record_id="loc_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "missing annotation" in feedback[0]
    assert "not evidence of biological absence" in feedback[0]


def test_sceptic_rejects_incompatible_cell_populations():
    """Comparing incompatible cell populations without normalisation must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Expression diverges in incompatible cell population comparison.",
        mechanism="Mismatched population across unnormalised datasets.",
        concern="high",
        cited_field="cell_expression.fraction_expressing",
        source_record_id="cell_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "incompatible cell populations" in feedback[0]


def test_sceptic_rejects_rna_conflated_with_protein_abundance():
    """Treating single-cell RNA transcript count as proof of protein abundance must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="High transcript levels confirm high protein abundance in mouse cells.",
        mechanism="Protein expression confirmed directly by RNA expression.",
        concern="moderate",
        cited_field="cell_expression.fraction_expressing",
        source_record_id="cell_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "cannot be treated as a direct proxy for protein abundance" in feedback[0]


def test_sceptic_rejects_gtex_bgee_numerical_comparison():
    """Computing a fold difference or dividing GTEx by Bgee must be rejected."""
    layers = _make_fixture_layers()
    f = Finding(
        id="f1",
        claim="Expression shows 4-fold difference between GTEx and Bgee.",
        mechanism="Calculated by dividing GTEx TPM by Bgee expression score.",
        concern="high",
        cited_field="tissue_expression.tpm",
        source_record_id="tissue_rec",
    )
    accepted, feedback = review([f], layers, use_llm=False)
    assert len(accepted) == 0
    assert len(feedback) == 1
    assert "numerical comparison between GTEx and Bgee" in feedback[0]


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


def test_revision_happens_at_most_once(monkeypatch):
    """Every claim rejected: the Interpreter is re-run once, then it stops."""
    from agents.interpreter import Draft
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
