#!/usr/bin/env python3
"""Bounded 2017-18 senior non-team event source inventory, not entrant ingestion.

Here 'individual-event' excludes Olympic team results; the sports are Pairs
and Ice Dance. Discover actual Entry/Result links from 11 official indexes.
Never infer CAT numbers, count missing pages as zero entrants, or edit sources.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup

SEASON = '2017-2018'
HOSTS = {'results.isu.org', 'www.isuresults.com'}
# Fixed acquisition scope chosen before inspecting any new entrant outcomes.
TARGETS = (
    ('gprus2017', 'Grand Prix Series', 'Rostelecom Cup 2017', 'www.isuresults.com'),
    ('gpcan2017', 'Grand Prix Series', 'Skate Canada International', 'www.isuresults.com'),
    ('gpchn2017', 'Grand Prix Series', 'Cup of China 2017', 'www.isuresults.com'),
    ('gpjpn2017', 'Grand Prix Series', 'NHK Trophy 2017', 'www.isuresults.com'),
    ('gpfra2017', 'Grand Prix Series', 'Internationaux de France', 'www.isuresults.com'),
    ('gpusa2017', 'Grand Prix Series', 'Skate America', 'www.isuresults.com'),
    ('gpf1718', 'Grand Prix Final', 'Grand Prix Final 2017', 'results.isu.org'),
    ('ec2018', 'European Championships', 'European Figure Skating Championships 2018', 'results.isu.org'),
    ('fc2018', 'Four Continents Championships', 'Four Continents Championships 2018', 'results.isu.org'),
    ('owg2018', 'Olympic Winter Games', 'Olympic Winter Games', 'results.isu.org'),
    ('wc2018', 'World Championships', 'World Figure Skating Championships 2018', 'results.isu.org'),
)
CATEGORIES = {'Pairs': 'Pair Skating', 'Pair Skating': 'Pair Skating', 'Ice Dance': 'Ice Dance'}
KINDS = {'Entries': 'entry', 'Result': 'result'}
FIELDS = ('event_id', 'event_code', 'event_family', 'discipline',
          'legacy_pair_event_rows', 'wc2018_overlay_rows', 'local_record_presence',
          'index_source_url', 'index_effective_url', 'index_raw_sha256',
          'index_status', 'official_entry_url', 'official_result_url',
          'linked_pages_status', 'error')
OUTPUT_NAMES = {'wc2018_resolved_event_overlay_v2.csv', 'wc2018_new_person_slots_v2.csv',
                'wc2018_new_pair_combinations_v2.csv', 'historical_plus_wc2018_event_index_v2.csv'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    return ' '.join((text or '').split())


def read_csv(path, required):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not set(required) <= set(reader.fieldnames or []):
            raise ValueError(f'{path}: missing required columns')
        rows = list(reader)
    if any(None in r or None in r.values() for r in rows):
        raise ValueError(f'{path}: malformed CSV')
    return rows


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def checked_url(url, code, index=False):
    """Restrict redirects and discovered links to this exact official event."""
    p = urlsplit(url)
    root = f'/results/season1718/{code}/'
    if (p.scheme != 'https' or p.hostname not in HOSTS or p.username is not None
            or p.password is not None or p.port is not None or p.query or p.fragment):
        raise ValueError('Unapproved official URL: ' + url)
    tail = p.path[len(root):] if p.path.startswith(root) else None
    if tail is None or (index and tail.lower() not in ('', 'index.htm', 'index.html')):
        raise ValueError('Wrong event index path: ' + url)
    if not index and not re.fullmatch(r'[A-Za-z0-9_-]+\.html?', tail, re.I):
        raise ValueError('Expected a same-event HTML source link: ' + url)
    return url


def parse_index(raw, source_url, code, title_fragment):
    checked_url(source_url, code, index=True)
    soup = BeautifulSoup(raw, 'html.parser')
    text = clean(soup.get_text(' ', strip=True))
    title = clean(soup.title.get_text(' ', strip=True)) if soup.title else ''
    identity = (title + ' ' + text[:1200]).casefold()
    year = '2018' if code in {'ec2018', 'fc2018', 'owg2018', 'wc2018'} else '2017'
    if title_fragment.casefold() not in identity or year not in identity:
        raise ValueError('Index event title/year does not match fixed source frame')
    found = {}
    for tr in soup.find_all('tr'):
        cells = tr.find_all(['td', 'th'], recursive=False)
        if not cells:
            continue
        label = clean(cells[0].get_text(' ', strip=True))
        if label not in CATEGORIES:
            continue  # Junior and Team labels are deliberately not normalized away.
        disc = CATEGORIES[label]
        local = {}
        for anchor in tr.find_all('a', href=True):
            if anchor.find_parent('tr') is not tr:
                continue
            kind = KINDS.get(clean(anchor.get_text(' ', strip=True)))
            if not kind:
                continue
            uri = checked_url(urljoin(source_url, anchor['href']), code)
            if kind in local:
                raise ValueError('Duplicate entry/result link in a category row')
            local[kind] = uri
        if not local:
            continue  # A schedule row is not an Entry/Result category row.
        if set(local) != {'entry', 'result'} or disc in found:
            raise ValueError('Incomplete or repeated senior category row')
        if local['entry'] == local['result']:
            raise ValueError('Entry and result cannot be the same source URL')
        found[disc] = local
    if set(found) != {'Ice Dance', 'Pair Skating'}:
        raise ValueError('Both senior individual-event categories are required')
    if len({u for pair in found.values() for u in pair.values()}) != 4:
        raise ValueError('Category sources overlap unexpectedly')
    return found


def cached_index(session, url, code, cache, offline=False):
    """Immutable per-directory snapshot; a new --cache requests a fresh snapshot."""
    checked_url(url, code, index=True)
    cache = Path(cache)
    raw_path, meta_path = cache / (code + '.html'), cache / (code + '.json')
    if raw_path.exists() or meta_path.exists():
        if not raw_path.is_file() or not meta_path.is_file():
            raise ValueError('Partial cache snapshot; choose a new --cache directory')
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('requested_url') != url or meta.get('raw_sha256') != sha(raw_path):
            raise ValueError('Cached source URL/hash mismatch')
        effective = checked_url(meta['effective_url'], code, index=True)
        return raw_path.read_bytes(), effective, meta['raw_sha256'], True
    if offline:
        raise FileNotFoundError('Official index not cached: ' + code)
    effective = url
    for _ in range(4):
        response = session.get(effective, timeout=(6, 20), allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            effective = checked_url(urljoin(effective, response.headers.get('Location', '')), code, index=True)
            continue
        response.raise_for_status()
        raw = response.content
        if b'<html' not in raw[:4096].lower() or len(raw) < 200:
            raise ValueError('Response is not a usable HTML index')
        digest = hashlib.sha256(raw).hexdigest()
        cache.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        meta_path.write_text(json.dumps({'requested_url': url, 'effective_url': effective,
            'raw_sha256': digest, 'retrieved_utc': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
        return raw, effective, digest, False
    raise ValueError('Too many official index redirects')


def baseline(history, extension):
    meta = json.loads(Path(extension).read_text(encoding='utf-8-sig'))
    if meta.get('stage') != 'wc2018_source_reviewed_extension_v2_NOT_FROZEN' or meta.get('event_key_collisions') != 0:
        raise ValueError('Require completed non-colliding WC2018 v2 extension')
    hashes = meta.get('output_sha256', {})
    if set(hashes) != OUTPUT_NAMES:
        raise ValueError('Unexpected WC2018 output lineage')
    for name, digest in hashes.items():
        if sha(Path(extension).parent / name) != digest:
            raise ValueError('WC2018 output hash mismatch: ' + name)
    old = read_csv(history, ('event_id', 'season', 'event', 'discipline', 'different_couples_seen'))
    legacy = {}
    for row in old:
        key = row['event_id']
        if key != '|'.join((row['season'], row['event'], row['discipline'])) or key in legacy:
            raise ValueError('Malformed/duplicate legacy event index key')
        legacy[key] = int(row['different_couples_seen'])
    overlay = read_csv(Path(extension).parent / 'wc2018_resolved_event_overlay_v2.csv', ('event_id',))
    counts = Counter(r['event_id'] for r in overlay)
    if counts != {SEASON + '|wc2018|Ice Dance': 31, SEASON + '|wc2018|Pair Skating': 28}:
        raise ValueError('WC2018 overlay is not the reviewed 59-row source')
    if set(counts) & set(legacy):
        raise ValueError('WC2018 already exists in legacy index')
    if (sum(legacy.values()) != meta.get('legacy_event_rows') or len(overlay) != meta.get('new_event_rows')
            or sum(legacy.values()) + len(overlay) != meta.get('union_index_rows')):
        raise ValueError('Extension and legacy index counts disagree')
    return legacy, counts


def run(history, extension, cache, out, offline=False, proxy=None):
    if Path(out).exists():
        raise FileExistsError('Output already exists; choose another --out directory')
    legacy, overlay = baseline(history, extension)
    session = requests.Session()
    session.headers['User-Agent'] = 'DoublesResearchDataset/0.3 (official historical source inventory)'
    if proxy:
        u = urlsplit(proxy)
        if u.scheme not in {'http', 'https'} or not u.hostname:
            raise ValueError('--proxy must be an HTTP(S) proxy')
        session.trust_env = False
        session.proxies.update({'http': proxy, 'https': proxy})
    Path(out).mkdir(parents=True)
    records, errors, cached = [], 0, 0
    for code, family, title, host in TARGETS:
        url = f'https://{host}/results/season1718/{code}/'
        effective = digest = error = ''
        links = {}
        try:
            raw, effective, digest, hit = cached_index(session, url, code, cache, offline)
            cached += int(hit)
            links = parse_index(raw, effective, code, title)
        except (OSError, ValueError, requests.RequestException) as exc:
            error = type(exc).__name__ + ': ' + str(exc)[:300]
            errors += 1
        for disc in ('Ice Dance', 'Pair Skating'):
            key = '|'.join((SEASON, code, disc))
            records.append(dict(zip(FIELDS, (
                key, code, family, disc, legacy.get(key, 0), overlay.get(key, 0),
                'LEGACY_EVENT_CELL_PRESENT' if key in legacy else
                'WC2018_OVERLAY_CELL_PRESENT' if key in overlay else 'NO_LOCAL_EVENT_CELL',
                url, effective, digest, 'INDEX_LINKS_VERIFIED' if links else 'INDEX_ERROR_HOLD',
                links.get(disc, {}).get('entry', ''), links.get(disc, {}).get('result', ''),
                'REFERENCED_ONLY_NOT_DOWNLOADED_OR_ROW_AUDITED', error))))
        write_csv(Path(out) / 'core1718_event_source_inventory_v1.csv', records)
        print(f'[{"INDEX_LINKS_VERIFIED" if links else "INDEX_ERROR_HOLD"}] {code}: {error}', flush=True)
    session.close()
    summary = {
        'stage': 'core1718_official_index_inventory_v1_NOT_FROZEN',
        'target_tournaments': len(TARGETS), 'target_discipline_cells': 2 * len(TARGETS),
        'index_pages_verified': len(TARGETS) - errors, 'index_pages_failed': errors,
        'indexes_replayed_from_cache': cached,
        'entry_result_urls_discovered': sum(bool(r[k]) for r in records for k in ('official_entry_url', 'official_result_url')),
        'local_legacy_cells': sum(r['local_record_presence'] == 'LEGACY_EVENT_CELL_PRESENT' for r in records),
        'local_overlay_cells': sum(r['local_record_presence'] == 'WC2018_OVERLAY_CELL_PRESENT' for r in records),
        'local_missing_cells': sum(r['local_record_presence'] == 'NO_LOCAL_EVENT_CELL' for r in records),
        'local_pair_event_rows_in_selected_frame': sum(r['legacy_pair_event_rows'] + r['wc2018_overlay_rows'] for r in records),
        'new_entrant_or_result_rows_ingested': 0,
        'all_entrant_coverage_fraction': None,
        'target_event_codes': [x[0] for x in TARGETS],
        'target_families': dict(Counter(x[1] for x in TARGETS)),
        'input_sha256': {str(history): sha(history), str(extension): sha(extension)},
        'output_sha256': {'core1718_event_source_inventory_v1.csv': sha(Path(out) / 'core1718_event_source_inventory_v1.csv')},
        'limitations': [
            'Researcher-defined senior core-event set; not all 2017-18 international competitions.',
            'Excludes Junior, Challenger, national events and Olympic team competition.',
            'An index link is not a fetched/validated entrant or result table.',
            'Local event-cell presence is not participant completeness or score agreement.',
            'Legacy result evidence is not promoted to independently confirmed official records.',
            'No original data, identities, scores, DOBs or WC2018 outputs are altered.',
            'No astrology, outcome-driven selection, null model or cohort freeze.'],
    }
    (Path(out) / 'core1718_source_inventory_manifest_v1.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history', type=Path, default=Path('data/historic/v4/event_inventory_v4.csv'))
    p.add_argument('--extension', type=Path, default=Path('output/frame/isu_wc2018_extension_v2/wc2018_extension_manifest_v2.json'))
    p.add_argument('--cache', type=Path, default=Path('cache/isu_core1718_indexes_v1'))
    p.add_argument('--out', type=Path, default=Path('output/frame/isu_core1718_source_inventory_v1'))
    p.add_argument('--offline', action='store_true')
    p.add_argument('--proxy')
    a = p.parse_args()
    r = run(a.history, a.extension, a.cache, a.out, a.offline, a.proxy)
    raise SystemExit(2 if r['index_pages_failed'] else 0)


if __name__ == '__main__':
    main()
