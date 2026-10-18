"""Offline regression tests for historical ISU birthdate discovery queue."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from audit_historic_dob_gap import historic_candidates
from audit_isu_identities import read_csv


def save(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricGapTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.root = root
        self.history = root / "historical_people.csv"
        self.old_pairs = root / "historic_pairs.csv"
        self.people = root / "ranked_people.csv"
        self.roster = root / "ranked_roster.csv"
        self.out = root / "out"
        self.hp = [
            dict(person_id="h_a", name_display="Alice ONE",
                 name_variants="ONE Alice", disciplines="Ice Dance",
                 represented_nations="CAN", distinct_identified_competitions="4"),
            dict(person_id="h_b", name_display="Bob TWO",
                 name_variants="Bob TWO", disciplines="Ice Dance",
                 represented_nations="CAN", distinct_identified_competitions="3"),
            dict(person_id="h_c", name_display="Cora THREE",
                 name_variants="Cora THREE", disciplines="Ice Dance",
                 represented_nations="CAN", distinct_identified_competitions="1"),
            dict(person_id="h_d", name_display="D. SOMETHING",
                 name_variants="D. SOMETHING", disciplines="Ice Dance",
                 represented_nations="CAN", distinct_identified_competitions="1"),
            dict(person_id="h_e", name_display="Evelyn FIVE",
                 name_variants="Evelyn FIVE", disciplines="Ice Dance",
                 represented_nations="CAN", distinct_identified_competitions="2"),
        ]
        def pair(pairid,a,b):
            return dict(pair_id=pairid, discipline="Ice Dance",person_a_id=a,person_b_id=b)
        self.oldp = [pair("hpair1","h_a","h_b"),pair("hpair2","h_c","h_b"),
                     pair("hpair3","h_e","h_d")]
        self.rp = [
            dict(canonical_person_id="a", roster_names="Alice ONE",
                 date_of_birth="2000-01-01",dob_status="consistent",
                 biography_profile_ids="isufs00000001",supplemental_source_url=""),
            dict(canonical_person_id="b", roster_names="Bob TWO",
                 date_of_birth="1999-02-02",dob_status="consistent",
                 biography_profile_ids="isufs00000001",supplemental_source_url=""),
            dict(canonical_person_id="e", roster_names="Evelyn FIVE",
                 date_of_birth="2000-02-03",dob_status="consistent",
                 biography_profile_ids="isufs00000002",supplemental_source_url=""),
        ]
        self.rr = [
            dict(canonical_person_a_id="a",canonical_person_b_id="b",discipline="Ice Dance"),
            dict(canonical_person_a_id="e",canonical_person_b_id="b",discipline="Ice Dance")
        ]
        self.save()

    def save(self):
        save(self.history,self.hp)
        save(self.old_pairs,self.oldp)
        save(self.people,self.rp)
        save(self.roster,self.rr)

    def audit(self):
        return historic_candidates(self.history,self.old_pairs,self.people,self.roster,self.out)

    def test_pair_correlated_cross_era_and_undiscovered_old_name(self):
        before = self.history.read_bytes()
        result = self.audit()
        self.assertEqual(result["historical_people"],5)
        records={x["historic_person_id"]:x for x in
                 read_csv(self.out/"historic_identity_dob_candidates.csv")}
        self.assertEqual(records["h_a"]["match_status"],"exact_name_same_pair")
        self.assertEqual(records["h_a"]["ranked_dob_candidate"],"2000-01-01")
        self.assertEqual(records["h_b"]["match_status"],"exact_name_same_pair")
        self.assertEqual(records["h_c"]["match_status"],"partner_alias_suggestion")
        self.assertIn("a",records["h_c"]["possible_partner_alias_ids"])
        self.assertEqual(records["h_d"]["match_status"],"abbreviated_or_incomplete_name")
        self.assertEqual(records["h_e"]["match_status"],"exact_name_only")
        self.assertEqual(result["same_pair_correlated_dob_candidates"],2)
        self.assertEqual(self.history.read_bytes(),before)
        self.assertEqual(len(read_csv(self.out/"historic_dob_followup_queue.csv")),3)

    def test_ambiguous_name_is_not_assigned(self):
        self.rp.append(dict(canonical_person_id="a2", roster_names="Alice ONE",
                            date_of_birth="2001-01-01",dob_status="consistent",
                            biography_profile_ids="",supplemental_source_url=""))
        self.save()
        result=self.audit()
        rows={x["historic_person_id"]:x for x in
              read_csv(self.out/"historic_identity_dob_candidates.csv")}
        self.assertEqual(rows["h_a"]["match_status"],"ambiguous_full_name")
        self.assertFalse(rows["h_a"]["ranked_canonical_id"])
        self.assertEqual(result["same_pair_correlated_dob_candidates"],0)

    def test_primary_dob_seed_keeps_sources_separate_and_detects_conflicts(self):
        seed = self.root / "primary_seed.csv"
        row = dict(
            historic_person_id="h_e", historic_name="Evelyn FIVE",
            date_of_birth="2000-02-03",
            source_url="https://results.isu.org/bios/isufs00000002.htm",
            evidence_status="manually_checked_source",
        )
        save(seed, [row])
        result = historic_candidates(self.history, self.old_pairs, self.people,
                                     self.roster, self.out, seed)
        self.assertEqual(result["primary_source_seed_people"], 1)
        self.assertEqual(result["primary_source_seed_conflicts"], 0)
        self.assertEqual(result["followup_people"], 2)
        pilot = read_csv(self.out / "historic_official_primary_pilot.csv")
        self.assertEqual(pilot[0]["primary_seed_consistency"], "agrees_with_ranked_dob")
        # Conflicting evidence is not used to remove anyone from follow-up.
        row["date_of_birth"] = "2000-02-04"
        save(seed, [row])
        result = historic_candidates(self.history, self.old_pairs, self.people,
                                     self.roster, self.out, seed)
        self.assertEqual(result["primary_source_seed_conflicts"], 1)
        self.assertEqual(result["followup_people"], 3)

    def test_untrusted_historic_seed_is_rejected(self):
        seed = self.root / "primary_seed.csv"
        save(seed, [dict(
            historic_person_id="h_e", historic_name="Evelyn FIVE",
            date_of_birth="2000-02-03",
            source_url="https://example.com/wiki/Evelyn",
            evidence_status="manually_checked_source",
        )])
        with self.assertRaisesRegex(ValueError, "not an allowed ISU host"):
            historic_candidates(self.history, self.old_pairs, self.people,
                                self.roster, self.out, seed)

    def test_checked_source_rows_match_public_historic_identity_ids(self):
        official = read_csv(Path(__file__).resolve().parent.parent /
                            "data/adjudications/isu_historic_primary_dob_seed_v1.csv")
        historic = {r["person_id"]: r["name_display"] for r in
                    read_csv(Path(__file__).resolve().parent.parent /
                             "data/historic/v4/athletes_v4.csv")}
        self.assertEqual(len(official), 7)
        for record in official:
            self.assertIn(record["historic_person_id"], historic)
            self.assertEqual(record["historic_name"], historic[record["historic_person_id"]])

    def test_incomplete_ranked_dates_rejected(self):
        self.rp[0]["date_of_birth"]=""
        self.save()
        with self.assertRaisesRegex(ValueError,"Incomplete ranked DOB"):
            self.audit()

    def test_wrong_historical_pair_person_rejected(self):
        self.oldp[0]["person_a_id"]="missing"
        self.save()
        with self.assertRaisesRegex(ValueError,"Historical pair"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
