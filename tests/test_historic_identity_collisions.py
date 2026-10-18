"""Offline checks for historic name collisions, DOB validation, and audit safety."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_historic_identity_collisions import audit, read_csv


def save(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricHomonymAuditTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.candidates = root / "source.csv"
        self.pairs = root / "pairs.csv"
        self.rules = root / "reviewed.csv"
        self.output = root / "output"
        self.pair_rows = [
            dict(pair_id="oldpair", discipline="Pair Skating",
                 person_a_id="arina", person_b_id="sergei"),
            dict(pair_id="newpair", discipline="Ice Dance",
                 person_a_id="arina", person_b_id="maxim"),
        ]
        def observation(p, pair, who, side, dob, name):
            return dict(
                historic_person_id=who, profile_id=p,
                historic_pair_ids=pair, side_on_profile=str(side),
                historic_name=name, observed_name=name,
                date_of_birth=dob, parse_status="dob_explicitly_bound_to_expected_name",
                source_url="https://results.isu.org/bios/" + p + ".htm",
            )
        self.source_rows = [
            observation("isufs00008744", "oldpair", "arina", 1,
                        "1989-12-18", "Arina USHAKOVA"),
            observation("isufs00008744", "oldpair", "sergei", 2,
                        "1986-03-31", "Sergei KAREV"),
            observation("isufs00101140", "newpair", "arina", 1,
                        "2002-06-27", "Arina USHAKOVA"),
            observation("isufs00101140", "newpair", "maxim", 2,
                        "2000-09-27", "Maxim NEKRASOV"),
        ]
        self.rule_rows = [
            dict(historic_person_id="arina", profile_id="isufs00008744",
                 side_on_profile="1", audit_person_id="arina_1989",
                 discipline="Pair Skating", expected_name="Arina USHAKOVA",
                 expected_dob="1989-12-18",
                 official_source_url="https://www.isuresults.com/bios/isufs00008744.htm",
                 evidence_status="source_corroborated"),
            dict(historic_person_id="arina", profile_id="isufs00101140",
                 side_on_profile="1", audit_person_id="arina_2002",
                 discipline="Ice Dance", expected_name="Arina USHAKOVA",
                 expected_dob="2002-06-27",
                 official_source_url="https://www.isuresults.com/bios/isufs00101140.htm",
                 evidence_status="source_corroborated"),
        ]
        self.save_all()

    def save_all(self):
        save(self.candidates, self.source_rows)
        save(self.pairs, self.pair_rows)
        save(self.rules, self.rule_rows)

    def test_two_proven_same_name_athletes_do_not_create_false_dob_conflict(self):
        original = self.candidates.read_bytes()
        result = audit(self.candidates, self.pairs, self.rules, self.output)
        self.assertEqual(result["source_person_slots"], 4)
        self.assertEqual(result["source_orig_person_ids"], 3)
        self.assertEqual(result["source_audited_person_ids"], 4)
        self.assertEqual(result["official_homonym_split_original_ids"], 1)
        self.assertEqual(result["official_homonym_split_profiles"], 2)
        self.assertEqual(result["identities_with_source_conflicts"], 0)
        self.assertEqual(result["identities_with_agreeing_dobs"], 4)
        people = {r["audit_person_id"]: r for r in
                  read_csv(self.output / "historic_audited_people.csv")}
        self.assertEqual(people["arina_1989"]["date_of_birth_candidate"], "1989-12-18")
        self.assertEqual(people["arina_2002"]["date_of_birth_candidate"], "2002-06-27")
        self.assertEqual(self.candidates.read_bytes(), original)

    def test_punctuation_variant_stays_review_only(self):
        self.source_rows[3]["parse_status"] = "dob_bound_to_punctuation_variant_review"
        self.save_all()
        s = audit(self.candidates, self.pairs, self.rules, self.output)
        self.assertEqual(s["identities_needing_name_review"], 1)
        rows = {r["audit_person_id"]: r for r in
                read_csv(self.output / "historic_audited_people.csv")}
        self.assertEqual(rows["maxim"]["date_of_birth_candidate"], "")
        self.assertEqual(rows["maxim"]["source_dob_values"], "2000-09-27")
        self.assertEqual(s["review_source_rows"], 1)

    def test_unreviewed_homonym_date_cannot_be_promoted(self):
        self.source_rows[2]["date_of_birth"] = "2002-06-28"
        self.save_all()
        report = audit(self.candidates, self.pairs, self.rules, self.output)
        self.assertEqual(report["homonym_split_evidence_mismatches"], 1)
        self.assertEqual(report["identities_with_unresolved_split"], 1)
        records = read_csv(self.output / "historic_identity_review.csv")
        self.assertTrue(any(r["identity_status"] == "homonym_evidence_mismatch"
                            for r in records))

    def test_wrong_side_and_unknown_pair_rejected(self):
        self.source_rows[0]["side_on_profile"] = "2"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "Historic pair/profile identity mismatch"):
            audit(self.candidates, self.pairs, self.rules, self.output)
        self.source_rows[0]["side_on_profile"] = "1"
        self.source_rows[0]["historic_pair_ids"] = "other"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "Unknown historical pair"):
            audit(self.candidates, self.pairs, self.rules, self.output)

    def test_same_person_profile_disagreement_stays_unresolved(self):
        # A true same-identity DOB disagreement should never be split
        # automatically by name, discipline or DOB.
        self.pair_rows[1]["discipline"] = "Pair Skating"
        self.pair_rows[1]["person_b_id"] = "sergei"
        self.rule_rows[1]["discipline"] = "Pair Skating"
        self.source_rows[3]["historic_person_id"] = "sergei"
        self.source_rows[3]["historic_name"] = "Sergei KAREV"
        self.source_rows[3]["observed_name"] = "Sergei KAREV"
        self.save_all()
        report = audit(self.candidates, self.pairs, self.rules, self.output)
        self.assertEqual(report["identities_with_source_conflicts"], 1)
        people = {r["audit_person_id"]: r for r in
                  read_csv(self.output / "historic_audited_people.csv")}
        self.assertEqual(people["sergei"]["date_of_birth_candidate"], "")
        self.assertEqual(people["sergei"]["source_dob_values"], "1986-03-31; 2000-09-27")
        reviews = read_csv(self.output / "historic_identity_review.csv")
        self.assertEqual(len([r for r in reviews if r["audit_person_id"] == "sergei"]), 2)

    def test_real_profile_split_roster_ids_exist(self):
        root = ROOT
        hist = read_csv(root / "data/historic/v4/athletes_v4.csv")
        rules = read_csv(root / "data/adjudications/isu_historic_homonym_splits_v1.csv")
        self.assertEqual(len(rules), 2)
        rawids = {r["person_id"] for r in hist}
        self.assertEqual({r["historic_person_id"] for r in rules},
                         {"person_91415bb478168"})
        self.assertTrue(all(r["historic_person_id"] in rawids for r in rules))


if __name__ == "__main__":
    unittest.main()
