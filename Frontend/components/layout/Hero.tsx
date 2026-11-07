/**
 * Hero: compact page intro, in the style of a research-portal query page
 * (title, one-line description, the databases it draws on).
 * A Server Component (no interactivity), so it ships no JavaScript.
 */

import { LAYER_META, LAYER_ORDER } from "@/lib/layers";
import { Container } from "./Container";
import { HeroArt } from "./HeroArt";

export function Hero() {
  return (
    // print:hidden: the intro is left out of printed/PDF reports.
    <section className="border-b border-rule bg-surface print:hidden">
      {/* Text left, decorative alignment art right (from `md` up). */}
      <Container className="flex items-center justify-between gap-8 py-7">
        <div className="min-w-0">
          {/* Breadcrumb-style context line, as on portal pages. */}
          <p className="mb-1.5 text-xs text-muted">Home / New assessment</p>
          <h1 className="text-2xl font-semibold tracking-tight">Cross-species comparison</h1>
          {/* What it does, and the code-computes / agents-interpret split. */}
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Check what sequence identity alone would miss before committing to an animal model. ASRA
            compares human and animal biology across sequence, subcellular localisation, cell-type and
            tissue expression. Every value is computed by code; agents only interpret the evidence, and
            a scientist signs off.
          </p>
          {/* Data-source chips, generated from the layer metadata. */}
          <ul className="mt-4 flex flex-wrap items-center gap-2 text-xs" aria-label="Data sources">
            {LAYER_ORDER.map((l) => (
              <li key={l} className="rounded border border-rule bg-sunken px-2 py-1">
                <span className="text-muted">{LAYER_META[l].title}: </span>
                <span className="font-medium">{LAYER_META[l].source}</span>
            </li>
          ))}
        </ul>
        </div>
        <HeroArt />
      </Container>
    </section>
  );
}
