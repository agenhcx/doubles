"""Offline synthetic regression of Milan 2018 event-first ISU entries/results."""
from __future__ import annotations
import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_isu_wc2018_entries_v1 import (
    parse_list, check_expected, link_entries_results, verify_gap_manifest,
    profile_href, decode_html, UntrustedPage, run,
)


def html_fixture(disc, kind, n, complete=None, *, change=False):
    title = 'Ice Dance' if disc == 'Ice Dance' else 'Pairs'
    prof_base = 10000 if disc == 'Ice Dance' else 20000
    rows = []
    if kind == 'entry':
        for i in range(1, n+1):
            name = f'First{i} PERSON / Second{i} PERSON'
            prof = f'isufs{prof_base+i:08d}'
            rows.append(f'<tr><td>{i}</td><td><a href="https://www.isuresults.com/bios/{prof}.htm">{name}</a></td><td><img src="flags/USA.gif" alt="USA"></td></tr>')
    else:
        complete = complete if complete is not None else n
        for i in range(1, n+1):
            if i == complete + 1:
                rows.append('<tr><th colspan="5">Final not Reached</th></tr>')
            prof = f'isufs{prof_base+i:08d}'
            name = f'First{i} PERSON / Second{i} PERSON'
            if change and i == 1:
                name = 'Alternate PERSON / Other PERSON'
            score = ('190.26' if i <= complete else '61,48')
            rows.append(f'<tr><td>{i}</td><td><a href="https://www.isuresults.com/bios/{prof}.htm">{name}</a></td><td>USA</td><td>{score}</td><td>{i}</td></tr>')
    return f'<html><meta charset="utf-8"><h1>ISU World Figure Skating Championships 2018 - {title}</h1><h2>{"Entries" if kind == "entry" else "Result"}</h2><table>{"".join(rows)}</table></html>'


def url(disc, kind):
    code = '004' if disc == 'Ice Dance' else '003'
    return f'https://results.isu.org/results/season1718/wc2018/CAT{code}{"EN" if kind == "entry" else "RS"}.HTM'


def parse_fixture(disc, kind, n, complete=None, **kw):
    h = html_fixture(disc, kind, n, complete, **kw)
    return parse_list(h, discipline=disc, kind=kind, source_uri=url(disc, kind), raw_sha=hashlib.sha256(h.encode()).hexdigest())


