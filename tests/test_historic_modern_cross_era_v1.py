"""Synthetic, offline tests for cross-era skater identity evidence QA."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_historic_modern_cross_era_v1 import cross_era, read


def write(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class CrossEraTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.hp, self.ht, self.m, self.bio, self.out = [root / n for n in
            ('people.csv', 'pairs.csv', 'modern.csv', 'bio.csv', 'out')]
        self.people = [
            {'projected_person_id': 'a', 'original_historic_person_ids': 'a',
             'historic_names': 'Madison HUBBELL', 'date_of_birth': '1991-02-24'},
            {'projected_person_id': 'b', 'original_historic_person_ids': 'b',
             'historic_names': 'Zachary DONOHUE', 'date_of_birth': '1991-01-08'},
            {'projected_person_id': 'c', 'original_historic_person_ids': 'c',
             'historic_names': 'Other SKATER', 'date_of_birth': '1996-09-01'},
        ]
        self.pairs = [
            {'discipline': 'Ice Dance', 'projected_person_a_id': 'a',
             'projected_person_b_id': 'b', 'original_pair_ids': 'p1; p2'},
            {'discipline': 'Ice Dance', 'projected_person_a_id': 'c',
             'projected_person_b_id': 'b', 'original_pair_ids': 'p3'},
        ]
        def season(a, name, pid):
            return {'pair_id': pid, 'discipline': 'Ice Dance',
                    'person_a_id': a, 'person_b_id': 'b',
                    'person_a_name': name, 'person_b_name': 'Zachary DONOHUE',
                    'season': '2018-19',
                    'profile_url': 'https://results.isu.org/bios/isufs00013466.htm'}
        self.modern = [season('a', 'Madison HUBBELL', 'mp1'),
                       season('alt_a', 'Madison HUBBEL', 'mp2')]
        def birth(pid, dob, profile='isufs00013466'):
            return {'profile_id': profile,
                    'profile_url': f'https://results.isu.org/bios/{profile}.htm',
                    'person_id': pid, 'date_of_birth': dob,
                    'status': 'exact_name_match', 'name_match_method': 'exact'}
        self.bios = [birth('a', '1991-02-24'),
                     birth('alt_a', '1991-02-24')]
        self.save()

    def save(self):
        write(self.hp, self.people)
        write(self.ht, self.pairs)
        write(self.m, self.modern)
        write(self.bio, self.bios)

    def audit(self):
        return cross_era(self.hp, self.ht, self.m, self.bio, self.out)

    def test_exact_pair_and_fuzzy_same_dob_not_auto_merged(self):
        initial = self.m.read_bytes()
        stats = self.audit()
        self.assertEqual(stats['cross_era_full_pair_name_bridges'], 1)
        self.assertEqual(stats['historic_modern_person_candidate_edges'], 3)
        self.assertEqual(stats['historic_slots_without_cross_era_lead'], 1)
        self.assertEqual(self.m.read_bytes(), initial)
        review = read(self.out / 'historic_modern_identity_review_v1.csv', ('identity_review_status',))
        self.assertTrue(any(r['identity_review_status'] == 'DOB_AGREES_AND_SAME_PAIR_REVIEW' for r in review))
        self.assertTrue(any(r['identity_review_status'] == 'DOB_AGREES_IDENTITY_REVIEW' and r['modern_provisional_id'] == 'alt_a' for r in review))
        self.assertTrue(all(r['ambiguity_status'] == 'HISTORIC_TO_MULTIPLE_MODERN_IDS' or r['historic_projected_id'] == 'b' for r in review))

    def test_conflicting_modern_dob_is_held(self):
        self.bios.append({'profile_id': 'isufs00022222',
                          'profile_url': 'https://results.isu.org/bios/isufs00022222.htm',
                          'person_id': 'a', 'date_of_birth': '1991-02-25',
                          'status': 'exact_name_match', 'name_match_method': 'exact'})
        self.save()
        stats = self.audit()
        self.assertEqual(stats['modern_bio_conflict_ids'], 1)
        review = read(self.out / 'historic_modern_identity_review_v1.csv', ('identity_review_status',))
        self.assertEqual(next(r['identity_review_status'] for r in review if r['modern_provisional_id'] == 'a'),
                         'MODERN_BIO_DOB_CONFLICT_HOLD')

    def test_exact_provisional_id_with_dob_disagreement_is_held(self):
        self.bios[0]['date_of_birth'] = '1991-02-25'
        self.save()
        self.audit()
        review = read(self.out / 'historic_modern_identity_review_v1.csv', ('identity_review_status',))
        self.assertEqual(next(r['identity_review_status'] for r in review if r['modern_provisional_id'] == 'a'),
                         'CROSS_ERA_DOB_DISAGREEMENT_HOLD')

    def test_optional_bio_file_preserves_just_name_leads(self):
        self.bio.unlink()
        stats = self.audit()
        self.assertFalse(stats['modern_bio_file_present'])
        self.assertEqual(stats['cross_era_full_pair_name_bridges'], 1)
        self.assertTrue(any(k.endswith('DOB_MISSING_REVIEW') for k in stats['review_status_counts']))

    def test_wrong_historic_link_rejected(self):
        self.pairs[0]['projected_person_b_id'] = 'unknown'
        self.save()
        with self.assertRaisesRegex(ValueError, 'invalid projected people'):
            self.audit()


if __name__ == '__main__':
    unittest.main()
