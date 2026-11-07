"""CLI runner for the ASRA multi-agent pipeline.

Loads the Gemini API key, runs the full agent pipeline against mock
evidence, and writes a timestamped audit log to
Backend/data/cache/run_log.json so every stage can be inspected.

Usage (from Backend/):
    .venv/bin/python -m api.main
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.agents import run_agents

# ---------------------------------------------------------------------------
# Logging — all agent-level logs go to stderr so they don't mix with the
# final JSON printed to stdout.
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("asra.main")


# ---------------------------------------------------------------------------
# Mock evidence matching the ASRA layer contract
# ---------------------------------------------------------------------------
# These two layers exercise both the "ok" and "incomplete" status paths
# so we can verify the agents handle missing data correctly.

MOCK_EVIDENCE: list[dict[str, Any]] = [
    {
        "gene": "SLC29A1",
        "species": "mus_musculus",
        "layer": "sequence",
        "status": "ok",
        "observations": [
            {"metric": "global_identity", "value": "78.4%"},
            {
                "metric": "mitochondrial_targeting_motif",
                "human": "Present (residues 1-24)",
                "mouse": "Absent",
            },
        ],
        "source_records": [
            "Ensembl:ENSG00000112759",
            "Biopython:PairwiseAligner",
        ],
        "limitations": [
            "Isoform choice pinned to canonical NP_001071661.1",
        ],
        "data_version": "v1.0",
    },
    {
        "gene": "SLC29A1",
        "species": "mus_musculus",
        "layer": "localisation",
        "status": "incomplete",
        "observations": [],
        "source_records": [],
        "limitations": [
            "UniProt annotation incomplete for mouse subcellular compartment",
        ],
        "data_version": None,
    },
]


# ---------------------------------------------------------------------------
# Audit-log writer
# ---------------------------------------------------------------------------

# Audit logs live at Backend/data/cache/.
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


def _write_run_log(payload: dict[str, Any]) -> Path:
    """Persist the full pipeline output to run_log.json for auditing.

    Creates the cache directory if it does not yet exist.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _CACHE_DIR / "run_log.json"
    log_path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("Audit log written → %s", log_path)
    return log_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the multi-agent pipeline against mock evidence and log results."""
    query = (
        "Investigate SLC29A1 translational risks in mouse for fialuridine"
    )

    log.info("=" * 60)
    log.info("ASRA Multi-Agent Pipeline")
    log.info("Query : %s", query)
    log.info("Layers: %d mock evidence entries", len(MOCK_EVIDENCE))
    log.info("=" * 60)

    # Execute the full four-stage pipeline.
    result = run_agents(query, MOCK_EVIDENCE)

    # Assemble the audit-trail payload with numbered stages.
    audit_payload: dict[str, Any] = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "evidence_input": MOCK_EVIDENCE,
        "stages": {
            "1_investigator": result["investigator"],
            "2_interpreter_draft": result["interpreter_draft"],
            "3_sceptic_critique": result["sceptic_critique"],
            "4_final_report": result["final_report"],
        },
        "revision_was_needed": result["revision_was_needed"],
    }

    # Write the full audit trail to disk.
    log_path = _write_run_log(audit_payload)

    # Print a human-readable summary to stdout.
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nRevision needed : {result['revision_was_needed']}")
    print(
        f"Final findings  : "
        f"{len(result['final_report'].get('findings', []))}"
    )
    print(f"Audit log       : {log_path}")
    print("\n--- Final Report ---")
    print(json.dumps(result["final_report"], indent=2))


# Guard so the file can also be imported without side effects.
if __name__ == "__main__":
    main()
