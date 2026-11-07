/**
 * Select: a styled native <select>.
 * Native is used on purpose: it is accessible and mobile-friendly for free.
 */

import type { SelectHTMLAttributes } from "react";
import { inputBase, inputBorder } from "./Field";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Red border + aria-invalid when true. */
  invalid?: boolean;
}

export function Select({ invalid = false, className = "", ...props }: SelectProps) {
  return (
    <select
      // `|| undefined` omits the attribute entirely when valid.
      aria-invalid={invalid || undefined}
      className={`${inputBase} ${inputBorder(invalid)} h-9 px-2.5 text-sm ${className}`}
      {...props}
    />
  );
}
