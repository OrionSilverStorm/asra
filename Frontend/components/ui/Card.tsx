/**
 * Card primitives: a flat bordered panel with a grey heading bar and a body,
 * as used for entry sections on UniProt / AlphaFold DB.
 *
 * Usage:
 *   <Card id="evidence">
 *     <CardHeader eyebrow="Evidence" title="Comparison layers" />
 *     <CardBody>...</CardBody>
 *   </Card>
 */

import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Anchor id, so the report's "On this page" nav can link here. */
  id?: string;
}

/** Outer container. Rendered as <section> so each card is a landmark region. */
export function Card({ children, className = "", id }: CardProps) {
  return (
    // scroll-mt-4: leave a gap above the card when jumped to via an anchor.
    <section id={id} className={`scroll-mt-4 overflow-hidden rounded border border-rule bg-surface ${className}`}>
      {children}
    </section>
  );
}

interface CardHeaderProps {
  /** Main heading. */
  title: string;
  /** Small uppercase label above the title, e.g. "Evidence". */
  eyebrow?: string;
  /** Optional content on the right, e.g. a count, legend or button. */
  actions?: ReactNode;
}

/** Grey heading bar with title, eyebrow and optional actions. */
export function CardHeader({ title, eyebrow, actions }: CardHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-rule bg-sunken px-4 py-2.5 sm:px-5">
      <div>
        {eyebrow && (
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{eyebrow}</p>
        )}
        <h2 className="text-[15px] font-semibold">{title}</h2>
      </div>
      {actions}
    </header>
  );
}

/** Padded content area. Pass `className` for grid/flex layouts inside. */
export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-4 py-4 sm:px-5 ${className}`}>{children}</div>;
}
