"""Offline structural tests for a publication-ready ISU cohort *candidate*."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_isu_ranked_cohort import build_cohort, read_csv


def csv_write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class RankedCohortTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.people = self.root / "people.csv"
        self.roster = self.root / "roster.csv"
        self.out = self.root / "out"
        self.p = [
            {"canonical_person_id": "a", "roster_names": "Alice ONE",
             "date_of_birth": "2000-01-01", "dob_status": "consistent"},
            {"canonical_person_id": "b", "roster_names": "Bob TWO",
             "date_of_birth": "1999-01-01", "dob_status": "consistent"},
            {"canonical_person_id": "c", "roster_names": "Cora THREE",
             "date_of_birth": "2001-01-01", "dob_status": "consistent"},
        ]
        def rr(pair, season, a, b):
            return {
                "canonical_pair_id": pair, "canonical_person_a_id": a,
                "canonical_person_b_id": b, "season": season, "level": "senior",
                "discipline": "Ice Dance", "rank": "3", "ranking_points": "70",
                "person_a_name": a, "person_b_name": b, "nation": "CAN",
                "source_url": "https://results.isu.org/example",
                "profile_url": "https://results.isu.org/bios/isufs00000001.htm"
            }
        self.r = [
            rr("pair1", "2024-25", "a", "b"),
            rr("pair1", "2025-26", "a", "b"),
            rr("pair2", "2025-26", "a", "c"),
        ]
        self.save()

    def save(self):
        csv_write(self.people, self.p)
        csv_write(self.roster, self.r)

    def test_deduplicates_seasons_but_preserves_rankings_and_multi_partner(self):
        orig = self.roster.read_bytes()
        result = build_cohort(self.people, self.roster, self.out)
        self.assertEqual(result["unique_athletes_with_dob"], 3)
        self.assertEqual(result["unique_ranked_pairs"], 2)
        self.assertEqual(result["ranking_pair_season_level_rows"], 3)
        self.assertEqual(result["people_in_multiple_pairs"], 1)
        self.assertEqual(result["max_number_of_pairs_per_person"], 2)
        self.assertEqual(result["people_seen_on_both_roster_sides"], 0)
        self.assertEqual(self.roster.read_bytes(), orig)
        pairs = read_csv(self.out / "isu_ranked_pairs_candidate_v1.csv")
        self.assertEqual(len(pairs), 2)
        self.assertEqual(next(r for r in pairs if r["canonical_pair_id"] == "pair1")[
            "distinct_ranking_seasons"], "2")
        season_rows = read_csv(self.out / "isu_ranked_pair_seasons_candidate_v1.csv")
        self.assertEqual(len(season_rows), 3)

    def test_missing_dob_rejected(self):
        self.p[0]["date_of_birth"] = ""
        self.p[0]["dob_status"] = "no_verified_bio"
        self.save()
        with self.assertRaisesRegex(ValueError, "Incomplete/conflicting DOB"):
            build_cohort(self.people, self.roster, self.out)

    def test_duplicate_pair_season_rejected(self):
        self.r.append(dict(self.r[0]))
        self.save()
        with self.assertRaisesRegex(ValueError, "Duplicate pair-season-level"):
            build_cohort(self.people, self.roster, self.out)

    def test_reused_pair_id_for_different_members_rejected(self):
        self.r[1]["canonical_person_b_id"] = "c"
        self.save()
        with self.assertRaisesRegex(ValueError, "different members"):
            build_cohort(self.people, self.roster, self.out)

    def test_unknown_person_and_source_absence_rejected(self):
        self.r[0]["canonical_person_b_id"] = "missing"
        self.save()
        with self.assertRaisesRegex(ValueError, "missing person"):
            build_cohort(self.people, self.roster, self.out)
        self.r[0]["canonical_person_b_id"] = "b"
        self.r[0]["source_url"] = ""
        self.save()
        with self.assertRaisesRegex(ValueError, "Missing ranking provenance"):
            build_cohort(self.people, self.roster, self.out)


if __name__ == "__main__":
    unittest.main()
