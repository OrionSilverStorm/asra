from __future__ import annotations
"""Sequence statistics computed directly from the submitted protein.

Pure Python, no network. Mirrors Frontend/lib/sequence.ts `computeStats`
so both sides report identical numbers.
"""

from collections import Counter

from contract import ResidueFraction, SequenceStats

# Average residue masses in Daltons (water removed).
RESIDUE_MASS = {
    "A": 71.08, "R": 156.19, "N": 114.10, "D": 115.09, "C": 103.14, "E": 129.12, "Q": 128.13,
    "G": 57.05, "H": 137.14, "I": 113.16, "L": 113.16, "K": 128.17, "M": 131.19, "F": 147.18,
    "P": 97.12, "S": 87.08, "T": 101.10, "W": 186.21, "Y": 163.18, "V": 99.13, "X": 110.00,
}
# One water molecule is added per chain for the free termini.
WATER_MASS = 18.02


def compute_stats(sequence: str) -> SequenceStats:
    """Length, approximate mass (kDa) and residue composition, most common first."""
    counts = Counter(sequence)
    mass_da = WATER_MASS + sum(RESIDUE_MASS.get(r, RESIDUE_MASS["X"]) * n for r, n in counts.items())
    return SequenceStats(
        length=len(sequence),
        # Daltons -> kilodaltons, 2 decimal places (same rounding as the frontend).
        estimated_mass_k_da=round(mass_da / 1000, 2),
        composition=[
            ResidueFraction(residue=r, fraction=n / len(sequence)) for r, n in counts.most_common()
        ],
    )
