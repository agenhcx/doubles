"""Offline regression tests for source-reviewed historic shared-partner DOB aliases."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_historic_shared_partner_aliases import audit
from audit_isu_identities import read_csv


def save(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


class SharedPartnerAliasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.people = root / "people.csv"
        self.pairs = root / "pairs.csv"
        self.rules = root / "rules.csv"
        self.out = root / "out"

        def person(aid, orig, name, dob, disc):
            return {
                "audit_person_id": aid,
                "original_historic_person_id": orig,
                "historic_name": name,
                "disciplines": disc,
                "date_of_birth_primary_candidate": dob,
                "dob_coverage_status": "official_source_linked",
            }
        self.people_rows = [
            person("a1", "a1", "Alisa ONE", "2000-01-01", "Ice Dance"),
            person("a2", "a2", "Alice ONE", "2000-01-01", "Ice Dance"),
            person("a3", "a3", "Random THREE", "2000-01-01", "Ice Dance"),
            person("b", "b", "Bob TWO", "1999-02-02", "Ice Dance"),
            person("split_dance", "hom", "Arina DUP", "1989-12-18", "Ice Dance"),
            person("split_pair", "hom", "Arina DUP", "2002-06-27", "Pair Skating"),
            person("sam", "sam", "Sam PARTNER", "2001-09-09", "Pair Skating"),
        ]
        def pair(pid, discipline, a, b, an, bn):
            return {
                "pair_id": pid, "discipline": discipline,
                "person_a_id": a, "person_b_id": b,
                "person_a_name": an, "person_b_name": bn,
                "first_season": "2013-2014",
                "observed_seasons": "2013-2014",
                "identified_event_count": "2",
            }
        self.pair_rows = [
            pair("old", "Ice Dance", "a1", "b", "Alisa ONE", "Bob TWO"),
            pair("new", "Ice Dance", "a2", "b", "Alice ONE", "Bob TWO"),
            pair("coincidence", "Ice Dance", "a3", "b", "Random THREE", "Bob TWO"),
            pair("hom_dance", "Ice Dance", "hom", "b", "Arina DUP", "Bob TWO"),
            pair("hom_pair", "Pair Skating", "hom", "sam", "Arina DUP", "Sam PARTNER"),
        ]
        self.rule_rows = [dict(
            canonical_person_id="a1", alternate_person_id="a2",
            expected_dob="2000-01-01", discipline="Ice Dance",
            shared_partner_person_id="b", canonical_pair_id="old",
            alternate_pair_id="new", official_profile_id="isufs00001001",
            profile_side="1",
            official_source_url="https://www.isuresults.com/bios/isufs00001001.htm",
            corroborating_source_url="https://results.isu.org/results/ec2008/SEG005.HTM",
            evidence_status="source_reviewed_same_person",
            identity_note="Matched source name change and same partner",
        )]
        self.save()

    def save(self):
        save(self.people, self.people_rows)
        save(self.pairs, self.pair_rows)
        save(self.rules, self.rule_rows)

    def perform(self):
        return audit(self.people, self.pairs, self.rules, self.out)

    def test_reversible_projection_and_unreviewed_same_dob_no_auto_merge(self):
        before = self.pairs.read_bytes()
        result = self.perform()
        self.assertEqual(result["input_audited_person_slots"], 7)
        self.assertEqual(result["input_original_pair_ids"], 5)
        self.assertEqual(result["possible_same_partner_same_official_dob_alias_groups"], 3)
        self.assertEqual(result["source_reviewed_alias_groups"], 1)
        self.assertEqual(result["additional_alias_groups_for_review"], 2)
        self.assertEqual(result["source_reviewed_reversible_merges_applied_to_preview_only"], 1)
        self.assertEqual(result["projected_person_identity_slots"], 6)
        self.assertEqual(result["projected_unique_pair_groups"], 4)
        self.assertEqual(result["pair_groups_with_multiple_old_pair_ids"], 1)
        self.assertEqual(self.pairs.read_bytes(), before)
        candidate = read_csv(self.out / "historic_shared_partner_same_dob_candidates_v1.csv")
        self.assertEqual(len(candidate), 3)
        self.assertEqual(candidate[0]["identity_review_status"],
                         "source_reviewed_reversible_merge")
        self.assertEqual(len([x for x in candidate
                              if x["identity_review_status"] ==
                              "candidate_same_partner_same_dob_not_merged"]), 2)
        preview = read_csv(self.out / "historic_reviewed_pair_groups_preview_v1.csv")
        merged = [r for r in preview if r["original_pair_rows"] == "2"]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["original_pair_ids"], "new; old")
        self.assertEqual(merged[0]["event_count_aggregation_status"],
                         "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP")
        persons = read_csv(self.out / "historic_reviewed_person_id_preview_v1.csv")
        self.assertTrue(any(r["projected_person_id"] == "split_dance"
                            for r in persons))
        self.assertTrue(any(r["projected_person_id"] == "split_pair"
                            for r in persons))

    def test_wrong_reviewed_dob_rejected_instead_of_merging(self):
        self.rule_rows[0]["expected_dob"] = "2000-01-02"
        self.save()
        with self.assertRaisesRegex(ValueError, "DOB disagrees"):
            self.perform()

    def test_wrong_shared_partner_cannot_authorize_merge(self):
        self.rule_rows[0]["shared_partner_person_id"] = "sam"
        self.save()
        with self.assertRaisesRegex(ValueError, "does not share exact historic partner"):
            self.perform()

    def test_impostor_and_wrong_profile_side_cannot_authorize(self):
        self.rule_rows[0]["official_source_url"] = (
            "https://www.isuresults.com.evil.test/bios/isufs00001001.htm"
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "valid official ISU biography"):
            self.perform()
        self.rule_rows[0]["official_source_url"] = (
            "https://www.isuresults.com/bios/isufs00001001.htm"
        )
        self.rule_rows[0]["profile_side"] = "2"
        self.save()
        with self.assertRaisesRegex(ValueError, "official side differs"):
            self.perform()

    def test_ambiguous_homonym_in_same_discipline_is_rejected(self):
        self.people_rows[5]["disciplines"] = "Ice Dance"
        self.save()
        with self.assertRaisesRegex(ValueError, "ambiguous audited ID"):
            self.perform()

    def test_official_reviewed_merge_rejects_secondary_only_dob(self):
        self.people_rows[0]["dob_coverage_status"] = "secondary_only_review"
        self.save()
        with self.assertRaisesRegex(ValueError, "Non-official or invalid DOB"):
            self.perform()

    def test_unchanged_person_without_official_dob_cannot_be_called_complete(self):
        self.people_rows[3]["dob_coverage_status"] = "dob_not_found"
        self.people_rows[3]["date_of_birth_primary_candidate"] = ""
        self.save()
        with self.assertRaisesRegex(ValueError, "missing or conflicting official DOBs"):
            self.perform()

    def test_new_four_reviewed_links_are_source_specific_not_similarity_merges(self):
        actual = read_csv(ROOT /
            "data/adjudications/isu_historic_shared_partner_id_merges_v2.csv")
        added = actual[4:]
        self.assertEqual(len(added), 4)
        expected = {
            ("person_003a7fd7f01ee", "person_688a8dc761563", "1994-12-15"),
            ("person_7e8f44ec75fa7", "person_e70285027598e", "1975-09-09"),
            ("person_9ab326510e11c", "person_a34cc3563255b", "1991-11-05"),
            ("person_2431ac0d4737d", "person_6cbe40b096dfc", "1991-06-17")
        }
        self.assertEqual({
            (r["canonical_person_id"], r["alternate_person_id"], r["expected_dob"])
            for r in added
        }, expected)
        for r in added:
            self.assertTrue(r["official_source_url"].startswith("https://"))
            self.assertTrue(r["corroborating_source_url"].startswith("https://"))
            self.assertIn("source_reviewed_same_person", r["evidence_status"])
            self.assertTrue(len(r["identity_note"]) > 70)

    def test_real_eight_reviewed_links_match_original_partner_pairs(self):
        root = ROOT
        rules = read_csv(root /
            "data/adjudications/isu_historic_shared_partner_id_merges_v2.csv")
        self.assertEqual(len(rules), 8)
        all_pairs = {r["pair_id"]: r for r in read_csv(
            root / "data/historic/v4/couples_v4.csv"
        )}
        seen = set()
        for rule in rules:
            self.assertNotIn(rule["alternate_person_id"], seen)
            seen.add(rule["alternate_person_id"])
            self.assertTrue(rule["identity_note"])
            self.assertEqual(rule["evidence_status"], "source_reviewed_same_person")
            for member, pair_id in (
                (rule["canonical_person_id"], rule["canonical_pair_id"]),
                (rule["alternate_person_id"], rule["alternate_pair_id"])
            ):
                self.assertIn(pair_id, all_pairs)
                pair = all_pairs[pair_id]
                self.assertEqual(pair["discipline"], rule["discipline"])
                names = {pair["person_a_id"], pair["person_b_id"]}
                self.assertIn(member, names)
                self.assertIn(rule["shared_partner_person_id"], names)


if __name__ == "__main__":
    unittest.main()
