"""Sceptic: rejects unsupported claims and downgrades weak ones.

Gets the RAW layer results, not just the Interpreter's output, so it checks
claims against evidence instead of reinforcing the same error.

Adversarial audit checks (deterministic):
1. Citable evidence: rejects findings with missing or invalid source records,
   or whose cited_field does not exist in the evidence layer.
2. Safety language: rejects unsupported clinical safety predictions (e.g.
   "safe", "non-toxic", "will not cause toxicity").
3. Missing annotations: rejects claims that treat an empty or incomplete
   annotation as proof of biological absence.
4. Incompatible cell populations: rejects or flags comparisons between
   incompatible cell populations or unnormalised datasets.
5. RNA vs Protein: rejects claims that treat RNA/transcript levels as direct
   evidence of protein abundance or functional transporter capacity.
6. GTEx vs Bgee: rejects numerical ratios or fold-difference comparisons
   between GTEx and Bgee.
7. Incomplete data downgrade: forces findings resting on 'incomplete' layers
   to concern 'flagged'.
"""

from __future__ import annotations

import re
from typing import Optional

from contract import Finding, LayerResult

# Regex matching explicit clinical safety claims forbidden by the safety guidelines.
_SAFETY_RE = re.compile(
    r"\b(safe|safety\s+prediction|will\s+not\s+cause\s+toxicity|non-toxic|proven\s+safe|clinically\s+safe|safe\s+starting\s+dose)\b",
    re.IGNORECASE,
)

# Regex matching claims of biological absence
_ABSENCE_RE = re.compile(
    r"\b(is\s+absent|is\s+not\s+present|does\s+not\s+localize|does\s+not\s+localise|proved\s+absent|proven\s+absent|biological\s+absence)\b",
    re.IGNORECASE,
)

# Regex matching RNA-to-protein conflation
_RNA_PROTEIN_RE = re.compile(
    r"\b(protein\s+abundance|protein\s+expression|protein\s+levels|transporter\s+protein\s+capacity)\b",
    re.IGNORECASE,
)

# Regex matching cross-database ratio or fold difference between GTEx and Bgee
_GTEX_BGEE_RATIO_RE = re.compile(
    r"\b(gtex\s*(?:/|divided\s+by|vs|compared\s+to|ratio)\s*bgee|fold\s+difference\s+between\s+gtex\s+and\s+bgee|bgee\s*(?:/|ratio)\s*gtex)\b",
    re.IGNORECASE,
)


def _validate_citation(f: Finding, layers: list[LayerResult]) -> Optional[str]:
    """Check if finding cites an existing source record and matching field."""
    # Build lookup of source_record_id -> LayerResult
    layer_by_source = {
        s.id: l for l in layers for s in l.source_records
    }
    layer = layer_by_source.get(f.source_record_id)
    if layer is None or layer.status == "unavailable":
        return f"source '{f.source_record_id}' not in the evidence."

    # If the layer has observations, verify cited_field matches one
    if layer.observations:
        valid_fields = {f"{layer.layer}.{obs.field}" for obs in layer.observations} | {
            obs.field for obs in layer.observations
        }
        if f.cited_field not in valid_fields:
            return (
                f"cited field '{f.cited_field}' does not match any observation in "
                f"layer '{layer.layer}'."
            )
    return None


def _check_safety_prediction(f: Finding) -> Optional[str]:
    """Flag forbidden clinical safety claims."""
    combined = f"{f.claim} {f.mechanism}"
    match = _SAFETY_RE.search(combined)
    if match:
        return (
            f"unsupported clinical safety prediction ('{match.group(0)}'). "
            "ASRA produces retrospective biological risk assessments, not safety predictions."
        )
    return None


def _check_missing_annotation_absence(
    f: Finding, layers: list[LayerResult]
) -> Optional[str]:
    """Flag claims that treat missing annotation as evidence of biological absence."""
    layer_by_source = {s.id: l for l in layers for s in l.source_records}
    layer = layer_by_source.get(f.source_record_id)
    if not layer:
        return None

    # If the layer is incomplete or limitations note incomplete annotation
    is_incomplete = layer.status == "incomplete" or any(
        "incomplete" in lim.lower() or "missing" in lim.lower()
        for lim in layer.limitations
    )

    combined = f"{f.claim} {f.mechanism}"
    if is_incomplete and _ABSENCE_RE.search(combined):
        return (
            f"claims biological absence based on incomplete/missing annotation in "
            f"'{layer.layer}'. A missing annotation is not evidence of biological absence."
        )
    return None


