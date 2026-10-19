#!/usr/bin/env python3
"""Fetch the 44 discovered senior-core entry/result tables; never edit masters.

Counts are observations, not imposed legacy denominators. Raw HTML, row cells,
entry/result exceptions, and exact-name local comparisons remain separate.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('output/frame/isu_core1718_source_inventory_v1')
CODES = ('gprus2017', 'gpcan2017', 'gpchn2017', 'gpjpn2017', 'gpfra2017',
         'gpusa2017', 'gpf1718', 'ec2018', 'fc2018', 'owg2018', 'wc2018')
DISCIPLINES = ('Ice Dance', 'Pair Skating')
HOSTS = {'www.isuresults.com', 'results.isu.org'}
RECORD_FIELDS = ('event_id', 'event_code', 'discipline', 'page_kind', 'source_row',
    'ordinal_or_placement_raw', 'name_as_published', 'person_a_as_published',
    'person_b_as_published', 'name_layout', 'nation_as_published', 'profile_id',
    'profile_url', 'published_status', 'points_as_published', 'points_interpretation',
    'total_points', 'short_segment_points', 'short_rank_raw', 'free_rank_raw',
    'row_review_flags', 'source_url', 'effective_url', 'raw_sha256', 'source_cells_json')
PAGE_FIELDS = ('event_id', 'event_code', 'discipline', 'page_kind', 'source_url',
    'effective_url', 'cached', 'raw_sha256', 'parsed_rows', 'status', 'error')
LINK_FIELDS = ('event_id', 'entry_source_row', 'result_source_row', 'entry_name',
    'result_name', 'entry_profile_id', 'result_profile_id', 'link_status', 'result_status')
LOCAL_FIELDS = ('event_id', 'official_source_row', 'official_name', 'local_record_id',
    'local_name', 'match_status', 'placement_check', 'points_check', 'official_points_meaning')
CELL_FIELDS = ('event_id', 'official_entry_rows', 'official_result_rows', 'local_rows',
    'result_minus_local_rows', 'entry_result_status_counts', 'local_match_status_counts',
    'comparison_status')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path, fields):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        require(set(fields) <= set(reader.fieldnames or []), f'{path}: missing CSV fields')
        rows = list(reader)
    require(all(None not in r and None not in r.values() for r in rows), 'Malformed CSV row')
    return rows


def write_csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)


def clean(s):
    return ' '.join((s or '').split())


def norm(s):
    s = unicodedata.normalize('NFKD', s.casefold())
    return ' '.join(sorted(re.findall(r'[a-z0-9]+', ''.join(c for c in s if not unicodedata.combining(c)))))


def numeric(s):
    s = clean(s)
    if not re.fullmatch(r'\d+(?:[.,]\d+)?', s):
        return None
    try:
        return Decimal(s.replace(',', '.'))
    except InvalidOperation:
        return None


def checked_url(url, code):
    p = urlsplit(url)
    root = f'/results/season1718/{code}/'
    require(p.scheme == 'https' and p.hostname in HOSTS and p.username is None and
            p.password is None and p.port is None and not p.query and not p.fragment,
            'Unapproved source URL')
    require(p.path.startswith(root) and
            re.fullmatch(r'[A-Za-z0-9_-]+\.html?', p.path[len(root):], re.I), 'Wrong event HTML path')
    return url


def decode(raw):
    match = re.search(rb'charset\s*=\s*[\'\"]?([a-zA-Z0-9_-]+)', raw[:8192], re.I)
    for enc in ([match.group(1).decode('ascii')] if match else []) + ['utf-8', 'cp1252', 'latin-1']:
        try:
            return raw.decode(enc, errors='strict')
        except (UnicodeDecodeError, LookupError):
            pass
    raise ValueError('Cannot decode HTML')


def pair_names(cell):
    """Use explicit slash or HTML line breaks, never guess a name boundary."""
    text = clean(cell.get_text(' ', strip=True))
    if text.count('/') == 1:
        a, b = map(clean, text.split('/', 1))
        if a and b:
            return text, a, b, 'SLASH'
    fragment = BeautifulSoup(str(cell), 'html.parser')
    for br in fragment.find_all('br'):
        br.replace_with('\n')
    lines = [clean(x) for x in fragment.get_text(' ', strip=False).splitlines() if clean(x)]
    if len(lines) == 2:
        return text, lines[0], lines[1], 'HTML_LINE_BREAK'
    return text, '', '', 'UNSPLIT_NAME_REVIEW'


def header(cells, kind):
    labels = [re.sub(r'[^a-z#]', '', clean(c.get_text(' ', strip=True)).casefold()) for c in cells]
    if 'name' not in labels or 'nation' not in labels:
        return None
    h = {k: labels.index(k) for k in ('name', 'nation', 'points', 'sp', 'sd', 'fs', 'fd') if k in labels}
    position = next((i for i, x in enumerate(labels) if x in ('no', '#', 'pl', 'fpl', 'rank')), None)
    if position is None or (kind == 'result' and 'points' not in h):
        return None
    h['position'] = position
    return h


def parse_table(raw, cell, kind, url, effective=None):
    """Return explicit source rows; unfamiliar names/statuses are review flags."""
    checked_url(url, cell['event_code'])
    effective = checked_url(effective or url, cell['event_code'])
    soup = BeautifulSoup(decode(raw), 'html.parser')
    for tag in soup(['script', 'style', 'head']):
        tag.decompose()
    text = clean(soup.get_text(' ', strip=True))
    top = text[:1500].casefold()
    category = r'\bice dance\b' if cell['discipline'] == 'Ice Dance' else r'\b(?:pairs|pair skating)\b'
    require(re.search(category, top), 'Wrong/missing discipline on table page')
    require(not re.search(r'\b(?:junior|team)\s+(?:pairs|pair skating|ice dance)\b', top),
            'Junior or team category cannot enter the selected frame')
    require(re.search(r'\bentr(?:y|ies)\b' if kind == 'entry' else r'\bresults?\b', top),
            'Wrong entry/result page kind')
    tables = {}
    for tr in soup.find_all('tr'):
        cells = tr.find_all(['td', 'th'], recursive=False)
        h = header(cells, kind)
        if h is not None:
            table = tr.find_parent('table')
            if table is not None:
                tables[id(table)] = (table, h)
    require(len(tables) == 1, 'Expected one attributable entry/result table')
    table, h = next(iter(tables.values()))
    rows, identities, ordinals = [], set(), set()
    section = ''
    for tr in table.find_all('tr'):
        if tr.find_parent('table') is not table:
            continue
        cells = tr.find_all(['td', 'th'], recursive=False)
        values = [clean(c.get_text(' ', strip=True)) for c in cells]
        if not cells or header(cells, kind) is not None:
            continue
        rowtext = clean(' '.join(values))
        # Section labels may share the same table or occupy a colspan row.
        if len(cells) <= 2 and not tr.find('a', href=True):
            if re.search(r'final\s+not\s+reached', rowtext, re.I):
                section = 'FINAL_NOT_REACHED'
            elif re.fullmatch(r'(withdrawn|withdrawals|disqualified)', rowtext, re.I):
                section = rowtext.upper()
            continue
        require(len(cells) > max(h.values()), 'Truncated athlete row: refusing partial table')
        name, a, b, layout = pair_names(cells[h['name']])
        require(name, 'Blank athlete name in data row')
        flags = [] if a and b else ['UNSPLIT_NAME_REVIEW']
        links = []
        for anchor in cells[h['name']].find_all('a', href=True):
            p = urlsplit(urljoin(effective, anchor['href']))
            if '/bios/' not in p.path.lower():
                continue
            require(p.scheme in ('https', 'http') and p.hostname in HOSTS and p.username is None and
                    p.password is None and p.port is None and not p.query and not p.fragment,
                    'Unapproved Biography URL')
            match = re.fullmatch(r'/bios/(isufs\d+)\.htm', p.path, re.I)
            require(match, 'Malformed Biography path')
            links.append((match.group(1).lower(), urljoin(effective, anchor['href'])))
        links = sorted(set(links))
        require(len(links) <= 1, 'Multiple Biography IDs in one row')
        prof, profurl = links[0] if links else ('', '')
        if not prof:
            flags.append('NO_PROFILE_LINK_REVIEW')
        key = ('profile', prof) if prof else ('name', norm(name))
        require(key not in identities, 'Duplicate source participant identity')
        identities.add(key)
        nation_cell = cells[h['nation']]
        nations = set(re.findall(r'\b[A-Z]{3}\b', clean(nation_cell.get_text(' ', strip=True))))
        for img in nation_cell.find_all('img'):
            for candidate in (img.get('alt', ''), img.get('title', '')):
                if re.fullmatch('[A-Z]{3}', clean(candidate)):
                    nations.add(clean(candidate))
            stem = Path(urlsplit(img.get('src', '')).path).stem.upper()
            if re.fullmatch('[A-Z]{3}', stem):
                nations.add(stem)
        nation = next(iter(nations)) if len(nations) == 1 else clean(nation_cell.get_text(' ', strip=True))
        if len(nations) != 1:
            flags.append('NATION_UNRESOLVED_REVIEW')
        pos = values[h['position']]
        is_rank = bool(re.fullmatch(r'\d+\.?', pos))
        if is_rank:
            require(int(pos.rstrip('.')) > 0 and int(pos.rstrip('.')) not in ordinals, 'Repeated/invalid ordinal')
            ordinals.add(int(pos.rstrip('.')))
        # Explicit source status overrides position and point values.
        status_token = next((x.upper().replace('/', '') for x in values
                             if x.upper().replace('/', '') in {'WD', 'DNS', 'DSQ', 'DQ'}), '')
        sp = values[h['sp' if 'sp' in h else 'sd']] if 'sp' in h or 'sd' in h else ''
        fs = values[h['fs' if 'fs' in h else 'fd']] if 'fs' in h or 'fd' in h else ''
        points = values[h['points']] if 'points' in h else ''
        meaning, total, short = 'NOT_APPLICABLE', '', ''
        if kind == 'entry':
            state = {'WD': 'ENTRY_WITHDRAWN', 'DNS': 'ENTRY_DNS'}.get(status_token, 'PUBLISHED_ENTRY')
            if not is_rank:
                flags.append('ENTRY_ORDINAL_REVIEW')
        else:
            if status_token or section in ('WITHDRAWN', 'WITHDRAWALS', 'DISQUALIFIED'):
                state = {'WD': 'WITHDRAWN', 'DNS': 'DID_NOT_START', 'DSQ': 'DISQUALIFIED',
                         'DQ': 'DISQUALIFIED'}.get(status_token, 'DISQUALIFIED' if section == 'DISQUALIFIED' else 'WITHDRAWN')
                meaning = 'WITHDRAWAL_OR_DQ_POINTS_NOT_CLASSIFIED'
            elif section == 'FINAL_NOT_REACHED':
                state, meaning = 'FINAL_NOT_REACHED', 'SHORT_SEGMENT_ONLY_NOT_TOTAL'
                if numeric(points) is not None:
                    short = str(numeric(points))
            elif re.fullmatch(r'\d+\.?', fs):
                state, meaning = 'FINAL_COMPLETE', 'TOTAL_SCORE'
                if numeric(points) is not None:
                    total = str(numeric(points))
            else:
                state, meaning = 'RESULT_STATUS_UNRESOLVED_REVIEW', 'UNRESOLVED_NOT_TOTAL'
                flags.append('RESULT_STATUS_UNRESOLVED_REVIEW')
            if state in ('FINAL_COMPLETE', 'FINAL_NOT_REACHED') and (not is_rank or numeric(points) is None):
                flags.append('RANK_OR_POINTS_UNRESOLVED_REVIEW')
        rows.append(dict(zip(RECORD_FIELDS, (
            cell['event_id'], cell['event_code'], cell['discipline'], kind, len(rows) + 1,
            pos, name, a, b, layout, nation, prof, profurl, state, points, meaning, total, short,
            sp, fs, '; '.join(flags), url, effective, hashlib.sha256(raw).hexdigest(),
            json.dumps(values, ensure_ascii=False)))))
    require(rows, 'No data rows parsed; absence cannot be inferred')
    return rows


def pair_key(row):
    a, b = row.get('person_a_as_published', ''), row.get('person_b_as_published', '')
    return (norm(a), norm(b)) if a and b else None


def link_tables(entries, results):
    """Source-to-source one-to-one leads only, no real-person ID merging."""
    output, used = [], set()
    for e in entries:
        hits = [i for i, r in enumerate(results) if e['profile_id'] and r['profile_id'] == e['profile_id']]
        method = 'PROFILE'
        if not hits and pair_key(e):
            hits = [i for i, r in enumerate(results) if pair_key(r) == pair_key(e)]
            method = 'NAME_ONLY'
        require(len(hits) <= 1, 'Ambiguous entry/result source correspondence')
        r = results[hits[0]] if hits else None
        if r:
            require(hits[0] not in used, 'Many-to-one entry/result correspondence')
            used.add(hits[0])
        status = 'ENTRY_ONLY_NO_RESULT_EVIDENCE'
        if r:
            status = ('NAME_ONLY_LINK_REVIEW' if method == 'NAME_ONLY' else
                      'PROFILE_NATION_DIFFERENCE_REVIEW' if e['nation_as_published'] != r['nation_as_published'] else
                      'PROFILE_NAME_DIFFERENCE_REVIEW' if not pair_key(e) or pair_key(e) != pair_key(r) else
                      'PROFILE_AND_NAMES_AGREE_SOURCE_LINK')
            if e['row_review_flags'] or r['row_review_flags']:
                status += '; ROW_REVIEW_REQUIRED'
        output.append(dict(zip(LINK_FIELDS, (e['event_id'], e['source_row'], r['source_row'] if r else '',
            e['name_as_published'], r['name_as_published'] if r else '', e['profile_id'],
            r['profile_id'] if r else '', status, r['published_status'] if r else ''))))
    for i, r in enumerate(results):
        if i not in used:
            output.append(dict(zip(LINK_FIELDS, (r['event_id'], '', r['source_row'], '',
                r['name_as_published'], '', r['profile_id'], 'RESULT_ONLY_NO_ENTRY_EVIDENCE', r['published_status']))))
    return output


def compare_local(results, local):
    """Exact full-pair name comparison; discrepancies are not automatic corrections."""
    output, used = [], set()
    for r in results:
        key = pair_key(r)
        hits = [i for i, x in enumerate(local) if key and pair_key(x) == key]
        x = local[hits[0]] if len(hits) == 1 else None
        if x:
            require(hits[0] not in used, 'Many-to-one local comparison')
            used.add(hits[0])
        status = 'EXACT_NAME_LINK_CANDIDATE' if x else ('MULTIPLE_LOCAL_NAME_MATCHES_HOLD' if hits else 'NO_EXACT_LOCAL_PAIR_NAME_REVIEW')
        def comparison(a, b, rank=False):
            va, vb = numeric(a.rstrip('.') if rank else a), numeric(b.rstrip('.') if rank else b)
            return 'NOT_COMPARABLE' if va is None or vb is None else 'SAME_PUBLISHED_VALUE' if va == vb else 'DIFFERENT_PUBLISHED_VALUE_REVIEW'
        output.append(dict(zip(LOCAL_FIELDS, (r['event_id'], r['source_row'], r['name_as_published'],
            x['record_id'] if x else '', x['name_as_published'] if x else '', status,
            comparison(r['ordinal_or_placement_raw'], x['rank'], True) if x else '',
            comparison(r['points_as_published'], x['points']) if x else '', r['points_interpretation']))))
    for i, x in enumerate(local):
        if i not in used:
            output.append(dict(zip(LOCAL_FIELDS, (x['event_id'], '', '', x['record_id'],
                x['name_as_published'], 'LOCAL_ROW_WITHOUT_EXACT_OFFICIAL_NAME_LINK_REVIEW', '', '', ''))))
    return output


def cached_page(session, url, code, cache, offline=False):
    checked_url(url, code)
    key = hashlib.sha256(url.encode()).hexdigest()
    rawpath, metapath = Path(cache) / (key + '.html'), Path(cache) / (key + '.json')
    if rawpath.exists() or metapath.exists():
        require(rawpath.is_file() and metapath.is_file(), 'Partial cache: use new --cache directory')
        m = json.loads(metapath.read_text(encoding='utf-8'))
        require(m.get('requested_url') == url and m.get('raw_sha256') == sha(rawpath), 'Cache hash/URL mismatch')
        return rawpath.read_bytes(), checked_url(m['effective_url'], code), True
    if offline:
        raise FileNotFoundError('Table not cached: ' + url)
    effective = url
    for _ in range(5):
        response = session.get(effective, timeout=(6, 20), allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            effective = checked_url(urljoin(effective, response.headers.get('Location', '')), code)
            continue
        response.raise_for_status()
        raw = response.content
        require(len(raw) > 100 and b'<html' in raw[:8192].lower(), 'Response is not HTML')
        rawpath.parent.mkdir(parents=True, exist_ok=True)
        rawpath.write_bytes(raw)
        metapath.write_text(json.dumps({'requested_url': url, 'effective_url': effective,
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'retrieved_utc': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
        return raw, effective, False
    raise ValueError('Too many redirects')


def load_inputs(root, inventory, manifest, extension):
    m = json.loads(manifest.read_text(encoding='utf-8-sig'))
    require(m.get('stage') == 'core1718_official_index_inventory_v1_NOT_FROZEN' and
            m.get('index_pages_verified') == 11 and m.get('index_pages_failed') == 0 and
            m.get('entry_result_urls_discovered') == 44, 'Require completed 11-index source audit')
    require(m['output_sha256'].get('core1718_event_source_inventory_v1.csv') == sha(inventory), 'Inventory hash mismatch')
    pins = {k.replace('\\', '/'): v for k, v in m['input_sha256'].items()}
    require(pins.get('output/frame/isu_wc2018_extension_v2/wc2018_extension_manifest_v2.json') == sha(extension), 'Extension manifest hash mismatch')
    rows = read_csv(inventory, ('event_id', 'event_code', 'discipline', 'index_status', 'official_entry_url', 'official_result_url', 'legacy_pair_event_rows', 'wc2018_overlay_rows'))
    keys, urls = set(), set()
    for c in rows:
        key = (c['event_code'], c['discipline'])
        require(key not in keys and key[0] in CODES and key[1] in DISCIPLINES and
                c['event_id'] == '2017-2018|' + '|'.join(key) and c['index_status'] == 'INDEX_LINKS_VERIFIED', 'Bad/repeated inventory cell')
        keys.add(key)
        for kind in ('entry', 'result'):
            url = checked_url(c['official_' + kind + '_url'], key[0])
            require(url not in urls, 'Source URL reused across categories/kinds')
            urls.add(url)
    require(len(keys) == 22 and len(urls) == 44, 'Incomplete fixed source frame')
    ex = json.loads(extension.read_text(encoding='utf-8-sig'))
    require(ex.get('stage') == 'wc2018_source_reviewed_extension_v2_NOT_FROZEN' and ex.get('event_key_collisions') == 0, 'Invalid WC extension')
    events = root / 'data/historic/v4/pair_events_v4.csv'
    exinputs = {k.replace('\\', '/'): v for k, v in ex['input_sha256'].items()}
    require(exinputs.get('data/historic/v4/pair_events_v4.csv') == sha(events), 'Legacy event source hash mismatch')
    for name, digest in ex['output_sha256'].items():
        require(Path(name).name == name and sha(extension.parent / name) == digest, 'WC extension output hash mismatch')
    overlay = extension.parent / 'wc2018_resolved_event_overlay_v2.csv'
    local = defaultdict(list)
    wanted = {c['event_id'] for c in rows}
    for path, kind in ((events, 'legacy'), (overlay, 'overlay')):
        cols = ('event_id', 'person_a_name', 'person_b_name', 'rank', 'score_as_reported', 'pair_event_id') if kind == 'legacy' else ('event_id', 'person_a_as_published', 'person_b_as_published', 'final_placement', 'points_as_published', 'extension_event_id')
        for r in read_csv(path, cols):
            if r['event_id'] not in wanted:
                continue
            a, b = (r['person_a_name'], r['person_b_name']) if kind == 'legacy' else (r['person_a_as_published'], r['person_b_as_published'])
            local[r['event_id']].append({'event_id': r['event_id'], 'person_a_as_published': a,
                'person_b_as_published': b, 'name_as_published': a + ' / ' + b,
                'record_id': r['pair_event_id'] if kind == 'legacy' else r['extension_event_id'],
                'rank': r['rank'] if kind == 'legacy' else r['final_placement'],
                'points': r['score_as_reported'] if kind == 'legacy' else r['points_as_published']})
    for c in rows:
        require(len(local[c['event_id']]) == int(c['legacy_pair_event_rows']) + int(c['wc2018_overlay_rows']), 'Local cell count changed')
    paths = (inventory, manifest, extension, events, overlay)
    return rows, local, {str(p): sha(p) for p in paths}


def run(root=ROOT, out=None, cache=None, offline=False, proxy=None, no_env_proxy=False, delay=.4):
    root = Path(root).resolve()
    inventory, manifest = (root / BASE / n for n in ('core1718_event_source_inventory_v1.csv', 'core1718_source_inventory_manifest_v1.json'))
    extension = root / 'output/frame/isu_wc2018_extension_v2/wc2018_extension_manifest_v2.json'
    cells, local, inputs = load_inputs(root, inventory, manifest, extension)
    out = Path(out).resolve() if out else root / 'output/frame/isu_core1718_entry_results_v1'
    cache = Path(cache).resolve() if cache else root / 'cache/isu_core1718_entry_results_v1'
    require(not out.exists(), 'Output exists: choose a new --out directory; no overwrite')
    require(delay >= 0, 'Delay must be nonnegative')
    out.mkdir(parents=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'DoublesResearchDataset/0.3 (public historical event source audit)'
    if proxy:
        p = urlsplit(proxy)
        require(p.scheme in ('http', 'https') and p.hostname, 'Invalid proxy URL')
        session.trust_env = False
        session.proxies.update(http=proxy, https=proxy)
    elif no_env_proxy:
        session.trust_env = False
    pages, records, parsed = [], [], {}
    interrupted = False
    try:
        for c in cells:
            for kind in ('entry', 'result'):
                url = c['official_' + kind + '_url']
                page = dict.fromkeys(PAGE_FIELDS, '')
                page.update(event_id=c['event_id'], event_code=c['event_code'], discipline=c['discipline'],
                            page_kind=kind, source_url=url, status='FAILED_NOT_EMPTY_POPULATION')
                try:
                    raw, effective, was_cached = cached_page(session, url, c['event_code'], cache, offline)
                    page.update(effective_url=effective, cached=was_cached, raw_sha256=hashlib.sha256(raw).hexdigest())
                    rr = parse_table(raw, c, kind, url, effective)
                    page.update(parsed_rows=len(rr), status='PARSED_WITH_ROW_REVIEW' if any(x['row_review_flags'] for x in rr) else 'PARSED')
                    records.extend(rr)
                    parsed[(c['event_id'], kind)] = rr
                except (ValueError, OSError, requests.RequestException) as exc:
                    page['error'] = type(exc).__name__ + ': ' + str(exc)[:500]
                except KeyboardInterrupt:
                    page.update(status='INTERRUPTED', error='User interrupted; cache retained')
                    interrupted = True
                pages.append(page)
                write_csv(out / 'core1718_table_page_inventory_v1.csv', pages, PAGE_FIELDS)
                print(f"[{len(pages)}/44] {c['event_code']} {c['discipline']} {kind}: {page['status']} {page['parsed_rows']} {page['error']}", flush=True)
                if interrupted:
                    break
                if not offline and not page['cached']:
                    time.sleep(delay)
            if interrupted:
                break
    finally:
        session.close()
    links, comparisons, summaries = [], [], []
    for c in cells:
        event = c['event_id']
        entries, results = parsed.get((event, 'entry')), parsed.get((event, 'result'))
        ll, cc, errors = [], [], []
        if entries is not None and results is not None:
            try:
                ll = link_tables(entries, results)
            except ValueError as e:
                errors.append(str(e))
        else:
            errors.append('SOURCE_TABLE_UNAVAILABLE_NOT_ZERO_ENTRANTS')
        if results is not None:
            try:
                cc = compare_local(results, local[event])
            except ValueError as e:
                errors.append(str(e))
        links.extend(ll)
        comparisons.extend(cc)
        summaries.append(dict(zip(CELL_FIELDS, (event, len(entries) if entries is not None else '',
            len(results) if results is not None else '', len(local[event]),
            len(results) - len(local[event]) if results is not None else '',
            json.dumps(Counter(x['link_status'] for x in ll), sort_keys=True),
            json.dumps(Counter(x['match_status'] for x in cc), sort_keys=True),
            '; '.join(errors) if errors else 'SOURCE_COMPARISONS_COMPLETED_NOT_IDENTITY_APPROVAL'))))
    require(all(sha(p) == digest for p, digest in inputs.items()), 'Inputs changed during collection')
    write_csv(out / 'core1718_official_table_records_v1.csv', records, RECORD_FIELDS)
    write_csv(out / 'core1718_entry_result_links_v1.csv', links, LINK_FIELDS)
    write_csv(out / 'core1718_local_result_comparison_v1.csv', comparisons, LOCAL_FIELDS)
    write_csv(out / 'core1718_cell_counts_v1.csv', summaries, CELL_FIELDS)
    failed = sum(not p['status'].startswith('PARSED') for p in pages)
    review = sum(bool(r['row_review_flags']) for r in records)
    report = {'stage': 'core1718_official_entry_result_tables_v1_NOT_FROZEN',
        'source_status': 'INCOMPLETE' if failed or len(pages) != 44 else 'PARSED_WITH_ROW_REVIEW' if review else 'ALL_44_TABLES_PARSED',
        'target_pages': 44, 'pages_attempted': len(pages), 'pages_parsed': len(pages) - failed,
        'pages_failed_or_interrupted': failed, 'pages_not_attempted': 44 - len(pages),
        'official_entry_rows': sum(r['page_kind'] == 'entry' for r in records),
        'official_result_rows': sum(r['page_kind'] == 'result' for r in records),
        'source_rows_with_review_flags': review, 'local_rows_in_selected_frame': sum(map(len, local.values())),
        'result_status_counts': dict(Counter(r['published_status'] for r in records if r['page_kind'] == 'result')),
        'entry_result_link_status_counts': dict(Counter(r['link_status'] for r in links)),
        'local_match_status_counts': dict(Counter(r['match_status'] for r in comparisons)),
        'cells_with_comparison_errors': sum(s['comparison_status'] != 'SOURCE_COMPARISONS_COMPLETED_NOT_IDENTITY_APPROVAL' for s in summaries),
        'local_published_rank_difference_rows': sum(r['placement_check'] == 'DIFFERENT_PUBLISHED_VALUE_REVIEW' for r in comparisons),
        'local_published_points_difference_rows': sum(r['points_check'] == 'DIFFERENT_PUBLISHED_VALUE_REVIEW' for r in comparisons),
        'all_entrant_coverage_fraction': None, 'input_sha256': inputs,
        'limitations': ['Published entry lists are not proof of actual starts; final website snapshots may omit early withdrawals.',
            'Parsing success is not person identity confirmation or global competition coverage.',
            'No row counts are forced to equal the 291 local records; failed pages are unknown, not zero.',
            'Exact-name local links are candidates; spelling and nation differences are never silently corrected.',
            'FNR points are short-segment only; withdrawal/DQ points remain unclassified.',
            'Legacy score meanings are not reclassified even when numerical values match.',
            'Junior, Challenger, domestic and Olympic team events remain outside this bounded source frame.',
            'No original data, DOBs, scores, masters or WC2018 outputs are changed; no astrology or cohort freeze.']}
    report['output_sha256'] = {p.name: sha(p) for p in out.glob('*.csv')}
    (out / 'core1718_entry_result_manifest_v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--proxy')
    parser.add_argument('--no-env-proxy', action='store_true')
    parser.add_argument('--delay', type=float, default=.4)
    a = parser.parse_args()
    result = run(a.root, a.out, a.cache, a.offline, a.proxy, a.no_env_proxy, a.delay)
    raise SystemExit(2 if result['source_status'] == 'INCOMPLETE' or result['cells_with_comparison_errors'] else 0)
