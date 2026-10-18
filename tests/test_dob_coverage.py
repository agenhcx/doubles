"""Offline tests for DOB-completeness summary; no network or external data."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from report_isu_dob_coverage import build_coverage


def save(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.people = self.base / "people.csv"
        self.roster = self.base / "roster.csv"
        self.out = self.base / "out"
        self.person_rows = [
            dict(canonical_person_id="a", roster_names="Alice ONE",
                 date_of_birth="2000-01-01", dob_status="consistent"),
            dict(canonical_person_id="b", roster_names="Bob TWO",
                 date_of_birth="", dob_status="no_verified_bio"),
            dict(canonical_person_id="c", roster_names="Cora THREE",
                 date_of_birth="2001-01-01", dob_status="consistent"),
            dict(canonical_person_id="d", roster_names="Dina FOUR",
                 date_of_birth="", dob_status="dob_conflict"),
        ]
        def ranked(pair, season, a, b):
            return dict(canonical_pair_id=pair, discipline="Ice Dance",
                        season=season, level="senior",
                        canonical_person_a_id=a, canonical_person_b_id=b,
                        person_a_name=a, person_b_name=b,
                        source_url="https://results.isu.org/ws/standings",
                        profile_url="")
        self.ranking = [
            ranked("pair1", "2024-25", "a", "c"),
            ranked("pair1", "2025-26", "a", "c"),
            ranked("pair2", "2025-26", "a", "b"),
            ranked("pair3", "2025-26", "b", "d"),
        ]
        self.save()

    def save(self):
        save(self.people, self.person_rows)
        save(self.roster, self.ranking)

    def test_counts_missing_people_pairs_and_seasons(self):
        original = self.roster.read_bytes()
        s = build_coverage(self.people, self.roster, self.out)
        self.assertEqual(s["canonical_people"], 4)
        self.assertEqual(s["people_with_consistent_dob"], 2)
        self.assertEqual(s["people_without_consistent_dob"], 2)
        self.assertEqual(s["people_with_dob_conflict"], 1)
        self.assertEqual(s["canonical_pairs"], 3)
        self.assertEqual([s["pairs_both_dob"], s["pairs_one_dob"],
                          s["pairs_no_dob"]], [1, 1, 1])
        self.assertEqual(s["ranking_rows_both_dob"], 2)
        self.assertEqual(self.roster.read_bytes(), original)
        with (self.out / "dob_missing_people.csv").open(encoding="utf-8-sig", newline="") as f:
            people = list(csv.DictReader(f))
        self.assertEqual({p["canonical_person_id"] for p in people}, {"b", "d"})
        with (self.out / "dob_coverage_by_season.csv").open(encoding="utf-8-sig", newline="") as f:
            cohort = list(csv.DictReader(f))
        self.assertEqual(len(cohort), 2)
        latest = next(r for r in cohort if r["season"] == "2025-26")
        self.assertEqual((latest["pairs_both_dob"],latest["pairs_one_dob"],
                          latest["pairs_no_dob"]), ("1","1","1"))

    def test_conflicting_canonical_pair_members_rejected(self):
        self.ranking.append(dict(self.ranking[0], canonical_person_b_id="d"))
        self.save()
        with self.assertRaisesRegex(ValueError, "inconsistent members"):
            build_coverage(self.people, self.roster, self.out)

    def test_invalid_consistent_dob_rejected(self):
        self.person_rows[0]["date_of_birth"] = ""
        self.save()
        with self.assertRaisesRegex(ValueError, "contradicts status"):
            build_coverage(self.people, self.roster, self.out)

    def test_unknown_canonical_person_rejected(self):
        self.ranking[0]["canonical_person_a_id"] = "unknown"
        self.save()
        with self.assertRaisesRegex(ValueError, "unknown person"):
            build_coverage(self.people, self.roster, self.out)


if __name__ == "__main__":
    unittest.main()
