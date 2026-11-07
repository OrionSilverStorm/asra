# Precache gene list — why each entry is in it

Companion to `precache_genes.txt`.

- **GAPDH** — conserved control, already a benchmark case. Proves the system raises no
  alarm on a conserved housekeeping gene.
- **ACTB** — second conserved control, backup if a judge wants a different one.
- **CLDN18** — the headline live-demo target. Claudin 18.2 is an active oncology target
  (zolbetuximab, CAR-T and ADC programmes). CLDN18.1 and CLDN18.2 differ only in exon 1,
  so the therapeutic rationale rests entirely on which isoform is expressed where — a
  direct test of the isoform-pinning trap. Not a historical case: a target someone is
  choosing a species for right now.
- **KRAS** — second current target, highly annotated, safe fallback if CLDN18 returns
  thin data.
- **GPR15** — poor-annotation case, for demonstrating an honest "insufficient data"
  response. Annotation coverage to be verified in UniProt before the demo.
