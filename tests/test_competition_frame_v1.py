"""Regression tests: evidence-frame audit must not invent event coverage."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_competition_frame_v1 import audit, family, read_csv


def save(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class FrameAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        self.ev, self.ses, self.ranks, self.col, self.dob, self.gaps, self.out = (
            d / p for p in ('events.csv','seasons.csv','ranking.csv','collision.json',
                            'dob.json','gaps.csv','out'))
        self.events = [dict(event_id=f'2017-2018|{code}|{disc}',
                            season='2017-2018', event=code, discipline=disc,
                            different_couples_seen='5',
                            source_urls='https://github.com/example/source.csv')
                       for code in ('gpfra2017','owg2018') for disc in
                       ('Ice Dance','Pair Skating')]
        self.seasons = [dict(season='2017-2018', discipline=d,
                             different_competitions='2', pair_event_results='10')
                        for d in ('Ice Dance','Pair Skating')]
        self.ranking = [dict(season='2020-21', discipline=d, level='senior',
                             pair_id=f'p_{d}', profile_url='',
                             source_url=f'https://results.isu.org/{d}')
                        for d in ('Ice Dance','Pair Skating')]
        self.gap_rows = [dict(
            season='2017-2018', event_code='wc2018', discipline=d,
            source_event_name='Milan Worlds',
            official_entry_url=('https://results.isu.org/results/season1718/wc2018/' +
                                ('CAT004EN.HTM' if d=='Ice Dance' else 'CAT003EN.HTM')),
            official_event_index_url='https://results.isu.org/results/season1718/wc2018/index.htm',
            official_published_entry_pairs=('31' if d=='Ice Dance' else '28'),
            source_status='official_entry_page_checked',
            review_note='Official event entry list independently checked in advance, not automatically ingested.'
        ) for d in ('Ice Dance','Pair Skating')]
        self.save()

    def save(self):
        save(self.ev,self.events)
        save(self.ses,self.seasons)
        save(self.ranks,self.ranking)
        save(self.gaps,self.gap_rows)
        self.col.write_text(json.dumps(dict(event_collision_groups=0,
                   original_pair_event_records=20,
                   projected_distinct_pair_event_groups=20)),encoding='utf-8')
        self.dob.write_text(json.dumps(dict(v6_remaining_missing_dob_slots=0,
                    v6_dob_conflict_slots=0, v6_covered_canonical_name_id_slots=4)),encoding='utf-8')

    def run_audit(self):
        return audit(self.ev,self.ses,self.ranks,self.col,self.dob,self.gaps,self.out)

    def test_gap_and_output_no_source_modification(self):
        before = self.ev.read_bytes()
        result = self.run_audit()
        self.assertEqual(result['historic_event_by_discipline_instances'],4)
        self.assertEqual(result['historic_pair_event_records'],20)
        self.assertEqual(result['manual_official_missing_event_discipline_units'],2)
        self.assertEqual(result['manual_official_missing_event_pair_entries'],59)
        self.assertEqual(result['modern_2020_21_ranking_rows'],2)
        self.assertEqual(result['historical_by_event_family']['Grand Prix Series'],1)
        self.assertEqual(result['historical_by_event_family']['Olympic Winter Games'],1)
        self.assertEqual(self.ev.read_bytes(),before)
        resultrows=read_csv(self.out/'official_event_gap_review_v1.csv', ('gap_priority',))
        self.assertTrue(all(x['gap_priority'] ==
            'OFFICIAL_EVENT_ENTRIES_MISSING_FROM_HISTORIC_V4' for x in resultrows))

    def test_gp_france_not_grand_prix_final(self):
        self.assertEqual(family('gpfra2017'),'Grand Prix Series')
        self.assertEqual(family('gpf1718'),'Grand Prix Final')
        self.assertEqual(family('wc2018'),'World Championships')
        self.assertEqual(family('unknown'),'UNCLASSIFIED_EVENT_CODE')

    def test_tampered_historic_count_rejected(self):
        self.seasons[0]['pair_event_results']='12'
        self.save()
        with self.assertRaisesRegex(ValueError,'Historical season summary disagrees'):
            self.run_audit()

    def test_rank_row_duplicate_rejected(self):
        self.ranking.append(dict(self.ranking[0]))
        self.save()
        with self.assertRaisesRegex(ValueError,'Repeated same-pair source ranking row'):
            self.run_audit()

    def test_gap_url_not_arbitrary(self):
        self.gap_rows[0]['official_entry_url']='https://results.isu.org.evil.test/results/season1718/wc2018/CAT004EN.HTM'
        self.save()
        with self.assertRaisesRegex(ValueError,'Unverified ISU event seed'):
            self.run_audit()

    def test_identity_collision_hold(self):
        self.save()
        self.col.write_text(json.dumps(dict(event_collision_groups=1,
                    original_pair_event_records=20,
                    projected_distinct_pair_event_groups=19)),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'outstanding event collisions'):
            self.run_audit()


if __name__=='__main__':
    unittest.main()
