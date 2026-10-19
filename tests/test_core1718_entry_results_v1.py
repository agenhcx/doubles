"""Synthetic HTML fixtures and offline integration; not fetched official HTML."""
import contextlib
import io
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_core1718_entry_results_v1 as c


def cell(code='gpcan2017', discipline='Pair Skating'):
    return {'event_id': f'2017-2018|{code}|{discipline}', 'event_code': code, 'discipline': discipline}


def url(code='gpcan2017', kind='entry', discipline='Pair Skating'):
    digit = '003' if discipline == 'Pair Skating' else '004'
    return f'https://www.isuresults.com/results/season1718/{code}/CAT{digit}{"EN" if kind == "entry" else "RS"}.HTM'


def fixture(kind='entry', japan=False, state='', nation='CAN', profile='isufs00001111', name=None, pos='1', free='1', score='123.45', disc='Pair Skating'):
    name = name or ('Alice PERSON<br>Bob PARTNER' if japan else 'Alice PERSON / Bob PARTNER')
    title = 'Ice Dance' if disc == 'Ice Dance' else 'Pairs'
    short_label, free_label = ('SD', 'FD') if disc == 'Ice Dance' else ('SP', 'FS')
    h = ['#' if japan else 'No.', 'Name', 'Nation'] if kind == 'entry' else (
        ['PL', 'Name', 'Nation', short_label, free_label, 'Points'] if japan else
        ['FPl.', 'Name', 'Nation', 'Points', short_label, free_label])
    anchor = f'<a href="https://results.isu.org/bios/{profile}.htm">{name}</a>' if profile else name
    values = [pos, anchor, f'<img alt="{nation}" src="flags/{nation}.gif">{nation}']
    if kind == 'result':
        values += ['1', free, score] if japan else [score, '1', free]
    section = '<tr><th colspan="6">Final not Reached</th></tr>' if state == 'FNR' else ''
    body = f'<h2>{title} - {"Entry" if kind == "entry" else "Final Results"}</h2><table>'
    body += '<tr>' + ''.join('<th>' + x + '</th>' for x in h) + '</tr>' + section
    body += '<tr>' + ''.join('<td>' + x + '</td>' for x in values) + '</tr></table>'
    return ('<html><head><meta charset="utf-8"><title>Senior and Junior GP Final</title></head>' + body + '</html>').encode()


def parse(kind='entry', **kw):
    row = cell(discipline=kw.get('disc', 'Pair Skating'))
    return c.parse_table(fixture(kind=kind, **kw), row, kind, url(kind=kind, discipline=row['discipline']))