def _check_incompatible_cell_populations(
    f: Finding, layers: list[LayerResult]
) -> Optional[str]:
    """Flag comparisons across incompatible cell populations or unnormalised datasets."""
    layer_by_source = {s.id: l for l in layers for s in l.source_records}
    layer = layer_by_source.get(f.source_record_id)
    if not layer or layer.layer != "cell_expression":
        return None

    combined = f"{f.claim} {f.mechanism}".lower()
    incompatible_triggers = [
        "incompatible cell population",
        "mismatched population",
        "unnormalised",
        "unnormalized",
        "different cell types compared",
    ]
    if any(trigger in combined for trigger in incompatible_triggers):
        return (
            "comparison between incompatible cell populations or unnormalised "
            "single-cell datasets is invalid."
        )
    return None


def _check_rna_vs_protein(f: Finding, layers: list[LayerResult]) -> Optional[str]:
    """Flag treating RNA transcript expression as proven protein abundance."""
    layer_by_source = {s.id: l for l in layers for s in l.source_records}
    layer = layer_by_source.get(f.source_record_id)
    if not layer or layer.layer not in ("cell_expression", "tissue_expression"):
        return None

    combined = f"{f.claim} {f.mechanism}"
    if _RNA_PROTEIN_RE.search(combined):
        return (
            f"RNA expression in '{layer.layer}' cannot be treated as a direct proxy "
            "for protein abundance or functional transporter capacity."
        )
    return None


def _check_gtex_bgee_comparison(f: Finding) -> Optional[str]:
    """Flag numerical fold difference comparisons between GTEx and Bgee."""
    combined = f"{f.claim} {f.mechanism}"
    if _GTEX_BGEE_RATIO_RE.search(combined) or (
        "gtex" in combined.lower()
        and "bgee" in combined.lower()
        and any(w in combined.lower() for w in ["fold", "ratio", "divided by"])
    ):
        return (
            "unsupported numerical comparison between GTEx and Bgee. "
            "They use incompatible methodologies and scales."
        )
    return None


def review(
    findings: list[Finding], layers: list[LayerResult]
) -> tuple[list[Finding], list[str]]:
    """Adversarially audit findings against raw layer results.

    Returns
    -------
    tuple[list[Finding], list[str]]
        accepted: findings that passed scientific audit (with incomplete downgraded).
        feedback: rejection reasons passed back to the Interpreter for revision.
    """
    layer_by_source = {s.id: l for l in layers for s in l.source_records}
    accepted: list[Finding] = []
    feedback: list[str] = []

    for f in findings:
        # Check 1: Citation and field validity
        citation_err = _validate_citation(f, layers)
        if citation_err:
            feedback.append(f"Rejected '{f.claim}': {citation_err}")
            continue

        # Check 2: Safety predictions
        safety_err = _check_safety_prediction(f)
        if safety_err:
            feedback.append(f"Rejected '{f.claim}': {safety_err}")
            continue

        # Check 3: Missing annotation treated as biological absence
        absence_err = _check_missing_annotation_absence(f, layers)
        if absence_err:
            feedback.append(f"Rejected '{f.claim}': {absence_err}")
            continue

        # Check 4: Incompatible cell populations
        cell_err = _check_incompatible_cell_populations(f, layers)
        if cell_err:
            feedback.append(f"Rejected '{f.claim}': {cell_err}")
            continue

        # Check 5: RNA expression treated as protein abundance
        rna_err = _check_rna_vs_protein(f, layers)
        if rna_err:
            feedback.append(f"Rejected '{f.claim}': {rna_err}")
            continue

        # Check 6: GTEx vs Bgee numerical comparisons
        gtex_bgee_err = _check_gtex_bgee_comparison(f)
        if gtex_bgee_err:
            feedback.append(f"Rejected '{f.claim}': {gtex_bgee_err}")
            continue

        # Check 7: Rests on incomplete data -> downgrade concern to 'flagged'
        layer = layer_by_source.get(f.source_record_id)
        if layer and layer.status == "incomplete" and f.concern != "flagged":
            accepted.append(
                f.model_copy(
                    update={
                        "concern": "flagged",
                        "sceptic_note": "Rests on incomplete data; downgraded to flagged.",
                    }
                )
            )
        else:
            accepted.append(f)

    return accepted, feedback
