"""No-network QA for pending historic shared-partner identity source matrices."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_historic_pending_alias_evidence import make_queue
from audit_isu_identities import read_csv


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class HistoricPendingEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.candidates = base / "candidates.csv"
        self.people = base / "people.csv"
        self.pairs = base / "pairs.csv"
        self.priority = base / "priority.csv"
        self.seed = base / "seed.csv"
        self.out = base / "out"
        self.cands = [dict(
            discipline="Ice Dance", audit_person_a_id="a",
            audit_person_b_id="b", historic_person_a_id="a",
            historic_person_b_id="b", historic_name_a="Alisa ONE",
            historic_name_b="Alice ONE", shared_dob="2000-01-01",
            shared_partner_ids="z", shared_partner_names="Zack ZERO",
            historic_pair_ids_a="pair_old", historic_pair_ids_b="pair_new",
            identity_review_status="candidate_same_partner_same_dob_not_merged",
        )]
        self.people_rows = [
            dict(audit_person_id=p, original_historic_person_id=p,
                 date_of_birth_primary_candidate="2000-01-01",
                 dob_coverage_status="official_source_linked",
                 source_urls="https://www.isuresults.com/bios/isufs00010001.htm")
            for p in ("a", "b")
        ]
        self.pair_rows = [
            dict(pair_id="pair_old", discipline="Ice Dance",
                 person_a_id="a", person_b_id="z"),
            dict(pair_id="pair_new", discipline="Ice Dance",
                 person_a_id="b", person_b_id="z"),
        ]
        self.priority_rows = [dict(
            historic_person_id="a", date_of_birth="2000-01-01",
            source_url="https://www.isuresults.com/bios/isufs00010001.htm",
            official_observed_name="Alisa ONE"
        )]
        self.seed_rows = [dict(
            historic_person_id="other", date_of_birth="1999-01-01",
            source_url="https://www.isuresults.com/bios/isufs00010002.htm",
            source_observed_name="Different PERSON"
        )]
        self.save()

    def save(self):
        for path, rows in (
            (self.candidates, self.cands), (self.people, self.people_rows),
            (self.pairs, self.pair_rows), (self.priority, self.priority_rows),
            (self.seed, self.seed_rows)
        ):
            save(path, rows)

    def run_audit(self):
        return make_queue(
            self.candidates, self.people, self.pairs,
            self.priority, self.seed, self.out
        )

    def test_curated_link_one_side_is_review_only(self):
        raw = self.candidates.read_bytes()
        result = self.run_audit()
        self.assertEqual(result["remaining_alias_groups"], 1)
        self.assertEqual(result["already_reviewed_alias_groups"], 0)
        self.assertEqual(result["curated_source_tiers"],
                         {"one_id_has_curated_source": 1})
        self.assertEqual(result["unreviewed_distinct_audit_ids"], 2)
        rows = read_csv(self.out / "historic_pending_alias_official_evidence_v1.csv")
        self.assertEqual(len(rows), 1)
        self.assertIn("isufs00010001", rows[0]["primary_curated_source_a"])
        self.assertEqual(rows[0]["primary_curated_source_b"], "")
        self.assertEqual(rows[0]["review_status"],
                         "NOT_APPROVED_REQUIRES_IDENTITY_SOURCE_REVIEW")
        self.assertEqual(self.candidates.read_bytes(), raw)

    def test_reviewed_pairs_are_excluded_but_never_mutate_source(self):
        self.cands.append(dict(self.cands[0],
                               audit_person_a_id="different",
                               audit_person_b_id="other",
                               identity_review_status="source_reviewed_reversible_merge"))
        self.save()
        result = self.run_audit()
        self.assertEqual(result["already_reviewed_alias_groups"], 1)
        self.assertEqual(result["remaining_alias_groups"], 1)

    def test_wrong_shared_partner_is_rejected(self):
        self.cands[0]["shared_partner_ids"] = "nonexistent"
        self.save()
        with self.assertRaisesRegex(ValueError, "does not share claimed"):
            self.run_audit()

    def test_unverified_dob_status_or_inconsistent_date_rejected(self):
        self.people_rows[1]["dob_coverage_status"] = "secondary_only_review"
        self.save()
        with self.assertRaisesRegex(ValueError, "lacks matching official"):
            self.run_audit()
        self.people_rows[1]["dob_coverage_status"] = "official_source_linked"
        self.people_rows[1]["date_of_birth_primary_candidate"] = "2001-01-01"
        self.save()
        with self.assertRaisesRegex(ValueError, "lacks matching official"):
            self.run_audit()

    def test_fake_approved_domain_in_curated_source_rejected(self):
        self.priority_rows[0]["source_url"] = (
            "https://www.isuresults.com.malicious.example/bios/isufs00010001.htm"
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "Curated DOB source is malformed"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
