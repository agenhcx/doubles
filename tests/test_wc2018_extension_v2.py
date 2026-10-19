"""Synthetic fixtures, not real biographies or performance evidence."""
import copy
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_wc2018_extension_v2 import (SOURCES, project, audit, sha, write, record_sha)


def fixture():
    with (ROOT / SOURCES['rules']).open(encoding='utf-8-sig', newline='') as f:
        rules = list(csv.DictReader(f))
    obs, official, old, groups, people, events = [], [], [], [], {}, []
    def person(ident, name, dob='1995-01-01'):
        people[ident] = dict(projected_person_id=ident, historic_names=name,
                            original_historic_person_ids=ident, date_of_birth=dob)
    def oldpair(pid, d, a, b, an, bn):
        old.append(dict(pair_id=pid, discipline=d, person_a_id=a, person_b_id=b,
                        person_a_name=an, person_b_name=bn))
        groups.append(dict(discipline=d, projected_person_a_id=a, projected_person_b_id=b, original_pair_ids=pid))
        events.append(dict(pair_event_id='old_event_' + pid, pair_id=pid,
                           discipline=d, event_id='2016-2017|example|' + d,
                           rank='1', score_as_reported='99.50'))
    for dec in rules:
        for s in ('a', 'b'):
            if s == 'a' and dec['action'] == 'NEW_PAIR_NEW_MEMBER_A':
                continue
            person(dec['historic_person_' + s + '_id'], dec['historic_name_' + s], dec['dob_' + s])
    smart = rules[1]
    oldpair(smart['reference_original_pair_id'], smart['discipline'], smart['historic_person_a_id'],
            smart['historic_person_b_id'], smart['historic_name_a'], smart['historic_name_b'])
    # Give every reused old member a previous source-pair lineage.
    for k, (d, member, name) in enumerate([
        ('Ice Dance', rules[0]['historic_person_a_id'], rules[0]['historic_name_a']),
        ('Ice Dance', rules[0]['historic_person_b_id'], rules[0]['historic_name_b']),
        ('Pair Skating', rules[2]['historic_person_b_id'], rules[2]['historic_name_b'])]):
        partner = 'old_partner_' + str(k)
        person(partner, 'Earlier Partner ' + str(k))
        oldpair('prior_pair_' + str(k), d, member, partner, name, 'Earlier Partner ' + str(k))
    for disc, n, finals in [('Ice Dance', 31, 20), ('Pair Skating', 28, 16)]:
        for i in range(1, n + 1):
            dec = rules[0] if disc == 'Ice Dance' and i == 1 else rules[1] if disc == 'Ice Dance' and i == 2 else rules[2] if disc == 'Pair Skating' and i == 28 else None
            prefix = ('d' if disc == 'Ice Dance' else 'p') + str(i)
            if dec:
                prof, an, bn, pid = dec['isu_profile_id'], dec['event_name_a'], dec['event_name_b'], ''
            else:
                prof = 'isufs' + str((10000 if disc == 'Ice Dance' else 20000) + i)
                an, bn, pid = 'First ' + prefix, 'Second ' + prefix, 'old_' + prefix
                a, b = 'person_a_' + prefix, 'person_b_' + prefix
                person(a, an); person(b, bn)
                oldpair(pid, disc, a, b, an, bn)
            code = '004' if disc == 'Ice Dance' else '003'
            r = dict(event_id='2017-2018|wc2018|' + disc, discipline=disc,
                     name_as_published=an+' / '+bn, person_a_as_published=an,
                     person_b_as_published=bn, nation_as_published='TEST', isu_profile_id=prof,
                     entry_source_url=f'https://results.isu.org/results/season1718/wc2018/CAT{code}EN.HTM',
                     result_source_url=f'https://results.isu.org/results/season1718/wc2018/CAT{code}RS.HTM',
                     result_status='FINAL_COMPLETE' if i <= finals else 'FINAL_NOT_REACHED',
                     final_placement=str(i), points_as_published='150.01' if i <= finals else '45,67',
                     points_interpretation='TOTAL_SCORE' if i <= finals else 'SHORT_SEGMENT_ONLY_NOT_TOTAL',
                     historic_original_pair_ids=pid)
            src = dict(r, result_points_as_published=r['points_as_published'],
                       result_points_interpretation=r['points_interpretation'],
                       entry_result_link_status='PROFILE_MATCH_BOTH_OFFICIAL_PAGES')
            obs.append(r); official.append(src)
    return [obs, official, old, groups, list(people.values()), events, rules]


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.args = fixture()

    def test_expected_59_57_2_1_counts_and_no_input_mutation(self):
        before = copy.deepcopy(self.args)
        rows, new_people, pairs, union, report = project(*self.args)
        self.assertEqual(self.args, before)
        self.assertEqual((len(rows), len(new_people), len(pairs)), (59, 1, 2))
        self.assertEqual(report['inherited_exact_name_pair_candidates'], 56)
        self.assertEqual(report['reviewed_existing_pair_name_variants'], 1)
        self.assertEqual(len(union), len(self.args[5]) + 59)
        self.assertEqual(report['projected_registry_pair_groups'], len(self.args[3]) + 2)
        self.assertEqual(report['projected_registry_person_slots'], len(self.args[4]) + 1)
        self.assertEqual(sum(bool(r['total_score']) for r in rows), 36)
        self.assertEqual(sum(bool(r['short_segment_score']) for r in rows), 23)

    def test_fnr_score_is_not_a_total(self):
        rows = project(*self.args)[0]
        kash = next(r for r in rows if r['isu_profile_id'] == 'isufs00105349')
        self.assertEqual(kash['total_score'], '')
        self.assertEqual(kash['short_segment_score'], '45.67')
        self.assertEqual(kash['points_as_published'], '45,67')
        self.assertEqual(rows[-1]['final_placement'], '28')

    def test_bad_reviewed_dob_fails(self):
        self.args[6][0]['dob_a'] = '1994-06-09'
        with self.assertRaisesRegex(ValueError, 'DOB/ID disagreement'): project(*self.args)

    def test_variant_requires_the_exact_old_pair(self):
        self.args[6][1]['reference_original_pair_id'] = 'prior_pair_0'
        with self.assertRaisesRegex(ValueError, 'existing original pair'): project(*self.args)

    def test_new_person_exact_name_collision_held(self):
        self.args[4].append(dict(projected_person_id='other_kash', historic_names='Elizaveta KASHITSYNA',
                                original_historic_person_ids='other_kash', date_of_birth='2001-06-15'))
        with self.assertRaisesRegex(ValueError, 'exact historic name'): project(*self.args)

    def test_wrong_official_member_never_silently_repaired(self):
        self.args[0][0]['person_b_as_published'] = 'Wrong Partner'
        with self.assertRaisesRegex(ValueError, 'official source'): project(*self.args)

    def test_hostile_ledger_url_rejected(self):
        self.args[6][0]['official_bio_url'] = 'https://results.isu.org.evil.test/bios/isufs00103181.htm'
        with self.assertRaisesRegex(ValueError, 'Rule source URL'): project(*self.args)

    def test_unreviewed_rule_rejected(self):
        self.args[6][0]['evidence_status'] = 'CANDIDATE'
        with self.assertRaisesRegex(ValueError, 'Unreviewed rule'): project(*self.args)

    def test_fnr_relabelled_in_both_sources_rejected(self):
        self.args[0][-1]['points_interpretation'] = 'TOTAL_SCORE'
        self.args[1][-1]['result_points_interpretation'] = 'TOTAL_SCORE'
        with self.assertRaisesRegex(ValueError, 'FNR score'): project(*self.args)

    def test_already_present_event_not_appended_twice(self):
        old = next(r for r in self.args[5] if r['pair_id'] == self.args[6][1]['reference_original_pair_id'])
        old['event_id'] = '2017-2018|wc2018|Ice Dance'
        with self.assertRaisesRegex(ValueError, 'already present'): project(*self.args)

    def test_legacy_record_identity_collision_rejected(self):
        self.args[5].append(dict(self.args[5][0]))
        with self.assertRaisesRegex(ValueError, 'Legacy event identity'): project(*self.args)

    def test_incomplete_59_frame_rejected(self):
        self.args[0].pop()
        with self.assertRaisesRegex(ValueError, 'all 59'): project(*self.args)

    def prepare_files(self, root):
        mapping = dict(zip(('observations', 'official', 'original_pairs', 'pairs', 'people', 'events', 'rules'), self.args))
        mapping['pending'] = [dict(event_id=r['event_id'], isu_profile_id=r['isu_profile_id'])
                              for r in self.args[0] if not r['historic_original_pair_ids']]
        for key, rows in mapping.items():
            p = root / SOURCES[key]; p.parent.mkdir(parents=True, exist_ok=True)
            write(p, rows, list(rows[0]))
        meta = dict(stage='wc2018_identity_event_extension_crosswalk_preview_not_frozen',
                    official_entry_result_records=59,
                    source_reviewed_historic_person_slots=len(self.args[4]),
                    source_reviewed_historic_pair_groups=len(self.args[3]),
                    original_historic_pair_ids=len(self.args[2]),
                    input_sha256={str(SOURCES[k]).replace('/', '\\'): sha(root / SOURCES[k])
                                  for k in ('official', 'original_pairs', 'pairs', 'people')})
        p = root / SOURCES['bridge']; p.write_text(json.dumps(meta), encoding='utf-8')
        coll = dict(event_collision_groups=0, original_pair_event_records=len(self.args[5]),
                    inputs_sha256={str(SOURCES[k]).replace('/', '\\'): sha(root / SOURCES[k]) for k in ('pairs', 'events')})
        p = root / SOURCES['collision']; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(coll), encoding='utf-8')

    def test_end_to_end_hashes_union_provenance_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.prepare_files(root)
            before = {k: sha(root / p) for k, p in SOURCES.items()}
            report = audit(root)
            out = root/'output/frame/isu_wc2018_extension_v2'
            self.assertEqual(report['new_event_rows'], 59)
            for filename, digest in report['output_sha256'].items():
                self.assertEqual(sha(out / filename), digest)
            self.assertEqual({k: sha(root/p) for k,p in SOURCES.items()}, before)
            with self.assertRaisesRegex(ValueError, 'Output already exists'): audit(root)
            again = audit(root, root/'replay')
            self.assertEqual(again['output_sha256'], report['output_sha256'])

    def test_stale_input_fails_before_writing_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.prepare_files(root)
            p = root/SOURCES['people']; p.write_bytes(p.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError, 'Bridge source hash mismatch'): audit(root)
            self.assertFalse((root/'output/frame/isu_wc2018_extension_v2').exists())


if __name__ == '__main__':
    unittest.main()
