/**
 * Hero: the intro section at the top of the home page.
 * A Server Component (no interactivity), so it ships no JavaScript.
 */

import { Container } from "./Container";

export function Hero() {
  return (
    // print:hidden — the marketing intro is left out of printed/PDF reports.
    <section className="border-b border-rule print:hidden">
      <Container className="py-12 sm:py-16">
        {/* Eyebrow label in the accent colour. */}
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-accent">
          Cross-species comparison
        </p>
        {/* Page's main <h1>: the value proposition in one sentence. */}
        <h1 className="max-w-3xl font-serif text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          Check what sequence identity alone would miss, before committing to an animal model.
        </h1>
        {/* Short summary of the architecture: code computes, agents interpret, human signs off. */}
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          ASRA compares human and animal biology across sequence, subcellular localisation,
          cell-type and tissue expression. Every value is computed by code; agents only interpret
          the evidence, and a scientist signs off.
        </p>
      </Container>
    </section>
  );
}
