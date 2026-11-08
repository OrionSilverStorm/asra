"""Mocked UniProt tests; the live smoke test is deliberately run separately."""

from copy import deepcopy
from http.client import IncompleteRead
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from Backend.tools import localisation


HUMAN_ACCESSION = "Q99808"
MOUSE_ACCESSION = "Q9JIM1"
RELEASE_HEADERS = {"x-uniprot-release": "2026_03"}
CONTRACT_KEYS = {
    "layer", "status", "observations", "measurements", "sources", "limitations"
}


def evidence(code="ECO:0000269", publication="12345678"):
    """A location's evidence must carry its own experimental citation."""
    return {"evidenceCode": code, "source": "PubMed", "id": publication}


def annotation(name="Cell membrane", identifier="SL-0039", evidences=None):
    location = {"id": identifier, "value": name}
    if evidences is not None:
        location["evidences"] = evidences
    return {"location": location}


def record(accession, taxon, locations=None, reviewed=True):
    human = taxon == 9606
    if locations is None:
        locations = [annotation(evidences=[evidence()])]
    return {
        "primaryAccession": accession,
        "entryType": (
            "UniProtKB reviewed (Swiss-Prot)"
            if reviewed else "UniProtKB unreviewed (TrEMBL)"
        ),
        "organism": {
            "taxonId": taxon,
            "scientificName": "Homo sapiens" if human else "Mus musculus",
        },
        "genes": [{"geneName": {"value": "SLC29A1" if human else "Slc29a1"}}],
        "comments": [{
            "commentType": "SUBCELLULAR LOCATION",
            "subcellularLocations": locations,
        }],
        "entryAudit": {"entryVersion": 123},
    }


class MockUniProt:
    """Serve independent search and accession responses without network access."""

    def __init__(self, human=None, animal=None):
        human = human if human is not None else record(HUMAN_ACCESSION, 9606)
        animal = animal if animal is not None else record(MOUSE_ACCESSION, 10090)
        self.search_results = {
            (9606, True): [human],
            (10090, True): [animal],
            (9606, False): [],
            (10090, False): [],
        }
        self.records = {
            HUMAN_ACCESSION: human,
            MOUSE_ACCESSION: animal,
        }
        self.calls = []

    def response(self, url):
        self.calls.append(url)
        parsed = urlparse(url)
        if parsed.path.endswith("/search"):
            parameters = parse_qs(parsed.query)
            query = parameters["query"][0]
            assert "gene_exact:" in query
            assert parameters["size"] == ["100"]
            assert "reviewed:true" in query or "reviewed:false" in query
            taxon = 9606 if "organism_id:9606" in query else 10090
            assert f"organism_id:{taxon}" in query
            reviewed = "reviewed:true" in query
            return {"results": deepcopy(self.search_results[taxon, reviewed])}
        accession = parsed.path.rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(self.records[accession])

    def request_json(self, url):
        return self.response(url), dict(RELEASE_HEADERS)


@pytest.fixture
def api(monkeypatch):
    server = MockUniProt()
    monkeypatch.setattr(localisation, "_request_json", server.request_json)
    return server


def compare():
    return localisation.run_localisation("SLC29A1", "mus_musculus")


def location_ids(locations):
    return {location["id"] for location in locations}


def test_contract_and_experimental_overlap(api):
    result = compare()

    assert set(result) == CONTRACT_KEYS
    assert result["layer"] == "localisation"
    assert result["status"] == "complete"
    assert isinstance(result["observations"], list)
    assert isinstance(result["sources"], list)
    assert isinstance(result["limitations"], list)
    measurements = result["measurements"]
    assert measurements["gene"] == "SLC29A1"
    assert measurements["species"] == "mus_musculus"
    assert measurements["errors"] == []
    assert measurements["proteins"]["human"]["accession"] == HUMAN_ACCESSION
    assert measurements["proteins"]["human"]["taxon_id"] == 9606
    assert measurements["proteins"]["animal"]["accession"] == MOUSE_ACCESSION
    assert measurements["proteins"]["animal"]["taxon_id"] == 10090
    comparison = measurements["comparison"]
    assert comparison["status"] == "overlap_only"
    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039"}
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False
    assert any(f"/{HUMAN_ACCESSION}.json" in url for url in api.calls)
    assert any(f"/{MOUSE_ACCESSION}.json" in url for url in api.calls)
    # The full result must remain JSON-serializable for callers.
    json.dumps(result)


