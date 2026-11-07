"""Milestone 4 regressions for biological coordinates and integration evidence."""

from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.sequence import run_sequence
from tools.sequence_adapter import to_layer_result
from tools.sequence_validation import audit_tracebacks, validate_snapshot


@pytest.fixture(scope='module')
def validated():
    return validate_snapshot()


def pair(validated, gene, species):
    return next(r for r in validated['validated_pairs'] if (r['gene'], r['species']) == (gene, species))


def test_motif_coordinates_and_exact_curation_provenance(validated):
    mouse = pair(validated, 'SLC29A1', 'mus_musculus')
    motif = mouse['motif']['sequence_observation']
    assert (motif['human_window'], motif['animal_window']) == ('PERN', 'PARS')
    assert [r['animal_position'] for r in motif['residues']] == [71, 72, 73, 74]
    for p in mouse['proteins'].values():
        assert p['identity']['entry_type'] == 'UniProtKB reviewed (Swiss-Prot)'
        assert p['identity']['protein_existence'] == '1: Evidence at protein level'


def test_cd28_rhesus_has_four_substitutions_and_sparse_annotations(validated):
    rhesus = pair(validated, 'CD28', 'macaca_mulatta')
    assert [(r['human_position'], r['human_residue'], r['animal_residue']) for r in rhesus['substitutions']] == [
        (11, 'F', 'L'), (155, 'V', 'A'), (175, 'I', 'C'), (179, 'V', 'M')]
    assert rhesus['tracebacks']['tracebacks_examined'] == 1
    assert sum(rhesus['proteins']['human']['feature_types'].values()) == 14
    assert rhesus['proteins']['animal']['feature_types'] == {'Transmembrane': 1, 'Domain': 1, 'Region': 1}
    assert rhesus['proteins']['animal']['identity']['protein_existence'] == '4: Predicted'


@pytest.mark.parametrize('species,count,variable', [
    ('rattus_norvegicus', 2, [1]), ('macaca_fascicularis', 2, [1]),
    ('canis_lupus_familiaris', 2, [1]), ('sus_scrofa', 8, [1, 71, 321]),
])
def test_all_tied_optima_distinguish_invariant_metrics_from_maps(validated, species, count, variable):
    row = pair(validated, 'SLC29A1', species)
    t = row['tracebacks']
    assert row['status'] == 'incomplete'
    assert t['exhaustive'] and t['tracebacks_examined'] == count
    assert t['variable_human_positions'] == variable
    assert all(lo == hi for lo, hi in t['metric_ranges'].values())
    if species == 'sus_scrofa':
        assert t['variable_mapping_residues']['71'] == [
            {'animal_position': 155, 'animal_residue': 'A'},
            {'animal_position': 162, 'animal_residue': 'T'}]


def test_bounded_traceback_sample_never_claims_exhaustive_invariance():
    audit = audit_tracebacks('MAA', 'MMAA', limit=1)
    assert not audit['exhaustive'] and audit['tracebacks_examined'] == 1
    with pytest.raises(ValueError):
        audit_tracebacks('MAA', 'MMAA', limit=0)


def test_plain_gene_call_and_adapter_preserve_incomplete_tied_state():
    resolved = {'gene': 'SYNTHETIC', 'species': 'mus_musculus',
                'source': {'protein_id': 'H', 'sequence': 'MAA'},
                'target': {'protein_id': 'A', 'sequence': 'MMAA'},
                'orthology': {'type': 'ortholog_one2one'}, 'source_url': 'https://example.org'}
    with patch('tools.sequence.resolve_orthologue', return_value=resolved):
        result = run_sequence('SYNTHETIC', 'mus_musculus')
    assert result['status'] == to_layer_result(result).status == 'incomplete'


def test_snapshot_has_nine_explicit_states_and_complete_adapter_roundtrips(validated):
    rows = [r for r in validated['species_states'] if r['gene'] == 'SLC29A1']
    assert len({r['frontend_species'] for r in rows}) == 9
    assert {r['sequence']['status'] for r in rows} == {'ok', 'incomplete', 'orthologue_unavailable', 'ambiguous_orthologue'}
    assert all(r['adapter_roundtrip'] == 'passed' for r in validated['validated_pairs'])
    # The pinned independent audit is evidence; dynamic retrieval timestamps vary.
    pinned = json.loads((Path(__file__).parent / 'fixtures/role3/milestone4.json').read_text())
    assert [r['tracebacks'] for r in pinned['validated_pairs']] == [r['tracebacks'] for r in validated['validated_pairs']]


def test_independent_uniprot_refresh_and_alternative_accessions():
    root = Path(__file__).parent / 'fixtures/role3'
    records = json.loads((root / 'milestone4_live.json').read_text())
    entries = {}
    for record in records:
        assert sha256(record['body'].encode()).hexdigest() == record['sha256']
        payload = json.loads(record['body'])
        assert 'link' not in record['headers']  # This search inventory is not paginated.
        for entry in payload.get('results', [payload] if 'primaryAccession' in payload else []):
            entries[entry['primaryAccession']] = entry
    tape = json.loads((root / 'species_compatibility/http.json').read_text())
    for record in tape:
        if record['url'].endswith('.json') and record.get('status_code') == 200:
            entry = json.loads(record['body'])
            accession = entry['primaryAccession']
            if accession in entries:
                assert entries[accession]['sequence'] == entry['sequence']
    # Alternatives use the same gene but distinct protein xrefs; no silent swap.
    for accession, gene in [('O54698', 'ENSRNOG00000019752'),
                            ('A0A8I3NK92', 'ENSCAFG00845011282'),
                            ('A0A287B2T6', 'ENSSSCG00000001700')]:
        assert any(p['key'] == 'GeneId' and p['value'].split('.')[0] == gene
                   for ref in entries[accession]['uniProtKBCrossReferences'] if ref['database'] == 'Ensembl'
                   for p in ref['properties'])
