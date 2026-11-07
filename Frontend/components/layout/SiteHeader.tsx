/**
 * SiteHeader: top bar on every page (rendered by app/layout.tsx).
 *
 * Shows the ASRA wordmark and, directly underneath, the caveat strip. The
 * design doc requires the "not a safety prediction" caveat on every screen,
 * and putting it in the header guarantees that.
 */

import Link from "next/link";
import { CaveatBanner } from "@/components/report/CaveatBanner";
import { Container } from "./Container";

export function SiteHeader() {
  return (
    // Slightly translucent surface with blur, for a clean layered look.
    <header className="border-b border-rule bg-surface/80 backdrop-blur">
      <Container className="flex h-16 items-center justify-between">
        {/* Wordmark links home. Next's <Link> does client-side navigation. */}
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-serif text-xl font-semibold tracking-tight">ASRA</span>
          {/* Full name hidden on phones to save space. */}
          <span className="hidden text-sm text-muted sm:inline">Across-Species Risk Assessment</span>
        </Link>
        <span className="text-xs font-medium uppercase tracking-wider text-muted">Research preview</span>
      </Container>
      {/* Mandatory caveat, visible on every page. */}
      <CaveatBanner variant="strip" />
    </header>
  );
}
