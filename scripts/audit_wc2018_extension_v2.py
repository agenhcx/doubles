#!/usr/bin/env python3
"""Stage 59 WC2018 observations after three source-specific pair decisions.

Never overwrite masters. The union is an index back to immutable original
records, NOT a pooled score table or a frozen natural-person cohort.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAME = Path('output/frame/isu_wc2018_identity_bridge_v1')
HISTORY = Path('output/historic_dob/cross_era_identity/ambiguity_source_v3')
SOURCES = {
    'bridge': FRAME / 'official_wc2018_identity_bridge_manifest_v1.json',
    'observations': FRAME / 'official_wc2018_new_event_observations_preview_v1.csv',
    'pending': FRAME / 'official_wc2018_nonmatching_historical_pairs_review_v1.csv',
    'official': Path('output/frame/isu_wc2018_pilot_v1/official_entry_result_link_review_v1.csv'),
    'original_pairs': Path('data/historic/v4/couples_v4.csv'),
    'pairs': HISTORY / 'historical_source_reviewed_pair_preview_v3.csv',
    'people': HISTORY / 'historical_source_reviewed_person_preview_v3.csv',
    'events': Path('data/historic/v4/pair_events_v4.csv'),
    'collision': HISTORY / 'event_collision_audit/historic_alias_event_collision_manifest_v1.json',
    'rules': Path('data/adjudications/isu_wc2018_pair_extension_rules_v2.csv'),
}
EXPECTED = {('Ice Dance', 'FINAL_COMPLETE'): 20, ('Ice Dance', 'FINAL_NOT_REACHED'): 11,
            ('Pair Skating', 'FINAL_COMPLETE'): 16, ('Pair Skating', 'FINAL_NOT_REACHED'): 12}
ACTIONS = {'NEW_PAIR_EXISTING_MEMBERS', 'EXISTING_PAIR_NAME_VARIANT', 'NEW_PAIR_NEW_MEMBER_A'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def norm(value):
    value = unicodedata.normalize('NFKD', value.casefold())
    return ' '.join(sorted(re.findall(r'[a-z0-9]+', ''.join(
        c for c in value if not unicodedata.combining(c)))))


def parts(value):
    return {v.strip() for v in value.split(';') if v.strip()}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_sha(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def uid(kind, *values):
    return kind + '_' + hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()[:24]


def read(path, required):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(set(required) <= set(reader.fieldnames or []), f'{path}: missing columns')
        rows = list(reader)
    require(all(None not in r and None not in r.values() for r in rows), f'{path}: malformed CSV row')
    return rows


def write(path, rows, columns):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)


def index(rows, key, label):
    result = {}
    for row in rows:
        k = row[key]
        require(k and k not in result, label + ': duplicate/blank ID')
        result[k] = row
    return result


def valid_date(value):
    try:
        return date.fromisoformat(value).isoformat() == value and date(1850, 1, 1) <= date.fromisoformat(value) <= date.today()
    except (ValueError, TypeError):
        return False


def project(observations, official, original_pairs, pairs, people, events, rules):
    """Pure projection; acceptance gates are independent of rank/performance."""
    hp = index(people, 'projected_person_id', 'Historic people')
    old = index(original_pairs, 'pair_id', 'Original pairs')
    require(all(valid_date(p['date_of_birth']) for p in people), 'Invalid historic DOB')
    by_old, by_key = {}, {}
    for group in pairs:
        key = (group['discipline'], group['projected_person_a_id'], group['projected_person_b_id'])
        require(key not in by_key and key[1] != key[2] and all(x in hp for x in key[1:]), 'Invalid canonical pair')
        require(parts(group['original_pair_ids']), 'Empty pair lineage')
        by_key[key] = group
        for pid in parts(group['original_pair_ids']):
            require(pid in old and pid not in by_old and old[pid]['discipline'] == key[0], 'Invalid original pair lineage')
            by_old[pid] = key
    require(set(by_old) == set(old), 'Historic pair lineage incomplete')
    for pid, key in by_old.items():
        for side, ident in zip(('a', 'b'), key[1:]):
            require(old[pid]['person_' + side + '_id'] in parts(hp[ident]['original_historic_person_ids']), 'Historical member lineage mismatch')

    source = {}
    for r in official:
        key = (r['event_id'], r['isu_profile_id'])
        require(key not in source, 'Duplicate official event/profile')
        require(r['entry_result_link_status'] == 'PROFILE_MATCH_BOTH_OFFICIAL_PAGES', 'Unapproved official source join')
        source[key] = r
    require(len(observations) == len(source) == 59, 'WC2018 requires all 59 source records')
    decisions = index(rules, 'isu_profile_id', 'Rules')
    require(len(rules) == 3 and {r['action'] for r in rules} == ACTIONS, 'Expected three distinct reviewed decisions')
    for r in rules:
        require(r['evidence_status'] == 'SOURCE_REVIEWED_EVENT_LOCAL', 'Unreviewed rule')
        require(r['official_bio_url'] == 'https://results.isu.org/bios/' + r['isu_profile_id'] + '.htm', 'Rule source URL mismatch')
        require(re.fullmatch(r'isufs\d+', r['isu_profile_id']) and all(valid_date(r['dob_' + s]) for s in ('a', 'b')), 'Invalid reviewed source/date')

    output, new_people, new_pairs, used_rules, seen, event_keys = [], [], {}, set(), set(), set()
    status_counts, placements = Counter(), {}
    for r in observations:
        disc, prof = r['discipline'], r['isu_profile_id']
        require(disc in ('Ice Dance', 'Pair Skating') and r['event_id'] == '2017-2018|wc2018|' + disc, 'Wrong event/discipline')
        skey = (r['event_id'], prof)
        require(skey in source and skey not in seen, 'Missing/repeated event source')
        seen.add(skey)
        src = source[skey]
        for f in ('discipline', 'name_as_published', 'person_a_as_published', 'person_b_as_published',
                  'nation_as_published', 'entry_source_url', 'result_source_url', 'result_status', 'final_placement'):
            require(r[f] == src[f], 'Observation differs from official source: ' + f)
        for x, y in (('points_as_published', 'result_points_as_published'), ('points_interpretation', 'result_points_interpretation')):
            require(r[x] == src[y], 'Observation differs from official score semantics')
        require(re.fullmatch(r'\d{1,3}[.,]\d{2}', r['points_as_published']), 'Malformed points')
        interpretation = {'FINAL_COMPLETE': 'TOTAL_SCORE', 'FINAL_NOT_REACHED': 'SHORT_SEGMENT_ONLY_NOT_TOTAL'}
        require(r['result_status'] in interpretation and r['points_interpretation'] == interpretation[r['result_status']], 'FNR score cannot become total')
        status_counts[(disc, r['result_status'])] += 1
        require(r['final_placement'].isdigit(), 'Invalid placement')
        placements.setdefault(disc, []).append(int(r['final_placement']))
        code = '004' if disc == 'Ice Dance' else '003'
        for f, suffix in (('entry_source_url', 'EN'), ('result_source_url', 'RS')):
            require(r[f] == f'https://results.isu.org/results/season1718/wc2018/CAT{code}{suffix}.HTM', 'Unapproved event URL')
        original_ids = parts(r['historic_original_pair_ids'])
        if original_ids:
            require(prof not in decisions and len(original_ids) == 1, 'Unexpected inherited pair/rule overlap')
            original_id = next(iter(original_ids))
            require(original_id in by_old, 'Unknown historical pair')
            key = by_old[original_id]
            require(key[0] == disc and all(norm(r['person_' + s + '_as_published']) == norm(old[original_id]['person_' + s + '_name']) for s in ('a', 'b')), 'Inherited two-name match is invalid')
            method = 'INHERITED_EXACT_PAIR_CANDIDATE'
            rule_id, bio = '', ''
        else:
            require(prof in decisions, 'Unreviewed unmatched pair')
            dec = decisions[prof]
            used_rules.add(prof)
            require(dec['discipline'] == disc and all(r['person_' + s + '_as_published'] == dec['event_name_' + s] for s in ('a', 'b')), 'Rule member/discipline mismatch')
            key = (disc, dec['historic_person_a_id'], dec['historic_person_b_id'])
            for side, ident in zip(('a', 'b'), key[1:]):
                if side == 'a' and dec['action'] == 'NEW_PAIR_NEW_MEMBER_A':
                    require(ident == 'source_person_' + prof + '_1' and ident not in hp, 'New person ID collision')
                    require(not any(norm(dec['event_name_a']) == norm(n) for p in people for n in parts(p['historic_names'])), 'New person has an exact historic name; review required')
                    new_people.append({'person_id': ident, 'name_as_published': dec['event_name_a'], 'date_of_birth': dec['dob_a'], 'official_bio_url': dec['official_bio_url'], 'status': 'NEW_EVENT_SOURCE_SLOT_NOT_GLOBAL_IDENTITY_PROOF'})
                else:
                    require(ident in hp and hp[ident]['date_of_birth'] == dec['dob_' + side], 'Reviewed historic DOB/ID disagreement')
                    require(dec['historic_name_' + side] in parts(hp[ident]['historic_names']), 'Reviewed historical name missing')
            method, rule_id, bio = dec['action'], dec['rule_id'], dec['official_bio_url']
            if method == 'EXISTING_PAIR_NAME_VARIANT':
                pid = dec['reference_original_pair_id']
                require(pid in by_old and by_old[pid] == key, 'Variant does not match the existing original pair')
                require(all(old[pid]['person_' + s + '_name'] == dec['historic_name_' + s] for s in ('a', 'b')), 'Variant original names differ')
                original_ids = {pid}
            else:
                require(not dec['reference_original_pair_id'] and key not in by_key and key not in new_pairs, 'New pair already exists')
                new_pairs[key] = {'pair_key': uid('extension_pair', *key), 'discipline': disc, 'person_a_id': key[1], 'person_b_id': key[2], 'name_as_published': r['name_as_published'], 'rule_id': rule_id, 'official_bio_url': bio}
        ekey = (*key, r['event_id'])
        require(key[1] != key[2] and ekey not in event_keys, 'Self-pair or duplicate canonical event')
        event_keys.add(ekey)
        datum = dict(r)
        datum.update(canonical_person_a_id=key[1], canonical_person_b_id=key[2],
                     inherited_original_pair_ids='; '.join(sorted(original_ids)),
                     extension_event_id=uid('extension_event', *ekey), identity_basis=method,
                     source_review_rule_id=rule_id, source_review_bio_url=bio,
                     total_score=r['points_as_published'].replace(',', '.') if r['result_status'] == 'FINAL_COMPLETE' else '',
                     short_segment_score=r['points_as_published'].replace(',', '.') if r['result_status'] == 'FINAL_NOT_REACHED' else '')
        output.append(datum)
    require(status_counts == EXPECTED and used_rules == set(decisions), 'Wrong result distribution or unused rules')
    require(all(sorted(placements[d]) == list(range(1, n + 1)) for d, n in (('Ice Dance', 31), ('Pair Skating', 28))), 'Placement gap/duplicate')
    require(len(new_people) == 1 and len(new_pairs) == 2, 'Unexpected person/pair extension counts')

    union, old_keys, old_ids = [], set(), set()
    for i, r in enumerate(events, 1):
        require(r['pair_id'] in by_old and r['pair_event_id'] and r['pair_event_id'] not in old_ids, 'Legacy event identity invalid')
        old_ids.add(r['pair_event_id'])
        key = by_old[r['pair_id']]
        require(r['discipline'] == key[0] and r['event_id'], 'Legacy event discipline/ID mismatch')
        ekey = (*key, r['event_id'])
        require(ekey not in event_keys, 'WC2018 already present: refusing duplicate append')
        require(ekey not in old_keys, 'Unresolved legacy canonical event collision')
        old_keys.add(ekey)
        union.append({'record_id': r['pair_event_id'], 'event_id': r['event_id'], 'canonical_person_a_id': key[1], 'canonical_person_b_id': key[2], 'source_kind': 'UNCHANGED_LEGACY_EVENT_ROW', 'source_record_number': i, 'source_record_sha256': record_sha(r)})
    for i, r in enumerate(output, 1):
        require(r['extension_event_id'] not in old_ids, 'Extension record ID collision')
        union.append({'record_id': r['extension_event_id'], 'event_id': r['event_id'], 'canonical_person_a_id': r['canonical_person_a_id'], 'canonical_person_b_id': r['canonical_person_b_id'], 'source_kind': 'WC2018_EVENT_LOCAL_OVERLAY', 'source_record_number': i, 'source_record_sha256': record_sha(r)})
    report = {'stage': 'wc2018_source_reviewed_extension_v2_NOT_FROZEN',
              'old_historic_person_slots': len(people), 'old_historic_pair_groups': len(pairs),
              'inherited_exact_name_pair_candidates': sum(r['identity_basis'] == 'INHERITED_EXACT_PAIR_CANDIDATE' for r in output),
              'reviewed_existing_pair_name_variants': 1, 'new_pair_combinations': len(new_pairs),
              'new_event_source_person_slots': len(new_people), 'projected_registry_person_slots': len(people) + len(new_people),
              'projected_registry_pair_groups': len(pairs) + len(new_pairs), 'legacy_event_rows': len(events),
              'new_event_rows': len(output), 'union_index_rows': len(union), 'event_key_collisions': 0,
              'total_score_rows_in_new_event': 36, 'short_segment_only_rows_in_new_event': 23,
              'limitations': ['56 inherited exact-name pair links remain candidates, not new independent identity confirmations.',
                             'New person means an event-scoped registry slot, not proof of global novelty.',
                             'ISU biography agreement is not independent DOB replication.',
                             'The union is a source-row index. Legacy score meanings are not reclassified or pooled.',
                             'No original data, modern roster, historical master or cohort is overwritten.',
                             'No astrology, outcome-driven filtering, null models or cohort freeze.']}
    return output, new_people, list(new_pairs.values()), union, report


def audit(root=ROOT, out=None):
    root = Path(root).resolve()
    paths = {k: root / v for k, v in SOURCES.items()}
    before = {k: sha(p) for k, p in paths.items()}
    meta = json.loads(paths['bridge'].read_text(encoding='utf-8'))
    require(meta.get('stage') == 'wc2018_identity_event_extension_crosswalk_preview_not_frozen' and meta.get('official_entry_result_records') == 59, 'Wrong bridge manifest')
    pinned = {k.replace('\\', '/'): v for k, v in meta['input_sha256'].items()}
    for label in ('official', 'original_pairs', 'pairs', 'people'):
        require(pinned.get(SOURCES[label].as_posix()) == before[label], 'Bridge source hash mismatch: ' + label)
    collision = json.loads(paths['collision'].read_text(encoding='utf-8'))
    lineage = {k.replace('\\', '/'): v for k, v in collision['inputs_sha256'].items()}
    for label in ('pairs', 'events'):
        require(lineage.get(SOURCES[label].as_posix()) == before[label], 'Collision source hash mismatch: ' + label)
    require(collision.get('event_collision_groups') == 0, 'Prior event collision unresolved')
    tables = {k: read(paths[k], fields) for k, fields in {
        'observations': ('event_id', 'isu_profile_id', 'historic_original_pair_ids', 'points_as_published'),
        'official': ('event_id', 'isu_profile_id', 'result_points_as_published', 'entry_result_link_status'),
        'original_pairs': ('pair_id', 'discipline', 'person_a_id', 'person_b_id', 'person_a_name', 'person_b_name'),
        'pairs': ('discipline', 'projected_person_a_id', 'projected_person_b_id', 'original_pair_ids'),
        'people': ('projected_person_id', 'historic_names', 'original_historic_person_ids', 'date_of_birth'),
        'events': ('pair_event_id', 'pair_id', 'discipline', 'event_id'),
        'rules': ('rule_id', 'isu_profile_id', 'action', 'evidence_status'),
        'pending': ('event_id', 'isu_profile_id')}.items()}
    require({r['isu_profile_id'] for r in tables['pending']} == {r['isu_profile_id'] for r in tables['rules']} and len(tables['pending']) == 3, 'Pending queue differs from reviewed rules')
    require(len(tables['events']) == collision['original_pair_event_records'], 'Legacy event count mismatch')
    for label, field in (('people', 'source_reviewed_historic_person_slots'), ('pairs', 'source_reviewed_historic_pair_groups'), ('original_pairs', 'original_historic_pair_ids')):
        require(len(tables[label]) == meta[field], 'Bridge registry count mismatch: ' + label)
    data = project(*(tables[k] for k in ('observations', 'official', 'original_pairs', 'pairs', 'people', 'events', 'rules')))
    require(all(sha(paths[k]) == v for k, v in before.items()), 'Input changed during audit')
    output_dir = Path(out).resolve() if out else root / 'output/frame/isu_wc2018_extension_v2'
    files = ['wc2018_resolved_event_overlay_v2.csv', 'wc2018_new_person_slots_v2.csv',
             'wc2018_new_pair_combinations_v2.csv', 'historical_plus_wc2018_event_index_v2.csv']
    require(not output_dir.exists(), 'Output already exists: use a new --out path; no overwrite permitted')
    output_dir.mkdir(parents=True)
    for filename, rows in zip(files, data[:4]):
        write(output_dir / filename, rows, list(rows[0]))
    report = data[4]
    report['input_sha256'] = {str(SOURCES[k]): v for k, v in before.items()}
    report['output_sha256'] = {f: sha(output_dir / f) for f in files}
    report['union_source_tables'] = {'UNCHANGED_LEGACY_EVENT_ROW': str(SOURCES['events']), 'WC2018_EVENT_LOCAL_OVERLAY': files[0]}
    (output_dir / 'wc2018_extension_manifest_v2.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    audit(args.root, args.out)
