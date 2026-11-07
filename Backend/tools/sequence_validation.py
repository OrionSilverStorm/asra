"""Role 3 independent offline scientific audit; never changes the source tape.

From Backend: python -m tools.sequence_validation --output /tmp/validation.json
Enumerates at most 10,000 tracebacks; invariance is asserted only if exhaustive.
"""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
from unittest.mock import patch

from Bio.Align import PairwiseAligner, substitution_matrices

from tools.sequence import STANDARD_RESIDUES, run_sequence
from tools.sequence_adapter import to_layer_result
from tools.sequence_species_audit import audit

TAPE = Path(__file__).resolve().parents[1] / 'tests/fixtures/role3/species_compatibility'


def audit_tracebacks(human, animal, *, limit=10000):
    """Independently count columns/maps for all optima, or report a bounded sample.

    Score alone does not imply identical identity, coverage, substitutions or gaps.
    Changed coordinates list every human position with more than one observed map.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError('limit must be a positive integer')
    aligner = PairwiseAligner(mode='global', substitution_matrix=substitution_matrices.load('BLOSUM62'),
                              open_gap_score=-10, extend_gap_score=-0.5, epsilon=1e-6)
    mappings = [set() for _ in human]
    metrics = []
    iterator = iter(aligner.align(human, animal))
    for alignment in islice(iterator, limit):
        hpos = apos = paired = matches = substitutions = 0
        h, a = alignment[0], alignment[1]
        for x, y in zip(h, a):
            hpos += x != '-'
            apos += y != '-'
            if x != '-':
                mappings[hpos - 1].add(apos if y != '-' else None)
            if x != '-' and y != '-':
                paired += 1
                if x in STANDARD_RESIDUES and y in STANDARD_RESIDUES:
                    matches += x == y
                    substitutions += x != y
        metrics.append({'score': float(alignment.score), 'alignment_columns': len(h),
                        'paired_columns': paired, 'exact_matches': matches, 'substitutions': substitutions,
                        'identity_percent': 100 * matches / len(h),
                        'human_coverage_percent': 100 * paired / len(human),
                        'animal_coverage_percent': 100 * paired / len(animal)})
    exhaustive = next(iterator, None) is None
    return {'tracebacks_examined': len(metrics), 'exhaustive': exhaustive,
            'metric_ranges': {k: [min(m[k] for m in metrics), max(m[k] for m in metrics)] for k in metrics[0]},
            'variable_human_positions': [i for i, targets in enumerate(mappings, 1) if len(targets) > 1],
            'variable_mapping_residues': {
                str(i): [{'animal_position': p, 'animal_residue': animal[p - 1] if p else None}
                         for p in sorted(targets, key=lambda v: -1 if v is None else v)]
                for i, targets in enumerate(mappings, 1) if len(targets) > 1},
            'human_mapping_options': {str(i): sorted(targets, key=lambda v: -1 if v is None else v)
                                      for i, targets in enumerate(mappings, 1)},
            'scope': 'All optima under recorded scoring' if exhaustive else 'Sample only; invariant findings are not established'}


def validate_snapshot():
    """Replay public interfaces, check the complete adapter roundtrip, then audit.

    The original response timestamps remain in the tape. Runtime retrieval times
    during replay are not new biological source retrievals.
    """
    captured = []

    def capture(*args, **kwargs):
        result = run_sequence(*args, **kwargs)
        captured.append(result)
        return result

    with patch('tools.sequence_species_audit.run_sequence', capture):
        compatibility = audit(TAPE, replay=True)
    tape = json.loads((TAPE / 'http.json').read_text())
    entries = {json.loads(r['body'])['primaryAccession']: json.loads(r['body']) for r in tape
               if r['url'].endswith('.json') and r.get('status_code') == 200}
    rows = []
    for result in captured:
        layer = to_layer_result(result)
        wire = json.loads(layer.model_dump_json(by_alias=True))
        recovered = {o['field']: json.loads(o['value']) for o in wire['observations']}
        for key, value in recovered.items():
            assert value == json.loads(json.dumps(result[key])), key
        assert wire['source_records'] == [dict(url=None, **s) if 'url' not in s else s for s in result['source_records']]
        assert wire['limitations'][:len(result['limitations'])] == result['limitations']
        assert all(o['sourceRecordId'] in {s['id'] for s in wire['source_records']} for o in wire['observations'])
        functional = result['functional_analysis']
        proteins = {}
        for label, protein in functional['proteins'].items():
            identity = protein['identity']
            entry = entries[identity['accession']]
            proteins[label] = {'identity': identity, 'feature_types': dict(Counter(f['type'] for f in protein['features'])),
                               'entry_type': entry['entryType'], 'protein_existence': entry['proteinExistence'],
                               'alternative_products': [c for c in entry.get('comments', []) if c['commentType'] == 'ALTERNATIVE PRODUCTS'],
                               'sequence_cautions': [c for c in entry.get('comments', []) if c['commentType'] == 'SEQUENCE CAUTION']}
        rows.append({'gene': result['gene'], 'species': result['species'], 'status': result['status'],
                     'proteins': proteins, 'substitutions': result['substitutions'], 'indels': result['indels'],
                     'motif': functional['slc29a1_motif'], 'adapter_roundtrip': 'passed',
                     'tracebacks': audit_tracebacks(result['human']['sequence'], result['animal']['sequence'])})
    return {'evidence_sha256': sha256((TAPE / 'http.json').read_bytes()).hexdigest(),
            'source': str(TAPE.relative_to(Path(__file__).resolve().parents[2])),
            'species_states': [{k: row[k] for k in ('gene', 'frontend_species', 'resolver', 'sequence')}
                               for row in compatibility['rows']], 'validated_pairs': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(validate_snapshot(), indent=2) + '\n')
