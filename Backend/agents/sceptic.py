"""Sceptic: rejects unsupported claims and downgrades weak ones.

Gets the RAW layer results, not just the Interpreter's output, so it checks
claims against evidence instead of reinforcing the same error.

Review has two passes (design doc: "deterministic first, LLM second"):
1. Deterministic checks (_check):
   - Citable evidence: rejects findings whose source record is missing or
     unavailable, or whose cited_field is not backed by that source record.
   - Safety predictions: rejects claims promising clinical safety or lack of toxicity.
   - Missing annotations: rejects claims that treat missing annotations as proof of absence.
   - Incompatible populations: rejects unnormalised or incompatible cell population comparisons.
   - RNA vs protein: rejects treating RNA expression as direct proof of protein abundance.
   - GTEx vs Bgee: rejects numerical ratios or fold-difference calculations across disparate scales.
   - Incomplete data: forces findings resting on incomplete database records to concern 'flagged',
     while preserving concern for findings backed by published experimental literature.

2. Gemini pass (_challenge):
   Evaluates each finding that survived the deterministic checks against the
   prompt in agents/prompts/sceptic.md. Can only accept, downgrade or reject.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from agents import llm
from agents.evidence import compact_for_prompt
from contract import Finding, LayerResult

log = logging.getLogger("asra.agents")

# Prompt template, loaded once at import.
PROMPT = (Path(__file__).parent / "prompts" / "sceptic.md").read_text(encoding="utf-8")

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

# Localisation fields that only record "annotated here, not annotated there".
_ANNOTATION_ONLY_FIELDS = {"localisation.human_only_compartments", "localisation.animal_only_compartments"}

# Claim wording that reports a missing database annotation (e.g. "not annotated for mouse").
_NOT_ANNOTATED_RE = re.compile(
    r"\b(?:not|never|un|no|lacks?|lacking|without|missing)\s*-?\s*(?:\w+\s+){0,4}?annotat",
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


class Verdict(BaseModel):
    """The Sceptic's ruling on one finding."""

    finding_id: str
    verdict: Literal["accept", "downgrade", "reject"]
    # Why: the Sceptic's note for the report (accept/downgrade) or the feedback
    # passed to the Interpreter on a revision pass (reject).
    note: str


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


def rests_on_missing_annotation(f: Finding) -> bool:
    """True if the finding's only basis is that one species lacks a database annotation.

    That is a difference between records, not between biologies, so it must
    not trigger an experiment recommendation (the finding itself may stay,
    flagged, so the gap is still visible).
    """
    return f.cited_field in _ANNOTATION_ONLY_FIELDS or bool(_NOT_ANNOTATED_RE.search(f.claim))


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


def _is_literature_finding(f: Finding, layers: list[LayerResult]) -> bool:
    """True if the finding is backed by published experimental literature."""
    # 1. Source record ID prefix (DOI, PubMed ID, or literature prefix)
    src_id = f.source_record_id.lower()
    if any(src_id.startswith(p) for p in ("doi:", "pmid:", "pub:", "literature:")):
        return True

    # 2. Cited field indicator (e.g. literature_human_mitochondrial_location)
    field_name = f.cited_field.split(".")[-1].lower()
    if field_name.startswith("literature_") or field_name == "literature":
        return True

    # 3. Look up matching source record across all layers
    for layer in layers:
        for s in layer.source_records:
            if s.id == f.source_record_id:
                s_id = s.id.lower()
                if any(s_id.startswith(p) for p in ("doi:", "pmid:", "pub:", "literature:")):
                    return True
                if s.url and any(domain in s.url.lower() for domain in ("doi.org", "ncbi.nlm.nih.gov/pubmed", "pubmed")):
                    return True
                s_source = s.source.lower()
                if any(term in s_source for term in ("j biol chem", "br j pharmacol", "doi:", "pmid", "et al.")):
                    return True

        # 4. Look up matching observation across all layers
        for obs in layer.observations:
            if obs.source_record_id == f.source_record_id and f"{layer.layer}.{obs.field}" == f.cited_field:
                if obs.field.lower().startswith("literature_"):
                    return True
                if obs.value.startswith("LITERATURE"):
                    return True

    return False


