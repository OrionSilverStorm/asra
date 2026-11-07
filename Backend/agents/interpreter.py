"""Interpreter: explains observations and the possible failure mechanism.

Hard rule (design doc): every claim must cite the layer field behind it.

Current state: no LLM is wired in, so it returns no findings. When adding
the model call, load the prompt from agents/prompts/interpreter.md, log the
prompt and response (pipeline/run_log.py), and return `Finding` objects only.
The agent must never produce a number; Python computes all quantities.
"""

from typing import Optional

from contract import Finding, LayerResult


def interpret(evidence: list[LayerResult], feedback: Optional[list[str]] = None) -> list[Finding]:
    """Draft findings from evidence; `feedback` is the Sceptic's notes on a revision pass."""
    # TODO: LLM call. Until then, no claims are made rather than invented ones.
    return []
