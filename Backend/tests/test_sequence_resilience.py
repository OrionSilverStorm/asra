"""Deterministic transport failures and verified raw snapshot alignment; no live APIs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from unittest.mock import patch

import httpx
import pytest

from tools import resolver, sequence_pinned as pinned
from tools.resolver import ResolvedQuery
from tools.sequence_layer import run_sequence_layer, _retry_after


def query(gene="SLC29A1", species="mus_musculus"):
    return ResolvedQuery(species, "ACDEFGHIKLMN", gene, gene)


def fields(layer):
    return {o.field: json.loads(o.value) for o in layer.observations}


def response(status, retry_after=None):
    return httpx.Response(status, headers={"Retry-After": retry_after} if retry_after else {},
        request=httpx.Request("GET", pinned.SOURCE_URL))


def test_timeouts_recover_pinned_raw_sequences():
    with patch.object(resolver.httpx, "get", side_effect=httpx.ReadTimeout("frozen failure")) as get, \
         patch("tools.sequence_layer.time.sleep") as sleep:
        result = run_sequence_layer(query())
    assert get.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [1, 2]
    assert result.status == "incomplete"
    f = fields(result)
    assert f["measurements"]["exact_matches"] == 366
    assert f["measurements"]["alignment_columns"] == 461
    assert f["measurements"]["identity_percent"] == 100 * 366 / 461
    assert f["measurements"]["human_coverage_percent"] == 100 * 455 / 456
    assert f["measurements"]["animal_coverage_percent"] == 100 * 455 / 460
    assert f["provenance"]["accessions"] == {"human": "Q99808", "animal": "Q9JIM1"}
    assert f["retrieved_at"] == pinned._load()["homology.json"]["retrieved_at"]
    assert "not fresh live" in f["provenance"]["mode"]
    assert f["provenance"]["source_release"] == "unknown"
    assert "UniProt 2026_04" in result.data_version
    assert "after 3 attempts" in f["provenance"]["fallback_reason"]
    assert {s.url for s in result.source_records} == {pinned.SOURCE_URL,
        "https://rest.uniprot.org/uniprotkb/Q99808.json", "https://rest.uniprot.org/uniprotkb/Q9JIM1.json"}


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_statuses_retry_then_fallback(status):
    with patch.object(resolver.httpx, "get", return_value=response(status)) as get, patch("tools.sequence_layer.time.sleep"):
        assert run_sequence_layer(query()).status == "incomplete"
    assert get.call_count == 3


@pytest.mark.parametrize("header,calls,waits", [("2", 3, [2, 2]), ("4", 2, [4]), ("3600", 1, []), ("bad", 3, [1, 2])])
def test_retry_after_cap_never_retries_early(header, calls, waits):
    with patch.object(resolver.httpx, "get", return_value=response(429, header)) as get, patch("tools.sequence_layer.time.sleep") as sleep:
        assert run_sequence_layer(query()).status == "incomplete"
    assert get.call_count == calls
    assert [c.args[0] for c in sleep.call_args_list] == waits
    assert sum(waits) <= 5


def test_retry_after_http_date():
    delay = _retry_after(format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60)))
    assert 58 <= delay <= 60


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_permanent_errors_never_fallback(status):
    with patch.object(resolver.httpx, "get", return_value=response(status)) as get, patch("tools.sequence_layer.time.sleep") as sleep:
        assert run_sequence_layer(query()).status == "unavailable"
    assert get.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("gene,species", [("GADPH", "mus_musculus"), ("GAPDH", "mus_musculus"),
    ("CYP3A4", "mus_musculus"), ("SLC29A1", "macaca_mulatta"), ("slc29a1", "mus_musculus")])
def test_exact_pair_only(gene, species):
    with patch.object(resolver.httpx, "get", side_effect=httpx.ReadTimeout("offline")), patch("tools.sequence_layer.time.sleep"):
        assert run_sequence_layer(query(gene, species)).status == "unavailable"


@pytest.mark.parametrize("kind", ["ortholog_one2many", "ortholog_many2many"])
def test_ambiguity_never_falls_back(kind):
    tape = pinned._load()["homology.json"]
    payload = json.loads(tape["body"])
    payload["data"][0]["homologies"][0]["type"] = kind
    resp = httpx.Response(200, json=payload, request=httpx.Request("GET", pinned.SOURCE_URL))
    with patch.object(resolver.httpx, "get", return_value=resp) as get:
        result = run_sequence_layer(query())
    assert get.call_count == 1 and result.status == "unavailable"
    assert fields(result)["ambiguous_candidates"][0]["type"] == kind


def test_successful_live_recovery_uses_no_fallback():
    tape = pinned._load()["homology.json"]
    success = httpx.Response(200, text=tape["body"], request=httpx.Request("GET", tape["url"]))
    with patch.object(resolver.httpx, "get", side_effect=[httpx.ReadTimeout("first"), success]) as get, \
         patch("tools.sequence_layer.time.sleep"), \
         patch("tools.sequence_functional.add_functional_analysis", side_effect=lambda r: r), \
         patch.object(pinned, "pinned_slc29a1") as fallback:
        result = run_sequence_layer(query())
    assert get.call_count == 2
    fallback.assert_not_called()
    assert result.data_version == "Ensembl REST homology; source release unknown"
    assert "mode" not in fields(result)["provenance"]


@pytest.mark.parametrize("change", ["accession", "sequence", "species", "protein", "missing", "orthology"])
def test_semantic_mismatch_fails_closed(change):
    records = deepcopy(pinned._load())
    if change == "missing": del records["Q99808.json"]
    elif change == "accession": records["Q99808.json"]["primaryAccession"] = "WRONG"
    elif change == "sequence": records["Q99808.json"]["sequence"]["value"] = "ACDEFG"
    else:
        payload = json.loads(records["homology.json"]["body"])
        rel = payload["data"][0]["homologies"][0]
        if change == "orthology": rel["type"] = "ortholog_many2many"
        else: rel["source"]["species" if change == "species" else "protein_id"] = "WRONG"
        records["homology.json"]["body"] = json.dumps(payload)
    with patch.object(pinned, "_load", return_value=records), \
         patch.object(resolver.httpx, "get", side_effect=httpx.ReadTimeout("offline")), patch("tools.sequence_layer.time.sleep"):
        result = run_sequence_layer(query())
    assert result.status == "unavailable"
    assert "Pinned sequence evidence rejected" in result.limitations[0]


@pytest.mark.parametrize("missing", [True, False])
def test_file_integrity_failure_fails_closed(tmp_path, missing):
    for name in pinned.FILE_HASHES:
        (tmp_path / name).write_bytes((pinned.PINNED / name).read_bytes())
    if missing: (tmp_path / "Q99808.json").unlink()
    else: (tmp_path / "Q99808.json").write_text('{}')
    with patch.object(pinned, "PINNED", tmp_path), \
         patch.object(resolver.httpx, "get", side_effect=httpx.ReadTimeout("offline")), patch("tools.sequence_layer.time.sleep"):
        assert run_sequence_layer(query()).status == "unavailable"


def test_mismatched_submitted_accession_never_fallback():
    q = ResolvedQuery("mus_musculus", "ACDEFGHIKLMN", "sp|P10747|OTHER_HUMAN GN=SLC29A1", "SLC29A1")
    with patch.object(resolver.httpx, "get", side_effect=httpx.ReadTimeout("offline")), patch("tools.sequence_layer.time.sleep"):
        assert run_sequence_layer(q).status == "unavailable"


def test_timeout_then_ambiguous_remains_unavailable():
    with patch("tools.sequence_layer.run_sequence", side_effect=[resolver.EnsemblAPIError("timeout", transient=True),
        resolver.AmbiguousOrthologueError("many", [{"type": "ortholog_many2many"}])]), patch("tools.sequence_layer.time.sleep"):
        result = run_sequence_layer(query())
    assert result.status == "unavailable"
    assert fields(result)["ambiguous_candidates"] == [{"type": "ortholog_many2many"}]


@pytest.mark.parametrize("error", [httpx.UnsupportedProtocol("invalid URL"), httpx.LocalProtocolError("invalid request")])
def test_invalid_transport_request_never_retries_or_falls_back(error):
    with patch.object(resolver.httpx, "get", side_effect=error) as get, patch("tools.sequence_layer.time.sleep") as sleep:
        assert run_sequence_layer(query()).status == "unavailable"
    assert get.call_count == 1
    sleep.assert_not_called()


def test_live_missing_sequence_is_not_hidden_by_snapshot():
    payload = json.loads(pinned._load()["homology.json"]["body"])
    del payload["data"][0]["homologies"][0]["target"]["seq"]
    resp = httpx.Response(200, json=payload, request=httpx.Request("GET", pinned.SOURCE_URL))
    with patch.object(resolver.httpx, "get", return_value=resp) as get:
        assert run_sequence_layer(query()).status == "unavailable"
    assert get.call_count == 1
