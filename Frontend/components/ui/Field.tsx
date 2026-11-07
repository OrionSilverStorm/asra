/**
 * Field: label + input slot + hint/error text, wired up for accessibility.
 *
 * The input itself is passed as `children`, so Field works with Select,
 * Textarea or anything else. Give the input `id={id}` and
 * `aria-describedby` pointing at `${id}-error` or `${id}-hint` so screen
 * readers announce the helper text.
 */

import type { ReactNode } from "react";

interface FieldProps {
  /** Must match the child input's id (links <label htmlFor>). */
  id: string;
  label: string;
  /** Optional step number shown before the label (numbered query form). */
  step?: number;
  /** Helper text shown when there is no error. */
  hint?: ReactNode;
  /** Error message; replaces the hint and turns red. */
  error?: string | null;
  children: ReactNode;
}

export function Field({ id, label, step, hint, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="flex items-center gap-2 text-sm font-semibold">
        {/* Numbered circle, as on the cBioPortal query page. */}
        {step !== undefined && (
          <span aria-hidden className="grid size-5 place-items-center rounded-full bg-accent text-[11px] font-bold text-accent-ink">
            {step}
          </span>
        )}
        {label}
      </label>
      {children}
      {/* Show the error if there is one, otherwise the hint (if any). */}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-sm text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

/** Classes shared by every text-style input (Select, Textarea). */
export const inputBase =
  "w-full rounded border bg-surface text-ink placeholder:text-muted/70 transition focus:outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-60";

/** Border colour: red when invalid, otherwise neutral with accent on focus. */
export function inputBorder(invalid: boolean) {
  return invalid ? "border-danger" : "border-rule focus:border-accent";
}
