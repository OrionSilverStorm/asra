/**
 * Textarea: a styled native <textarea> sharing styles with Select.
 */

import type { TextareaHTMLAttributes } from "react";
import { inputBase, inputBorder } from "./Field";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Red border + aria-invalid when true. */
  invalid?: boolean;
}

export function Textarea({ invalid = false, className = "", ...props }: TextareaProps) {
  return (
    <textarea
      // `|| undefined` omits the attribute entirely when valid.
      aria-invalid={invalid || undefined}
      className={`${inputBase} ${inputBorder(invalid)} px-3 py-2.5 ${className}`}
      {...props}
    />
  );
}
