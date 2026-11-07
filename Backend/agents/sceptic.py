"""Sceptic: rejects unsupported claims and downgrades weak ones.

Gets the RAW layer results, not just the Interpreter's output, so it checks
claims against evidence instead of reinforcing the same error.

These checks are deterministic and run even before any LLM is added:
- a finding citing a source record no layer returned is rejected
- a finding resting on an 'incomplete' layer is forced to concern 'flagged'
"""

from contract import Finding, LayerResult


def review(findings: list[Finding], layers: list[LayerResult]) -> tuple[list[Finding], list[str]]:
    """Return (accepted findings, feedback notes for one revision pass)."""
    # Map each source record ID to the status of the layer that produced it.
    status_by_source = {s.id: l.status for l in layers for s in l.source_records}
    accepted: list[Finding] = []
    feedback: list[str] = []

    for f in findings:
        status = status_by_source.get(f.source_record_id)
        if status is None or status == "unavailable":
            # No matching evidence: reject outright.
            feedback.append(f"Rejected '{f.claim}': source '{f.source_record_id}' not in the evidence.")
        elif status == "incomplete" and f.concern != "flagged":
            # Rests on partial data: keep it, but never ranked high.
            accepted.append(f.model_copy(update={
                "concern": "flagged",
                "sceptic_note": "Rests on incomplete data; downgraded.",
            }))
        else:
            accepted.append(f)
    return accepted, feedback