class TableParserTests(unittest.TestCase):
    def test_slash_layout_and_total(self):
        r = parse('result')[0]
        self.assertEqual(r['person_a_as_published'], 'Alice PERSON')
        self.assertEqual(r['total_points'], '123.45')
        self.assertEqual(r['published_status'], 'FINAL_COMPLETE')
        self.assertFalse(r['row_review_flags'])

    def test_japanese_br_and_points_last(self):
        r = parse('result', japan=True)[0]
        self.assertEqual(r['name_layout'], 'HTML_LINE_BREAK')
        self.assertEqual(r['person_b_as_published'], 'Bob PARTNER')
        self.assertEqual(r['total_points'], '123.45')

    def test_japanese_entry_hash_ordinal(self):
        self.assertEqual(parse(japan=True)[0]['ordinal_or_placement_raw'], '1')

    def test_fnr_comma_is_not_total(self):
        r = parse('result', state='FNR', pos='17', free='', score='47,57')[0]
        self.assertEqual(r['short_segment_points'], '47.57')
        self.assertEqual(r['total_points'], '')

    def test_withdrawal_score_not_assumed_short_or_total(self):
        r = parse('result', pos='WD', free='', score='57.25')[0]
        self.assertEqual(r['published_status'], 'WITHDRAWN')
        self.assertEqual((r['total_points'], r['short_segment_points']), ('', ''))

    def test_dns_and_dq_statuses(self):
        for status, label in [('DNS', 'DID_NOT_START'), ('DQ', 'DISQUALIFIED')]:
            with self.subTest(status=status):
                self.assertEqual(parse('result', pos=status, free='', score='')[0]['published_status'], label)

    def test_unknown_free_status_is_held(self):
        r = parse('result', free='')[0]
        self.assertEqual(r['points_interpretation'], 'UNRESOLVED_NOT_TOTAL')
        self.assertIn('RESULT_STATUS_UNRESOLVED_REVIEW', r['row_review_flags'])

    def test_published_oar_bul_not_normalized(self):
        for nation in ('OAR', 'BUL'):
            with self.subTest(nation=nation):
                self.assertEqual(parse(nation=nation)[0]['nation_as_published'], nation)

    def test_preserve_abbreviated_and_surname_first(self):
        r = parse(name='PERSON A / PARTNER B')[0]
        self.assertEqual(r['person_a_as_published'], 'PERSON A')

    def test_no_profile_retained_with_flag(self):
        r = parse(profile='')[0]
        self.assertEqual(r['profile_id'], '')
        self.assertIn('NO_PROFILE_LINK_REVIEW', r['row_review_flags'])

    def test_unsplit_name_not_invented(self):
        r = parse(name='Alice PERSON Bob PARTNER')[0]
        self.assertEqual(r['person_a_as_published'], '')
        self.assertIn('UNSPLIT_NAME_REVIEW', r['row_review_flags'])

    def test_wrong_category_rejected(self):
        raw = fixture().replace(b'Pairs - Entry', b'Junior Pairs - Entry')
        with self.assertRaisesRegex(ValueError, 'Junior or team'):
            c.parse_table(raw, cell(), 'entry', url())

    def test_wrong_source_event_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Wrong event'):
            c.parse_table(fixture(), cell(), 'entry', url(code='wc2018'))

    def test_empty_table_is_not_zero_entrants(self):
        raw = b'<html><h1>Pairs Entry</h1><table><tr><th>No.</th><th>Name</th><th>Nation</th></tr></table></html>'
        with self.assertRaisesRegex(ValueError, 'No data rows'):
            c.parse_table(raw, cell(), 'entry', url())

    def test_duplicate_profile_refused(self):
        raw = fixture()
        start = raw.index(b'<tr><td>')
        end = raw.index(b'</tr>', start) + 5
        raw = raw.replace(b'</table>', raw[start:end] + b'</table>')
        with self.assertRaisesRegex(ValueError, 'Duplicate source'):
            c.parse_table(raw, cell(), 'entry', url())

    def test_lossless_declared_encoding(self):
        raw = '<meta charset="iso-8859-1">TÖRN'.encode('iso-8859-1')
        self.assertIn('TÖRN', c.decode(raw))

    def test_country_text_flag_mismatch_held(self):
        raw = fixture().replace(b'</td></tr></table>', b'</td></tr></table>').replace(b'>CAN</td>', b'>USA</td>')
        r = c.parse_table(raw, cell(), 'entry', url())[0]
        self.assertIn('NATION_UNRESOLVED_REVIEW', r['row_review_flags'])


