"""Role 3 live frontend compatibility audit and reproducible HTTP replay.

Run from Backend: python -m tools.sequence_species_audit --live --output PATH.
Only this explicit audit reads frontend source. Runtime sequence tools do not
depend on TypeScript files. HTTP calls are sequential with >=0.4 s spacing,
20 s operation timeouts and one bounded retry for transient HTTP/transport errors.
Successful UniProt responses are reused within one audit (reported as cache hits).
Resolver and run_sequence homology calls each hit the live service separately.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from unittest.mock import patch

import httpx

from tools.resolver import (
    resolve_orthologue, OrthologueNotFoundError, AmbiguousOrthologueError,
    EnsemblAPIError, MissingSequenceError, InvalidEnsemblResponseError,
)
from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SPECIES = ROOT / "Frontend" / "lib" / "species.ts"
CD28_SPECIES = ("macaca_mulatta", "macaca_fascicularis", "mus_musculus")


def frontend_species(path=FRONTEND_SPECIES):
    """Extract literal selectable IDs; fail rather than silently miss new syntax."""
    source = path.read_text()
    block = re.search(r"export const SPECIES:\s*Species\[\]\s*=\s*\[(.*?)\];", source, re.S)
    if not block:
        raise ValueError("Frontend SPECIES declaration changed; review extraction.")
    species = re.findall(r'\{\s*id:\s*"([^"]+)"', block[1])
    if not species or len(species) != len(set(species)) or len(species) != block[1].count("{ id:"):
        raise ValueError("Frontend species extraction is incomplete or ambiguous.")
    return species


def error_record(exc):
    """Machine-readable failure categories; keep raw candidates for ambiguity."""
    category = next((code for cls, code in (
        (OrthologueNotFoundError, "orthologue_unavailable"),
        (AmbiguousOrthologueError, "ambiguous_orthologue"),
        (EnsemblAPIError, "api_failure"),
        (MissingSequenceError, "missing_sequence"),
        (InvalidEnsemblResponseError, "invalid_ensembl_response"),
        (httpx.HTTPError, "api_failure"),
    ) if isinstance(exc, cls)), "unexpected_error")
    result = {"status": category, "error_type": type(exc).__name__, "reason": str(exc)}
    if isinstance(exc, AmbiguousOrthologueError):
        result["candidates"] = exc.candidates
    return result


def protein_summary(protein):
    return {key: protein[key] for key in ("gene_id", "protein_id", "species")} | {
        "sequence_length": len(protein["sequence"]),
        "sequence_sha256": sha256(protein["sequence"].encode("ascii")).hexdigest(),
    }


class RecordedHTTP:
    """A scoped audit-only wrapper around real HTTP with a persistent tape."""

    def __init__(self, output, *, replay=False):
        self.output = Path(output)
        self.replay = replay
        self.records = json.loads((self.output / "http.json").read_text()) if replay else []
        self.events, self.cache = [], {}
        self.last_request = 0.0
        self.actual_get = httpx.get
        self.cursor = 0

    def get(self, url, **kwargs):
        key = str(httpx.Request("GET", url, params=kwargs.get("params")).url)
        if key in self.cache:
            self.events.append({"url": key, "cache_hit": True})
            return self.cache[key]
        for attempt in range(2):
            if self.replay:
                record = self.records[self.cursor]
                self.cursor += 1
                if record["url"] != key:
                    raise ValueError(f"Replay URL mismatch: {record['url']} != {key}")
            else:
                time.sleep(max(0.0, 0.4 - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                record = {"url": key, "attempt": attempt + 1, "retrieved_at": datetime.now(timezone.utc).isoformat()}
                try:
                    response = self.actual_get(url, **{**kwargs, "timeout": httpx.Timeout(20, connect=10)})
                    record.update(status_code=response.status_code, body=response.text,
                                  headers={k: v for k, v in response.headers.items() if k in {
                                      "x-uniprot-release", "x-uniprot-release-date", "date", "link",
                                      "retry-after", "x-ratelimit-remaining", "x-ratelimit-reset"}})
                except httpx.HTTPError as exc:
                    record.update(error_type=type(exc).__name__, error=str(exc))
                self.records.append(record)
                self.output.mkdir(parents=True, exist_ok=True)
                (self.output / "http.json").write_text(json.dumps(self.records, indent=2) + "\n")
            self.events.append({k: v for k, v in record.items() if k != "body"})
            transient = "error" in record or record.get("status_code") in {429, 500, 502, 503, 504}
            if transient and attempt == 0:
                retry = record.get("headers", {}).get("retry-after", "1")
                try:
                    delay = max(1.0, float(retry))
                except ValueError:
                    delay = None
                # Fail explicitly rather than retry before a long/date Retry-After.
                if delay is not None and delay <= 5.0:
                    if not self.replay:
                        time.sleep(delay)
                    continue
            if "error" in record:
                cls = httpx.ReadTimeout if "Timeout" in record["error_type"] else httpx.RequestError
                raise cls(record["error"], request=httpx.Request("GET", key))
            response = httpx.Response(record["status_code"], text=record["body"],
                                      headers=record["headers"], request=httpx.Request("GET", key))
            if response.is_success and key.startswith("https://rest.uniprot.org/"):
                self.cache[key] = response
            return response


def check_pair(gene, species):
    """Actually call both APIs; one failing does not suppress the other check."""
    row = {"gene": gene, "frontend_species": species, "ensembl_species": species}
    try:
        resolved = resolve_orthologue(gene, species)
        row["resolver"] = {"status": "ok", "human": protein_summary(resolved["source"]),
                           "animal": protein_summary(resolved["target"]),
                           "source_url": resolved["source_url"], "orthology": resolved["orthology"]}
    except Exception as exc:
        row["resolver"] = error_record(exc)
    try:
        result = run_sequence(gene, species, functional=True)
        analysis = result["functional_analysis"]
        proteins = {}
        for label, protein in analysis["proteins"].items():
            identity = protein["identity"]
            proteins[label] = {
                **protein_summary(result[label]), "annotation_status": protein["status"],
                "reason_code": protein.get("reason_code"), "reason": protein.get("reason"),
                "uniprot_accession": identity["accession"] if identity else None,
                "uniprot_isoform": identity["isoform"] if identity else None,
                "feature_count": len(protein["features"]),
                "uniprot_release": identity.get("release") if identity else None,
            }
        row["sequence"] = {"status": result["status"], "functional_status": analysis["status"],
                           "proteins": proteins, "measurements": result["measurements"],
                           "limitations": result["limitations"],
                           "source_records": result["source_records"],
                           "slc29a1_motif": analysis["slc29a1_motif"]["sequence_observation"]}
        try:
            to_layer_result(result)
            row["sequence"]["adapter_status"] = "ok"
        except Exception as exc:
            row["sequence"]["adapter_status"] = error_record(exc)
    except Exception as exc:
        row["sequence"] = error_record(exc)
    return row


def audit(output, *, replay=False):
    """Sequential full frontend audit, prioritising CD28 rhesus first."""
    output = Path(output)
    transport = RecordedHTTP(output, replay=replay)
    ids = frontend_species()
    report = {"frontend_species": ids, "frontend_sha256": sha256(FRONTEND_SPECIES.read_bytes()).hexdigest(),
              "mode": "http_replay" if replay else "live", "rows": [],
              "policy": "Sequential; >=0.4 s between requests; 20 s operation / 10 s connect timeout; one transient retry, wait capped at 5 s; successful UniProt requests reused within audit. No homology request reuse."}
    with patch.object(httpx, "get", transport.get):
        try:
            response = httpx.get("https://rest.ensembl.org/info/species", params={"content-type": "application/json"})
            response.raise_for_status()
            catalogue = response.json()["species"]
            report["catalogue"] = {s: [{k: record.get(k) for k in ("name", "taxon_id", "assembly", "release", "aliases")}
                                      for record in catalogue if record["name"] == s or s in record.get("aliases", [])]
                                   for s in ids}
        except Exception as exc:
            report["catalogue_error"] = error_record(exc)
        for gene, species in [("CD28", s) for s in CD28_SPECIES] + [("SLC29A1", s) for s in ids]:
            print(f"Checking {gene} / {species}", flush=True)
            row = check_pair(gene, species)
            report["rows"].append(row)
            report["http_events"] = transport.events
            if not replay:
                output.mkdir(parents=True, exist_ok=True)
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(f"  resolver={row['resolver']['status']} sequence={row['sequence']['status']}", flush=True)
    if replay and transport.cursor != len(transport.records):
        raise ValueError("Not all recorded HTTP responses consumed.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.output, replay=args.replay)
