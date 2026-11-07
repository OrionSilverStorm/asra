/**
 * The list of comparison species offered in the form, plus small helpers.
 *
 * To add a species: add its ID to `SpeciesId` in types.ts, then add an entry
 * here. The dropdown picks it up automatically.
 */

import type { Species, SpeciesId } from "./types";

/** Every species the user can pick, in display order within each group. */
export const SPECIES: Species[] = [
  // Rodents: the usual first-line preclinical models
  { id: "mus_musculus", commonName: "Mouse", scientificName: "Mus musculus", group: "Rodent" },
  { id: "rattus_norvegicus", commonName: "Rat", scientificName: "Rattus norvegicus", group: "Rodent" },
  { id: "cavia_porcellus", commonName: "Guinea pig", scientificName: "Cavia porcellus", group: "Rodent" },
  // Non-human primates: closest to human, used for biologics
  { id: "macaca_mulatta", commonName: "Rhesus macaque", scientificName: "Macaca mulatta", group: "Non-human primate" },
  { id: "macaca_fascicularis", commonName: "Cynomolgus macaque", scientificName: "Macaca fascicularis", group: "Non-human primate" },
  // Non-rodent mammals: common second species in regulatory toxicology
  { id: "canis_lupus_familiaris", commonName: "Dog (beagle)", scientificName: "Canis lupus familiaris", group: "Non-rodent mammal" },
  { id: "sus_scrofa", commonName: "Minipig", scientificName: "Sus scrofa", group: "Non-rodent mammal" },
  { id: "oryctolagus_cuniculus", commonName: "Rabbit", scientificName: "Oryctolagus cuniculus", group: "Non-rodent mammal" },
  // Other
  { id: "danio_rerio", commonName: "Zebrafish", scientificName: "Danio rerio", group: "Other" },
];

/** Order in which groups appear as <optgroup>s in the dropdown. */
export const SPECIES_GROUPS: Species["group"][] = [
  "Rodent",
  "Non-human primate",
  "Non-rodent mammal",
  "Other",
];

/**
 * Look up a species by ID. Throws if the ID is unknown, which should be
 * impossible because IDs are validated before a request is built.
 */
export function getSpecies(id: SpeciesId): Species {
  const found = SPECIES.find((s) => s.id === id);
  if (!found) throw new Error(`Unknown species: ${id}`);
  return found;
}

/**
 * Type guard: narrows a plain string (e.g. a <select> value) to SpeciesId.
 * After `if (isSpeciesId(v))`, TypeScript treats `v` as a SpeciesId.
 */
export function isSpeciesId(value: string): value is SpeciesId {
  return SPECIES.some((s) => s.id === value);
}
