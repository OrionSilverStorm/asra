/**
 * Button: the one button component used everywhere.
 *
 * Wraps a native <button> so it keeps all native behaviour (keyboard,
 * disabled, form submit) and only adds consistent styling via `variant`.
 */

import type { ButtonHTMLAttributes } from "react";

/** Visual styles: primary = main action, secondary = outlined, ghost = text-only. */
type Variant = "primary" | "secondary" | "ghost";

/** Tailwind classes per variant. Colours come from tokens in globals.css. */
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:opacity-90",
  secondary: "border border-rule bg-surface text-ink hover:bg-sunken",
  ghost: "text-muted hover:text-ink hover:bg-sunken",
};

/** All native button props, plus our `variant`. */
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  // `type` defaults to "button" so a Button inside a <form> doesn't submit
  // it by accident; pass type="submit" explicitly for the submit button.
  return (
    <button
      type={type}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
