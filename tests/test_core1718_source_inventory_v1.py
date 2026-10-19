"""Offline synthetic source-frame fixtures; no real entrant outcomes are invented."""
import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_core1718_source_inventory_v1 import (
    TARGETS, OUTPUT_NAMES, parse_index, checked_url, cached_index, baseline, run, sha,
)


def fixture(title='World Figure Skating Championships 2018', mixed=False, comnet=False):
    rows = []
    categories = [('Pairs', '003', '03'), ('Ice Dance', '004', '04')]
    if mixed:
        categories += [('Junior Pairs', '007', '07'), ('Junior Ice Dance', '008', '08'),
                       ('Team Pairs', '013', '13'), ('Team Ice Dance', '014', '14')]
    for label, cat, digit in categories:
        a = f'data{digit}00.htm' if comnet else f'CAT{cat}EN.HTM'
        b = f'data{digit}90.htm' if comnet else f'CAT{cat}RS.HTM'
        rows.append(f'<tr><td>{label}</td><td><a href="{a}">Entries</a></td>'
                    f'<td><a href="{b}">Result</a></td></tr>')
    return ('<html><head><title>' + title + '</title></head><body><table>' +
            ''.join(rows) + '</table></body></html>').encode()


def url(code='wc2018', host='results.isu.org'):
    return f'https://{host}/results/season1718/{code}/'


def save_csv(path, rows, columns):
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def snapshot(cache, code, host, raw):
    cache.mkdir(parents=True, exist_ok=True)
    (cache / (code + '.html')).write_bytes(raw)
    (cache / (code + '.json')).write_text(json.dumps({
        'requested_url': url(code, host), 'effective_url': url(code, host),
        'raw_sha256': hashlib.sha256(raw).hexdigest()}), encoding='utf-8')


