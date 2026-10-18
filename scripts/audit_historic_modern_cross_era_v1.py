#!/usr/bin/env python3
"""Cross-era ISU skater identity EVIDENCE audit. Never merges people or events.

Historic ISU v3 audited identities versus 2018–2026 season rank entrants.
Modern ISU Biography matches are optional and always evidence, not identity proof.
No BaZi, performance-dependent filtering, or mutations of original data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

HIST_PEOPLE = Path('output/historic_dob/shared_partner_identity/historic_reviewed_person_id_preview_v1.csv')
HIST_PAIRS = Path('output/historic_dob/shared_partner_identity/historic_reviewed_pair_groups_preview_v1.csv')
MODERN = Path('output/master/season_roster.csv')
BIOS = Path('output/bios/birth_candidates.csv')
OUT = Path('output/historic_dob/cross_era_identity')
OFFICIAL = {'results.isu.org', 'www.isuresults.com'}

REVIEW_FIELDS = [
    'discipline', 'historic_projected_id', 'modern_provisional_id',
    'historic_names', 'modern_names', 'historic_dob', 'modern_official_dob',
    'modern_bio_urls', 'modern_profile_urls', 'modern_seasons',
    'shared_partner_historic_id', 'cross_era_same_pair', 'name_similarity',
    'evidence_flags', 'identity_review_status', 'ambiguity_status',
]
PAIR_FIELDS = [
    'discipline', 'historic_projected_a_id', 'historic_projected_b_id',
    'modern_a_id', 'modern_b_id', 'modern_pair_ids', 'modern_seasons',
    'modern_profile_urls', 'historic_original_pair_ids',
    'review_status',
]


def read(path, required):
    with Path(path).open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'{path} missing columns: {sorted(missing)}')
        return list(reader)


def output(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def parts(s):
    return {x.strip() for x in (s or '').split(';') if x.strip()}


def joined(values):
    return '; '.join(sorted(set(x for x in values if x)))


def norm(s):
    raw = unicodedata.normalize('NFKD', (s or '').casefold())
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return ' '.join(sorted(re.findall(r'[a-z0-9]+', raw)))


def date_ok(s):
    try:
        return bool(s and date.fromisoformat(s).isoformat() == s)
    except ValueError:
        return False


def bio_url_ok(u, ident):
    p = urlsplit(u)
    return (p.scheme == 'https' and p.hostname in OFFICIAL and
            not p.username and not p.password and not p.port and
            not p.query and not p.fragment and
            p.path.lower() == f'/bios/{ident.lower()}.htm' and
            bool(re.fullmatch(r'isufs\d+', ident.lower())))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cross_era(people_path=HIST_PEOPLE, pairs_path=HIST_PAIRS,
              modern_path=MODERN, bios_path=BIOS, out_dir=OUT):
    people = read(people_path, ('projected_person_id', 'original_historic_person_ids',
                                'historic_names', 'date_of_birth'))
    pairs = read(pairs_path, ('discipline', 'projected_person_a_id',
                              'projected_person_b_id', 'original_pair_ids'))
    modern = read(modern_path, ('pair_id', 'discipline', 'person_a_id',
                                'person_b_id', 'person_a_name', 'person_b_name',
                                'season', 'profile_url'))
    if not people or not pairs or not modern:
        raise ValueError('Empty historic people, historic pairs or modern season roster')
    optional_bios = Path(bios_path).is_file()
    bios = (read(bios_path, ('profile_id', 'profile_url', 'person_id',
                            'date_of_birth', 'status')) if optional_bios else [])

    historic = {}
    for p in people:
        pid, dob = p['projected_person_id'], p['date_of_birth']
        if not pid or pid in historic or not date_ok(dob):
            raise ValueError('Duplicate historic identity or invalid audited DOB')
        historic[pid] = p

    h_original = defaultdict(set)
    h_names = defaultdict(set)
    h_dates = defaultdict(set)
    h_partners = defaultdict(set)
    historic_pair_keys = {}
    original_pair_ids_seen = set()
    for p in pairs:
        d, a, b = p['discipline'], p['projected_person_a_id'], p['projected_person_b_id']
        if not d or a not in historic or b not in historic or a == b:
            raise ValueError('Historic reviewed pair has invalid projected people')
        key = (d, a, b)
        if key in historic_pair_keys:
            raise ValueError('Duplicate projected historic pair group')
        pair_ids = parts(p['original_pair_ids'])
        if not pair_ids or original_pair_ids_seen.intersection(pair_ids):
            raise ValueError('Missing or repeated historic original pair IDs')
        original_pair_ids_seen.update(pair_ids)
        historic_pair_keys[key] = pair_ids
        h_partners[(d, a)].add(b)
        h_partners[(d, b)].add(a)
        for pid in (a, b):
            for original in parts(historic[pid]['original_historic_person_ids']):
                h_original[(d, original)].add(pid)
            for name in parts(historic[pid]['historic_names']):
                if norm(name):
                    h_names[(d, norm(name))].add(pid)
            h_dates[(d, historic[pid]['date_of_birth'])].add(pid

    modern_people = {}
    modern_pairs = defaultdict(lambda: {'pair_ids': set(), 'seasons': set(), 'profiles': set()})
    for row in modern:
        d, a, b = row['discipline'], row['person_a_id'], row['person_b_id']
        if not d or not a or not b or a == b:
            raise ValueError('Modern roster has missing/malformed member ID')
        key = (d, a, b)
        modern_pairs[key]['pair_ids'].add(row['pair_id'])
        modern_pairs[key]['seasons'].add(row['season'])
        modern_pairs[key]['profiles'].add(row['profile_url'])
        for pid, name, partner in ((a, row['person_a_name'], b),
                                   (b, row['person_b_name'], a)):
            k = (d, pid)
            if k not in modern_people:
                modern_people[k] = {'names': set(), 'partners': set(),
                                    'seasons': set(), 'profiles': set()}
            v = modern_people[k]
            v['names'].add(name)
            v['partners'].add(partner)
            v['seasons'].add(row['season'])
            v['profiles'].add(row['profile_url'])

    bio_by_modern = defaultdict(lambda: {'dates': set(), 'urls': set()})
    invalid_bio_rows = 0
    for b in bios:
        if b['status'] != 'exact_name_match':
            continue
        method = b.get('name_match_method', 'exact')
        if (not b['person_id'] or not date_ok(b['date_of_birth']) or
                method not in ('exact', 'roster_confirmed_country_suffix', '') or
                not bio_url_ok(b['profile_url'], b['profile_id'])):
            invalid_bio_rows += 1
            continue
        rec = bio_by_modern[b['person_id']]
        rec['dates'].add(b['date_of_birth'])
        rec['urls'].add(b['profile_url'])

    def canonical_modern_partner(d, person_id):
        return h_original.get((d, person_id), set())

    def common_partner(d, hid, mid):
        m = modern_people[(d, mid)]
        matching = set()
        for pid in m['partners']:
            matching.update(h_partners.get((d, hid), set()).intersection(
                canonical_modern_partner(d, pid)))
        return matching

    # Complete historical couples are strong candidate anchors, but not proof.
    pair_bridges = []
    full_pair_bridges = set()
    for (d, a, b), info in sorted(modern_pairs.items()):
        for ha in sorted(h_original.get((d, a), ())):
            for hb in sorted(h_original.get((d, b), ())):
                old_key = (d, ha, hb)
                if old_key not in historic_pair_keys:
                    continue
                full_pair_bridges.add((d, ha, a))
                full_pair_bridges.add((d, hb, b))
                pair_bridges.append({
                    'discipline': d, 'historic_projected_a_id': ha,
                    'historic_projected_b_id': hb, 'modern_a_id': a,
                    'modern_b_id': b, 'modern_pair_ids': joined(info['pair_ids']),
                    'modern_seasons': joined(info['seasons']),
                    'modern_profile_urls': joined(info['profiles']),
                    'historic_original_pair_ids': joined(historic_pair_keys[old_key]),
                    'review_status': 'SAME_PROVISIONAL_NAME_PAIR_REVIEW_NOT_APPROVED',
                })

    proposals = defaultdict(set)
    for (d, mid), mp in modern_people.items():
        for hid in h_original.get((d, mid), set()):
            proposals[(d, hid, mid)].add('IDENTICAL_PROVISIONAL_NAME_ID')
        for name in mp['names']:
            for hid in h_names.get((d, norm(name)), set()):
                proposals[(d, hid, mid)].add('SAME_NORMALIZED_PUBLISHED_NAME')
        br = bio_by_modern.get(mid, {})
        dates = br.get('dates', set())
        if len(dates) != 1:
            continue
        birthdate = next(iter(dates))
        for hid in h_dates.get((d, birthdate), set()):
            histnames = parts(historic[hid]['historic_names'])
            similarity = max((SequenceMatcher(None, norm(x), norm(y)).ratio()
                              for x in histnames for y in mp['names']), default=0.)
            shared = common_partner(d, hid, mid)
            if similarity >= 0.75:
                proposals[(d, hid, mid)].add('SAME_DOB_SIMILAR_NAME')
            elif shared and similarity >= 0.45:
                proposals[(d, hid, mid)].add('SAME_DOB_SHARED_PARTNER_NAME')

    matched_by_h = defaultdict(set)
    matched_by_m = defaultdict(set)
    for d, hid, mid in proposals:
        matched_by_h[hid].add((d, mid))
        matched_by_m[(d, mid)].add(hid)

    review = []
    for (d, hid, mid), flags in sorted(proposals.items()):
        hist, cur = historic[hid], modern_people[(d, mid)]
        dates = bio_by_modern.get(mid, {}).get('dates', set())
        shared = common_partner(d, hid, mid)
        paired = (d, hid, mid) in full_pair_bridges
        similarity = max((SequenceMatcher(None, norm(x), norm(y)).ratio()
                          for x in parts(hist['historic_names']) for y in cur['names']),
                         default=0.)
        if len(dates) > 1:
            status = 'MODERN_BIO_DOB_CONFLICT_HOLD'
        elif len(dates) == 1 and hist['date_of_birth'] not in dates:
            status = 'CROSS_ERA_DOB_DISAGREEMENT_HOLD'
        elif len(dates) == 1 and paired:
            status = 'DOB_AGREES_AND_SAME_PAIR_REVIEW'
        elif len(dates) == 1:
            status = 'DOB_AGREES_IDENTITY_REVIEW'
        elif paired:
            status = 'SAME_PAIR_MODERN_DOB_MISSING_REVIEW'
        else:
            status = 'NAME_MATCH_MODERN_DOB_MISSING_REVIEW'
        ambig = []
        if len(matched_by_h[hid]) > 1:
            ambig.append('HISTORIC_TO_MULTIPLE_MODERN_IDS')
        if len(matched_by_m[(d, mid)]) > 1:
            ambig.append('MODERN_TO_MULTIPLE_HISTORIC_IDS')
        if paired:
            flags.add('COMPLETE_HISTORIC_MODERN_PAIR_BRIDGE')
        review.append({
            'discipline': d, 'historic_projected_id': hid,
            'modern_provisional_id': mid, 'historic_names': hist['historic_names'],
            'modern_names': joined(cur['names']),
            'historic_dob': hist['date_of_birth'],
            'modern_official_dob': joined(dates),
            'modern_bio_urls': joined(bio_by_modern.get(mid, {}).get('urls', set())),
            'modern_profile_urls': joined(cur['profiles']),
            'modern_seasons': joined(cur['seasons']),
            'shared_partner_historic_id': joined(shared),
            'cross_era_same_pair': 'YES' if paired else 'NO',
            'name_similarity': f'{similarity:.4f}',
            'evidence_flags': joined(flags),
            'identity_review_status': status,
            'ambiguity_status': joined(ambig) or 'NONE',
        })

    missing = []
    for hid, person in sorted(historic.items()):
        if hid not in matched_by_h:
            missing.append({
                'historic_projected_id': hid,
                'historic_names': person['historic_names'],
                'historic_dob': person['date_of_birth'],
                'review_status': 'NO_CROSS_ERA_EVIDENCE_DO_NOT_INFER_ABSENCE',
            })
    bio_conflicts = [{
        'modern_provisional_id': mid,
        'dates': joined(rec['dates']), 'source_urls': joined(rec['urls']),
        'review_status': 'DOB_CONFLICT_HOLD',
    } for mid, rec in sorted(bio_by_modern.items()) if len(rec['dates']) > 1]

    output(Path(out_dir) / 'historic_modern_identity_review_v1.csv', review, REVIEW_FIELDS)
    output(Path(out_dir) / 'historic_modern_pair_bridges_v1.csv', pair_bridges, PAIR_FIELDS)
    output(Path(out_dir) / 'historic_modern_unlinked_historic_v1.csv', missing,
           ['historic_projected_id', 'historic_names', 'historic_dob', 'review_status'])
    output(Path(out_dir) / 'historic_modern_bio_conflicts_v1.csv', bio_conflicts,
           ['modern_provisional_id', 'dates', 'source_urls', 'review_status'])
    tally = Counter(r['identity_review_status'] for r in review)
    provenance = {str(p): digest(p) for p in (people_path, pairs_path, modern_path)}
    if optional_bios:
        provenance[str(bios_path)] = digest(bios_path)
    summary = {
        'stage': 'cross_era_identity_leads_only_not_frozen',
        'historic_reviewed_person_slots': len(historic),
        'historic_original_pair_ids_mapped': len(original_pair_ids_seen),
        'historic_projected_pairs': len(historic_pair_keys),
        'modern_ranking_rows': len(modern),
        'modern_unique_name_ids': len({k[1] for k in modern_people}),
        'modern_discipline_id_slots': len(modern_people),
        'modern_pairs': len(modern_pairs),
        'modern_bio_file_present': optional_bios,
        'modern_exact_bio_dob_ids': sum(len(v['dates']) == 1 for v in bio_by_modern.values()),
        'modern_bio_conflict_ids': len(bio_conflicts),
        'modern_exact_bio_rows_ignored_invalid': invalid_bio_rows,
        'cross_era_full_pair_name_bridges': len(pair_bridges),
        'historic_modern_person_candidate_edges': len(review),
        'historic_slots_with_any_cross_era_lead': len(matched_by_h),
        'historic_slots_without_cross_era_lead': len(missing),
        'modern_discipline_slots_with_cross_era_lead': len(matched_by_m),
        'review_status_counts': dict(sorted(tally.items())),
        'inputs_sha256': provenance,
        'limitations': [
            'All matches are evidence candidates; no historical or modern person IDs are merged',
            'Same hashed person ID proves name normalization only, not identity',
            'Same-partner matching may miss couples with both member names changed',
            'Modern ISU biographies may be incomplete; lack of DOB is not disagreement',
            'A name/DOB collision or mirrored ISU URLs is not independent identity proof',
            'Season rankings are not event-start lists or event results',
            'No BaZi, outcomes-based sampling or statistical inference',
        ],
    }
    summary_path = Path(out_dir) / 'historic_modern_cross_era_manifest_v1.json'
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--historic-people', type=Path, default=HIST_PEOPLE)
    p.add_argument('--historic-pairs', type=Path, default=HIST_PAIRS)
    p.add_argument('--modern', type=Path, default=MODERN)
    p.add_argument('--bios', type=Path, default=BIOS)
    p.add_argument('--out', type=Path, default=OUT)
    a = p.parse_args()
    cross_era(a.historic_people, a.historic_pairs, a.modern, a.bios, a.out)


if __name__ == '__main__':
    main()
