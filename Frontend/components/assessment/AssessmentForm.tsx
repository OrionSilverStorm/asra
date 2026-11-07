"use client";
// ^ Client Component: it uses state and event handlers, which only run in
//   the browser. Everything it imports is bundled for the client too.

/**
 * AssessmentForm: species dropdown + sequence box + buttons.
 *
 * Owns the input values and validation errors. It does NOT make network
 * calls. On a valid submit it builds an AssessmentRequest and hands it to
 * `onSubmit`, and the parent (AssessmentWorkspace) decides what to do.
 */

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { parseSequence, validateSequence } from "@/lib/sequence";
import { isSpeciesId } from "@/lib/species";
import type { AssessmentRequest } from "@/lib/types";
import { SequenceInput } from "./SequenceInput";
import { SpeciesSelect } from "./SpeciesSelect";

interface AssessmentFormProps {
  /** Called with a validated request when the user submits. */
  onSubmit: (request: AssessmentRequest) => void;
  /** True while the parent is waiting on a response; disables inputs. */
  submitting: boolean;
}

/** One optional message per field; null/undefined = no error. */
interface Errors {
  species?: string | null;
  sequence?: string | null;
}

export function AssessmentForm({ onSubmit, submitting }: AssessmentFormProps) {
  // Raw input values (controlled inputs).
  const [species, setSpecies] = useState("");
  const [sequence, setSequence] = useState("");
  // Validation messages, only filled in on submit.
  const [errors, setErrors] = useState<Errors>({});

  function handleSubmit(e: FormEvent) {
    // Stop the browser's default full-page form submission.
    e.preventDefault();

    // Validate both fields at once so the user sees every problem together.
    const next: Errors = {
      species: isSpeciesId(species) ? null : "Choose a comparison species.",
      sequence: validateSequence(sequence),
    };
    setErrors(next);

    // Bail on any error. The `isSpeciesId` re-check also narrows the type.
    if (next.species || next.sequence || !isSpeciesId(species)) return;

    // Send the cleaned sequence, not the raw text.
    const parsed = parseSequence(sequence);
    onSubmit({ species, sequence: parsed.sequence, sequenceLabel: parsed.label });
  }

  return (
    // noValidate: we do our own validation with nicer messages.
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <SpeciesSelect
        value={species}
        onChange={(v) => {
          setSpecies(v);
          // Clear this field's error as soon as the user changes it.
          setErrors((er) => ({ ...er, species: null }));
        }}
        error={errors.species}
        disabled={submitting}
      />
      <SequenceInput
        value={sequence}
        onChange={(v) => {
          setSequence(v);
          setErrors((er) => ({ ...er, sequence: null }));
        }}
        error={errors.sequence}
        disabled={submitting}
      />

      {/* Action row, separated from the inputs by a rule. */}
      <div className="flex items-center justify-end gap-3 border-t border-rule pt-5">
        {/* Clear: disabled when there is nothing to clear. */}
        <Button
          variant="ghost"
          disabled={submitting || (!species && !sequence)}
          onClick={() => {
            setSpecies("");
            setSequence("");
            setErrors({});
          }}
        >
          Clear
        </Button>
        {/* Submit: shows a spinner and changes text while running. */}
        <Button type="submit" disabled={submitting}>
          {submitting && <Spinner />}
          {submitting ? "Running assessment…" : "Run assessment"}
        </Button>
      </div>
    </form>
  );
}
