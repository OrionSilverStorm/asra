/**
 * SequenceInput: the protein-sequence text box.
 *
 * Controlled by AssessmentForm. While the user types, the hint line shows
 * a live residue count and whether a gene was found in the FASTA header
 * (no gene = only sequence statistics will run), so they can sanity-check
 * the input before submitting.
 */

import { Field } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Textarea";
import { EXAMPLE_HEADER, EXAMPLE_SEQUENCE, geneFromLabel, parseSequence } from "@/lib/sequence";

interface SequenceInputProps {
  /** Raw text exactly as typed/pasted. */
  value: string;
  onChange: (value: string) => void;
  /** Validation message from the form, if any. */
  error?: string | null;
  /** True while a request is running. */
  disabled?: boolean;
}

export function SequenceInput({ value, onChange, error, disabled }: SequenceInputProps) {
  const id = "sequence";

  // Re-parse on every render. It's cheap (single pass over the string) and
  // keeps the live count in sync without extra state.
  const { sequence, label } = parseSequence(value);

  // Gene the backend will resolve from the header (same rule, see lib/sequence.ts).
  const gene = geneFromLabel(label);

  // Empty box -> instructions; otherwise -> "N residues · gene status".
  const hint = value.trim() ? (
    <>
      {sequence.length.toLocaleString()} residues ·{" "}
      {gene ? (
        <span className="text-ok">gene {gene}: full orthologue comparison will run</span>
      ) : (
        <span className="text-warn">
          no gene found{label ? " in header" : ""}: only sequence statistics will run. Use a UniProt header with GN=…
        </span>
      )}
    </>
  ) : (
    "Single-letter amino-acid codes. Raw sequence or one FASTA record."
  );

  return (
    <Field id={id} step={2} label="Enter a protein sequence" hint={hint} error={error}>
      <Textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        invalid={!!error}
        disabled={disabled}
        rows={8}
        // Sequences aren't words: turn off spellcheck squiggles and autofill.
        spellCheck={false}
        autoComplete="off"
        // Plain-language instruction, then a real FASTA record (human insulin)
        // so the expected shape is obvious without reading the hint.
        // Example truncated to one line of residues so the placeholder stays short.
        placeholder={`Paste a protein sequence, with or without a FASTA header. For example:\n\n${EXAMPLE_HEADER}\n${EXAMPLE_SEQUENCE.slice(0, 60)}…`}
        aria-describedby={error ? `${id}-error` : `${id}-hint`}
        // Monospace so residues line up; break-all so long lines wrap.
        className="resize-y font-mono text-[13px] leading-relaxed break-all"
      />
    </Field>
  );
}
