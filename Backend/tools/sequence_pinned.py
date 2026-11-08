"""Verified SLC29A1 human/mouse snapshot, used only by the transient-error path."""
from hashlib import sha256
import json
from pathlib import Path

from tools.resolver import InvalidEnsemblResponseError, _protein_record
from tools.sequence import _sequence_evidence
from tools.sequence_functional import verify_entry

PINNED = Path(__file__).resolve().parents[1] / "data/sequence/slc29a1"
FILE_HASHES = {
    "homology.json": "fa218cd537f988840c240fa2c0d3d0953351c8875b9048cb82b99bc72519389a",
    "manifest.json": "16410ed67d9e6d25d510c11656e562027bcb201e18cfb5fbd3f31bbce197653e",
    "Q99808.json": "e96bdde7656c7db1b0c9f2d82f29594641a7611022fb44c3cf4c2f57818fa5f6",
    "Q9JIM1.json": "8f7337103be2b661a6aca28ffe18d32f0e24e4fd109a89fb3c5e8d7926849094",
}
EXPECTED = (
    ("Q99808", "ENSG00000112759", "ENSP00000360820", "homo_sapiens", "49bca4bf056d239c66207751c15e2f1bf5c5f810a8685932c00ef588360f46ae"),
    ("Q9JIM1", "ENSMUSG00000023942", "ENSMUSP00000063096", "mus_musculus", "8b9af2e71601f3c470efac73271b652b839acad3382426f71753c58e81af5284"),
)
SOURCE_URL = "https://rest.ensembl.org/homology/symbol/homo_sapiens/SLC29A1?target_species=mus_musculus&type=orthologues&sequence=protein&aligned=0&format=full"


def _load():
    records = {}
    for name, digest in FILE_HASHES.items():
        raw = (PINNED / name).read_bytes()
        if sha256(raw).hexdigest() != digest:
            raise ValueError(f"Pinned {name} checksum mismatch")
        records[name] = json.loads(raw)
    return records


def pinned_slc29a1(gene, species, failure):
    """No HTTP, reports or saved metrics: validate raw records then align anew."""
    if (gene, species) != ("SLC29A1", "mus_musculus"):
        raise InvalidEnsemblResponseError("No verified pinned pair for this query")
    try:
        records = _load()
        tape = records["homology.json"]
        data = json.loads(tape["body"])["data"]
        if tape["status_code"] != 200 or tape["url"] != SOURCE_URL or len(data) != 1 or len(data[0]["homologies"]) != 1:
            raise ValueError("Pinned homology source mismatch")
        relationship = data[0]["homologies"][0]
        if relationship["type"] != "ortholog_one2one":
            raise ValueError("Pinned orthology is not unique one-to-one")
        proteins = {}
        for side, (accession, gene_id, protein_id, organism, digest) in zip(("source", "target"), EXPECTED):
            protein = _protein_record(relationship[side], organism)
            if (protein["gene_id"], protein["protein_id"]) != (gene_id, protein_id):
                raise ValueError("Pinned Ensembl identifiers mismatch")
            if sha256(protein["sequence"].encode("ascii")).hexdigest() != digest:
                raise ValueError("Pinned sequence checksum mismatch")
            entry = records[f"{accession}.json"]
            if entry["primaryAccession"] != accession:
                raise ValueError("Pinned UniProt accession mismatch")
            metadata = records["manifest.json"][accession]
            if metadata["url"] != f"https://rest.uniprot.org/uniprotkb/{accession}.json":
                raise ValueError("Pinned UniProt citation mismatch")
            verify_entry(protein, entry, metadata)  # full sequence, species and Ensembl cross-reference
            proteins[side] = protein
        output = _sequence_evidence({"gene": gene, "species": species, **proteins,
            "orthology": {k: v for k, v in relationship.items() if k not in {"source", "target"}},
            "source_url": SOURCE_URL})
        output["status"] = "incomplete"
        output["retrieved_at"] = tape["retrieved_at"]
        output["data_version"] = "Pinned Ensembl homology (release unknown); UniProt 2026_04 snapshots"
        output["source_records"][0]["source"] = "Pinned Ensembl REST homology snapshot; not a fresh retrieval"
        for accession, *_ in EXPECTED:
            output["source_records"].append({"id": f"pinned_uniprot:{accession}",
                "source": f"Recorded UniProt {accession}", "url": records["manifest.json"][accession]["url"]})
        output["provenance"].update({"mode": "pinned snapshot fallback; not fresh live evidence",
            "fallback_reason": failure, "snapshot_file_sha256": FILE_HASHES.copy(),
            "uniprot_snapshots": records["manifest.json"],
            "accessions": {side: row[0] for side, row in zip(("human", "animal"), EXPECTED)}})
        output["limitations"] = [
            "Pinned/recorded evidence after transient Ensembl failure: " + failure,
            "Original snapshot retrieval dates are retained; no current orthology or annotation retrieval is claimed.",
            "Ensembl release is unknown. UniProt release describes the independent recorded sequence verification only.",
            "Functional annotations were not refreshed or projected by this fallback; sequence similarity does not establish functional equivalence.",
            *[s for s in output["limitations"] if "Retrieval time is recorded" not in s],
        ]
        return output
    except (OSError, ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
        raise InvalidEnsemblResponseError(f"Pinned sequence evidence rejected: {exc}") from exc
