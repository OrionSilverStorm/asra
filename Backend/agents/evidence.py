"""Compact layer evidence for LLM prompts (Interpreter and Sceptic).

The gene-based sequence layer stores rich JSON in its observation values
(~220k characters for SLC29A1, mostly residue maps and raw UniProt
features). Agents only need the measurements, the substitutions that
matter and the caveats, so this module condenses those values for prompts.

Rules:
- Every layer, observation field and source_record_id is kept, so any
  citation the agents make is still checked against the full layers by the
  Sceptic's deterministic pass (which never sees this compact copy).
- Values are only dropped or summarised, never changed or recomputed.
- Non-JSON observation values (all other layers) pass through untouched.
"""

import json

from contract import LayerResult

# Fields replaced by a one-line note: per-residue maps and aligned strings.
_OMIT = {"human_to_animal", "animal_to_human", "alignment"}


def _label(s: dict) -> str:
    """'E72A': human residue, human position, animal residue."""
    return f"{s.get('human_residue', '?')}{s.get('human_position', '?')}{s.get('animal_residue', '?')}"


def _protein(p: dict) -> dict:
    """Protein record without its full residue sequence."""
    return {k: v for k, v in p.items() if k not in {"sequence", "seq"}}


def _functional(fa: dict) -> dict:
    """Keep statuses, identities, the motif check and annotated substitutions."""
    # Feature id -> "Type: description", to name what each substitution overlaps.
    names = {f.get("id"): f"{f.get('type')}: {f.get('description') or ''}".strip(": ")
             for f in fa.get("mapped_human_features", [])}
    return {
        "status": fa.get("status"),
        "proteins": {
            side: {
                "status": p.get("status"),
                "reason_code": p.get("reason_code"),
                "identity": {k: p.get("identity", {}).get(k) for k in ("status", "accession", "isoform")},
                "feature_count": len(p.get("features", [])),
            }
            for side, p in fa.get("proteins", {}).items()
        },
        # Annotated substitutions with the human features they overlap.
        "functional_substitutions": [
            {"substitution": _label(s),
             "features": sorted({names[a["feature_id"]] for a in s.get("annotation_overlaps", [])
                                 if a.get("feature_id") in names})}
            for s in fa.get("functional_substitutions", [])
        ],
        "other_substitutions_count": len(fa.get("other_substitutions", [])),
        "unclassified_substitutions_count": len(fa.get("unclassified_substitutions", [])),
        "slc29a1_motif": fa.get("slc29a1_motif"),
        "limitations": fa.get("limitations", []),
    }


def _candidates(items: list) -> list:
    """Ambiguous orthologue candidates without their full sequences."""
    return [{k: (_protein(v) if isinstance(v, dict) else v) for k, v in c.items()}
            if isinstance(c, dict) else c for c in items]


def _compact_value(field: str, value):
    """Condensed form of one decoded sequence observation."""
    if field in _OMIT:
        size = len(value) if isinstance(value, (dict, list)) else 1
        return f"omitted from prompt: residue-level {field.replace('_', ' ')} ({size} entries); full data in the report"
    if field in {"human", "animal"} and isinstance(value, dict):
        return _protein(value)
    if field == "substitutions" and isinstance(value, list):
        return [_label(s) for s in value if isinstance(s, dict)]
    if field == "functional_analysis" and isinstance(value, dict):
        return _functional(value)
    if field == "ambiguous_candidates" and isinstance(value, list):
        return _candidates(value)
    return value


def compact_for_prompt(layers: list[LayerResult]) -> list[dict]:
    """Prompt-ready dicts for the given layers, with large JSON condensed."""
    out = []
    for layer in layers:
        data = layer.model_dump(mode="json")
        for obs in data["observations"]:
            try:
                decoded = json.loads(obs["value"])
            except (TypeError, ValueError):
                continue  # plain-string observation: leave as is
            # Only rewrite structured values; plain JSON scalars stay as written.
            if isinstance(decoded, (dict, list)):
                obs["value"] = json.dumps(_compact_value(obs["field"], decoded), separators=(",", ":"))
        out.append(data)
    return out
