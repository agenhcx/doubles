"""Offline synthetic tests for source-reviewed cross-era ISU bio DOB rescue."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_cross_era_bio_rescues_v1 import audit, read_csv


def save(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class CrossEraBioRescueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.review = root / "review.csv"
        self.roster = root / "roster.csv"
        self.ledger = root / "ledger.csv"
        self.manifest = root / "manifest.json"
        self.out = root / "result"
        self.reviews = [{
            "discipline": "Ice Dance", "historic_projected_id": "h1",
            "modern_provisional_id": "m1", "historic_dob": "1999-03-04",
            "modern_official_dob": "", "modern_bio_urls": "",
            "cross_era_same_pair": "YES",
            "evidence_flags": "SAME_NORMALIZED_PUBLISHED_NAME",
            "identity_review_status": "SAME_PAIR_MODERN_DOB_MISSING_REVIEW",
            "ambiguity_status": "HISTORIC_TO_MULTIPLE_MODERN_IDS",
        }]
        self.modern = [{
            "discipline": "Ice Dance", "person_a_id": "m1",
            "person_b_id": "p1", "person_a_name": "Alisa OLD",
            "person_b_name": "Partner YOUNG", "season": "2018-19",
            "profile_url": "https://results.isu.org/bios/isufs00011111.htm",
        }]
        self.sources = [{
            "discipline": "Ice Dance", "historic_projected_id": "h1",
            "modern_provisional_id": "m1", "modern_roster_name": "Alisa OLD",
            "modern_partner_name": "Partner YOUNG", "source_profile_side": "1",
            "expected_dob": "1999-03-04", "source_printed_name": "Alisa NEW",
            "official_dob_source_url": "https://results.isu.org/bios/isufs00011111.htm",
            "official_context_url": "",
            "source_review_note": "An official date-bearing pair biography shows a new surname and identical partner",
        }]
        self.save()

    def save(self):
        save(self.review, self.reviews)
        save(self.roster, self.modern)
        save(self.ledger, self.sources)
        m = {
            "historic_modern_person_candidate_edges": len(self.reviews),
            "inputs_sha256": {
                r"output\master\season_roster.csv": hashlib.sha256(
                    self.roster.read_bytes()).hexdigest(),
            },
        }
        self.manifest.write_text(json.dumps(m), encoding="utf-8")

    def run_audit(self):
        return audit(self.review, self.manifest, self.roster, self.ledger, self.out)

    def test_preserves_input_and_holds_ambiguous_person_after_date_rescue(self):
        original = self.review.read_bytes()
        result = self.run_audit()
        self.assertEqual(result["source_reviewed_dob_rescue_edges"], 1)
        self.assertEqual(result["remaining_modern_dob_missing_edges"], 0)
        self.assertEqual(result["cross_era_ambiguous_edges_still_held"], 1)
        self.assertEqual(self.review.read_bytes(), original)
        rows, _ = read_csv(self.out / "historic_modern_identity_source_augmented_v1.csv",
                           ("identity_review_status", "dob_evidence_origin"))
        self.assertEqual(rows[0]["modern_official_dob"], "1999-03-04")
        self.assertEqual(rows[0]["identity_review_status"],
                         "SOURCE_REVIEWED_DOB_AGREES_AND_SAME_PAIR_REVIEW")
        self.assertEqual(rows[0]["ambiguity_status"],
                         "HISTORIC_TO_MULTIPLE_MODERN_IDS")

    def test_mismatched_birthdate_rejected(self):
        self.sources[0]["expected_dob"] = "1999-03-05"
        self.save()
        with self.assertRaisesRegex(ValueError, "Curated DOB differs"):
            self.run_audit()

    def test_wrong_roster_member_role_and_partner_rejected(self):
        self.sources[0]["source_profile_side"] = "2"
        self.save()
        with self.assertRaisesRegex(ValueError, "Source-side/name/partner"):
            self.run_audit()
        self.sources[0]["source_profile_side"] = "1"
        self.sources[0]["modern_partner_name"] = "OTHER"
        self.save()
        with self.assertRaisesRegex(ValueError, "Source-side/name/partner"):
            self.run_audit()

    def test_malicious_url_rejected(self):
        self.sources[0]["official_dob_source_url"] = (
            "https://results.isu.org.evil.test/bios/isufs00011111.htm")
        self.save()
        with self.assertRaisesRegex(ValueError, "non-ISU official"):
            self.run_audit()

    def test_stale_modern_roster_does_not_permit_reuse_of_review(self):
        self.roster.write_bytes(self.roster.read_bytes() + b" \n")
        with self.assertRaisesRegex(ValueError, "roster SHA disagrees"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