def test_positive_annotation_difference_never_establishes_absence(api):
    api.records[HUMAN_ACCESSION]["comments"][0]["subcellularLocations"].append(
        annotation("Mitochondrion membrane", "SL-0173", [evidence()])
    )

    result = compare()

    assert result["status"] == "complete"
    comparison = result["measurements"]["comparison"]
    assert comparison["status"] == "annotation_differences"
    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039"}
    assert location_ids(comparison["human_only_annotations"]) == {"SL-0173"}
    assert comparison["animal_only_annotations"] == []
    supported = comparison["supported_annotation_differences"]
    assert len(supported) == 1
    assert supported[0]["side"] == "human"
    assert comparison["biological_difference_supported"] is False
    limitations = " ".join(result["limitations"]).lower()
    assert "absence" in limitations or "absent" in limitations
    assert "literature" in limitations


@pytest.mark.parametrize("missing_comments", [True, False])
def test_missing_annotation_does_not_create_species_difference(api, missing_comments):
    """An unannotated compartment is unknown, never a negative observation."""
    api.records[MOUSE_ACCESSION]["comments"] = (
        [] if missing_comments else [{
            "commentType": "SUBCELLULAR LOCATION",
            "subcellularLocations": [],
        }]
    )

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["animal"]["locations"] == []
    comparison = result["measurements"]["comparison"]
    assert comparison["status"] == "incomplete_evidence"
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False
    assert result["limitations"]


def test_by_similarity_annotation_is_not_direct_experimental_support(api):
    location = api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"][0]
    location["location"]["evidences"] = [{
        "evidenceCode": "ECO:0000250", "source": "UniProtKB", "id": HUMAN_ACCESSION
    }]

    result = compare()

    assert result["status"] == "partial"
    protein = result["measurements"]["proteins"]["animal"]
    assert protein["locations"][0]["evidence_support"] == "by_similarity"
    assert any("not independent" in limitation and HUMAN_ACCESSION in limitation
               for limitation in result["limitations"])
    comparison = result["measurements"]["comparison"]
    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039"}
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False


def test_location_without_evidence_is_preserved_but_incomplete(api):
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"] = [
        annotation()
    ]

    result = compare()

    assert result["status"] == "partial"
    location = result["measurements"]["proteins"]["animal"]["locations"][0]
    assert location["name"] == "Cell membrane"
    assert location["evidence"] == []
    assert location["evidence_support"] == "missing"


def test_inferred_unique_annotation_does_not_become_supported_difference(api):
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"].append(
        annotation("Endosome", "SL-0101", [{"evidenceCode": "ECO:0000250"}])
    )

    comparison = compare()["measurements"]["comparison"]

    assert location_ids(comparison["animal_only_annotations"]) == {"SL-0101"}
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False


def test_location_ids_are_used_despite_label_variants(api):
    location = api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"][0]
    location["location"]["value"] = "Plasma membrane"

    comparison = compare()["measurements"]["comparison"]

    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039"}
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []


def test_annotation_order_does_not_change_comparison(api):
    locations = [
        annotation("Cell membrane", "SL-0039", [evidence()]),
        annotation("Endosome", "SL-0101", [evidence()]),
    ]
    api.records[HUMAN_ACCESSION]["comments"][0]["subcellularLocations"] = locations
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"] = list(
        reversed(locations)
    )

    comparison = compare()["measurements"]["comparison"]

    assert comparison["status"] == "overlap_only"
    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039", "SL-0101"}
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []


