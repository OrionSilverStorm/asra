/**
 * SequenceViewer: the submitted sequence in UniProt style: monospace
 * blocks of 10 residues, each labelled with its end position.
 *
 * Blocks wrap as whole units, so the view fits any width (no horizontal
 * scroll on phones). Long sequences scroll inside a capped-height box on
 * screen and print in full.
 */

/** Residues per block (the UniProt / FASTA convention). */
const BLOCK = 10;

export function SequenceViewer({ sequence }: { sequence: string }) {
  // Split into consecutive 10-residue chunks; the last may be shorter.
  const blocks = Array.from({ length: Math.ceil(sequence.length / BLOCK) }, (_, i) =>
    sequence.slice(i * BLOCK, (i + 1) * BLOCK),
  );

  return (
    <div
      // Labelled so screen readers announce it as the sequence, not 50 numbers.
      aria-label={`Sequence, ${sequence.length} residues`}
      role="group"
      className="max-h-56 overflow-y-auto rounded border border-rule bg-sunken px-3 py-2.5 print:max-h-none print:overflow-visible"
    >
      <div className="flex flex-wrap gap-x-3 gap-y-1.5 font-mono text-[13px] leading-tight">
        {blocks.map((b, i) => (
          <span key={i} className="flex flex-col">
            {/* End position of this block, right-aligned above it. */}
            <span aria-hidden className="text-right text-[10px] text-muted">
              {i * BLOCK + b.length}
            </span>
            <span className="tracking-wide">{b}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