class LinkAndLocalTests(unittest.TestCase):
    def test_profile_and_names(self):
        self.assertEqual(c.link_tables(parse(), parse('result'))[0]['link_status'], 'PROFILE_AND_NAMES_AGREE_SOURCE_LINK')

    def test_entry_only_not_called_withdrawn(self):
        self.assertEqual(c.link_tables(parse(), [])[0]['link_status'], 'ENTRY_ONLY_NO_RESULT_EVIDENCE')

    def test_result_only_retained(self):
        self.assertEqual(c.link_tables([], parse('result'))[0]['link_status'], 'RESULT_ONLY_NO_ENTRY_EVIDENCE')

    def test_name_only_hold(self):
        r = parse('result', profile='isufs00002222')
        self.assertEqual(c.link_tables(parse(), r)[0]['link_status'], 'NAME_ONLY_LINK_REVIEW')

    def test_name_difference_same_profile_not_silently_corrected(self):
        r = parse('result', name='Alias PERSON / Bob PARTNER')
        self.assertEqual(c.link_tables(parse(), r)[0]['link_status'], 'PROFILE_NAME_DIFFERENCE_REVIEW')

    def test_many_to_one_refused(self):
        with self.assertRaisesRegex(ValueError, 'Many-to-one'):
            c.link_tables(parse() + parse(), parse('result'))

    def test_local_values_compared_without_reclassifying(self):
        local = [{'event_id': cell()['event_id'], 'person_a_as_published': 'PERSON Alice',
                  'person_b_as_published': 'PARTNER Bob', 'name_as_published': 'PERSON Alice / PARTNER Bob',
                  'record_id': 'legacy1', 'rank': '17', 'points': '47.57'}]
        r = c.compare_local(parse('result', state='FNR', free='', pos='17', score='47,57'), local)[0]
        self.assertEqual(r['points_check'], 'SAME_PUBLISHED_VALUE')
        self.assertEqual(r['official_points_meaning'], 'SHORT_SEGMENT_ONLY_NOT_TOTAL')
        self.assertEqual(local[0]['points'], '47.57')

    def test_local_missing_is_name_review_not_new_person(self):
        r = c.compare_local(parse('result'), [])[0]
        self.assertEqual(r['match_status'], 'NO_EXACT_LOCAL_PAIR_NAME_REVIEW')

    def test_numeric_disagreement_retained(self):
        local = [{'event_id': cell()['event_id'], 'person_a_as_published': 'Alice PERSON',
                  'person_b_as_published': 'Bob PARTNER', 'name_as_published': 'Alice PERSON / Bob PARTNER',
                  'record_id': 'x', 'rank': '2', 'points': '120'}]
        r = c.compare_local(parse('result'), local)[0]
        self.assertEqual(r['placement_check'], 'DIFFERENT_PUBLISHED_VALUE_REVIEW')
        self.assertEqual(r['points_check'], 'DIFFERENT_PUBLISHED_VALUE_REVIEW')


class OfflineRunTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.cache = self.root / 'cache/isu_core1718_entry_results_v1'
        self.cache.mkdir(parents=True)
        self.ext = self.root / 'output/frame/isu_wc2018_extension_v2'
        self.ext.mkdir(parents=True)
        self.inv = self.root / c.BASE
        self.inv.mkdir(parents=True)
        self.old = self.root / 'data/historic/v4/pair_events_v4.csv'
        self.old.parent.mkdir(parents=True)
        inventory, legacy, overlay = [], [], []
        for code in c.CODES:
            for disc in c.DISCIPLINES:
                cl = cell(code, disc)
                inv = dict(cl, index_status='INDEX_LINKS_VERIFIED', legacy_pair_event_rows='0' if code == 'wc2018' else '1',
                           wc2018_overlay_rows='1' if code == 'wc2018' else '0')
                for kind in ('entry', 'result'):
                    u = url(code, kind, disc)
                    inv['official_' + kind + '_url'] = u
                    raw = fixture(kind, japan=code in ('gpjpn2017', 'gpf1718'), disc=disc)
                    key = hashlib.sha256(u.encode()).hexdigest()
                    (self.cache / (key + '.html')).write_bytes(raw)
                    (self.cache / (key + '.json')).write_text(json.dumps({'requested_url': u, 'effective_url': u,
                                                                        'raw_sha256': hashlib.sha256(raw).hexdigest()}))
                inventory.append(inv)
                if code != 'wc2018':
                    legacy.append({'event_id': cl['event_id'], 'person_a_name': 'Alice PERSON', 'person_b_name': 'Bob PARTNER',
                                   'rank': '1', 'score_as_reported': '123.45', 'pair_event_id': cl['event_id'] + '|old'})
                else:
                    overlay.append({'event_id': cl['event_id'], 'person_a_as_published': 'Alice PERSON', 'person_b_as_published': 'Bob PARTNER',
                                    'final_placement': '1', 'points_as_published': '123.45', 'extension_event_id': cl['event_id'] + '|new'})
        c.write_csv(self.old, legacy, tuple(legacy[0]))
        op = self.ext / 'wc2018_resolved_event_overlay_v2.csv'
        c.write_csv(op, overlay, tuple(overlay[0]))
        em = {'stage': 'wc2018_source_reviewed_extension_v2_NOT_FROZEN', 'event_key_collisions': 0,
              'input_sha256': {'data\\historic\\v4\\pair_events_v4.csv': c.sha(self.old)},
              'output_sha256': {op.name: c.sha(op)}}
        ep = self.ext / 'wc2018_extension_manifest_v2.json'
        ep.write_text(json.dumps(em))
        ip = self.inv / 'core1718_event_source_inventory_v1.csv'
        c.write_csv(ip, inventory, tuple(inventory[0]))
        im = {'stage': 'core1718_official_index_inventory_v1_NOT_FROZEN', 'index_pages_verified': 11, 'index_pages_failed': 0,
              'entry_result_urls_discovered': 44, 'output_sha256': {ip.name: c.sha(ip)},
              'input_sha256': {'output/frame/isu_wc2018_extension_v2/wc2018_extension_manifest_v2.json': c.sha(ep)}}
        (self.inv / 'core1718_source_inventory_manifest_v1.json').write_text(json.dumps(im))

    def run_audit(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return c.run(self.root, **kwargs)

    def test_all_44_offline_and_input_preservation(self):
        before = c.sha(self.old)
        m = self.run_audit( offline=True)
        self.assertEqual(m['pages_parsed'], 44)
        self.assertEqual(m['official_entry_rows'], 22)
        self.assertEqual(m['official_result_rows'], 22)
        self.assertEqual(m['cells_with_comparison_errors'], 0)
        self.assertEqual(m['local_published_points_difference_rows'], 0)
        self.assertEqual(c.sha(self.old), before)
        self.assertIsNone(m['all_entrant_coverage_fraction'])

    def test_output_refuses_overwrite(self):
        out = self.root / 'occupied'
        out.mkdir()
        with self.assertRaisesRegex(ValueError, 'Output exists'):
            self.run_audit( out=out, offline=True)

    def test_missing_page_unknown_not_zero(self):
        u = url(c.CODES[0], 'result', 'Ice Dance')
        key = hashlib.sha256(u.encode()).hexdigest()
        (self.cache / (key + '.html')).unlink()
        (self.cache / (key + '.json')).unlink()
        m = self.run_audit( offline=True)
        self.assertEqual(m['pages_parsed'], 43)
        self.assertEqual(m['source_status'], 'INCOMPLETE')
        self.assertEqual(m['cells_with_comparison_errors'], 1)
        cells = c.read_csv(self.root / 'output/frame/isu_core1718_entry_results_v1/core1718_cell_counts_v1.csv', ['event_id'])
        r = next(x for x in cells if x['event_id'] == cell(c.CODES[0], 'Ice Dance')['event_id'])
        self.assertEqual(r['official_result_rows'], '')
        self.assertEqual(r['result_minus_local_rows'], '')

    def test_cache_corruption_is_failure(self):
        u = url(c.CODES[0])
        key = hashlib.sha256(u.encode()).hexdigest()
        (self.cache / (key + '.html')).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'Cache hash'):
            c.cached_page(None, u, c.CODES[0], self.cache, True)

    def test_changed_inventory_rejected(self):
        p = self.inv / 'core1718_event_source_inventory_v1.csv'
        p.write_bytes(p.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Inventory hash'):
            self.run_audit( offline=True)

    def test_changed_legacy_rejected(self):
        self.old.write_bytes(self.old.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Legacy event source hash'):
            self.run_audit( offline=True)

    def test_external_redirect_not_fetched(self):
        sess, response = Mock(), Mock()
        response.status_code = 302
        response.headers = {'Location': 'https://evil.example/attack'}
        sess.get.return_value = response
        with self.assertRaisesRegex(ValueError, 'Unapproved source'):
            c.cached_page(sess, url(), 'gpcan2017', self.root / 'newcache')
        self.assertEqual(sess.get.call_count, 1)


if __name__ == '__main__':
    unittest.main()
