/**
 * Checkbox: a single tick box with a label and optional hint.
 *
 * Not built on Field: a checkbox puts its label after the control, so the
 * layout differs from the text-style inputs.
 */

interface CheckboxProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Helper text under the label. */
  hint?: string;
  disabled?: boolean;
}

export function Checkbox({ id, label, checked, onChange, hint, disabled }: CheckboxProps) {
  return (
    <div className="flex items-start gap-2.5">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        // mt-0.5 nudges the box onto the label's first line.
        className="mt-0.5 size-4 shrink-0 accent-accent focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
      />
      <div className="flex flex-col gap-0.5">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint && (
          <p id={`${id}-hint`} className="text-sm text-muted">
            {hint}
          </p>
        )}
      </div>
    </div>
  );
}
