/**
 * Container: centres content and applies the site's max width and side
 * padding (16px on phones, more on larger screens). Every page section
 * wraps its content in one so edges line up across the site.
 */

import type { ReactNode } from "react";

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8 ${className}`}>{children}</div>;
}
