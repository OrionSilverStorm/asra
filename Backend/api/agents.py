"""Multi-agent pipeline for ASRA translational risk assessment.

Implements three specialised agents (Investigator, Interpreter, Sceptic)
plus a single deterministic revision cycle.  All agents run on Google
Gemini and are constrained by system prompts that enforce grounding,
citation, and the no-number-generation rule.

Public API
----------
    run_agents(query, evidence) -> dict

Pipeline stages
---------------
    1. Investigator  — parse query → target gene, species, selected layers
    2. Interpreter   — read evidence → drafted findings + concerns
    3. Sceptic       — audit draft against raw evidence → critique
    4. Revision      — if Sceptic disapproves, Interpreter revises once
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The .env lives at the project root (two directories above this file).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Model identifier shared by every agent call.
MODEL = "gemini-flash-latest"

# Module-level logger for the agent pipeline.
log = logging.getLogger("asra.agents")


# ---------------------------------------------------------------------------
# Gemini client factory
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    """Return a configured Gemini client.

    Exits immediately if GEMINI_API_KEY is unset so the error message is
    clear rather than a cryptic 401 from the API.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: GEMINI_API_KEY is not set.\n"
            f"Add your key to {_PROJECT_ROOT / '.env'}"
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from a Gemini response.

    Gemini occasionally wraps its output in markdown code fences
    (```json … ```).  This helper strips them before parsing.
    """
    # Remove optional opening fence (```json or just ```).
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    # Remove optional closing fence.
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Surface the raw text so the caller can diagnose prompt issues.
        log.error("Failed to parse JSON from Gemini response:\n%s", text)
        raise ValueError(
            f"Gemini returned non-JSON output: {exc}"
        ) from exc


# =========================================================================
# System prompts
# =========================================================================

INVESTIGATOR_SYSTEM = """\
You are the Investigator agent in the ASRA (Across-Species Risk Assessment)
multi-agent pipeline.

YOUR ROLE:
Parse the researcher's free-text query to extract structured parameters for
the downstream pipeline.

OUTPUT FORMAT — respond with **only** a JSON object, no surrounding prose:
{
  "target_gene": "<gene symbol, e.g. SLC29A1>",
  "comparison_species": "<Ensembl-style id, e.g. mus_musculus>",
  "selected_layers": ["sequence", "localisation", "cell_expression", "tissue_expression"],
  "investigation_plan": "<one-paragraph summary of what the pipeline will check>"
}

RULES:
1. selected_layers may only contain values from: sequence, localisation,
   cell_expression, tissue_expression.
2. Include all four layers unless the query explicitly excludes one.
3. Do NOT produce or calculate any numbers.
4. Do NOT use the word "safe" or emit numeric safety scores.
5. This system produces retrospective biological risk assessments,
   not safety predictions.
"""

INTERPRETER_SYSTEM = """\
You are the Interpreter agent in the ASRA (Across-Species Risk Assessment)
multi-agent pipeline.

YOUR ROLE:
Read pre-computed evidence from the data layers and produce a **drafted**
scientific evaluation of cross-species translational risks.

HARD CONSTRAINTS — violating any of these invalidates the report:
1. NEVER produce, calculate, or invent any number, percentage, fold-change,
   or quantitative value.  Every number you cite MUST be copied verbatim
   from the evidence observations.
2. STRICT GROUNDING: every biological claim must cite the exact "layer" name
   and at least one entry from that layer's "source_records" array.
3. MISSING DATA: if a layer has status "incomplete" or "unavailable", you
   MUST explicitly describe the evidence gap.  Do NOT speculate or fill in
   missing biological data.
4. SAFETY LANGUAGE: never use the word "safe".  Never emit numeric safety
   or risk scores.  This is a retrospective biological risk assessment.
5. Use formal scientific register; do not hedge with "might" unless the
   evidence is genuinely ambiguous.

OUTPUT FORMAT — respond with **only** a JSON object:
{
  "findings": [
    {
      "layer": "<layer name from the evidence>",
      "claim": "<one-sentence statement of a cross-species difference>",
      "evidence_quote": "<verbatim value or observation copied from the evidence>",
      "citations": ["<source_records entry>"]
    }
  ],
  "translational_concerns": [
    "<risk mechanism tied to a specific finding above>"
  ],
  "recommended_experiments": [
    "<concrete follow-up assay to resolve an identified uncertainty>"
  ]
}
"""

SCEPTIC_SYSTEM = """\
You are the Sceptic agent in the ASRA (Across-Species Risk Assessment)
multi-agent pipeline.

