"""Offline regression tests for ISU profile-scoped identity and DOB auditing."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_isu_identities import audit, read_csv


def write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class IsuIdentityAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.roster = self.base / "roster.csv"
        self.births = self.base / "births.csv"
        self.aliases = self.base / "aliases.csv"
        self.splits = self.base / "splits.csv"
        self.out = self.base / "output"

        def ranked(prof, season, pair, a, aname, b, bname):
            return dict(
                season=season, discipline="Ice Dance",
                pair_id=pair, person_a_id=a, person_a_name=aname,
                person_b_id=b, person_b_name=bname,
                profile_url="https://results.isu.org/bios/" + prof + ".htm"
            )

        self.ranking_rows = [
            ranked("isufs00000001", "2018-19", "pair_old",
                   "a1", "Alice ONE", "b1", "Bob TWO"),
            ranked("isufs00000001", "2019-20", "pair_later",
                   "a2", "Alicia ONE", "b1", "Bob TWO"),
            ranked("isufs00000002", "2020-21", "pair_other",
                   "a1", "Alice ONE", "c1", "Cora THREE")
        ]
        self.bio_rows = [
            dict(profile_id="isufs00000001", side_on_profile="1",
                 profile_url="https://results.isu.org/bios/isufs00000001.htm",
                 observed_name="Alicia ONE", roster_name="Alicia ONE",
                 person_id="a2", status="exact_name_match",
                 date_of_birth="2000-01-01", place_of_birth_raw="City A"),
            dict(profile_id="isufs00000001", side_on_profile="2",
                 profile_url="https://results.isu.org/bios/isufs00000001.htm",
                 observed_name="Robert TWO", roster_name="",
                 person_id="", status="needs_review",
                 date_of_birth="1999-03-04", place_of_birth_raw="City B"),
            dict(profile_id="isufs00000002", side_on_profile="1",
                 profile_url="https://results.isu.org/bios/isufs00000002.htm",
                 observed_name="Alice ONE", roster_name="Alice ONE",
                 person_id="a1", status="exact_name_match",
                 date_of_birth="2000-01-02", place_of_birth_raw="City A"),
            dict(profile_id="isufs00000002", side_on_profile="2",
                 profile_url="https://results.isu.org/bios/isufs00000002.htm",
                 observed_name="Cora THREE", roster_name="Cora THREE",
                 person_id="c1", status="exact_name_match",
                 date_of_birth="2001-01-01", place_of_birth_raw="")
        ]
        self.alias_rows = [
            dict(profile_id="isufs00000001", side_on_profile="2",
                 observed_name="Robert TWO", roster_name="Bob TWO",
                 roster_person_id="b1", expected_dob="1999-03-04",
                 evidence_status="source_corroborated")
        ]
        self.split_rows = [
            dict(profile_id="isufs00000001", side_on_profile="1",
                 canonical_person_id="a1", alternate_person_id="a2",
                 canonical_name="Alice ONE", alternate_name="Alicia ONE",
                 evidence_status="source_corroborated")
        ]
        self.save()

    def save(self):
        write(self.roster, list(self.ranking_rows[0]), self.ranking_rows)
        write(self.births, list(self.bio_rows[0]), self.bio_rows)
        write(self.aliases, list(self.alias_rows[0]), self.alias_rows)
        write(self.splits, list(self.split_rows[0]), self.split_rows)

    def run_audit(self):
        return audit(self.roster, self.births, self.aliases, self.splits, self.out)

    def test_split_alias_and_dob_conflict_without_master_mutation(self):
        before = self.roster.read_bytes()
        result = self.run_audit()
        self.assertEqual(result["raw_person_ids"], 4)
        self.assertEqual(result["canonical_person_ids"], 3)
        self.assertEqual(result["canonical_pair_ids"], 2)
        self.assertEqual(result["bios_linked_rows"], 4)
        self.assertEqual(result["bios_unresolved_rows"], 0)
        self.assertEqual(result["unique_people_with_dob_conflict"], 1)
        self.assertEqual(result["unique_people_with_consistent_dob"], 2)
        self.assertEqual(self.roster.read_bytes(), before)
        people = {r["canonical_person_id"]: r for r in
                  read_csv(self.out / "identity_canonical_people.csv")}
        self.assertEqual(people["a1"]["dob_status"], "dob_conflict")
        self.assertEqual(people["a1"]["date_of_birth"], "")
        self.assertEqual(people["b1"]["date_of_birth"], "1999-03-04")
        self.assertEqual(people["c1"]["birth_places_raw"], "")
        roster_rows = read_csv(self.out / "identity_canonical_season_roster.csv")
        self.assertEqual(roster_rows[0]["canonical_pair_id"],
                         roster_rows[1]["canonical_pair_id"])
        self.assertEqual(roster_rows[1]["canonical_person_a_id"], "a1")

    def test_wrong_bio_alias_date_is_not_linked(self):
        self.bio_rows[1]["date_of_birth"] = "1999-03-05"
        self.save()
        result = self.run_audit()
        self.assertEqual(result["bios_unresolved_rows"], 1)
        unresolved = read_csv(self.out / "identity_unresolved.csv")
        self.assertEqual(unresolved[0]["link_status"], "manual_alias_evidence_mismatch")

    def test_wrong_profile_side_mapping_is_rejected(self):
        self.split_rows[0]["alternate_person_id"] = "b1"
        self.save()
        with self.assertRaisesRegex(ValueError, "Split IDs not on"):
            self.run_audit()

    def test_unknown_roster_person_id_cannot_gain_dob(self):
        self.bio_rows[0]["person_id"] = "intruder"
        self.save()
        result = self.run_audit()
        self.assertEqual(result["bios_unresolved_rows"], 1)
        unresolved = read_csv(self.out / "identity_unresolved.csv")
        self.assertEqual(unresolved[0]["link_status"], "person_profile_side_mismatch")


if __name__ == "__main__":
    unittest.main()
