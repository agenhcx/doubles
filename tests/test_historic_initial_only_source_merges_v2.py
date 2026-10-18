"""Tests for 6 source-reviewed initial-only couples and v2 identity projection."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_historic_initial_only_source_merges_v2 import audit, read

def save(p, rows):
    with Path(p).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricInitialSourceV2Tests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        self.v3people, self.v3pairs, self.candidates, self.candidatepairs, self.original, self.rules, self.out = (
            root / n for n in ("v3people.csv", "v3pairs.csv", "candidate.csv",
                               "candidatepairs.csv", "original.csv", "rules.csv", "out"))
        def person(pid, name, dob):
            return {
                "projected_person_id": pid, "audit_person_ids": pid,
                "original_historic_person_ids": pid, "historic_names": name,
                "date_of_birth": dob, "source_person_rows": "1",
                "status": "unchanged_audit_identity",
            }
        self.people = [
            person("sa", "SINITSINA V", "1995-04-29"),
            person("sb", "ZHIGANSHIN R", "1992-09-25"),
            person("fa", "Victoria SINITSINA", "1995-04-29"),
            person("fb", "Ruslan ZHIGANSHIN", "1992-09-25"),
        ]
        def group(pid, a, b, name):
            return {
                "discipline": "Ice Dance",
                "projected_person_a_id": a, "projected_person_b_id": b,
                "original_pair_ids": pid, "original_pair_rows": "1",
                "original_pair_names": name, "original_pair_seasons": "2013-2014",
                "pair_group_status": "unique_original_pair_id",
                "event_count_aggregation_status": "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP",
            }
        self.groups = [
            group("short", "sa", "sb", "SINITSINA V / ZHIGANSHIN R"),
            group("full", "fa", "fb", "Victoria SINITSINA / Ruslan ZHIGANSHIN"),
        ]
        self.oldpairs = [{
            "pair_id": pid, "discipline": "Ice Dance",
            "person_a_id": a, "person_b_id": b,
            "person_a_name": an, "person_b_name": bn,
        } for pid, a, b, an, bn in (
            ("short", "sa", "sb", "SINITSINA V", "ZHIGANSHIN R"),
            ("full", "fa", "fb", "Victoria SINITSINA", "Ruslan ZHIGANSHIN"),
        )]
        self.candidatesrows = [{
            "discipline": "Ice Dance", "abbreviated_pair_id": "short",
            "member_side": str(i), "abbreviated_person_id": alt,
            "abbreviated_name": an, "matched_full_person_id": full,
            "matched_full_name": fn, "abbreviated_official_dob": dob,
            "full_name_official_dob": dob, "original_full_pair_id": "full",
            "review_status": "OFFICIAL_DOB_AGREES_SAME_PAIR_STRUCTURE_REVIEW",
            "structural_match_status": "BOTH_PARTNERS_MATCH_HISTORIC_PAIR",
        } for i, alt, an, full, fn, dob in (
            (1, "sa", "SINITSINA V", "fa", "Victoria SINITSINA", "1995-04-29"),
            (2, "sb", "ZHIGANSHIN R", "fb", "Ruslan ZHIGANSHIN", "1992-09-25"),
        )]
        self.candidatepairrows = [{
            "discipline": "Ice Dance", "abbreviated_pair_id": "short",
            "original_full_pair_id": "full",
            "matching_abbreviated_member_count": "2",
            "dob_agree_both_sides": "YES",
            "status": "SOURCE_NAME_DOB_PAIR_CANDIDATE_NO_MERGE",
        }]
        self.ledger = [{
            "discipline": "Ice Dance", "abbreviated_pair_id": "short",
            "full_pair_id": "full",
            "abbreviated_person_a_id": "sa", "full_person_a_id": "fa",
            "expected_dob_a": "1995-04-29",
            "abbreviated_person_b_id": "sb", "full_person_b_id": "fb",
            "expected_dob_b": "1992-09-25",
            "official_profile_id": "isufs00011268",
            "official_profile_url": "https://results.isu.org/bios/isufs00011268.htm",
            "official_event_results_url": "https://results.isu.org/results/owg2014/CAT004RS.HTM",
            "evidence_status": "source_reviewed_same_couple_and_members",
            "source_observed_name_a": "Victoria SINITSINA",
            "source_observed_name_b": "Ruslan ZHIGANSHIN",
            "review_note": "Official ISU pair biography gives both full DOBs and 2014 Olympics result page lists abbreviated names",
        }]
        self.save()

    def save(self):
        for p, rows in (
            (self.v3people, self.people), (self.v3pairs, self.groups),
            (self.candidates, self.candidatesrows),
            (self.candidatepairs, self.candidatepairrows),
            (self.original, self.oldpairs), (self.rules, self.ledger)
        ):
            save(p, rows)

    def run_audit(self):
        return audit(self.v3people, self.v3pairs, self.candidates,
                     self.candidatepairs, self.original, self.rules, self.out)

    def test_projection_reversible_and_two_member_aliases(self):
        source_before = self.original.read_bytes()
        p_before = self.v3people.read_bytes()
        stats = self.run_audit()
        self.assertEqual(stats["input_v3_person_identity_slots"], 4)
        self.assertEqual(stats["projected_v2_identity_slots"], 2)
        self.assertEqual(stats["input_v3_pair_groups"], 2)
        self.assertEqual(stats["projected_v2_unique_pair_groups"], 1)
        self.assertEqual(stats["original_historic_pair_ids_preserved"], 2)
        self.assertEqual(self.original.read_bytes(), source_before)
        self.assertEqual(self.v3people.read_bytes(), p_before)
        people = read(self.out / "historic_reviewed_person_id_preview_v2.csv", ("projected_person_id",))
        self.assertTrue(any(r["projected_person_id"] == "fa" and
                            r["audit_person_ids"] == "fa; sa" for r in people))
        merged = read(self.out / "historic_reviewed_pair_groups_preview_v2.csv", ("original_pair_ids",))
        self.assertEqual(merged[0]["original_pair_rows"], "2")
        self.assertEqual(merged[0]["event_count_aggregation_status"],
                         "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP")

    def test_reject_wrong_official_dob(self):
        self.ledger[0]["expected_dob_b"] = "1992-09-24"
        self.save()
        with self.assertRaisesRegex(ValueError, "Candidate evidence conflicts"):
            self.run_audit()

    def test_reject_swapped_member_mapping(self):
        self.ledger[0]["abbreviated_person_a_id"] = "sb"
        self.save()
        with self.assertRaisesRegex(ValueError, "original member side"):
            self.run_audit()

    def test_reject_unreviewed_or_hostile_evidence(self):
        self.ledger[0]["evidence_status"] = "candidate_only"
        self.save()
        with self.assertRaisesRegex(ValueError, "not explicitly source-reviewed"):
            self.run_audit()
        self.ledger[0]["evidence_status"] = "source_reviewed_same_couple_and_members"
        self.ledger[0]["official_profile_url"] = (
            "https://results.isu.org.evil.test/bios/isufs00011268.htm")
        self.save()
        with self.assertRaisesRegex(ValueError, "valid source-specific ISU"):
            self.run_audit()

    def test_refuse_already_collapsed_historic_pair(self):
        self.groups[1]["original_pair_ids"] = "short"
        self.save()
        with self.assertRaisesRegex(ValueError, "Repeated or unknown original pair ID"):
            self.run_audit()

    def test_exactly_six_curated_couples_and_twelve_distinct_ids(self):
        rows = read(ROOT / "data/adjudications/isu_historic_initial_only_pair_merges_v1.csv",
                    ("evidence_status",))
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r["abbreviated_pair_id"] for r in rows}), 6)
        self.assertEqual(len({r["full_pair_id"] for r in rows}), 6)
        self.assertEqual(len({x for r in rows for x in (
            r["abbreviated_person_a_id"], r["abbreviated_person_b_id"])}), 12)
        self.assertTrue(all(r["evidence_status"] ==
                            "source_reviewed_same_couple_and_members" for r in rows))


if __name__ == "__main__":
    unittest.main()
