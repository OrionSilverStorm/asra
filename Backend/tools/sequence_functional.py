"""Role 3 Milestone 3: verified UniProt features and alignment observations.

No gene-name/fuzzy sequence matching or automatic annotation transfer. UniProt
cross-reference, organism, displayed isoform and exact full sequence must agree.
Non-displayed isoforms are reported as unsupported rather than reusing canonical
coordinates. All mappings describe the selected traceback, not functional effects.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import re

import httpx

BASE = "https://rest.uniprot.org/uniprotkb"
FEATURE_TYPES = frozenset({
    "Active site", "Binding site", "Site", "Domain", "Region", "Motif",
    "DNA binding", "Calcium binding", "Zinc finger", "Metal binding",
    "Nucleotide binding", "Transmembrane",
    "Modified residue", "Glycosylation", "Mutagenesis",
})
STANDARD = frozenset("ACDEFGHIKLMNPQRSTVWY")
LITERATURE_ID = "doi:10.1074/jbc.M513825200"
LITERATURE = {
    "id": LITERATURE_ID,
    "source": "Lee et al. (2006), J Biol Chem 281:16700–16706; PMID 16595656",
    "url": "https://doi.org/10.1074/jbc.M513825200",
}


class AnnotationError(RuntimeError):
    """Unusable annotation evidence; sequence measurements remain available."""

    code = "invalid_annotation_response"


class AnnotationAPIError(AnnotationError):
    """Transport/HTTP failure, distinct from missing biological records."""

    code = "api_failure"


class MissingUniProtMappingError(AnnotationError):
    """Successful search returned no protein cross-reference mapping."""

    code = "missing_uniprot_mapping"


class UnverifiedUniProtMappingError(AnnotationError):
    """Candidates exist but identity cannot be uniquely verified."""

    code = "unverified_uniprot_mapping"


def _get(url, *, params=None):
    """Bounded read with explicit API/JSON errors and response metadata."""
    try:
        response = httpx.get(url, params=params, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise AnnotationAPIError(f"UniProt retrieval failed: {type(exc).__name__}: {exc}") from exc
    except ValueError as exc:
        raise AnnotationError("UniProt returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise AnnotationError("UniProt JSON must be an object.")
    return payload, {
        "url": str(response.url),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "release": response.headers.get("x-uniprot-release"),
        "release_date": response.headers.get("x-uniprot-release-date"),
        "pagination_present": 'rel="next"' in response.headers.get("link", ""),
    }


def _same_id(requested, returned):
    # Ensembl omits versions in homology. Explicit requested versions must agree.
    return requested == returned or ("." not in requested and requested == returned.split(".")[0])


def verify_entry(protein, entry, provenance):
    """Verify the exact coordinate-bearing sequence, accession and isoform."""
    accession = entry.get("primaryAccession")
    if not isinstance(accession, str) or not re.fullmatch(r"[A-Z0-9]+", accession):
        raise AnnotationError("Missing/invalid primary UniProt accession.")
    scientific = entry.get("organism", {}).get("scientificName", "")
    if scientific.lower().replace(" ", "_") != protein.get("species"):
        raise AnnotationError("UniProt organism does not match the resolved protein species.")
    expected_taxon = protein.get("metadata", {}).get("taxon_id")
    if expected_taxon is not None and str(expected_taxon) != str(entry["organism"].get("taxonId")):
        raise AnnotationError("UniProt taxon does not match the Ensembl taxon.")
    matches = []
    for ref in entry.get("uniProtKBCrossReferences", []):
        if ref.get("database") != "Ensembl":
            continue
        properties = {p["key"]: p["value"] for p in ref.get("properties", [])}
        if _same_id(protein["protein_id"], properties.get("ProteinId", "")):
            if protein.get("gene_id") and not _same_id(protein["gene_id"], properties.get("GeneId", "")):
                continue
            matches.append(ref)
    if not matches:
        raise AnnotationError("No matching Ensembl protein/gene cross-reference in UniProt.")
    isoforms = [iso for c in entry.get("comments", []) if c.get("commentType") == "ALTERNATIVE PRODUCTS"
                for iso in c.get("isoforms", [])]
    displayed = {i for iso in isoforms if iso.get("isoformSequenceStatus") == "Displayed"
                 for i in iso.get("isoformIds", [])}
    linked = {ref.get("isoformId", accession) for ref in matches}
    if len(linked) != 1:
        raise AnnotationError("Ambiguous Ensembl-to-UniProt isoform cross-references.")
    isoform = next(iter(linked))
    if isoform != accession and isoform not in displayed:
        raise AnnotationError(f"Non-displayed isoform {isoform}: canonical feature coordinates unsupported.")
    seq = entry.get("sequence", {}).get("value")
    if not seq or seq != protein["sequence"] or set(seq) - STANDARD:
        raise AnnotationError("UniProt displayed sequence is not an exact unambiguous full-length match.")
    return {
        "status": "verified", "accession": accession, "isoform": isoform,
        "coordinate_sequence": "displayed", "protein_id": protein["protein_id"],
        "organism": deepcopy(entry["organism"]), "cross_references": deepcopy(matches),
        "sequence_sha256": sha256(seq.encode("ascii")).hexdigest(),
        "entry_audit": deepcopy(entry.get("entryAudit", {})),
        # Exact sequence verification is distinct from curation/experimental support.
        "entry_type": entry.get("entryType"),
        "protein_existence": entry.get("proteinExistence"),
        "source_record_id": f"uniprot:{accession}",
        **{key: deepcopy(provenance[key]) for key in
           ("url", "retrieved_at", "release", "release_date", "search", "rejected_candidates")
           if key in provenance},
    }


def retrieve_annotations(protein):
    """Search by protein xref, check all results; never pick a first hit."""
    protein_id = protein.get("protein_id", "")
    if not re.fullmatch(r"ENS[A-Z]*P[0-9]+(?:\.[0-9]+)?", protein_id):
        raise AnnotationError("A valid Ensembl protein identifier is required for UniProt lookup.")
    payload, search = _get(f"{BASE}/search", params={
        "query": f"xref:ensembl-{protein_id.split('.')[0]}", "format": "json", "size": 500,
    })
    if search["pagination_present"]:
        raise AnnotationError("UniProt search is paginated; mapping remains ambiguous.")
    if not isinstance(payload.get("results"), list):
        raise AnnotationError("UniProt search has no results list.")
    if not payload["results"]:
        raise MissingUniProtMappingError("UniProt search returned no Ensembl protein cross-reference mapping.")
    verified, rejected = [], []
    for candidate in payload["results"]:
        try:
            identity = verify_entry(protein, candidate, search)
            verified.append((candidate, identity))
        except (AnnotationError, KeyError, TypeError, AttributeError) as exc:
            rejected.append(str(exc))
    if len(verified) != 1:
        raise UnverifiedUniProtMappingError(f"Expected one verified UniProt mapping; got {len(verified)}. Rejected: {rejected}")
    candidate, identity = verified[0]
    # Retrieve accession-specific JSON; the search result and record must agree.
    entry, provenance = _get(f"{BASE}/{identity['accession']}.json")
    checked = verify_entry(protein, entry, provenance)
    if any(checked[key] != identity[key] for key in ("accession", "isoform", "sequence_sha256")):
        raise AnnotationError("UniProt search and accession response disagree on identity.")
    checked["search"] = search
    checked["rejected_candidates"] = rejected
    return entry, checked


def extract_features(entry, identity):
    """Keep raw evidence including ECO codes; uncertain endpoints stay unmapped."""
    result = []
    sequence = entry["sequence"]["value"]
    for index, feature in enumerate(entry.get("features", [])):
        if feature.get("type") not in FEATURE_TYPES:
            continue
        location = feature.get("location", {})
        start, end = location.get("start", {}), location.get("end", {})
        lo, hi = start.get("value"), end.get("value")
        exact = (type(lo) is int and type(hi) is int and 1 <= lo <= hi <= len(sequence)
                 and start.get("modifier") == end.get("modifier") == "EXACT"
                 and location.get("sequence", identity["isoform"]) in
                 {identity["accession"], identity["isoform"]})
        result.append({
            "id": f"{identity['source_record_id']}:feature:{index}",
            "origin": "UniProt", "source_record_id": identity["source_record_id"],
            "type": feature["type"], "description": feature.get("description", ""),
            "start": lo, "end": hi, "coordinate_status": "exact" if exact else "unsupported",
            "raw": deepcopy(feature),
            "evidence_references": [
                {**e, "url": f"https://pubmed.ncbi.nlm.nih.gov/{e['id']}/"}
                if e.get("source") == "PubMed" and e.get("id") else deepcopy(e)
                for e in feature.get("evidences", [])],
        })
    return result


def map_feature(feature, result):
    """Map every human position explicitly; gaps/ambiguous residues stay visible."""
    mapped = {**deepcopy(feature), "residues": []}
    if feature["coordinate_status"] != "exact":
        mapped["mapping_status"] = "unsupported_coordinates"
        return mapped
    human, animal = result["human"]["sequence"], result["animal"]["sequence"]
    mapping, reverse = result["human_to_animal"], result["animal_to_human"]
    if not 1 <= feature["start"] <= feature["end"] <= len(human):
        raise AnnotationError("Feature coordinates exceed the human sequence.")
    for position in range(feature["start"], feature["end"] + 1):
        if position not in mapping and str(position) not in mapping:
            raise AnnotationError("Missing human alignment mapping coordinate.")
        target = mapping.get(position, mapping.get(str(position)))
        if target is None:
            state, residue = "gap", None
        elif type(target) is not int or not 1 <= target <= len(animal) or reverse.get(target, reverse.get(str(target))) != position:
            raise AnnotationError("Non-reciprocal/out-of-range alignment mapping.")
        else:
            residue = animal[target - 1]
            state = ("ambiguous" if human[position - 1] not in STANDARD or residue not in STANDARD
                     else "identical" if human[position - 1] == residue else "substitution")
        mapped["residues"].append({"human_position": position, "animal_position": target,
                                   "human_residue": human[position - 1], "animal_residue": residue,
                                   "state": state})
    mapped["mapping_status"] = ("selected_traceback_only" if result["parameters"]["alternative_optimal_alignment_exists"]
                                else "mapped")
    mapped["interpretation"] = "Aligned sequence observation; no animal annotation or functional effect inferred."
    return mapped


def slc29a1_motif(result, identity):
    """A curated, accession-anchored literature check, not a general motif scan."""
    supported = (result.get("gene", "").upper() == "SLC29A1"
                 and identity.get("accession") == "Q99808"
                 and identity.get("coordinate_sequence") == "displayed")
    evidence = {
        "status": "unsupported", "source_record_id": LITERATURE_ID,
        "literature": {
            "human_positions": [71, 72, 73, 74], "pattern": "PEXN", "critical_positions": [71, 72, 74],
            "mechanism": "Lee et al. implicated an internal N-terminal-region PEXN sequence in hENT1 mitochondrial targeting.",
            "experiments": "Confocal microscopy of tagged truncated/point-mutant ENT1 in MDCK cells; human PEXN-to-PAXS lost mitochondrial localisation, mouse PAXS-to-PEXN acquired partial localisation. Mouse liver mitochondrial FIAU uptake was also tested.",
            "scope": "Published construct/cell and mouse-liver experiments; not a universal targeting predictor or a toxicity prediction. Published in 2006, after the 1993 clinical failure.",
        },
        "sequence_observation": None,
    }
    feature = None
    if supported:
        window = result["human"]["sequence"][70:74]
        if len(window) == 4 and window[0] == "P" and window[1] == "E" and window[3] == "N":
            feature = {"id": "literature:slc29a1:71-74", "origin": "literature",
                       "source_record_id": LITERATURE_ID, "type": "Motif",
                       "description": "SLC29A1 PEXN mitochondrial-targeting region (Lee 2006)",
                       "start": 71, "end": 74, "coordinate_status": "exact"}
            mapped = map_feature(feature, result)
            residues = mapped["residues"]
            positions = [r["animal_position"] for r in residues]
            contiguous = all(p is not None for p in positions) and positions == list(range(positions[0], positions[0] + 4))
            evidence["status"] = "observed"
            evidence["sequence_observation"] = {
                "human_window": window, "residues": residues,
                "animal_contiguous": contiguous,
                "animal_window": "".join(r["animal_residue"] for r in residues) if contiguous else None,
                "alignment_ambiguous": mapped["mapping_status"] == "selected_traceback_only",
                "interpretation": "Computed from these exact proteins and selected alignment; localisation and toxicity were not measured.",
            }
        else:
            evidence["reason"] = "Verified human sequence does not support literature coordinate anchor; no motif finding."
    else:
        evidence["reason"] = "Requires verified displayed human Q99808 and SLC29A1; no unsupported motif scan performed."
    return evidence, feature


def add_functional_analysis(result, *, retrieve=None):
    """Enrich a rich Role 3 result without mutating it; preserve partial evidence."""
    output = deepcopy(result)
    retrieve = retrieve or retrieve_annotations
    analysis = {"status": "ok", "proteins": {}, "mapped_human_features": [],
                "functional_substitutions": [], "other_substitutions": [],
                "unclassified_substitutions": [], "limitations": [
                    "Missing annotations are not evidence of biological absence; other substitutions have no selected annotation overlap, not proven lack of effect.",
                    "Feature overlap (including mutagenesis records) does not establish the effect of a naturally occurring substitution, altered function or drug toxicity.",
                    "Only displayed UniProt sequences are supported; non-displayed isoforms require explicit isoform annotations before coordinate transfer.",
                ]}
    for label in ("human", "animal"):
        try:
            entry, identity = retrieve(result[label])
            # Recheck injected/cached retrieval as rigorously as live retrieval.
            identity = verify_entry(result[label], entry, identity)
            features = extract_features(entry, identity)
            analysis["proteins"][label] = {"identity": identity, "features": features,
                                           "status": "ok" if features else "incomplete",
                                           "reason_code": None if features else "insufficient_functional_annotations"}
            output["source_records"].append({"id": identity["source_record_id"], "source": "UniProtKB",
                                              "url": f"{BASE}/{identity['accession']}.json"})
            if not features:
                analysis["limitations"].append(f"{label}: no selected functional feature annotations returned.")
            if any(f["coordinate_status"] != "exact" for f in features):
                analysis["proteins"][label]["status"] = "incomplete"
                analysis["proteins"][label]["reason_code"] = "insufficient_functional_annotations"
                analysis["limitations"].append(f"{label}: uncertain or isoform-specific feature coordinates were not projected.")
        except (AnnotationError, KeyError, TypeError, AttributeError) as exc:
            analysis["proteins"][label] = {"status": "unavailable", "identity": None, "features": [],
                                           "reason": str(exc), "reason_code": getattr(exc, "code", "invalid_annotation_response")}
            analysis["limitations"].append(f"{label}: {exc}")
    human = analysis["proteins"]["human"]
    try:
        motif, literature_feature = slc29a1_motif(result, human["identity"] or {})
    except AnnotationError as exc:
        motif, literature_feature = {"status": "unsupported", "reason": str(exc),
                                    "source_record_id": LITERATURE_ID, "sequence_observation": None}, None
        human["status"] = "incomplete"
        analysis["limitations"].append(f"Motif projection failed: {exc}")
    analysis["slc29a1_motif"] = motif
    if result.get("gene", "").upper() == "SLC29A1":
        output["source_records"].append(dict(LITERATURE))
    if human["identity"]:
        features = list(human["features"])
        if literature_feature:
            features.append(literature_feature)
        try:
            analysis["mapped_human_features"] = [map_feature(f, result) for f in features]
        except AnnotationError as exc:
            human["status"] = "incomplete"
            analysis["limitations"].append(f"Human feature projection failed: {exc}")
    animal_features = analysis["proteins"]["animal"]["features"]
    for substitution in result["substitutions"]:
        overlaps = [{"feature_id": f["id"], "protein": label, "source_record_id": f["source_record_id"]}
                    for label, features, position in (
                        ("human", analysis["mapped_human_features"], substitution["human_position"]),
                        ("animal", animal_features, substitution["animal_position"]))
                    for f in features if f["coordinate_status"] == "exact" and f["start"] <= position <= f["end"]]
        key = ("functional_substitutions" if overlaps else "other_substitutions"
               if all(p["status"] == "ok" for p in analysis["proteins"].values()) else "unclassified_substitutions")
        analysis[key].append({**substitution, "annotation_overlaps": overlaps})
    if any(p["status"] != "ok" for p in analysis["proteins"].values()):
        analysis["status"] = "incomplete"
    if result["parameters"]["alternative_optimal_alignment_exists"]:
        analysis["status"] = "incomplete"
        analysis["limitations"].append("Alternative optimal tracebacks exist; mapped features and overlaps depend on the selected traceback.")
    output["functional_analysis"] = analysis
    output["source_records"].append({"id": "sequence_functional_analysis",
                                      "source": "Role 3 alignment analysis; underlying sources cited within functional_analysis"})
    output["status"] = "incomplete" if analysis["status"] != "ok" else result["status"]
    output["limitations"] = [x for x in output["limitations"] if "No functional annotations" not in x] + analysis["limitations"]
    return output