def test_topology_notes_and_other_comment_types_are_not_compartments(api):
    comment = api.records[HUMAN_ACCESSION]["comments"][0]
    comment["molecule"] = "Isoform 1"
    comment["subcellularLocations"][0]["topology"] = {
        "value": "Multi-pass membrane protein", "evidences": [evidence()]
    }
    comment["subcellularLocations"][0]["orientation"] = {
        "value": "Cytoplasmic side", "evidences": [evidence()]
    }
    comment["note"] = {"texts": [{
        "value": "Mitochondrial transport requires additional literature evidence.",
        "evidences": [evidence()],
    }]}
    api.records[HUMAN_ACCESSION]["comments"].append({
        "commentType": "FUNCTION",
        "subcellularLocations": [annotation("Nucleus", "SL-0191", [evidence()])],
    })

    protein = compare()["measurements"]["proteins"]["human"]

    assert location_ids(protein["locations"]) == {"SL-0039"}
    assert protein["locations"][0]["molecule"] == "Isoform 1"
    assert protein["locations"][0]["topology"] is not None
    assert protein["locations"][0]["orientation"] is not None
    assert "Mitochondrial transport" in json.dumps(protein["notes"])
    assert "12345678" in json.dumps(protein["notes"])


def test_accession_sources_and_evidence_are_traceable(api):
    result = compare()
    protein = result["measurements"]["proteins"]["human"]

    assert HUMAN_ACCESSION in protein["source_url"]
    assert protein["api_url"].endswith(f"/{HUMAN_ACCESSION}.json")
    assert protein["entry_version"] == 123
    support = protein["locations"][0]["evidence"][0]
    assert support["evidenceCode"] == "ECO:0000269"
    assert support["source"] == "PubMed"
    assert support["id"] == "12345678"
    assert "pubmed.ncbi.nlm.nih.gov/12345678" in support["url"]
    assert HUMAN_ACCESSION in json.dumps(result["sources"])
    assert MOUSE_ACCESSION in json.dumps(result["sources"])


@pytest.mark.parametrize("field", ["species", "accession", "gene", "missing_species"])
def test_fetched_identity_mismatch_is_rejected(api, field):
    """Search hits do not authorize accepting a mismatched retrieved protein."""
    invalid = deepcopy(api.records[HUMAN_ACCESSION])
    if field == "species":
        invalid["organism"]["taxonId"] = 10090
    elif field == "accession":
        invalid["primaryAccession"] = "P12345"
    elif field == "gene":
        invalid["genes"] = [{"geneName": {"value": "SLC29A2"}}]
    else:
        invalid["organism"].pop("taxonId")
    api.records[HUMAN_ACCESSION] = invalid

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["human"] is None
    assert result["measurements"]["proteins"]["animal"] is not None
    assert result["measurements"]["errors"]
    assert result["measurements"]["comparison"]["status"] == "not_comparable"
    assert result["measurements"]["comparison"]["supported_annotation_differences"] == []


def test_ambiguous_reviewed_matches_are_not_arbitrarily_selected(api):
    api.search_results[9606, True].append(record("P12345", 9606))

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["human"] is None
    assert result["measurements"]["errors"]
    assert not any(f"/{HUMAN_ACCESSION}.json" in url for url in api.calls)
    assert not any("/P12345.json" in url for url in api.calls)


def test_unreviewed_fallback_is_explicitly_partial(api):
    animal = record(MOUSE_ACCESSION, 10090, reviewed=False)
    api.search_results[10090, True] = []
    api.search_results[10090, False] = [animal]
    api.records[MOUSE_ACCESSION] = animal

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["animal"]["reviewed"] is False
    assert any("reviewed%3Afalse" in url for url in api.calls)


def test_no_records_is_unavailable_not_annotation_difference(api):
    api.search_results = {key: [] for key in api.search_results}

    result = compare()

    assert result["status"] == "unavailable"
    assert result["measurements"]["proteins"] == {"human": None, "animal": None}
    comparison = result["measurements"]["comparison"]
    assert comparison["status"] == "not_comparable"
    assert comparison["supported_annotation_differences"] == []


@pytest.mark.parametrize("gene,species", [
    ("", "mus_musculus"),
    (None, "mus_musculus"),
    (123, "mus_musculus"),
    ("SLC29A1 OR *", "mus_musculus"),
    ("SLC29A1", ""),
    ("SLC29A1", None),
    ("SLC29A1", "unsupported_species"),
    ("SLC29A1", "homo_sapiens"),
    ("SLC29A1", "human"),
])
def test_invalid_inputs_fail_before_http(api, gene, species):
    result = localisation.run_localisation(gene, species)

    assert set(result) == CONTRACT_KEYS
    assert result["status"] == "error"
    assert result["measurements"]["errors"][0]["kind"] == "invalid_input"
    assert api.calls == []


