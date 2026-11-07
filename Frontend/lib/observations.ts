/**
 * Groups a layer's observations into human-vs-animal pairs for display.
 *
 * Layers report matching facts as `human_<key>` / `animal_<key>` (e.g.
 * human_compartments / animal_compartments). Pairing them lets the UI show
 * a side-by-side comparison. Pure function: no values are changed or computed.
 */

import type { Observation } from "./types";

/** One human/animal pair sharing a key. */
export interface ObservationPair {
  /** Readable key, e.g. "cell population". */
  label: string;
  human: Observation;
  animal: Observation;
  /** True when the two values are not the identical string (display hint only). */
  differs: boolean;
}

/** Splits observations into pairs and everything that has no partner. */
export function pairObservations(observations: Observation[]): {
  pairs: ObservationPair[];
  rest: Observation[];
} {
  // Field name → observation, for O(1) partner lookup.
  const byField = new Map(observations.map((o) => [o.field, o]));
  const pairs: ObservationPair[] = [];
  // Fields consumed by a pair, so they're left out of `rest`.
  const used = new Set<string>();

  for (const human of observations) {
    if (!human.field.startsWith("human_")) continue;
    const key = human.field.slice("human_".length);
    const animal = byField.get(`animal_${key}`);
    // No animal partner (e.g. human_only_compartments): stays in `rest`.
    if (!animal) continue;
    pairs.push({
      label: key.replace(/_/g, " "),
      human,
      animal,
      differs: human.value.trim() !== animal.value.trim(),
    });
    used.add(human.field).add(animal.field);
  }

  return { pairs, rest: observations.filter((o) => !used.has(o.field)) };
}
