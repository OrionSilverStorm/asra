"""Protein sequence utilities and statistics calculations.

Matches the calculations performed in Frontend/lib/sequence.ts to ensure
the backend and frontend produce identical sequence statistics.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Standard residue masses in Daltons (with water removed).
RESIDUE_MASS: dict[str, float] = {
    "A": 71.08,
    "R": 156.19,
    "N": 114.1,
    "D": 115.09,
    "C": 103.14,
    "E": 129.12,
    "Q": 128.13,
    "G": 57.05,
    "H": 137.14,
    "I": 113.16,
    "L": 113.16,
    "K": 128.17,
    "M": 131.19,
    "F": 147.18,
    "P": 97.12,
    "S": 87.08,
    "T": 101.1,
    "W": 186.21,
    "Y": 163.18,
    "V": 99.13,
    "X": 110.0,
}

# Mass of one water molecule added once for chain termini.
WATER_MASS = 18.02


def compute_sequence_stats(sequence: str) -> dict[str, Any]:
    """Compute length, estimated mass (kDa), and residue composition.

    Parameters
    ----------
    sequence:
        Normalised amino acid sequence (uppercase, no whitespace).

    Returns
    -------
    dict conforming to Frontend/lib/types.ts `SequenceStats`:
        length: int
        estimatedMassKDa: float
        composition: list of {"residue": str, "fraction": float}
    """
    clean_seq = sequence.strip().upper()
    total_len = len(clean_seq)
    if total_len == 0:
        return {"length": 0, "estimatedMassKDa": 0.0, "composition": []}

    counts = Counter(clean_seq)
    mass = WATER_MASS

    for residue, count in counts.items():
        mass += RESIDUE_MASS.get(residue, RESIDUE_MASS["X"]) * count

    # Sorted by fraction descending, then alphabetically by residue.
    composition = [
        {"residue": res, "fraction": round(count / total_len, 4)}
        for res, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]

    return {
        "length": total_len,
        "estimatedMassKDa": round(mass / 1000.0, 2),
        "composition": composition,
    }

