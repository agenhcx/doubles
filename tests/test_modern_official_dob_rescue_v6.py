"""Synthetic regression checks for v6 official modern DOB rescue projection."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_modern_official_dob_rescue_v6 import audit, read


def save(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class ModernDobSourceRescueV6Tests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        d = Path(td.name)
        (self.manifest, self.canonical, self.missing, self.roster,
         self.ledger, self.out) = [d / x for x in (
            "manifest.json", "canonical.csv", "missing.csv", "roster.csv",
            "ledger.csv", "out")]

        def person(id_, name, date_value, status):
            return dict(
                canonical_person_id=id_, original_modern_person_ids=id_,
                published_names=name, disciplines="Ice Dance",
                observed_seasons="2018-19", roster_rows="1",
                profile_ids="", accepted_dob=date_value, dob_status=status,
                official_dob_source_urls="", dob_evidence_kinds="",
                accepted_source_record_count="0" if not date_value else "1",
                cross_discipline_status="SINGLE_DISCIPLINE",
                review_priority="MISSING_BIOGRAPHY_URL_IN_RANKING"
                if not date_value else "NONE",
            )
        self.people = [
            person("missing_a", "Alisa NAME", "", "DOB_MISSING"),
            person("accepted_b", "Bob PARTNER", "2000-02-02",
                   "SOURCE_LINKED_DOB_IN_PREVIEW"),
        ]
        self.queue = [dict(self.people[0])]
        self.ranking = [dict(
            discipline="Ice Dance", person_a_id="missing_a", person_b_id="accepted_b",
            person_a_name="Alisa NAME", person_b_name="Bob PARTNER",
            pair_id="pair_one", season="2018-19", profile_url="",
        )]
        self.rules = [dict(
            canonical_person_id="missing_a", published_roster_name="Alisa NAME",
            discipline="Ice Dance", roster_partner_name="Bob PARTNER",
            roster_member_side="1", verified_date_of_birth="1999-01-01",
            official_printed_name="Alisa NAME",
            primary_official_source_url="https://results.isu.org/bios/isufs00009841.htm",
            identity_context_source_url="", source_tier="ISU_SAME_PAIR_BIO",
            review_status="source_reviewed_dob_evidence",
            source_review_note=(
                "The official ISU couple biography identifies the exact pair and "
                "reports 01.01.1999 for the named first member; this is synthetic test data."),
        )]
        self.save()

    def save(self):
        save(self.canonical, self.people)
        save(self.missing, self.queue)
        save(self.roster, self.ranking)
        save(self.ledger, self.rules)
        baseline = dict(
            stage="modern_source_reviewed_dob_coverage_audit_v5_not_frozen",
            canonical_modern_identity_name_ids=len(self.people),
            canonical_missing_dob=len(self.queue),
            canonical_conflicting_dob=0,
            canonical_with_one_source_linked_dob=1,
            input_sha256={
                "output\\master\\season_roster.csv":
                    hashlib.sha256(self.roster.read_bytes()).hexdigest(),
            })
        self.manifest.write_text(json.dumps(baseline), encoding="utf-8")

    def run_audit(self):
        return audit(self.manifest, self.canonical, self.missing,
                     self.roster, self.ledger, self.out)

    def test_source_preview_fills_only_missing_dob_preserves_inputs(self):
        original = self.canonical.read_bytes()
        summary = self.run_audit()
        self.assertEqual(summary["v6_reviewed_source_rescue_rows"], 1)
        self.assertEqual(summary["v6_covered_canonical_name_id_slots"], 2)
        self.assertEqual(summary["v6_remaining_missing_dob_slots"], 0)
        self.assertEqual(summary["v6_dob_conflict_slots"], 0)
        self.assertEqual(self.canonical.read_bytes(), original)
        updated, _ = read(
            self.out / "modern_canonical_dob_source_augmented_v6.csv",
            ("canonical_person_id", "accepted_dob", "dob_status"))
        a, b = {r["canonical_person_id"]: r for r in updated}["missing_a"], (
            {r["canonical_person_id"]: r for r in updated}["accepted_b"])
        self.assertEqual(a["accepted_dob"], "1999-01-01")
        self.assertEqual(a["dob_status"], "SOURCE_REVIEWED_ISU_DOB_PREVIEW")
        self.assertEqual(b["accepted_dob"], "2000-02-02")

    def test_wrong_partner_or_roster_member_side_rejected(self):
        self.rules[0]["roster_partner_name"] = "OTHER PARTNER"
        self.save()
        with self.assertRaisesRegex(ValueError, "roster role and partner"):
            self.run_audit()
        self.rules[0]["roster_partner_name"] = "Bob PARTNER"
        self.rules[0]["roster_member_side"] = "2"
        self.save()
        with self.assertRaisesRegex(ValueError, "roster role and partner"):
            self.run_audit()

    def test_unreviewed_source_or_hostile_url_rejected(self):
        self.rules[0]["review_status"] = "unverified"
        self.save()
        with self.assertRaisesRegex(ValueError, "curated DOB evidence"):
            self.run_audit()
        self.rules[0]["review_status"] = "source_reviewed_dob_evidence"
        self.rules[0]["primary_official_source_url"] = (
            "https://results.isu.org.evil.test/bios/isufs00009841.htm")
        self.save()
        with self.assertRaisesRegex(ValueError, "curated DOB evidence"):
            self.run_audit()

    def test_stale_modern_roster_rejected(self):
        self.roster.write_bytes(self.roster.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Modern roster changed"):
            self.run_audit()

    def test_missing_ledger_member_fails_closed(self):
        self.queue = [dict(self.people[0])]
        self.rules[0]["canonical_person_id"] = "not_missing"
        self.save()
        with self.assertRaisesRegex(ValueError, "no longer DOB missing"):
            self.run_audit()

    def test_versioned_ledger_contains_28_distinct_reviewed_ids(self):
        actual, _ = read(
            ROOT / "data/adjudications/isu_modern_dob_official_missing_rescues_v6.csv",
            ("canonical_person_id", "source_tier", "review_status"))
        self.assertEqual(len(actual), 28)
        self.assertEqual(len({r["canonical_person_id"] for r in actual}), 28)
        self.assertEqual(sum(r["source_tier"].startswith("NATIONAL_") for r in actual), 1)
        self.assertTrue(all(r["review_status"] ==
                            "source_reviewed_dob_evidence" for r in actual))


if __name__ == "__main__":
    unittest.main()
