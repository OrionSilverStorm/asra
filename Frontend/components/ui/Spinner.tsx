/**
 * Spinner: a small CSS-only loading indicator.
 * Uses `currentColor`, so it matches the text colour of wherever it sits
 * (e.g. white inside the primary button).
 */
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      // Decorative only; the loading state is announced via text elsewhere.
      aria-hidden
      // A circle with one transparent side, rotated forever = spinner.
      className={`inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    />
  );
}
