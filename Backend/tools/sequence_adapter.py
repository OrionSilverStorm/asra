"""Role 3 explicit bridge to the shared string-valued LayerResult contract.

Structured observations use JSON, retaining numeric types after json.loads.
No route or legacy sequence-only call invokes this adapter implicitly.
"""

import json

from contract import LayerResult, Observation, SourceRecord

# Enumerate the supported evidence schema so newly added fields demand review.
EVIDENCE_FIELDS = frozenset({
    "human", "animal", "orthology", "retrieved_at", "provenance",
    "alignment", "parameters", "measurements", "metric_definitions",
    "human_to_animal", "animal_to_human", "substitutions", "ambiguous_pairs", "indels",
})
DIRECT_FIELDS = frozenset({
    "gene", "species", "layer", "status", "source_records", "limitations", "data_version",
})
OPTIONAL_EVIDENCE_FIELDS = frozenset({"functional_analysis"})


def to_layer_result(result: dict) -> LayerResult:
    """Encode every rich evidence field explicitly; reject schema drift.

    The contract cannot carry native numeric observations. Each observation
    value is a JSON document, not a rounded display string. JSON coordinate
    map keys are strings. Consumers must decode these values explicitly.
    """
    expected = EVIDENCE_FIELDS | DIRECT_FIELDS
    if not expected <= set(result) or set(result) - expected - OPTIONAL_EVIDENCE_FIELDS:
        raise ValueError(f"Sequence schema mismatch: missing={sorted(expected - set(result))}, "
                         f"unhandled={sorted(set(result) - expected - OPTIONAL_EVIDENCE_FIELDS)}")
    if result["layer"] != "sequence":
        raise ValueError("Expected sequence layer evidence.")
    for source in result["source_records"]:
        if set(source) - set(SourceRecord.model_fields):
            raise ValueError("Unhandled source record fields; refusing to drop provenance.")
    sources = [SourceRecord.model_validate(source) for source in result["source_records"]]
    ids = [source.id for source in sources]
    if "ensembl_orthology" not in ids or len(ids) != len(set(ids)):
        raise ValueError("Expected a unique ensembl_orthology citation and unique source IDs.")
    if "functional_analysis" in result and "sequence_functional_analysis" not in ids:
        raise ValueError("Expected a sequence_functional_analysis source record.")
    return LayerResult(
        **{key: result[key] for key in DIRECT_FIELDS - {"source_records", "limitations"}},
        source_records=sources,
        observations=[Observation(field=key,
                                  value=json.dumps(result[key], allow_nan=False, sort_keys=True),
                                  source_record_id=("sequence_functional_analysis" if key == "functional_analysis" else "ensembl_orthology"))
                      for key in sorted(EVIDENCE_FIELDS | (OPTIONAL_EVIDENCE_FIELDS & set(result)))],
        limitations=[*result["limitations"],
                     "Structured sequence observations are JSON strings; decode to recover numeric measurements and mapped evidence. Coordinate map keys are JSON strings."],
    )
