/**
 * Card primitives: a bordered panel with an optional header and a body.
 *
 * Usage:
 *   <Card>
 *     <CardHeader eyebrow="Evidence" title="Comparison layers" />
 *     <CardBody>...</CardBody>
 *   </Card>
 */

import type { ReactNode } from "react";

/** Outer container. Rendered as <section> so each card is a landmark region. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-rule bg-surface ${className}`}>{children}</section>
  );
}

interface CardHeaderProps {
  /** Main heading (serif). */
  title: string;
  /** Small uppercase label above the title, e.g. "Evidence". */
  eyebrow?: string;
  /** Optional content on the right, e.g. a count or a button. */
  actions?: ReactNode;
}

/** Top strip of a card with title, eyebrow and optional actions. */
export function CardHeader({ title, eyebrow, actions }: CardHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-rule px-5 py-4 sm:px-6">
      <div>
        {eyebrow && (
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted">{eyebrow}</p>
        )}
        <h2 className="font-serif text-lg font-semibold">{title}</h2>
      </div>
      {actions}
    </header>
  );
}

/** Padded content area. Pass `className` for grid/flex layouts inside. */
export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 py-5 sm:px-6 ${className}`}>{children}</div>;
}
