/**
 * SiteHeader: top bar on every page (rendered by app/layout.tsx).
 *
 * A navy "portal" bar (as on cBioPortal / EMBL-EBI sites) with the ASRA
 * wordmark, in-page nav, a version chip and the theme toggle. Directly
 * underneath is the caveat strip: the design doc requires the "not a
 * safety prediction" caveat on every screen, and the header guarantees it.
 */

import Link from "next/link";
import { CaveatBanner } from "@/components/report/CaveatBanner";
import { Container } from "./Container";
import { ThemeToggle } from "./ThemeToggle";

/** In-page anchors (no extra routes): query form and footer sections. */
const NAV = [
  { href: "/#query", label: "Query" },
  { href: "/#data-sources", label: "Data sources" },
  { href: "/#about", label: "About" },
];

export function SiteHeader() {
  return (
    <header>
      {/* The bar itself is left out of printed reports; the caveat stays. */}
      <div className="bg-chrome text-chrome-ink print:hidden">
        <Container className="flex h-14 items-center gap-6">
          {/* Wordmark links home. Next's <Link> does client-side navigation. */}
          <Link href="/" className="flex items-center gap-2.5">
            {/* Square logo mark, like the badge-style marks of research portals. */}
            <span aria-hidden className="grid size-7 place-items-center rounded bg-accent font-mono text-xs font-bold text-accent-ink">
              AS
            </span>
            <span className="text-base font-semibold tracking-tight">ASRA</span>
            {/* Full name hidden on phones to save space. */}
            <span className="hidden text-sm text-chrome-muted md:inline">Across-Species Risk Assessment</span>
          </Link>

          {/* Section links, hidden on phones where the page is short anyway. */}
          <nav aria-label="Main" className="hidden gap-5 text-sm sm:flex">
            {NAV.map((n) => (
              <a key={n.href} href={n.href} className="text-chrome-muted transition hover:text-chrome-ink">
                {n.label}
              </a>
            ))}
          </nav>

          {/* Right side: version chip + theme toggle. */}
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden rounded border border-chrome-muted/40 px-2 py-0.5 font-mono text-[11px] text-chrome-muted lg:inline">
              v0.1 · research preview
            </span>
            <ThemeToggle />
          </div>
        </Container>
      </div>
      {/* Mandatory caveat, visible on every page. */}
      <CaveatBanner variant="strip" />
    </header>
  );
}
