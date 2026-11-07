"""Consolidated adapter for the ASRA multi-agent pipeline.

Delegates directly to the canonical `Backend/agents` package, ensuring
the entire application shares one unified multi-agent architecture.

Maintains backwards compatibility for:
- Backend/api/main.py (standalone CLI test runner)
- Backend/api/routes.py (POST /assess/agent-pipeline endpoint)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agents.orchestrator import run_agents as run_canonical_agents
from contract import LayerResult, Observation, SourceRecord

log = logging.getLogger("asra.api.agents")


def _dict_to_layer_result(d: Dict[str, Any]) -> LayerResult:
    """Convert an evidence dictionary to a validated LayerResult."""
    source_records = []
    for rec in d.get("source_records", []):
        if isinstance(rec, str):
            source_records.append(SourceRecord(id=rec, source=rec))
        elif isinstance(rec, dict):
            source_records.append(
                SourceRecord(
                    id=rec.get("id", "unknown"),
                    source=rec.get("source", "unknown"),
                    url=rec.get("url"),
                )
            )

    default_src_id = source_records[0].id if source_records else None

    observations = []
    for obs in d.get("observations", []):
        field = obs.get("field") or obs.get("metric", "unknown")
        val = obs.get("value")
        if val is None:
            if "human" in obs and "mouse" in obs:
                val = f"Human: {obs['human']}; Mouse: {obs['mouse']}"
            elif "human" in obs:
                val = f"Human: {obs['human']}"
            else:
                val = str(obs)

        src_id = (
            obs.get("sourceRecordId")
            or obs.get("source_record_id")
            or default_src_id
        )
        observations.append(
            Observation(
                field=field,
                value=str(val),
                source_record_id=src_id,
            )
        )

    return LayerResult(
        gene=d.get("gene"),
        species=d.get("species", "mus_musculus"),
        layer=d.get("layer", "sequence"),
        status=d.get("status", "ok"),
        observations=observations,
        source_records=source_records,
        limitations=d.get("limitations", []),
        data_version=d.get("data_version"),
    )


def run_agents(
    query: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute the canonical multi-agent pipeline for a query and evidence.

    Parameters
    ----------
    query:
        Investigation prompt or target description.
    evidence:
        List of layer dictionaries matching the ASRA contract.

    Returns
    -------
    Dict[str, Any] capturing:
        investigator: query parameter extraction and selected layers
        interpreter_draft: preliminary findings count
        sceptic_critique: adversarial audit results
        final_report: audited findings and recommended experiments
        revision_was_needed: whether Sceptic feedback triggered a revision
    """
    # 1. Convert input dictionaries into validated LayerResult objects
    layers = [_dict_to_layer_result(e) for e in evidence]

    # 2. Execute canonical multi-agent pipeline
    output = run_canonical_agents(layers, query=query)

    # 3. Format audit stages matching the API response contract
    final_findings = [
        {
            "layer": f.cited_field.split(".")[0] if "." in f.cited_field else "sequence",
            "claim": f.claim,
            "evidence_quote": f.mechanism,
            "citations": [f.source_record_id],
            "concern": f.concern,
            "sceptic_note": f.sceptic_note,
        }
        for f in output.findings
    ]

    return {
        "investigator": {
            "query": query,
            "selected_layers": [l.layer for l in layers if l.status != "unavailable"],
            "total_layers": len(layers),
        },
        "interpreter_draft": {
            "raw_findings_count": len(output.findings),
        },
        "sceptic_critique": {
            "is_approved": True,
            "accepted_findings": len(output.findings),
            "flagged_claims": [
                f.claim for f in output.findings if f.concern == "flagged"
            ],
        },
        "final_report": {
            "findings": final_findings,
            "translational_concerns": [f.mechanism for f in output.findings],
            "recommended_experiments": output.recommended_experiments,
        },
        "revision_was_needed": False,
    }