class FakeResponse:
    """Minimal urllib response with real JSON decoding and request boundaries."""

    def __init__(self, payload=None, raw=None):
        self.body = raw if raw is not None else json.dumps(payload).encode("utf-8")
        self.headers = dict(RELEASE_HEADERS)

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_real_http_helper_uses_timeout_for_every_request(monkeypatch):
    server = MockUniProt()
    requests = []

    def fake_urlopen(request, timeout):
        assert isinstance(request, Request)
        assert timeout == 20.0
        requests.append(request)
        return FakeResponse(server.response(request.full_url))

    monkeypatch.setattr(localisation, "urlopen", fake_urlopen)

    result = compare()

    assert result["status"] == "complete"
    assert len(requests) == 4
    assert all(request.full_url.startswith("https://rest.uniprot.org/") for request in requests)


@pytest.mark.parametrize("failure", ["timeout", "http", "json"])
def test_transport_failures_are_errors_not_missing_annotations(monkeypatch, failure):
    def fake_urlopen(request, timeout):
        assert timeout == 20.0
        if failure == "timeout":
            raise TimeoutError("Mock UniProt timeout")
        if failure == "http":
            raise HTTPError(request.full_url, 503, "Service unavailable", {}, None)
        return FakeResponse(raw=b"{not valid JSON")

    monkeypatch.setattr(localisation, "urlopen", fake_urlopen)

    result = compare()

    assert result["status"] == "error"
    assert result["measurements"]["proteins"] == {"human": None, "animal": None}
    assert result["measurements"]["errors"]
    assert all(error["kind"] != "missing_annotation" for error in result["measurements"]["errors"])
    assert result["measurements"]["comparison"]["status"] == "not_comparable"


def test_partial_api_failure_preserves_successful_species(monkeypatch):
    server = MockUniProt()

    def fake_urlopen(request, timeout):
        assert timeout == 20.0
        query = parse_qs(urlparse(request.full_url).query).get("query", [""])[0]
        if "organism_id:10090" in query:
            raise HTTPError(request.full_url, 503, "Service unavailable", {}, None)
        return FakeResponse(server.response(request.full_url))

    monkeypatch.setattr(localisation, "urlopen", fake_urlopen)

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["human"]["accession"] == HUMAN_ACCESSION
    assert result["measurements"]["proteins"]["animal"] is None
    assert result["measurements"]["errors"]
    assert result["measurements"]["comparison"]["status"] == "not_comparable"
    assert result["measurements"]["comparison"]["human_only_annotations"] == []
    assert result["measurements"]["comparison"]["supported_annotation_differences"] == []


def test_search_http_404_is_an_api_failure_not_missing_protein(monkeypatch):
    """Only a successful empty search establishes that no record was resolved."""
    def fake_urlopen(request, timeout):
        assert urlparse(request.full_url).path.endswith("/search")
        raise HTTPError(request.full_url, 404, "Search endpoint not found", {}, None)

    monkeypatch.setattr(localisation, "urlopen", fake_urlopen)

    result = compare()

    assert result["status"] == "error"
    assert result["measurements"]["proteins"] == {"human": None, "animal": None}
    assert result["measurements"]["errors"]
    assert all(error["kind"] == "api_error" for error in result["measurements"]["errors"])


def test_incomplete_http_body_returns_structured_api_error(monkeypatch):
    """A dropped connection during read must not escape the public function."""
    class TruncatedResponse(FakeResponse):
        def read(self):
            raise IncompleteRead(b'{"results":[', 128)

    monkeypatch.setattr(
        localisation, "urlopen", lambda request, timeout: TruncatedResponse()
    )

    result = compare()

    assert result["status"] == "error"
    assert result["measurements"]["errors"]
    assert all(error["kind"] == "api_error" for error in result["measurements"]["errors"])
    assert result["measurements"]["comparison"]["status"] == "not_comparable"