class Milan2018OfficialSourceTests(unittest.TestCase):
    def test_published_entries_and_final_not_reached_remain_separate(self):
        entries = parse_fixture('Pair Skating', 'entry', 28)
        results = parse_fixture('Pair Skating', 'result', 28, 16)
        check_expected(entries, n=28, kind='entry', disc='Pair Skating')
        check_expected(results, n=28, kind='result', disc='Pair Skating')
        self.assertEqual(len(entries), 28)
        self.assertEqual(sum(r['result_status'] == 'FINAL_NOT_REACHED' for r in results), 12)
        self.assertEqual(results[16]['total_points_if_final'], '')
        self.assertEqual(results[16]['short_segment_points_if_fnr'], '61.48')
        self.assertEqual(results[0]['total_points_if_final'], '190.26')
        self.assertEqual(entries[0]['entry_data_status'], 'OFFICIAL_ENTRIES_NOT_INFERRED_START')

    def test_two_event_disciplines_all_59_rows_joined_by_profile(self):
        entries = parse_fixture('Ice Dance', 'entry', 31) + parse_fixture('Pair Skating', 'entry', 28)
        results = parse_fixture('Ice Dance', 'result', 31, 20) + parse_fixture('Pair Skating', 'result', 28, 16)
        check_expected(results[:31], n=31, kind='result', disc='Ice Dance')
        linked, extra = link_entries_results(entries, results)
        self.assertEqual(len(linked), 59)
        self.assertEqual(len(extra), 0)
        self.assertTrue(all(x['entry_result_link_status'] == 'PROFILE_MATCH_BOTH_OFFICIAL_PAGES' for x in linked))
        self.assertEqual(sum(x['result_status'] == 'FINAL_NOT_REACHED' for x in linked), 23)

    def test_profile_same_different_published_name_held_for_review(self):
        entries = parse_fixture('Ice Dance', 'entry', 2)
        results = parse_fixture('Ice Dance', 'result', 2, 1, change=True)
        matched, _ = link_entries_results(entries, results)
        self.assertEqual(matched[0]['entry_result_link_status'], 'PROFILE_MATCH_PUBLISHED_NAME_DIFF_REVIEW')

    def test_mismatched_result_and_entry_profile_held_not_silently_linked(self):
        entries = parse_fixture('Ice Dance', 'entry', 2)
        results = parse_fixture('Ice Dance', 'result', 2, 1)
        results[0]['isu_profile_id'] = 'isufs00099999'
        linked, extras = link_entries_results(entries, results)
        self.assertEqual(linked[0]['entry_result_link_status'], 'NAME_ONLY_PROFILE_MISMATCH_HOLD')
        self.assertEqual(len(extras), 0)

    def test_wrong_source_uri_and_duplicate_names_rejected(self):
        with self.assertRaisesRegex(UntrustedPage, 'Unapproved fixed pilot source'):
            parse_list(html_fixture('Ice Dance', 'entry', 2), discipline='Ice Dance', kind='entry', source_uri='https://example.com/bios', raw_sha='a')
        h = html_fixture('Ice Dance', 'entry', 2)
        h = h.replace('First2 PERSON / Second2 PERSON', 'First1 PERSON / Second1 PERSON')
        with self.assertRaisesRegex(UntrustedPage, 'Duplicated published couple'):
            parse_list(h, discipline='Ice Dance', kind='entry', source_uri=url('Ice Dance', 'entry'), raw_sha='a')

    def test_lossless_legacy_isu_html_encoding(self):
        raw = '<meta charset="iso-8859-1">Cecilia TÖRN'.encode('iso-8859-1')
        self.assertIn('TÖRN', decode_html(raw))
        with self.assertRaisesRegex(UntrustedPage, 'Unapproved ISU biography'):
            profile_href('https://www.isuresults.com.evil.test/bios/isufs00098765.htm', url('Ice Dance','entry'))

    def test_fixed_two_gap_source_urls_are_validated(self):
        rows = []
        for d, n in [('Ice Dance', 31), ('Pair Skating', 28)]:
            rows.append(dict(discipline=d, season='2017-2018', event_code='wc2018', official_published_entry_pairs=str(n), official_entry_url=url(d,'entry')))
        self.assertEqual(len(verify_gap_manifest(rows)), 2)
        rows[0]['official_published_entry_pairs'] = '32'
        with self.assertRaisesRegex(ValueError, 'expected count'):
            verify_gap_manifest(rows)

    def test_offline_cache_full_pilot_and_original_sources_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td);cache=root/'cache';cache.mkdir();out=root/'out';gaps=root/'gaps.csv'
            rows = []
            for d, n, complete in [('Ice Dance',31,20),('Pair Skating',28,16)]:
                rows.append(dict(discipline=d, season='2017-2018',event_code='wc2018',official_published_entry_pairs=str(n),official_entry_url=url(d,'entry')))
                for kind in ('entry','result'):
                    name = f'wc2018_{"dance" if d=="Ice Dance" else "pairs"}_{kind}.html'
                    (cache/name).write_bytes(html_fixture(d,kind,n,complete).encode('utf-8'))
            with gaps.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            before=gaps.read_bytes()
            report=run(gaps_path=gaps,cache_dir=cache,output_dir=out,offline=True)
            self.assertEqual(report['source_status'],'SOURCE_PAGES_VALIDATED')
            self.assertEqual(report['pages_validated'],4)
            self.assertEqual(report['official_entry_records'],59)
            self.assertEqual(report['official_result_records'],59)
            self.assertEqual(report['joined_entry_result_records'],59)
            self.assertEqual(report['results_without_entry'],0)
            self.assertEqual(gaps.read_bytes(),before)
            self.assertEqual(report['result_category_counts']['Ice Dance|FINAL_NOT_REACHED'],11)
            self.assertEqual(report['result_category_counts']['Pair Skating|FINAL_NOT_REACHED'],12)

    def test_offline_missing_page_is_incomplete_and_no_fabricated_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);cache=root/'cache';cache.mkdir();out=root/'out';gap=root/'gap.csv'
            rows=[dict(discipline=d, season='2017-2018', event_code='wc2018', official_entry_url=url(d,'entry'), official_published_entry_pairs=str(n)) for d,n in [('Ice Dance',31),('Pair Skating',28)]]
            with gap.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            summary=run(gaps_path=gap,cache_dir=cache,output_dir=out,offline=True)
            self.assertEqual(summary['pages_validated'],0)
            self.assertEqual(summary['page_failures'],4)
            self.assertEqual(summary['official_entry_records'],0)
            self.assertEqual(summary['source_status'],'SOURCE_PAGES_INCOMPLETE_DO_NOT_USE_AS_COHORT')


if __name__ == '__main__':unittest.main()
