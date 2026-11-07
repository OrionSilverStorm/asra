/**
 * SiteFooter: bottom strip on every page.
 * `mt-auto` pushes it to the bottom even when the page content is short
 * (the <body> is a flex column, see app/layout.tsx).
 */

import { Container } from "./Container";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-rule">
      {/* Stacked on phones, side by side from the `sm` breakpoint up. */}
      <Container className="flex flex-col gap-2 py-6 text-sm text-muted sm:flex-row sm:justify-between">
        <p>ASRA · Agentverse 2026, UCL Biotech Track</p>
        {/* Scope statement from the design doc. */}
        <p>Retrospective explanation, not validated prediction. No patient data.</p>
      </Container>
    </footer>
  );
}