YOUR ROLE:
Act as an adversarial scientific auditor.  You receive BOTH the raw evidence
JSON and the Interpreter's draft.  Your job is to verify the draft's
integrity against the evidence.

CHECKS YOU MUST PERFORM:
1. UNGROUNDED CLAIMS — flag any claim that does not have a matching
   observation in the raw evidence.
2. INCOMPLETE DATA RELIANCE — flag any finding that treats an "incomplete"
   or "unavailable" layer as if it provided full data.
3. CITATION VERIFICATION — confirm every cited source_records entry
   actually appears in the corresponding layer's source_records array.
4. OVERCONFIDENCE — flag generalisations that overstate a single
   observation.
5. NUMBER FABRICATION — flag any number in the draft that does not appear
   verbatim in the evidence observations.
6. SAFETY LANGUAGE — flag any use of the word "safe" or numeric risk
   scores.

OUTPUT FORMAT — respond with **only** a JSON object:
{
  "is_approved": <true or false>,
  "flagged_claims": [
    {
      "claim": "<the claim text from the draft>",
      "issue_type": "<ungrounded | incomplete_reliance | citation_missing | overconfidence | number_fabrication | safety_language>",
      "critique": "<one-sentence explanation of the problem>"
    }
  ],
  "missing_data_warnings": [
    "<description of an evidence gap the draft should acknowledge>"
  ],
  "required_revisions": [
    "<specific instruction for the Interpreter's revision pass>"
  ]
}
"""

INTERPRETER_REVISION_SYSTEM = """\
You are the Interpreter agent performing a REVISION pass in the ASRA
multi-agent pipeline.

You will receive three inputs:
1. The raw evidence JSON (ground truth).
2. Your previous draft.
3. The Sceptic's critique.

YOUR TASK:
Produce a FINAL revised report that addresses every item in the Sceptic's
"required_revisions" and "flagged_claims".

All original HARD CONSTRAINTS still apply:
- NEVER produce or calculate numbers; copy verbatim from evidence only.
- Every claim must cite the exact layer and source_records entry.
- Explicitly flag gaps from incomplete / unavailable layers.
- Never use "safe" or emit numeric risk scores.

OUTPUT FORMAT — respond with **only** a JSON object using the same schema
as the original draft:
{
  "findings": [
    {
      "layer": "<layer name>",
      "claim": "<one-sentence statement>",
      "evidence_quote": "<verbatim from evidence>",
      "citations": ["<source_records entry>"]
    }
  ],
  "translational_concerns": ["<risk mechanism>"],
  "recommended_experiments": ["<follow-up assay>"]
}
"""


# =========================================================================
# Individual agent runners
# =========================================================================

def _call_agent(
    client: genai.Client,
    system_prompt: str,
    user_content: str,
) -> str:
    """Send a single prompt to Gemini and return the raw text response.

    Uses ``response_mime_type="application/json"`` to nudge Gemini toward
    well-formed JSON output, complementing the system-prompt instructions.
    """
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
    )
    return response.text


def run_investigator(
    client: genai.Client,
    query: str,
) -> dict[str, Any]:
    """Stage 1: parse the research query into structured parameters.

    Returns a dict with keys: target_gene, comparison_species,
    selected_layers, investigation_plan.
    """
    log.info("Investigator — parsing query")
    raw = _call_agent(client, INVESTIGATOR_SYSTEM, query)
    result = _extract_json(raw)
    log.info(
        "Investigator — target_gene=%s  species=%s  layers=%s",
        result.get("target_gene"),
        result.get("comparison_species"),
        result.get("selected_layers"),
    )
    return result


def run_interpreter(
    client: genai.Client,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stage 2: produce an initial scientific evaluation from the evidence.

    Returns a dict with keys: findings, translational_concerns,
    recommended_experiments.
    """
    log.info("Interpreter — drafting initial evaluation")
    prompt = (
        "Below is the evidence JSON from the ASRA data layers.\n"
        "Produce your drafted evaluation following your system "
        "instructions.\n\n"
        f"EVIDENCE:\n{json.dumps(evidence, indent=2)}"
    )
    raw = _call_agent(client, INTERPRETER_SYSTEM, prompt)
    result = _extract_json(raw)
    log.info(
        "Interpreter — produced %d finding(s)",
        len(result.get("findings", [])),
    )
    return result


