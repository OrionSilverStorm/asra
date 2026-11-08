from __future__ import annotations
"""Report origin: any fixture-backed layer makes the report "fixture", never "live"."""

from agents import AgentOutput
from contract import AssessmentRequest, LayerResult
from report import build_report
from tools.fixtures import FIXTURE_VERSION
from tools.sequence_stats import compute_stats

SEQ = "MACKMACKMACKMACK"
REQUEST = AssessmentRequest(species="mus_musculus", sequence=SEQ)


def _layer(name, data_version=None):
    """Minimal layer result with an optional data_version."""
    return LayerResult(gene="X", species="mus_musculus", layer=name, status="incomplete", data_version=data_version)


def _report(layers):
    return build_report(REQUEST, compute_stats(SEQ), layers, AgentOutput())


def test_live_when_no_fixture_layers():
    report = _report([_layer("sequence"), _layer("localisation", "UniProt 2026_04")])
    assert report.origin == "live"
    assert not any("Demo fixture" in n for n in report.limitations)


def test_fixture_when_any_layer_is_fixture():
    report = _report([_layer("sequence"), _layer("localisation", FIXTURE_VERSION)])
    assert report.origin == "fixture"
    assert any("Demo fixture" in n and "localisation" in n for n in report.limitations)
