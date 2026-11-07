/**
 * SectionNav: sticky "On this page" list of anchors, as on UniProt and
 * AlphaFold DB entry pages. Shown from `lg` up beside the report; hidden on
 * phones (one column) and in print (links are useless on paper).
 */

export interface NavSection {
  /** Anchor id of the section wrapper in ReportView. */
  id: string;
  label: string;
}

export function SectionNav({ sections }: { sections: NavSection[] }) {
  return (
    <nav aria-label="On this page" className="sticky top-4 hidden self-start lg:block print:hidden">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">On this page</p>
      {/* Left rule with each link as an indented row, like a docs sidebar. */}
      <ul className="flex flex-col border-l border-rule text-sm">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className="-ml-px block border-l-2 border-transparent py-1 pl-3 text-muted transition hover:border-accent hover:text-accent"
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
