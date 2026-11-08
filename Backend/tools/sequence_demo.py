from __future__ import annotations
"""Offline SLC29A1 Milestone 3 demonstration: python -m tools.sequence_demo.

Uses raw UniProt responses/release headers and the Ensembl protein identities
already pinned by Milestone 2. No live orthology call is claimed by this replay.
"""

from hashlib import sha256
import json
from pathlib import Path

from tools.sequence import align_proteins
from tools.sequence_adapter import to_layer_result
from tools.sequence_functional import add_functional_analysis

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "role3"
PROTEINS = {
    "human": ("Q99808", "ENSP00000360820", "ENSG00000112759", "homo_sapiens",
              "49bca4bf056d239c66207751c15e2f1bf5c5f810a8685932c00ef588360f46ae"),
    "animal": ("Q9JIM1", "ENSMUSP00000063096", "ENSMUSG00000023942", "mus_musculus",
               "8b9af2e71601f3c470efac73271b652b839acad3382426f71753c58e81af5284"),
}


def demonstration():
    """Replay verified annotations with exact sequence and raw snapshot hashes."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    entries, proteins = {}, {}
    for label, (accession, protein_id, gene_id, species, digest) in PROTEINS.items():
        raw = (FIXTURES / f"{accession}.json").read_bytes()
        if sha256(raw).hexdigest() != manifest[accession]["response_sha256"]:
            raise ValueError("UniProt snapshot checksum mismatch.")
        entry = json.loads(raw)
        sequence = entry["sequence"]["value"]
        if sha256(sequence.encode("ascii")).hexdigest() != digest:
            raise ValueError("Sequence differs from the pinned Milestone 2 Ensembl protein.")
        entries[protein_id] = (entry, manifest[accession])
        proteins[label] = {"protein_id": protein_id, "gene_id": gene_id,
                           "species": species, "sequence": sequence}
    result = {
        "gene": "SLC29A1", "species": "mus_musculus", "layer": "sequence", "status": "ok",
        **proteins, "orthology": {"type": "ortholog_one2one", "evidence": "Milestone 2 pinned pair; offline replay"},
        "source_records": [{"id": "ensembl_orthology", "source": "Milestone 2 pinned Ensembl protein pair",
                            "url": "https://rest.ensembl.org/homology/symbol/homo_sapiens/SLC29A1?target_species=mus_musculus&type=orthologues&sequence=protein&aligned=0&format=full"}],
        "retrieved_at": manifest["Q99808"]["retrieved_at"], "data_version": None,
        "provenance": {"mode": "offline snapshot replay", "ensembl_release": "unknown",
                       "sequence_hashes": {label: record[-1] for label, record in PROTEINS.items()}},
        **align_proteins(proteins["human"]["sequence"], proteins["animal"]["sequence"]),
    }
    enriched = add_functional_analysis(result, retrieve=lambda p: entries[p["protein_id"]])
    to_layer_result(enriched)  # Ensure the shared adapter accepts all evidence.
    return enriched


if __name__ == "__main__":
    result = demonstration()
    analysis = result["functional_analysis"]
    print(json.dumps({
        "status": result["status"], "measurements": result["measurements"],
        "proteins": {k: {"identity": v["identity"], "feature_count": len(v["features"])}
                     for k, v in analysis["proteins"].items()},
        "functional_substitutions": len(analysis["functional_substitutions"]),
        "other_substitutions": len(analysis["other_substitutions"]),
        "unclassified_substitutions": len(analysis["unclassified_substitutions"]),
        "slc29a1_motif": analysis["slc29a1_motif"], "limitations": result["limitations"],
    }, indent=2))
