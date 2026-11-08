/**
 * Benchmark case studies offered by the form's "Load a benchmark case" dropdown.
 *
 * Single source of truth for the dropdown: adding a case here is the only edit
 * needed, since AssessmentForm derives both the options and their groups from
 * this array.
 *
 * Every case submits the **human** protein and selects the animal to compare it
 * against. That matches Backend/tools/resolver.py `gene_from_label`, which only
 * takes a gene symbol from a human UniProt header's `GN=` field.
 *
 * Sequences are the canonical UniProt entries, fetched verbatim from
 * https://rest.uniprot.org/uniprotkb/<accession>.fasta — never hand-typed.
 *
 * Cases 1-4 are the project's committed benchmarks (tests/test_cases.md).
 * Cases 5-6 widen the species coverage beyond mouse and macaque; their
 * citations still need pinning before they appear in a write-up.
 */

import { EXAMPLE_HEADER, EXAMPLE_SEQUENCE } from "./sequence";
import type { SpeciesId } from "./types";

/** Dropdown groupings, in the order they appear. */
export type CaseGroup = "Harm cases" | "Did not translate" | "Controls";

/** The order <optgroup>s are rendered in; harm cases lead because they demo best. */
export const CASE_GROUPS: CaseGroup[] = ["Harm cases", "Did not translate", "Controls"];

export interface CaseStudy {
  /** Stable <option> value; never shown to the user. */
  id: string;
  /** Dropdown text: drug or control, then gene and comparison species. */
  label: string;
  /** Which <optgroup> the option sits in. */
  group: CaseGroup;
  /** Species pre-selected in the form when this case is loaded. */
  species: SpeciesId;
  /** Human gene symbol; the backend re-derives it from the header's GN=. */
  gene: string;
  /** FASTA header, kept verbatim so GN= resolves. */
  header: string;
  /** Residues only, no whitespace or line breaks. */
  sequence: string;
}

// ── Sequences ──────────────────────────────────────────────────────────────
// Case 1 reuses lib/sequence.ts so the sequence-box placeholder and this
// dropdown can never drift apart. The rest are inlined, split at the 60-residue
// line breaks of the source FASTA purely for readability.

/** UniProt P10747, human CD28, 220 aa. */
const CD28 =
  "MLRLLLALNLFPSIQVTGNKILVKQSPMLVAYDNAVNLSCKYSYNLFSREFRASLHKGLD" +
  "SAVEVCVVYGNYSQQLQVYSKTGFNCDGKLGNESVTFYLQNLYVNQTDIYFCKIEVMYPP" +
  "PYLDNEKSNGTIIHVKGKHLCPSPLFPGPSKPFWVLVVVGGVLACYSLLVTVAFIIFWVR" +
  "SKRSRLLHSDYMNMTPRRPGPTRKHYQPYAPPRDFAAYRS";

/** UniProt P04406, human GAPDH, 335 aa. */
const GAPDH =
  "MGKVKVGVNGFGRIGRLVTRAAFNSGKVDIVAINDPFIDLNYMVYMFQYDSTHGKFHGTV" +
  "KAENGKLVINGNPITIFQERDPSKIKWGDAGAEYVVESTGVFTTMEKAGAHLQGGAKRVI" +
  "ISAPSADAPMFVMGVNHEKYDNSLKIISNASCTTNCLAPLAKVIHDNFGIVEGLMTTVHA" +
  "ITATQKTVDGPSGKLWRDGRGALQNIIPASTGAAKAVGKVIPELNGKLTGMAFRVPTANV" +
  "SVVDLTCRLEKPAKYDDIKKVVKQASEGPLKGILGYTEHQVVSSDFNSDTHSSTFDAGAG" +
  "IALNDHFVKLISWYDNEFGYSNRVVDLMAHMASKE";

/** UniProt P08684, human CYP3A4, 503 aa. */
const CYP3A4 =
  "MALIPDLAMETWLLLAVSLVLLYLYGTHSHGLFKKLGIPGPTPLPFLGNILSYHKGFCMF" +
  "DMECHKKYGKVWGFYDGQQPVLAITDPDMIKTVLVKECYSVFTNRRPFGPVGFMKSAISI" +
  "AEDEEWKRLRSLLSPTFTSGKLKEMVPIIAQYGDVLVRNLRREAETGKPVTLKDVFGAYS" +
  "MDVITSTSFGVNIDSLNNPQDPFVENTKKLLRFDFLDPFFLSITVFPFLIPILEVLNICV" +
  "FPREVTNFLRKSVKRMKESRLEDTQKHRVDFLQLMIDSQNSKETESHKALSDLELVAQSI" +
  "IFIFAGYETTSSVLSFIMYELATHPDVQQKLQEEIDAVLPNKAPPTYDTVLQMEYLDMVV" +
  "NETLRLFPIAMRLERVCKKDVEINGMFIPKGVVVMIPSYALHRDPKYWTEPEKFLPERFS" +
  "KKNKDNIDPYIYTPFGSGPRNCIGMRFALMNMKLALIRVLQNFSFKPCKETQIPLKLSLG" +
  "GLLQPEKPVVLKVESRDGTVSGA";