def test_missing_id_matches_unambiguous_normalized_label(api):
    """Missing IDs must not create opposite claims about the same compartment."""
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"] = [
        {"location": {"value": "  cell   MEMBRANE  ", "evidences": [evidence()]}}
    ]

    result = compare()

    assert result["status"] == "partial"
    comparison = result["measurements"]["comparison"]
    assert comparison["status"] == "overlap_only"
    assert location_ids(comparison["overlapping_locations"]) == {"SL-0039"}
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False
    assert not any(item.get("type") == "annotation_difference" for item in result["observations"])


def test_missing_id_with_ambiguous_label_cannot_establish_differences(api):
    """A label referring to multiple IDs cannot support a unique comparison."""
    api.records[HUMAN_ACCESSION]["comments"][0]["subcellularLocations"] = [
        annotation("Cell membrane", "SL-0039", [evidence()]),
        annotation("Cell membrane", "SL-0001", [evidence()]),
    ]
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"] = [
        {"location": {"value": "Cell membrane", "evidences": [evidence()]}}
    ]

    result = compare()

    assert result["status"] == "partial"
    comparison = result["measurements"]["comparison"]
    assert comparison["status"] == "incomplete_evidence"
    assert comparison["human_only_annotations"] == []
    assert comparison["animal_only_annotations"] == []
    assert comparison["supported_annotation_differences"] == []
    assert comparison["biological_difference_supported"] is False


def test_paginated_search_is_rejected_as_ambiguous(api, monkeypatch):
    original_request = api.request_json

    def paginated_request(url):
        payload, headers = original_request(url)
        query = parse_qs(urlparse(url).query).get("query", [""])[0]
        if "organism_id:9606" in query:
            headers["link"] = (
                '<https://rest.uniprot.org/uniprotkb/search?cursor=next>; rel="next"'
            )
        return payload, headers

    monkeypatch.setattr(localisation, "_request_json", paginated_request)

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["human"] is None
    assert result["measurements"]["proteins"]["animal"] is not None
    assert any(error["kind"] == "ambiguous_record" for error in result["measurements"]["errors"])
    assert not any(f"/{HUMAN_ACCESSION}.json" in url for url in api.calls)


def test_malformed_annotations_retain_failed_record_url(api):
    api.records[HUMAN_ACCESSION]["comments"] = None

    result = compare()

    assert result["status"] == "partial"
    assert result["measurements"]["proteins"]["human"] is None
    errors = [error for error in result["measurements"]["errors"] if error["side"] == "human"]
    assert len(errors) == 1
    assert errors[0]["kind"] == "invalid_response"
    assert errors[0]["url"].endswith(f"/{HUMAN_ACCESSION}.json")


# ── Canonical ASRA Pipeline Integration & Contract Tests ────────────────────


def test_pipeline_resolved_query_complete_maps_to_ok(api):
    query = localisation.ResolvedQuery(
        species="mus_musculus",
        sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
        sequence_label=">SLC29A1",
        gene="SLC29A1",
    )
    result = localisation.run_localisation(query)

    assert isinstance(result, localisation.LayerResult)
    assert result.layer == "localisation"
    assert result.gene == "SLC29A1"
    assert result.species == "mus_musculus"
    assert result.status == "ok"
    assert result.data_version == "UniProtKB release 2026_03"

    source_ids = {s.id for s in result.source_records}
    assert HUMAN_ACCESSION in source_ids
    assert MOUSE_ACCESSION in source_ids
    assert "PubMed:12345678" in source_ids

    obs_map = {o.field: o for o in result.observations}
    assert "human_protein" in obs_map
    assert "animal_protein" in obs_map
    assert "human_subcellular_locations" in obs_map
    assert "animal_subcellular_locations" in obs_map
    assert "overlapping_location_sl_0039" in obs_map
    assert "comparison_summary" in obs_map
    assert "biological_difference_supported=False" in obs_map["comparison_summary"].value

    for obs in result.observations:
        assert obs.source_record_id in source_ids

    dumped = result.model_dump(mode="json", by_alias=True)
    assert "source_records" in dumped
    assert "data_version" in dumped
    assert "sourceRecordId" in dumped["observations"][0]


