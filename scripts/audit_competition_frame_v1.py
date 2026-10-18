#!/usr/bin/env python3
"""Offline competition-frame audit for ISU doubles research; no cohort selection.

Historical v4 data are selected EVENT RESULT entries. 2018-26 data are
Season's World Ranking rows, NOT event entry lists. Official, manually
checked gap rows are evidence leads, not automatically ingested events.
No identity merges, score aggregation, DOB inference, BaZi or null modeling.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

HIST_EVENTS = Path('data/historic/v4/event_inventory_v4.csv')
HIST_SEASONS = Path('data/historic/v4/season_coverage_v4.csv')
MODERN_RANKS = Path('output/master/season_roster.csv')
HIST_COLLISION = Path('output/historic_dob/cross_era_identity/ambiguity_source_v3/event_collision_audit/historic_alias_event_collision_manifest_v1.json')
MODERN_DOB = Path('output/historic_dob/modern_dob_rescue_v6/modern_official_dob_rescue_manifest_v6.json')
GAPS = Path('data/frame/isu_verified_entry_gaps_v1.csv')
OUT = Path('output/competition_frame_audit_v1')
DISCIPLINES = {'Ice Dance', 'Pair Skating'}
SEASON_RE = re.compile(r'^\d{4}-\d{4}$')
RANK_SEASON_RE = re.compile(r'^\d{4}-\d{2}$')

EVENT_FIELDS = ['season', 'discipline', 'event_instances', 'pair_event_records',
                'source_competitions', 'competition_family_count', 'family_breakdown',
                'direct_isu_event_links', 'third_party_only_event_links',
                'not_an_all_entrant_frame']
MODERN_FIELDS = ['season', 'discipline', 'level', 'ranking_rows',
                 'distinct_pair_name_ids', 'source_page_urls', 'profile_url_missing_rows',
                 'frame_type', 'pandemic_rank_exception', 'junior_rank_page_status']
FAMILY_FIELDS = ['event_family', 'unique_tournament_instances',
                 'event_discipline_instances', 'observed_pair_event_rows',
                 'provenance_caveat']
GAP_FIELDS = ['season', 'event_code', 'discipline', 'source_event_name',
              'official_entry_url', 'official_event_index_url',
              'official_published_entry_pairs', 'source_status', 'review_note',
              'historic_inventory_presence', 'gap_priority',
              'entries_pending_event_first_ingest']


def read_csv(path: Path, needed):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        missing = set(needed) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f'{path} missing columns {sorted(missing)}')
        return list(reader)


def write_csv(path: Path, records, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def digest(path: Path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def family(code):
    """GP France (gpfra2017) is not Grand Prix Final (gpf1718)."""
    if re.fullmatch(r'wc\d{4}', code, re.I):
        return 'World Championships'
    if re.fullmatch(r'ec\d{4}', code, re.I):
        return 'European Championships'
    if re.fullmatch(r'fc\d{4}', code, re.I):
        return 'Four Continents Championships'
    if re.fullmatch(r'owg\d{4}', code, re.I):
        return 'Olympic Winter Games'
    if re.fullmatch(r'gpf\d{2,4}', code, re.I):
        return 'Grand Prix Final'
    if re.fullmatch(r'gp(?:can|chn|fra|jpn|rus|usa)\d{2,4}', code, re.I):
        return 'Grand Prix Series'
    return 'UNCLASSIFIED_EVENT_CODE'


def direct_isu_url(value):
    urls = [v.strip() for v in (value or '').split(';') if v.strip()]
    return any(urlsplit(u).hostname in {'results.isu.org', 'www.isuresults.com'}
               for u in urls)


def official_entry_url(value, code, disc):
    p = urlsplit(value)
    if (p.scheme != 'https' or p.hostname not in {'results.isu.org', 'www.isuresults.com'}
            or p.username or p.password or p.port is not None or p.query or p.fragment):
        return False
    event_short = {'wc2018': 'season1718/wc2018'}
    suffix = 'CAT004EN.HTM' if disc == 'Ice Dance' else 'CAT003EN.HTM'
    return p.path == f'/results/{event_short.get(code, "invalid")}/{suffix}'


def audit(event_path=HIST_EVENTS, season_path=HIST_SEASONS,
          modern_path=MODERN_RANKS, collision_path=HIST_COLLISION,
          dob_path=MODERN_DOB, gap_path=GAPS, out_dir=OUT):
    paths = [event_path, season_path, modern_path, collision_path, dob_path, gap_path]
    events = read_csv(event_path, ('event_id', 'season', 'event', 'discipline',
                                   'different_couples_seen', 'source_urls'))
    season_counts = read_csv(season_path, ('season', 'discipline',
                                           'different_competitions', 'pair_event_results'))
    ranking = read_csv(modern_path, ('season', 'discipline', 'level', 'pair_id',
                                     'profile_url', 'source_url'))
    gaps = read_csv(gap_path, ('season', 'event_code', 'discipline', 'source_event_name',
                               'official_entry_url', 'official_event_index_url',
                               'official_published_entry_pairs', 'source_status', 'review_note'))
    with Path(collision_path).open(encoding='utf-8') as handle:
        collision = json.load(handle)
    with Path(dob_path).open(encoding='utf-8') as handle:
        dob = json.load(handle)
    if not all((events, season_counts, ranking, gaps)):
        raise ValueError('Required inventory, rankings or official gap seed is empty')
    if (collision.get('event_collision_groups') != 0 or
            collision.get('original_pair_event_records') !=
            collision.get('projected_distinct_pair_event_groups')):
        raise ValueError('Historical reviewed identity has outstanding event collisions')
    if (dob.get('v6_remaining_missing_dob_slots') != 0 or
            dob.get('v6_dob_conflict_slots') != 0):
        raise ValueError('Modern DOB source coverage is not complete in current preview')

    hist_seen, hist_group, fams = set(), defaultdict(list), defaultdict(list)
    for row in events:
        key = (row['season'], row['event'], row['discipline'])
        if (key in hist_seen or row['event_id'] != '|'.join(key) or
                row['discipline'] not in DISCIPLINES or
                not SEASON_RE.fullmatch(row['season'])):
            raise ValueError('Repeated or malformed historical event identity')
        hist_seen.add(key)
        category = family(row['event'])
        if category == 'UNCLASSIFIED_EVENT_CODE':
            raise ValueError('Unclassified event code; require explicit audit: ' + row['event'])
        try:
            count = int(row['different_couples_seen'])
        except ValueError as exc:
            raise ValueError('Invalid historical pair-event count') from exc
        if count < 0:
            raise ValueError('Negative historical event population')
        hist_group[(row['season'], row['discipline'])].append((row, category, count))
        fams[category].append((row, count))

    rows_hist = []
    checked_season_keys = set()
    for row in season_counts:
        key = (row['season'], row['discipline'])
        if key in checked_season_keys or key not in hist_group:
            raise ValueError('Historical season summary duplicates or lacks source events')
        checked_season_keys.add(key)
        evidence = hist_group[key]
        total = sum(c for _, _, c in evidence)
        if (len(evidence) != int(row['different_competitions']) or
                total != int(row['pair_event_results'])):
            raise ValueError('Historical season summary disagrees with event inventory')
        kinds = Counter(f for _, f, _ in evidence)
        thirdparty = sum(not direct_isu_url(r['source_urls']) for r, _, _ in evidence)
        rows_hist.append({
            'season': key[0], 'discipline': key[1],
            'event_instances': len(evidence), 'pair_event_records': total,
            'source_competitions': len({r['event'] for r, _, _ in evidence}),
            'competition_family_count': len(kinds),
            'family_breakdown': '; '.join(f'{k}={v}' for k, v in sorted(kinds.items())),
            'direct_isu_event_links': len(evidence) - thirdparty,
            'third_party_only_event_links': thirdparty,
            'not_an_all_entrant_frame': 'TRUE',
        })
    if checked_season_keys != set(hist_group):
        raise ValueError('Historical source has season/event groups missing from summary')
    total_event_rows = sum(x['pair_event_records'] for x in rows_hist)
    if total_event_rows != collision['original_pair_event_records']:
        raise ValueError('Historical source event counts disagree with latest identity audit')

    family_rows = []
    for name, entries in sorted(fams.items()):
        family_rows.append({
            'event_family': name,
            'unique_tournament_instances': len({(r['season'], r['event']) for r, _ in entries}),
            'event_discipline_instances': len(entries),
            'observed_pair_event_rows': sum(c for _, c in entries),
            'provenance_caveat': 'Third-party derived records need official result-page checks',
        })

    rank_groups = defaultdict(list)
    source_season_keys = set()
    for r in ranking:
        key = (r['season'], r['discipline'], r['level'])
        if (not RANK_SEASON_RE.fullmatch(r['season']) or
                r['discipline'] not in DISCIPLINES or
                r['level'] not in {'senior', 'junior'} or not r['pair_id'] or not r['source_url']):
            raise ValueError('Malformed modern Season Ranking input')
        unique = (key, r['pair_id'])
        if unique in source_season_keys:
            raise ValueError('Repeated same-pair source ranking row in one season+level')
        source_season_keys.add(unique)
        rank_groups[key].append(r)
    rank_rows = []
    for (season, disc, level), src in sorted(rank_groups.items()):
        rank_rows.append({
            'season': season, 'discipline': disc, 'level': level,
            'ranking_rows': len(src),
            'distinct_pair_name_ids': len({r['pair_id'] for r in src}),
            'source_page_urls': len({r['source_url'] for r in src}),
            'profile_url_missing_rows': sum(not r['profile_url'] for r in src),
            'frame_type': 'SEASONS_WORLD_RANKING_NOT_EVENT_ENTRIES',
            'pandemic_rank_exception': '2020_21_COVID_POINT_RULES' if season == '2020-21' else 'NONE',
            'junior_rank_page_status': 'AVAILABLE' if level == 'junior' else 'NOT_APPLICABLE',
        })

    gap_rows, gap_seen = [], set()
    for r in gaps:
        key = (r['season'], r['event_code'], r['discipline'])
        if key in gap_seen:
            raise ValueError('Duplicate manually reviewed source event gap')
        gap_seen.add(key)
        if (r['source_status'] != 'official_entry_page_checked' or
                r['discipline'] not in DISCIPLINES or
                r['season'] != '2017-2018' or r['event_code'] != 'wc2018' or
                not official_entry_url(r['official_entry_url'], r['event_code'], r['discipline']) or
                not r['official_event_index_url'].startswith(
                    'https://results.isu.org/results/season1718/wc2018/index.htm') or
                len(r['review_note']) < 45):
            raise ValueError('Unverified ISU event seed entry: ' + repr(key))
        observed = key in hist_seen
        n = int(r['official_published_entry_pairs'])
        if n < 1:
            raise ValueError('Official entry count must be positive')
        gap_rows.append({**r,
                         'historic_inventory_presence': 'PRESENT' if observed else 'NOT_PRESENT',
                         'gap_priority': 'REVIEW_EXISTING_EVENT_VS_ENTRIES' if observed
                          else 'OFFICIAL_EVENT_ENTRIES_MISSING_FROM_HISTORIC_V4',
                         'entries_pending_event_first_ingest': 0 if observed else n})
    if len(gap_rows) != 2:
        raise ValueError('This frozen pilot expects exactly two ISU Worlds 2018 disciplines')

    out = Path(out_dir)
    write_csv(out / 'historical_selected_event_frame_v1.csv', sorted(rows_hist, key=lambda x:(x['season'], x['discipline'])), EVENT_FIELDS)
    write_csv(out / 'historical_event_family_inventory_v1.csv', family_rows, FAMILY_FIELDS)
    write_csv(out / 'modern_rankings_source_frame_v1.csv', rank_rows, MODERN_FIELDS)
    write_csv(out / 'official_event_gap_review_v1.csv', gap_rows, GAP_FIELDS)
    result = {
        'stage': 'event_first_sampling_frame_gap_audit_v1_not_frozen',
        'historic_seasons_present': len({r['season'] for r in events}),
        'historic_unique_tournament_instances': len({(r['season'], r['event']) for r in events}),
        'historic_event_by_discipline_instances': len(events),
        'historic_pair_event_records': total_event_rows,
        'historic_source_direct_isu_event_cells': sum(r['direct_isu_event_links'] for r in rows_hist),
        'historic_source_third_party_only_event_cells': sum(r['third_party_only_event_links'] for r in rows_hist),
        'historical_by_event_family': {r['event_family']: r['unique_tournament_instances'] for r in family_rows},
        'modern_ranking_seasons_present': len({r['season'] for r in ranking}),
        'modern_ranking_page_units': len(rank_rows),
        'modern_ranking_rows': len(ranking),
        'modern_senior_ranking_rows': sum(r['ranking_rows'] for r in rank_rows if r['level'] == 'senior'),
        'modern_junior_ranking_rows': sum(r['ranking_rows'] for r in rank_rows if r['level'] == 'junior'),
        'modern_2020_21_ranking_rows': sum(r['ranking_rows'] for r in rank_rows if r['season'] == '2020-21'),
        'manual_official_missing_event_discipline_units': sum(r['historic_inventory_presence'] == 'NOT_PRESENT' for r in gap_rows),
        'manual_official_missing_event_pair_entries': sum(r['entries_pending_event_first_ingest'] for r in gap_rows),
        'reviewed_modern_dob_name_id_slots': dob.get('v6_covered_canonical_name_id_slots'),
        'input_sha256': {str(p): digest(p) for p in paths},
        'interpretation': [
            'No global coverage fraction: official all-competition entrant universe not yet enumerated',
            'Historic sources are selected senior event-result records; first two seasons contain only Worlds, and Milan 2018 Worlds is currently absent',
            'Modern sources are scored Season World Ranking pages, not start lists, event entrants or independent competition results',
            'Junior ranking pages available only for 2023-24 onward in this collection; earlier missing pages cannot be coded as zero junior entrants',
            '2020-21 Season Ranking rows have pandemic-specific non-comparable participation/point rules',
            'Official event entry pages and results must be ingested into distinct provenance-aware tables before making event-level denominators',
            'DOB 100 percent coverage is only of the current reviewed ranking name-ID slots, not all eligible athletes',
            'No birth-time astrology, performance-based sampling, outcomes, model fitting or cohort freeze',
        ],
    }
    (out / 'competition_frame_audit_manifest_v1.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--historical-events', type=Path, default=HIST_EVENTS)
    p.add_argument('--historical-seasons', type=Path, default=HIST_SEASONS)
    p.add_argument('--modern-rankings', type=Path, default=MODERN_RANKS)
    p.add_argument('--historic-collision', type=Path, default=HIST_COLLISION)
    p.add_argument('--modern-dob', type=Path, default=MODERN_DOB)
    p.add_argument('--official-gaps', type=Path, default=GAPS)
    p.add_argument('--out', type=Path, default=OUT)
    a = p.parse_args()
    audit(a.historical_events, a.historical_seasons, a.modern_rankings,
          a.historic_collision, a.modern_dob, a.official_gaps, a.out)


if __name__ == '__main__':
    main()