def run_sceptic(
    client: genai.Client,
    evidence: list[dict[str, Any]],
    draft: dict[str, Any],
) -> dict[str, Any]:
    """Stage 3: adversarial audit of the Interpreter's draft.

    Returns a dict with keys: is_approved, flagged_claims,
    missing_data_warnings, required_revisions.
    """
    log.info("Sceptic — auditing draft against raw evidence")
    prompt = (
        "Below are the RAW EVIDENCE and the INTERPRETER'S DRAFT.\n"
        "Perform all required checks per your system instructions.\n\n"
        f"RAW EVIDENCE:\n{json.dumps(evidence, indent=2)}\n\n"
        f"INTERPRETER'S DRAFT:\n{json.dumps(draft, indent=2)}"
    )
    raw = _call_agent(client, SCEPTIC_SYSTEM, prompt)
    result = _extract_json(raw)
    log.info(
        "Sceptic — approved=%s  flagged=%d  revisions_requested=%d",
        result.get("is_approved", False),
        len(result.get("flagged_claims", [])),
        len(result.get("required_revisions", [])),
    )
    return result


def run_interpreter_revision(
    client: genai.Client,
    evidence: list[dict[str, Any]],
    draft: dict[str, Any],
    critique: dict[str, Any],
) -> dict[str, Any]:
    """Stage 4: one deterministic revision pass addressing the Sceptic.

    Returns a dict with the same schema as the Stage-2 draft (findings,
    translational_concerns, recommended_experiments).
    """
    log.info("Interpreter (revision) — addressing Sceptic's critique")
    prompt = (
        "Revise your draft to address every item in the Sceptic's "
        "critique.\n\n"
        f"RAW EVIDENCE:\n{json.dumps(evidence, indent=2)}\n\n"
        f"YOUR PREVIOUS DRAFT:\n{json.dumps(draft, indent=2)}\n\n"
        f"SCEPTIC'S CRITIQUE:\n{json.dumps(critique, indent=2)}"
    )
    raw = _call_agent(client, INTERPRETER_REVISION_SYSTEM, prompt)
    result = _extract_json(raw)
    log.info(
        "Interpreter (revision) — final report has %d finding(s)",
        len(result.get("findings", [])),
    )
    return result


# =========================================================================
# Pipeline orchestrator
# =========================================================================

def run_agents(
    query: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute the full four-stage multi-agent pipeline.

    Parameters
    ----------
    query:
        Free-text research question (e.g. "Investigate SLC29A1
        translational risks in mouse for fialuridine").
    evidence:
        Pre-computed layer data matching the ASRA layer contract.

    Returns
    -------
    dict with keys:
        investigator          – parsed query parameters
        interpreter_draft     – initial scientific evaluation
        sceptic_critique      – adversarial audit results
        final_report          – revised (or approved) evaluation
        revision_was_needed   – whether the Sceptic triggered a revision
    """
    client = _get_client()

    # Stage 1 — Investigator parses the query.
    investigator = run_investigator(client, query)

    # Stage 2 — Interpreter drafts an evaluation from the evidence.
    interpreter_draft = run_interpreter(client, evidence)

    # Stage 3 — Sceptic audits the draft against raw evidence.
    sceptic_critique = run_sceptic(client, evidence, interpreter_draft)

    # Stage 4 — Deterministic revision: exactly one cycle.
    # Triggered when the Sceptic disapproves OR requests any revisions.
    needs_revision = (
        not sceptic_critique.get("is_approved", False)
        or len(sceptic_critique.get("required_revisions", [])) > 0
    )

    if needs_revision:
        log.info("Revision triggered — Sceptic did not fully approve")
        final_report = run_interpreter_revision(
            client, evidence, interpreter_draft, sceptic_critique,
        )
    else:
        log.info("No revision needed — Sceptic approved the draft")
        final_report = interpreter_draft

    return {
        "investigator": investigator,
        "interpreter_draft": interpreter_draft,
        "sceptic_critique": sceptic_critique,
        "final_report": final_report,
        "revision_was_needed": needs_revision,
    }

