/**
 * Protein-sequence utilities: parsing, validation and basic statistics.
 *
 * Pure functions with no React or browser dependencies, so they can be unit
 * tested on their own and reused anywhere (form, mock, report).
 */

import type { SequenceStats } from "./types";

/** The 20 standard amino acids plus X (unknown). Anything else is rejected. */
const VALID_RESIDUES = new Set("ACDEFGHIKLMNPQRSTVWYX".split(""));

/**
 * Average residue masses in Daltons (water removed). A peptide's mass is the
 * sum of its residues plus one water molecule for the free ends.
 */
const RESIDUE_MASS: Record<string, number> = {
  A: 71.08, R: 156.19, N: 114.1, D: 115.09, C: 103.14, E: 129.12, Q: 128.13,
  G: 57.05, H: 137.14, I: 113.16, L: 113.16, K: 128.17, M: 131.19, F: 147.18,
  P: 97.12, S: 87.08, T: 101.1, W: 186.21, Y: 163.18, V: 99.13, X: 110,
};
/** Mass of one water molecule, added once per chain. */
const WATER_MASS = 18.02;

/** Shortest sequence we accept; anything shorter is almost certainly a mistake. */
export const MIN_SEQUENCE_LENGTH = 10;

/** Result of parsing whatever the user pasted. */
export interface ParsedSequence {
  /** FASTA header text (without ">"), or null for a raw sequence. */
  label: string | null;
  /** Cleaned, uppercase residues. */
  sequence: string;
  /** Unique characters that are not valid residues (empty when valid). */
  invalidChars: string[];
}

/**
 * Accepts raw sequence or single-record FASTA.
 * Strips whitespace, digits (from numbered formats) and a trailing stop "*".
 */
export function parseSequence(input: string): ParsedSequence {
  const lines = input.trim().split(/\r?\n/);

  // A FASTA record starts with a ">" header line; pull it off if present.
  let label: string | null = null;
  if (lines[0]?.startsWith(">")) {
    label = lines.shift()!.slice(1).trim() || null;
  }

  // Join the remaining lines and remove formatting characters.
  const sequence = lines
    .join("")
    .replace(/[\s\d]/g, "") // spaces, newlines, position numbers
    .replace(/\*$/, "") // translation stop codon marker
    .toUpperCase();

  // Collect each offending character once so the error message stays short.
  const invalidChars = [...new Set(sequence.split("").filter((c) => !VALID_RESIDUES.has(c)))];
  return { label, sequence, invalidChars };
}

/**
 * Returns a user-facing error message, or null if the input is acceptable.
 * Checks run in order, so the user sees the most fundamental problem first.
 */
export function validateSequence(input: string): string | null {
  if (!input.trim()) return "Paste a protein sequence.";
  const { sequence, invalidChars } = parseSequence(input);

  // More than one ">" header means a multi-record FASTA file.
  if (input.trim().split(/\r?\n/).filter((l) => l.startsWith(">")).length > 1) {
    return "Only one FASTA record is supported.";
  }
  if (invalidChars.length) {
    return `Invalid residue character${invalidChars.length > 1 ? "s" : ""}: ${invalidChars.join(", ")}`;
  }
  if (sequence.length < MIN_SEQUENCE_LENGTH) {
    return `Sequence must be at least ${MIN_SEQUENCE_LENGTH} residues.`;
  }
  return null;
}

/**
 * Computes length, approximate mass and residue composition.
 * Expects an already-parsed, valid sequence.
 */
export function computeStats(sequence: string): SequenceStats {
  const counts = new Map<string, number>();
  let mass = WATER_MASS;

  // Single pass: count each residue and accumulate mass.
  for (const r of sequence) {
    counts.set(r, (counts.get(r) ?? 0) + 1);
    mass += RESIDUE_MASS[r] ?? RESIDUE_MASS.X;
  }

  // Turn counts into fractions, most common residue first.
  const composition = [...counts.entries()]
    .map(([residue, n]) => ({ residue, fraction: n / sequence.length }))
    .sort((a, b) => b.fraction - a.fraction);

  return {
    length: sequence.length,
    // Daltons -> kilodaltons, rounded to 2 decimal places.
    estimatedMassKDa: Math.round(mass / 10) / 100,
    composition,
  };
}