def _check(findings: list[Finding], layers: list[LayerResult]) -> tuple[list[Finding], list[str]]:
    """Deterministic audit: citations, safety terminology, missing data, and cross-layer rules."""
    status_by_source = {s.id: l.status for l in layers for s in l.source_records}
    layer_by_source = {s.id: l for l in layers for s in l.source_records}
    # (cited_field, source_record_id) pairs that actually exist in the evidence.
    cited = {
        (f"{l.layer}.{obs.field}", obs.source_record_id)
        for l in layers
        for obs in l.observations
        if obs.source_record_id
    }

    accepted: list[Finding] = []
    feedback: list[str] = []

    for f in findings:
        status = status_by_source.get(f.source_record_id)
        if status is None or status == "unavailable":
            # No matching evidence: reject outright.
            feedback.append(f"Rejected '{f.claim}': source '{f.source_record_id}' not in the evidence.")
            continue

        # Check safety predictions
        safety_err = _check_safety_prediction(f)
        if safety_err:
            feedback.append(f"Rejected '{f.claim}': {safety_err}")
            continue

        # Check missing annotation absence claims
        absence_err = _check_missing_annotation_absence(f, layers)
        if absence_err:
            feedback.append(f"Rejected '{f.claim}': {absence_err}")
            continue

        # Verify that cited_field is actually backed by source_record_id if observations exist
        layer = layer_by_source.get(f.source_record_id)
        if layer and layer.observations and (f.cited_field, f.source_record_id) not in cited:
            feedback.append(
                f"Rejected '{f.claim}': no observation '{f.cited_field}' is backed by '{f.source_record_id}'."
            )
            continue

        # Check incompatible cell populations
        cell_err = _check_incompatible_cell_populations(f, layers)
        if cell_err:
            feedback.append(f"Rejected '{f.claim}': {cell_err}")
            continue

        # Check RNA vs protein abundance conflation
        rna_err = _check_rna_vs_protein(f, layers)
        if rna_err:
            feedback.append(f"Rejected '{f.claim}': {rna_err}")
            continue

        # Check GTEx vs Bgee comparisons
        gtex_bgee_err = _check_gtex_bgee_comparison(f)
        if gtex_bgee_err:
            feedback.append(f"Rejected '{f.claim}': {gtex_bgee_err}")
            continue

        # Incomplete layer downgrade: only downgrade findings resting on incomplete database
        # records. Curated peer-reviewed experimental literature (e.g. Lai 2004, Lee 2006,
        # Eastwood 2010) retains its assigned concern level.
        if status == "incomplete" and not _is_literature_finding(f, layers) and f.concern != "flagged":
            accepted.append(
                f.model_copy(
                    update={
                        "concern": "flagged",
                        "sceptic_note": "Rests on incomplete data; downgraded.",
                    }
                )
            )
        else:
            accepted.append(f)

    return accepted, feedback


def _challenge(findings: list[Finding], layers: list[LayerResult]) -> tuple[list[Finding], list[str]]:
    """Gemini pass: apply per-finding verdicts. Only ever weakens a finding."""
    if not findings or not llm.available():
        return findings, []
    prompt = PROMPT.format(
        # Condensed copy for the model; _check above used the full layers.
        evidence=json.dumps(compact_for_prompt(layers)),
        findings=json.dumps([f.model_dump(mode="json") for f in findings], indent=2),
    )
    try:
        verdicts = {v.finding_id: v for v in llm.ask_json(prompt, Verdict, agent="sceptic")}
    except Exception:  # a failed challenge must not promote unchecked claims
        log.exception("Sceptic call failed")
        return findings, []

    accepted: list[Finding] = []
    feedback: list[str] = []
    for f in findings:
        verdict = verdicts.get(f.id)
        if verdict is None:  # not ruled on: keep the deterministic result
            accepted.append(f)
        elif verdict.verdict == "reject":
            feedback.append(f"Rejected '{f.claim}': {verdict.note}")
        else:
            # 'downgrade' lowers concern to flagged; 'accept' leaves it alone.
            concern = "flagged" if verdict.verdict == "downgrade" else f.concern
            accepted.append(f.model_copy(update={"concern": concern, "sceptic_note": verdict.note}))
    return accepted, feedback


def review(
    findings: list[Finding],
    layers: list[LayerResult],
    # Deterministic-only review, for tests that must not reach Gemini.
    use_llm: bool = True,
) -> tuple[list[Finding], list[str]]:
    """Return (accepted findings, feedback notes for one revision pass)."""
    accepted, feedback = _check(findings, layers)
    if use_llm:
        accepted, more = _challenge(accepted, layers)
        feedback += more
    return accepted, feedback