/** UniProt Q96SW2, human cereblon (CRBN), 442 aa. */
const CRBN =
  "MAGEGDQQDAAHNMGNHLPLLPAESEEEDEMEVEDQDSKEAKKPNIINFDTSLPTSHTYL" +
  "GADMEEFHGRTLHDDDSCQVIPVLPQVMMILIPGQTLPLQLFHPQEVSMVRNLIQKDRTF" +
  "AVLAYSNVQEREAQFGTTAEIYAYREEQDFGIEIVKVKAIGRQRFKVLELRTQSDGIQQA" +
  "KVQILPECVLPSTMSAVQLESLNKCQIFPSKPVSREDQCSYKWWQKYQKRKFHCANLTSW" +
  "PRWLYSLYDAETLMDRIKKQLREWDENLKDDSLPSNPIDFSYRVAACLPIDDVLRIQLLK" +
  "IGSAIQRLRCELDIMNKCTSLCCKQCQETEITTKNEIFSLSLCGPMAAYVNPHGYVHETL" +
  "TVYKACNLNLIGRPSTEHSWFPGYAWTVAQCKICASHIGWKFTATKKDMSPQKFWGLTRS" +
  "ALLPTIPDTEDEISPDKVILCL";

/** UniProt Q07869, human PPARα, 468 aa. */
const PPARA =
  "MVDTESPLCPLSPLEAGDLESPLSEEFLQEMGNIQEISQSIGEDSSGSFGFTEYQYLGSC" +
  "PGSDGSVITDTLSPASSPSSVTYPVVPGSVDESPSGALNIECRICGDKASGYHYGVHACE" +
  "GCKGFFRRTIRLKLVYDKCDRSCKIQKKNRNKCQYCRFHKCLSVGMSHNAIRFGRMPRSE" +
  "KAKLKAEILTCEHDIEDSETADLKSLAKRIYEAYLKNFNMNKVKARVILSGKASNNPPFV" +
  "IHDMETLCMAEKTLVAKLVANGIQNKEAEVRIFHCCQCTSVETVTELTEFAKAIPGFANL" +
  "DLNDQVTLLKYGVYEAIFAMLSSVMNKDGMLVAYGNGFITREFLKSLRKPFCDIMEPKFD" +
  "FAMKFNALELDDSDISLFVAAIICCGDRPGLLNVGHIEKMQEGIVHVLRLHLQSNHPDDI" +
  "FLFPKLLQKMADLRQLVTEHAQLVQIIKKTESDAALHPLLQEIYRDMY";

// ── The cases ──────────────────────────────────────────────────────────────

export const CASE_STUDIES: CaseStudy[] = [
  {
    // Benchmark case 1. Mouse ENT1 has no experimental localisation in UniProt,
    // so the localisation layer is expected to return 'incomplete'.
    id: "fialuridine",
    label: "Fialuridine · SLC29A1 (ENT1) · mouse",
    group: "Harm cases",
    species: "mus_musculus",
    gene: "SLC29A1",
    header: EXAMPLE_HEADER,
    sequence: EXAMPLE_SEQUENCE,
  },
  {
    // Benchmark case 2. Cynomolgus is the species actually dosed preclinically;
    // the recorded Census run covers rhesus, so expect the human-only fallback.
    id: "tgn1412",
    label: "TGN1412 · CD28 · cynomolgus macaque",
    group: "Harm cases",
    species: "macaca_fascicularis",
    gene: "CD28",
    header:
      ">sp|P10747|CD28_HUMAN T-cell-specific surface glycoprotein CD28 OS=Homo sapiens OX=9606 GN=CD28 PE=1 SV=1",
    sequence: CD28,
  },
  {
    // Added case. Rabbit is the sensitive species and the rodents are not, so a
    // human/rabbit difference is NOT the explanation for the human harm: this
    // doubles as a test of whether the Sceptic pushes back on that framing.
    id: "thalidomide",
    label: "Thalidomide · CRBN · rabbit",
    group: "Harm cases",
    species: "oryctolagus_cuniculus",
    gene: "CRBN",
    header: ">sp|Q96SW2|CRBN_HUMAN Protein cereblon OS=Homo sapiens OX=9606 GN=CRBN PE=1 SV=1",
    sequence: CRBN,
  },
  {
    // Added case, and the inverse direction: the animal over-predicted harm.
    // Rodent liver expresses far more PPARalpha than human liver, so the rodent
    // tumour signal did not carry over.
    id: "fibrates",
    label: "Fibrates (PPARα agonists) · PPARA · rat",
    group: "Did not translate",
    species: "rattus_norvegicus",
    gene: "PPARA",
    header:
      ">sp|Q07869|PPARA_HUMAN Peroxisome proliferator-activated receptor alpha OS=Homo sapiens OX=9606 GN=PPARA PE=1 SV=2",
    sequence: PPARA,
  },
  {
    // Benchmark case 3: specificity control. Raising any concern here is a fail.
    id: "gapdh",
    label: "Conserved control · GAPDH · mouse",
    group: "Controls",
    species: "mus_musculus",
    gene: "GAPDH",
    header:
      ">sp|P04406|G3P_HUMAN Glyceraldehyde-3-phosphate dehydrogenase OS=Homo sapiens OX=9606 GN=GAPDH PE=1 SV=3",
    sequence: GAPDH,
  },
  {
    // Benchmark case 4: honesty under absence. The mouse Cyp3a locus holds at
    // least six genes, so no single identity figure is defensible.
    id: "cyp3a4",
    label: "Missing data · CYP3A4 · mouse",
    group: "Controls",
    species: "mus_musculus",
    gene: "CYP3A4",
    header: ">sp|P08684|CP3A4_HUMAN Cytochrome P450 3A4 OS=Homo sapiens OX=9606 GN=CYP3A4 PE=1 SV=4",
    sequence: CYP3A4,
  },
];

/** The FASTA text a case puts in the sequence box: header line, then residues. */
export const caseFasta = (c: CaseStudy): string => `${c.header}\n${c.sequence}`;

/** Look a case up by its <option> value; undefined for the empty placeholder. */
export const findCase = (id: string): CaseStudy | undefined =>
  CASE_STUDIES.find((c) => c.id === id);