def test_pipeline_slc29a1_human_vs_mouse_realistic_partial_maps_to_incomplete(api):
    """Simulate real SLC29A1 UniProt records (Q99808 human vs Q9JIM1 mouse)."""
    api.records[HUMAN_ACCESSION]["comments"][0]["subcellularLocations"] = [
        annotation("Cell membrane", "SL-0039", [evidence("ECO:0000269", "9228014")]),
        annotation("Basolateral cell membrane", "SL-0029", [evidence("ECO:0000269", "12527552")]),
        annotation("Apical cell membrane", "SL-0014", [evidence("ECO:0000269", "12527552")]),
    ]
    api.records[MOUSE_ACCESSION]["comments"][0]["subcellularLocations"] = [
        annotation(
            "Cell membrane",
            "SL-0039",
            [{"evidenceCode": "ECO:0000250", "source": "UniProtKB", "id": HUMAN_ACCESSION}],
        )
    ]

    query = localisation.ResolvedQuery(
        species="mus_musculus",
        sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
        sequence_label=">SLC29A1",
        gene="SLC29A1",
    )
    result = localisation.run_localisation(query)

    assert isinstance(result, localisation.LayerResult)
    assert result.status == "incomplete"
    assert result.gene == "SLC29A1"
    assert result.species == "mus_musculus"

    source_ids = {s.id for s in result.source_records}
    assert {HUMAN_ACCESSION, MOUSE_ACCESSION, "PubMed:9228014", "PubMed:12527552"} <= source_ids

    obs_map = {o.field: o for o in result.observations}
    assert "overlapping_location_sl_0039" in obs_map
    assert "annotation_difference_sl_0029" in obs_map
    assert "annotation_difference_sl_0014" in obs_map
    assert obs_map["annotation_difference_sl_0029"].source_record_id == HUMAN_ACCESSION
    assert "does not establish absence in the other species" in obs_map["annotation_difference_sl_0029"].value
    assert "evidence_completeness" in obs_map
    assert "biological_difference_supported=False" in obs_map["comparison_summary"].value

    limitations_text = " ".join(result.limitations)
    assert "ENT1/fialuridine mitochondrial mechanism" in limitations_text
    assert f"transferred by similarity from {HUMAN_ACCESSION}" in limitations_text
    assert "Missing localisation annotations do not establish biological absence" in limitations_text

    # Deterministic Sceptic citation verification check
    for obs in result.observations:
        assert obs.source_record_id is not None
        assert obs.source_record_id in source_ids


def test_pipeline_status_mapping_missing_gene_unavailable_and_error(api, monkeypatch):
    # 1. Missing gene -> unavailable
    no_gene_query = localisation.ResolvedQuery(
        species="mus_musculus",
        sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
        sequence_label=None,
        gene=None,
    )
    no_gene_res = localisation.run_localisation(no_gene_query)
    assert isinstance(no_gene_res, localisation.LayerResult)
    assert no_gene_res.status == "unavailable"
    assert no_gene_res.observations == []
    assert any("Needs a resolved gene identifier" in lim for lim in no_gene_res.limitations)

    # 2. Missing animal annotations -> incomplete, never annotation_difference
    api.records[MOUSE_ACCESSION]["comments"] = []
    query = localisation.ResolvedQuery(
        species="mus_musculus",
        sequence="MTTSHQPQDRYKAVWLIFFMLGLGTLLPWNFFMTATKYFTNRLDMSQNVSLVTAELSKDAQASAAPGSGPER",
        sequence_label=">SLC29A1",
        gene="SLC29A1",
    )
    partial_res = localisation.run_localisation(query)
    assert partial_res.status == "incomplete"
    obs_fields = {o.field for o in partial_res.observations}
    assert not any(f.startswith("annotation_difference_") for f in obs_fields)
    obs_map = {o.field: o for o in partial_res.observations}
    assert "does not establish biological absence" in obs_map["animal_subcellular_locations"].value

    # 3. No records found -> unavailable
    api.search_results = {key: [] for key in api.search_results}
    unavail_res = localisation.run_localisation(query)
    assert unavail_res.status == "unavailable"
    assert unavail_res.observations == []

    # 4. API failure -> unavailable with error limitation preserved
    def failing_request(url):
        raise localisation._DataError("api_error", "UniProt returned HTTP 503.", url)

    monkeypatch.setattr(localisation, "_request_json", failing_request)
    err_res = localisation.run_localisation(query)
    assert err_res.status == "unavailable"
    assert any("HTTP 503" in lim for lim in err_res.limitations)

