/**
 * SiteFooter: institutional-style footer (as on EMBL-EBI resources) in
 * three short columns: about, data sources, scope.
 * `mt-auto` pushes it to the bottom even when the page content is short
 * (the <body> is a flex column, see app/layout.tsx). The ids are targets
 * for the header nav.
 */

import { LAYER_META, LAYER_ORDER } from "@/lib/layers";
import { Container } from "./Container";

/** Small uppercase column heading, shared by all three columns. */
function ColumnTitle({ children }: { children: string }) {
  return <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-chrome-ink">{children}</h2>;
}

export function SiteFooter() {
  return (
    // Hidden in print: a dark block wastes ink, and the report carries its own caveat.
    <footer className="mt-auto bg-chrome text-sm text-chrome-muted print:hidden">
      {/* One column on phones, three from `sm` up. */}
      <Container className="grid gap-8 py-8 sm:grid-cols-3">
        <div id="about" className="scroll-mt-4">
          <ColumnTitle>About</ColumnTitle>
          <p>ASRA · Across-Species Risk Assessment</p>
          <p>Agentverse 2026, UCL Biotech Track</p>
        </div>
        {/* Data sources, generated from the layer metadata. */}
        <div id="data-sources" className="scroll-mt-4">
          <ColumnTitle>Data sources</ColumnTitle>
          <ul className="flex flex-col gap-1">
            {LAYER_ORDER.map((l) => (
              <li key={l}>
                {LAYER_META[l].title}: <span className="text-chrome-ink">{LAYER_META[l].source}</span>
              </li>
            ))}
          </ul>
        </div>
        {/* Scope statement from the design doc. */}
        <div>
          <ColumnTitle>Scope</ColumnTitle>
          <p>Retrospective explanation, not validated prediction. No patient data.</p>
        </div>
      </Container>
    </footer>
  );
}
