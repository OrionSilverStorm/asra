/**
 * Legend: a row of coloured squares with labels, like the confidence key
 * under an AlphaFold structure. Used for residue classes, layer status
 * and concern levels, so every colour-coded view explains itself.
 */

export interface LegendItem {
  label: string;
  /** Tailwind background class for the swatch, e.g. "bg-ok". */
  swatch: string;
}

export function Legend({ items, label }: { items: LegendItem[]; label: string }) {
  return (
    // aria-label names the legend for screen readers (e.g. "Status key").
    <ul aria-label={label} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span aria-hidden className={`size-2.5 rounded-sm ${i.swatch}`} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}
