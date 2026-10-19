"""Regression checks for official Milan 2018 identity bridge and non-destructive event extension."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_wc2018_identity_bridge_v1 import audit, read, sha

def save(path,records,fields=None):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(records[0]),extrasaction='ignore')
        w.writeheader();w.writerows(records)


class Milan2018IdentityBridgeTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        d=Path(td.name)
        self.manifest=d/'manifest.json';self.inventory=d/'inventory.csv';self.events=d/'joined.csv'
        self.old=d/'old.csv';self.h_pairs=d/'h_pairs.csv';self.h_people=d/'h_people.csv'
        self.old_events=d/'old_events.csv';self.modern=d/'modern.csv';self.modern_people=d/'modern_people.csv';self.out=d/'out'
        self.source=dict(
            stage='official_isu_wc2018_entry_result_source_pilot_not_frozen',
            source_status='SOURCE_PAGES_VALIDATED',pages_validated=4,
            official_entry_records=59,official_result_records=59,
            joined_entry_result_records=59,results_without_entry=0,
            entry_result_link_status_counts={'PROFILE_MATCH_BOTH_OFFICIAL_PAGES':59},
        )
        self.rows=[];self.pages=[]
        for disc, code, count, finals in [
            ('Ice Dance','004',31,20),('Pair Skating','003',28,16)]:
            prefix='https://results.isu.org/results/season1718/wc2018/CAT'+code
            uentry=prefix+'EN.HTM';uresult=prefix+'RS.HTM'
            for kind,url in [('entry',uentry),('result',uresult)]:
                self.pages.append(dict(
                    discipline=disc,page_kind=kind,requested_url=url,
                    raw_sha256=(('abcd' if kind=='entry' else 'f012')*16),
                    rows_parsed=str(count),expected_rows=str(count),status='VALIDATED'))
            for i in range(1,count+1):
                profile=f'isufs{int(code)*100+i:08d}'
                name=f'First{i} Skater{code} / Second{i} Skater{code}'
                done=i<=finals
                self.rows.append(dict(
                    event_id='2017-2018|wc2018|'+disc,discipline=disc,
                    entry_ordinal=str(i),name_as_published=name,
                    person_a_as_published=f'First{i} Skater{code}',
                    person_b_as_published=f'Second{i} Skater{code}',
                    nation_as_published='USA',isu_profile_id=profile,
                    isu_profile_url=f'http://www.isuresults.com/bios/{profile}.htm',
                    entry_source_url=uentry,entry_source_sha256='abcd'*16,
                    result_source_url=uresult,final_placement=str(i),
                    result_status='FINAL_COMPLETE' if done else 'FINAL_NOT_REACHED',
                    result_points_as_published='180.40' if done else '48,23',
                    result_points_interpretation='TOTAL_SCORE' if done else 'SHORT_SEGMENT_ONLY_NOT_TOTAL',
                    result_profile_id=profile,result_nation_as_published='USA',
                    entry_result_link_status='PROFILE_MATCH_BOTH_OFFICIAL_PAGES',
                ))
        self.write_source()
        self.hist=[]
        for i,r in enumerate(self.rows[:56]):
            self.hist.append(dict(pair_id=f'h{i}',discipline=r['discipline'],person_a_id=f'person_{i}_a',person_b_id=f'person_{i}_b',person_a_name=r['person_a_as_published'],person_b_name=r['person_b_as_published']))
        for i in range(497):
            self.hist.append(dict(pair_id=f'x{i}',discipline='Ice Dance',person_a_id=f'x_person_{i}_a',person_b_id=f'x_person_{i}_b',person_a_name=f'Foo{i} Pseudo',person_b_name=f'Bar{i} Pseudo'))
        self.hgroup=[]
        for i in range(514):
            old=self.hist[i]
            orig=[old['pair_id']]
            if i<39:orig.append(self.hist[514+i]['pair_id'])
            self.hgroup.append(dict(discipline=old['discipline'],projected_person_a_id=f'P{(i*2)%865}',projected_person_b_id=f'P{(i*2+1)%865}',original_pair_ids='; '.join(orig)))
        self.hpeople=[dict(projected_person_id=f'P{i}',date_of_birth='1990-01-01') for i in range(865)]
        self.mod=[]
        for i in range(40):
            r=self.rows[i]
            self.mod.append(dict(pair_id=f'm{i}',discipline=r['discipline'],person_a_id=f'm{i}a',person_b_id=f'm{i}b',person_a_name=r['person_a_as_published'],person_b_name=r['person_b_as_published'],profile_url=r['isu_profile_url'],season='2018-19'))
        for i in range(1544):
            self.mod.append(dict(pair_id=f'mdummy{i}',discipline='Ice Dance',person_a_id=f'dummy{i}a',person_b_id=f'dummy{i}b',person_a_name=f'First{i} DUMMY',person_b_name=f'Second{i} DUMMY',profile_url='',season='2025-26'))
        self.mpeople=[dict(discipline=r['discipline'],original_modern_person_id=r['person_'+side+'_id'],canonical_modern_person_id=r['person_'+side+'_id']) for r in self.mod for side in ('a','b')]
        self.save_inputs()

    def write_source(self):
        save(self.inventory,self.pages)
        save(self.events,self.rows)
        self.source['page_inventory_sha256']=sha(self.inventory)
        self.manifest.write_text(json.dumps(self.source),encoding='utf-8')

    def save_inputs(self):
        save(self.old,self.hist)
        save(self.h_pairs,self.hgroup)
        save(self.h_people,self.hpeople)
        save(self.old_events,[dict(event_id='2016-2017|wc2017|Ice Dance')])
        save(self.modern,self.mod)
        save(self.modern_people,self.mpeople)

    def run_audit(self):
        return audit(self.events,self.manifest,self.inventory,self.old,self.h_pairs,self.h_people,self.old_events,self.modern,self.modern_people,self.out)

    def test_preserves_original_sources_and_writes_independent_59_event_preview(self):
        original=self.events.read_bytes();old=self.old.read_bytes();rank=self.modern.read_bytes()
        r=self.run_audit()
        self.assertEqual(r['official_entry_result_records'],59)
        self.assertEqual(r['historic_exact_two_name_pair_matches'],56)
        self.assertEqual(r['historic_new_pair_combination_review'],3)
        self.assertEqual(r['new_official_event_observations_preview'],59)
        self.assertEqual(r['original_event_observations_mutated'],0)
        self.assertEqual(self.events.read_bytes(),original)
        self.assertEqual(self.old.read_bytes(),old)
        self.assertEqual(self.modern.read_bytes(),rank)
        ext=read(self.out/'official_wc2018_new_event_observations_preview_v1.csv',('result_status',))
        self.assertEqual(len(ext),59)
        self.assertEqual(sum(x['result_status']=='FINAL_NOT_REACHED' for x in ext),23)
        self.assertEqual(sum(x['historic_pair_link_status']=='NO_EXACT_HISTORIC_PAIR_NEW_COMBINATION_REVIEW' for x in ext),3)
        self.assertTrue(all(x['historical_identity_merge_action']=='NONE_SOURCE_CROSSWALK_PREVIEW_ONLY' for x in ext))

    def test_incomplete_official_source_rejected(self):
        self.source['pages_validated']=2
        self.write_source()
        with self.assertRaisesRegex(ValueError,'incomplete'):
            self.run_audit()

    def test_stale_page_inventory_rejected(self):
        self.inventory.write_bytes(self.inventory.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'SHA disagrees'):
            self.run_audit()

    def test_wrong_short_segment_total_semantics_rejected(self):
        target=next(r for r in self.rows if r['result_status']=='FINAL_NOT_REACHED')
        target['result_points_interpretation']='TOTAL_SCORE'
        self.write_source()
        with self.assertRaisesRegex(ValueError,'short-program score'):
            self.run_audit()

    def test_previous_worlds_event_cannot_be_appended_twice(self):
        save(self.old_events,[dict(event_id='2017-2018|wc2018|Pair Skating')])
        with self.assertRaisesRegex(ValueError,'already present'):
            self.run_audit()

    def test_missing_one_historic_lineage_group_rejected(self):
        self.hgroup[0]['original_pair_ids']='fake_pair'
        self.save_inputs()
        with self.assertRaisesRegex(ValueError,'not uniquely represented'):
            self.run_audit()

if __name__=='__main__':unittest.main()
