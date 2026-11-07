/**
 * SpeciesSelect: the "Comparison species" dropdown.
 *
 * A controlled input: the parent (AssessmentForm) owns the value and passes
 * it in, and gets told about changes via `onChange`. Options are generated
 * from lib/species.ts and grouped by animal type.
 */

import { Field } from "@/components/ui/Field";
import { Select } from "@/components/ui/Select";
import { SPECIES, SPECIES_GROUPS } from "@/lib/species";

interface SpeciesSelectProps {
  /** Currently selected SpeciesId, or "" for nothing selected. */
  value: string;
  onChange: (value: string) => void;
  /** Validation message from the form, if any. */
  error?: string | null;
  /** True while a request is running. */
  disabled?: boolean;
}

export function SpeciesSelect({ value, onChange, error, disabled }: SpeciesSelectProps) {
  const id = "species";
  return (
    <Field id={id} step={1} label="Select a comparison species" hint="Compared against the human orthologue." error={error}>
      <Select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        invalid={!!error}
        disabled={disabled}
        // Screen readers read the error if present, otherwise the hint.
        aria-describedby={error ? `${id}-error` : `${id}-hint`}
      >
        {/* Placeholder: shown initially, can't be re-selected. */}
        <option value="" disabled>
          Select a species…
        </option>
        {/* One <optgroup> per group, containing that group's species. */}
        {SPECIES_GROUPS.map((group) => (
          <optgroup key={group} label={group}>
            {SPECIES.filter((s) => s.group === group).map((s) => (
              <option key={s.id} value={s.id}>
                {s.commonName} ({s.scientificName})
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
    </Field>
  );
}