class Core1718SourceInventoryTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.cache = self.root / 'cache'
        self.out = self.root / 'out'

    def parse(self, raw):
        return parse_index(raw, url(), 'wc2018', 'World Figure Skating Championships 2018')

    def make_baseline(self):
        folder = self.root / 'extension'
        folder.mkdir()
        self.extension = folder / 'wc2018_extension_manifest_v2.json'
        self.history = self.root / 'history.csv'
        history = []
        for code, _, _, _ in TARGETS:
            if code != 'wc2018':
                for disc in ('Ice Dance', 'Pair Skating'):
                    history.append(dict(event_id=f'2017-2018|{code}|{disc}', season='2017-2018',
                        event=code, discipline=disc, different_couples_seen='1'))
        save_csv(self.history, history, ('event_id', 'season', 'event', 'discipline', 'different_couples_seen'))
        overlay = [{'event_id': f'2017-2018|wc2018|{disc}'} for disc, n in
                   [('Ice Dance', 31), ('Pair Skating', 28)] for _ in range(n)]
        save_csv(folder / 'wc2018_resolved_event_overlay_v2.csv', overlay, ('event_id',))
        for name in OUTPUT_NAMES - {'wc2018_resolved_event_overlay_v2.csv'}:
            (folder / name).write_text('synthetic_placeholder\n', encoding='utf-8')
        meta = dict(stage='wc2018_source_reviewed_extension_v2_NOT_FROZEN',
                    event_key_collisions=0, legacy_event_rows=20, new_event_rows=59, union_index_rows=79,
                    output_sha256={name: sha(folder / name) for name in OUTPUT_NAMES})
        self.extension.write_text(json.dumps(meta), encoding='utf-8')

    def cache_all(self):
        for code, _, title, host in TARGETS:
            if '2017' not in title and '2018' not in title:
                title += ' 2018' if code == 'owg2018' else ' 2017'
            snapshot(self.cache, code, host, fixture(title, mixed=True, comnet=code in {'gpjpn2017', 'gpf1718'}))

    def test_two_senior_categories_and_four_links(self):
        result = self.parse(fixture())
        self.assertEqual(set(result), {'Ice Dance', 'Pair Skating'})
        self.assertTrue(result['Pair Skating']['entry'].endswith('CAT003EN.HTM'))

    def test_comnet_data_paths_are_extracted_not_guessed(self):
        result = self.parse(fixture(comnet=True))
        self.assertTrue(result['Ice Dance']['result'].endswith('data0490.htm'))

    def test_junior_and_team_rows_not_imported(self):
        result = self.parse(fixture(mixed=True))
        self.assertEqual(sum(len(x) for x in result.values()), 4)
        self.assertFalse(any('007' in x for d in result.values() for x in d.values()))

    def test_wrong_event_title_rejected(self):
        with self.assertRaisesRegex(ValueError, 'title/year'):
            self.parse(fixture('Unrelated Championship 2018'))

    def test_duplicate_senior_rows_rejected(self):
        raw = fixture().replace(b'</table>', fixture().split(b'<table>')[1].split(b'</table>')[0] + b'</table>')
        with self.assertRaisesRegex(ValueError, 'repeated senior'):
            self.parse(raw)

    def test_missing_result_not_reported_as_empty_event(self):
        raw = fixture().replace(b'<a href="CAT003RS.HTM">Result</a>', b'')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.parse(raw)

    def test_duplicate_source_urls_across_disciplines_rejected(self):
        raw = fixture().replace(b'CAT004EN.HTM', b'CAT003EN.HTM')
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.parse(raw)

    def test_unsafe_and_cross_event_links_rejected(self):
        bad = ('https://results.isu.org.evil.test/x.htm', url() + '../ec2018/x.htm',
               url() + 'x.htm?next=evil', url() + 'x.pdf', url('ec2018') + 'CAT003EN.HTM',
               'http://results.isu.org/results/season1718/wc2018/x.htm')
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                checked_url(value, 'wc2018')

    def test_offline_missing_cache_never_uses_network(self):
        session = Mock()
        with self.assertRaises(FileNotFoundError):
            cached_index(session, url(), 'wc2018', self.cache, True)
        session.get.assert_not_called()

    def test_cache_hash_tampering_rejected(self):
        snapshot(self.cache, 'wc2018', 'results.isu.org', fixture())
        (self.cache / 'wc2018.html').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            cached_index(Mock(), url(), 'wc2018', self.cache, True)

    def test_valid_cache_replays_without_network(self):
        snapshot(self.cache, 'wc2018', 'results.isu.org', fixture())
        session = Mock()
        raw, effective, digest, hit = cached_index(session, url(), 'wc2018', self.cache, True)
        self.assertTrue(hit)
        self.assertEqual(raw, fixture())
        session.get.assert_not_called()

    def test_network_redirect_outside_event_is_blocked(self):
        session = Mock()
        session.get.return_value = Mock(status_code=302, headers={'Location': 'https://evil.test/'})
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            cached_index(session, url(), 'wc2018', self.cache)
        self.assertEqual(session.get.call_count, 1)

    def test_stale_extension_output_hash_rejected(self):
        self.make_baseline()
        (self.extension.parent / 'wc2018_new_pair_combinations_v2.csv').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'output hash mismatch'):
            baseline(self.history, self.extension)

    def test_full_offline_scope_reports_22_cells_44_links_without_ingestion(self):
        self.make_baseline()
        self.cache_all()
        before = self.history.read_bytes()
        with redirect_stdout(io.StringIO()), patch('requests.Session.get', side_effect=AssertionError('network')):
            r = run(self.history, self.extension, self.cache, self.out, offline=True)
        self.assertEqual(r['index_pages_verified'], 11)
        self.assertEqual(r['target_discipline_cells'], 22)
        self.assertEqual(r['entry_result_urls_discovered'], 44)
        self.assertEqual(r['local_legacy_cells'], 20)
        self.assertEqual(r['local_overlay_cells'], 2)
        self.assertEqual(r['new_entrant_or_result_rows_ingested'], 0)
        self.assertIsNone(r['all_entrant_coverage_fraction'])
        self.assertEqual(self.history.read_bytes(), before)

    def test_failed_page_retains_two_explicit_hold_rows(self):
        self.make_baseline()
        self.cache_all()
        (self.cache / 'ec2018.html').unlink()
        (self.cache / 'ec2018.json').unlink()
        with redirect_stdout(io.StringIO()):
            r = run(self.history, self.extension, self.cache, self.out, offline=True)
        self.assertEqual(r['index_pages_failed'], 1)
        self.assertEqual(r['entry_result_urls_discovered'], 40)
        with (self.out / 'core1718_event_source_inventory_v1.csv').open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 22)
        self.assertEqual(sum(x['index_status'] == 'INDEX_ERROR_HOLD' for x in rows), 2)

    def test_existing_output_is_not_overwritten(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            run('unused', 'unused', self.cache, self.out, offline=True)

    def test_legacy_wc2018_double_count_is_rejected(self):
        self.make_baseline()
        with self.history.open('a', encoding='utf-8') as f:
            f.write('2017-2018|wc2018|Ice Dance,2017-2018,wc2018,Ice Dance,31\n')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            baseline(self.history, self.extension)


if __name__ == '__main__':
    unittest.main()
