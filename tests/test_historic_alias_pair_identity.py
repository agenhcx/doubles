"""No-network identity evidence tests for unresolved historic ISU pair links."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_historic_alias_pair_identity import (
    build, read_csv, reviewed_exceptions, side_evidence
)


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class AliasPairIdentityTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        root = Path(context.name)
        self.fallback = root / "fallback.csv"
        self.historic = root / "pairs.csv"
        self.manual = root / "manual.csv"
        self.exceptions = root / "exceptions.csv"
        self.out = root / "out"
        self.pairs = [
            dict(pair_id="pair1", discipline="Ice Dance",
                 person_a_id="a", person_b_id="b",
                 person_a_name="Alice ONE", person_b_name="Bob TWO"),
            dict(pair_id="pair2", discipline="Ice Dance",
                 person_a_id="a_old", person_b_id="c",
                 person_a_name="Alisa ONE", person_b_name="Carl THREE"),
            dict(pair_id="pair3", discipline="Ice Dance",
                 person_a_id="a_alt", person_b_id="c",
                 person_a_name="A ONE", person_b_name="Carl THREE"),
            dict(pair_id="pair4", discipline="Ice Dance",
                 person_a_id="d", person_b_id="b",
                 person_a_name="Diana DIFFERENT", person_b_name="Bob TWO"),
            dict(pair_id="pair_manual", discipline="Pair Skating",
                 person_a_id="emilia", person_b_id="matthew",
                 person_a_name="Emilia SIMONEN", person_b_name="Matthew PENASSE"),
        ]

        def r(pair, side, histid, name, published, dob, *,
              profile="isufs00001001", fallback="", status="not_needed"):
            return dict(
                historic_pair_id=pair, discipline="Ice Dance",
                historic_person_id=histid, side_on_profile=side,
                historical_name=name, published_name=published,
                profile_id=profile,
                source_url="http://www.isuresults.com/bios/" + profile + ".htm",
                original_published_dob=dob,
                historical_name_dob_candidate=fallback,
                historical_name_parse_status=status,
                historical_name_observed_in_bio=(name if fallback else ""),
                candidate_review_status=(
                    "historic_name_labelled_dob_needs_identity_review"
                    if fallback else "not_recovered_needs_official_source"
                    if not dob else "original_official_dob_unaltered"
                ),
                original_identity_status="not_verified_directory_candidate_only"
            )
        self.rows = [
            r("pair1", "1", "a", "Alice ONE", "Alice ONE", "2000-01-01"),
            r("pair1", "2", "b", "Bob TWO", "Bob TWO", "1999-02-02"),
            r("pair2", "1", "a_old", "Alisa ONE", "Alice ONE", "",
              profile="isufs00001002", fallback="2000-01-01",
              status="dob_explicitly_bound_to_expected_name"),
            r("pair2", "2", "c", "Carl THREE", "Carl THREE", "1997-03-03",
              profile="isufs00001002"),
            r("pair3", "1", "a_alt", "A ONE", "Alice ONE", "",
              profile="isufs00001002"),
            r("pair3", "2", "c", "Carl THREE", "Carl THREE", "1997-03-03",
              profile="isufs00001002"),
            r("pair4", "1", "d", "Diana DIFFERENT", "Alice ONE", "",
              profile="isufs00001003"),
            r("pair4", "2", "b", "Bob TWO", "Bob TWO", "1999-02-02",
              profile="isufs00001003"),
        ]
        self.reviewed = [
            dict(
                historic_pair_id="pair3", historic_person_id="a_alt",
                side_on_profile="1", discipline="Ice Dance",
                historical_name="A ONE", index_name="Alice ONE",
                official_bio_name="Alice ONE", date_of_birth="2000-01-01",
                source_profile_id="isufs00001002",
                source_bio_url="https://results.isu.org/bios/isufs00001002.htm",
                independent_official_url="https://isu-skating.com/en/figure-skating/skaters/alice-one/",
                other_partner_historical_name="Carl THREE",
                evidence_status="source_corroborated",
                adjudication_reason="Official older and newer pair views same partner"
            )
        ]
        self.manual_rows = [
            dict(
                historic_pair_id="pair_manual", discipline="Pair Skating",
                historic_person_a_id="emilia", historic_person_b_id="matthew",
                historic_person_a_name="Emilia SIMONEN",
                historic_person_b_name="Matthew PENASSE",
                official_person_a_name="Emilia SIMONEN",
                official_person_b_name="Matthew PENASSE",
                official_person_a_dob="1996-01-12",
                official_person_b_dob="1988-09-07",
                official_person_a_source_url="https://isu-skating.com/en/figure-skating/skaters/pairs/emilia-simonen-matthew-penasse/",
                official_person_b_source_url="https://isu-skating.com/en/figure-skating/skaters/matthew-penasse/",
                provenance_status="reviewed_separate_official_skater_sources",
                official_profile_id="",
            )
        ]
        self.save_all()

    def save_all(self):
        save(self.historic, self.pairs)
        save(self.fallback, self.rows)
        save(self.exceptions, self.reviewed)
        save(self.manual, self.manual_rows)

    def run_audit(self):
        return build(self.fallback, self.historic, self.manual,
                     self.exceptions, self.out)

    def test_source_correlated_vs_exception_vs_partner_only_and_collisions(self):
        original = self.fallback.read_bytes()
        result = self.run_audit()
        self.assertEqual(result["pairs_processed"], 5)
        self.assertEqual(result["official_name_directory_candidate_pairs"], 4)
        self.assertEqual(result["pair_status_counts"][
            "dual_names_source_attested_pair"], 2)
        self.assertEqual(result["pair_status_counts"][
            "source_reviewed_alias_exception_pair"], 1)
        self.assertEqual(result["pair_status_counts"][
            "manual_official_source_pair"], 1)
        self.assertEqual(result["pair_status_counts"][
            "unverified_directory_identity_candidate"], 1)
        self.assertEqual(result["review_pair_rows"], 1)
        self.assertEqual(result["same_profile_side_multiple_historic_ids"], 1)
        self.assertEqual(result["source_correlated_dob_evidence_rows"], 8)
        self.assertEqual(result["source_correlated_original_historic_ids"], 7)
        self.assertEqual(result["historical_ids_with_conflicting_correlated_dates"], 0)
        self.assertEqual(original, self.fallback.read_bytes())

        review = read_csv(self.out / "historic_alias_unresolved_pair_review.csv")
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]["historic_pair_id"], "pair4")
        self.assertEqual(review[0]["person_a_dob_evidence"], "")

        person = read_csv(self.out / "historic_alias_correlated_dob_leads.csv")
        self.assertEqual({r["historic_person_id"] for r in person},
                         {"a", "b", "a_old", "a_alt", "c", "emilia", "matthew"})
        exception = next(r for r in person if r["historic_person_id"] == "a_alt")
        self.assertEqual(exception["dob_evidence_type"],
                         "independently_reviewed_official_alias")
        self.assertIn("isu-skating.com", exception["reviewed_exception_source_url"])

    def test_bad_exception_date_or_wrong_profile_link_is_rejected(self):
        self.reviewed[0]["date_of_birth"] = "2000-02-30"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "invalid DOB"):
            self.run_audit()
        self.reviewed[0]["date_of_birth"] = "2000-01-01"
        self.reviewed[0]["source_bio_url"] = "https://evil.example/bios/isufs00001002.htm"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "not linked"):
            self.run_audit()

    def test_mismatched_exception_historic_name_or_partner_is_rejected(self):
        self.reviewed[0]["other_partner_historical_name"] = "WRONG OTHER"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "mismatches historical pair"):
            self.run_audit()

    def test_untrusted_manual_primary_dob_sources_rejected(self):
        self.manual_rows[0]["official_person_a_source_url"] = "https://unofficial.example/profile"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "not official"):
            self.run_audit()

    def test_mismatched_historical_pair_ids_are_never_silently_assigned(self):
        self.rows[0]["historic_person_id"] = "different-person"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "mismatches historical pair"):
            self.run_audit()

    def test_all_real_reviewed_alias_exceptions_exist_in_historic_pair_roster(self):
        path = ROOT / "data/adjudications/isu_historic_alias_exceptions_v1.csv"
        original = {r["pair_id"]: r for r in
                    read_csv(ROOT / "data/historic/v4/couples_v4.csv")}
        exc = reviewed_exceptions(path)
        self.assertEqual(len(exc), 2)
        for (pairid, pid, side), rule in exc.items():
            self.assertIn(pairid, original)
            pair = original[pairid]
            key = "a" if side == "1" else "b"
            self.assertEqual(rule["historic_person_id"],
                             pair[f"person_{key}_id"])
            self.assertEqual(rule["historical_name"],
                             pair[f"person_{key}_name"])
            self.assertEqual(rule["discipline"], pair["discipline"])
            self.assertTrue(rule["other_partner_historical_name"])


if __name__ == "__main__":
    unittest.main()
