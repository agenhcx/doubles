"""Offline regression tests for official ISU alias biography DOB leads.

Alias candidates are NEVER automatically promoted to historical person DOBs.
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_isu_identities import read_csv
from collect_historic_alias_isu_bios import (
    checked_manual_pairs, validate_manual_against_historic, run
)


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class AliasBiographyTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.candidates = root / "candidates.csv"
        self.manual = root / "manual.csv"
        self.historic = root / "historic_pairs.csv"
        self.prior = root / "prior.csv"
        self.cache = root / "cache"
        self.output = root / "out"
        def c(pair, rank, aa, bb, a, b, profile="isufs00001001"):
            return dict(
                historic_pair_id=pair, discipline="Ice Dance",
                historic_person_a_id=aa, historic_person_b_id=bb,
                historic_person_a_name=a, historic_person_b_name=b,
                candidate_rank=rank, candidate_profile_id=profile,
                candidate_person_a_name="Alisa PEARSON",
                candidate_person_b_name="Roger YOUNG",
                candidate_profile_url="https://www.isuresults.com/bios/" + profile + ".htm"
            )
        self.cand_rows = [
            c("pair1", "1", "alice1", "roger", "Alysa PEARSON", "Roger YOUNG"),
            c("pair2", "1", "alice2", "roger", "Alysa PEARSON", "Roger YOUNG"),
            c("falsepair", "1", "emilia", "matthew",
              "Emilia SIMONEN", "Matthew PENASSE", "isufs00012160"),
        ]
        self.manual_rows = [dict(
            historic_pair_id="falsepair", discipline="Ice Dance",
            historic_person_a_id="emilia", historic_person_b_id="matthew",
            historic_person_a_name="Emilia SIMONEN",
            historic_person_b_name="Matthew PENASSE",
            official_person_a_name="Emilia SIMONEN",
            official_person_b_name="Matthew PENASSE",
            official_person_a_dob="1996-01-12",
            official_person_b_dob="1988-09-07",
            official_profile_id="",
            official_person_a_source_url="https://isu-skating.com/en/figure-skating/skaters/pairs/emilia-simonen-matthew-penasse/",
            official_person_b_source_url="https://isu-skating.com/figure-skating/skaters/matthew-penasse/",
            provenance_status="reviewed_separate_official_skater_sources",
            identity_basis="independent_official_identity",
            evidence_note="This candidate profile listed a different woman",
        )]
        self.historic_rows = [
            dict(pair_id="pair1", discipline="Ice Dance", person_a_id="alice1",
                 person_b_id="roger", person_a_name="Alysa PEARSON",
                 person_b_name="Roger YOUNG"),
            dict(pair_id="pair2", discipline="Ice Dance", person_a_id="alice2",
                 person_b_id="roger", person_a_name="Alysa PEARSON",
                 person_b_name="Roger YOUNG"),
            dict(pair_id="falsepair", discipline="Ice Dance", person_a_id="emilia",
                 person_b_id="matthew", person_a_name="Emilia SIMONEN",
                 person_b_name="Matthew PENASSE"),
        ]
        self.prior_rows = [
            dict(original_historic_person_ids="roger", date_of_birth_candidate="1995-05-05",
                 dob_status="consistent_source_candidate"),
        ]
        self.save()
        self.cache.mkdir()
        (self.cache / "isufs00001001.html").write_text(
            """<html><body>ICE DANCE Date of birth: 06.01.1997 Alisa PEARSON
            USA Place of birth: Boston Date of birth: 05.05.1995 Roger YOUNG
            USA Place of birth: Toronto</body></html>""",
            encoding="utf-8"
        )

    def save(self):
        save(self.candidates, self.cand_rows)
        save(self.manual, self.manual_rows)
        save(self.historic, self.historic_rows)
        save(self.prior, self.prior_rows)

    def collect(self):
        return run(
            self.candidates, self.manual, self.prior, self.cache, self.output,
            limit=0, offline=True, delay=0, no_env_proxy=True,
            historic_pairs_path=self.historic
        )

    def test_cache_bio_read_once_for_two_unverified_historical_pair_links(self):
        prior_bytes = self.prior.read_bytes()
        result = self.collect()
        self.assertEqual(result["initial_pairs_with_candidates"], 3)
        self.assertEqual(result["manual_source_pair_rows_excluded"], 1)
        self.assertEqual(result["manual_source_total"], 1)
        self.assertEqual(result["source_profiles_available"], 1)
        self.assertEqual(result["profiles_both_dobs_bound"], 1)
        self.assertEqual(result["official_profile_person_slots"], 2)
        self.assertEqual(result["slots_with_published_dob"], 2)
        self.assertEqual(result["source_lead_rows"], 4)
        self.assertEqual(result["agreement_with_existing_audited_dob"], 2)
        self.assertEqual(self.prior.read_bytes(), prior_bytes)
        leads = read_csv(self.output / "historic_alias_dob_leads.csv")
        self.assertTrue(all(r["historical_identity_link_status"] ==
                            "not_verified_directory_candidate_only"
                            for r in leads))
        self.assertEqual(sum(r["historical_name"] == "Alysa PEARSON" for r in leads), 2)
        self.assertEqual(len(read_csv(self.output / "historic_alias_bio_review.csv")), 2)

    def test_unexpected_reviewed_pair_member_id_rejected(self):
        self.manual_rows[0]["historic_person_b_id"] = "different"
        self.save()
        with self.assertRaisesRegex(ValueError, "contradicts historical member identity"):
            self.collect()

    def test_untrusted_or_invalid_manual_source_rejected(self):
        self.manual_rows[0]["official_person_a_source_url"] = "https://unofficial.example/fake"
        self.save()
        with self.assertRaisesRegex(ValueError, "Untrusted manual DOB source"):
            self.collect()
        self.manual_rows[0]["official_person_a_source_url"] = (
            "https://isu-skating.com/en/figure-skating/skaters/pairs/emilia-simonen-matthew-penasse/"
        )
        self.manual_rows[0]["official_person_b_dob"] = "1988-01-00"
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid manually reviewed official DOB"):
            self.collect()

    def test_official_directory_bio_can_disagree_with_prior_without_filling_it(self):
        self.prior_rows[0]["date_of_birth_candidate"] = "1995-05-06"
        self.save()
        result = self.collect()
        self.assertEqual(result["disagreement_with_existing_audited_dob"], 2)
        items = read_csv(self.output / "historic_alias_dob_leads.csv")
        self.assertEqual(sum(x["prior_dob_consistency"] == "conflict_with_prior_review"
                             for x in items), 2)
        self.assertTrue(all(x["historical_identity_link_status"] ==
                            "not_verified_directory_candidate_only"
                            for x in items))

    def test_real_manual_seven_pairs_and_official_sources_are_recorded(self):
        p = ROOT / "data/adjudications/isu_historic_manual_pair_dobs_v1.csv"
        r = checked_manual_pairs(p)
        self.assertEqual(len(r), 7)
        count = validate_manual_against_historic(
            r, ROOT / "data/historic/v4/couples_v4.csv")
        self.assertEqual(count, 7)
        self.assertIn("pair_40e2f37332851", r)
        self.assertEqual(r["pair_40e2f37332851"]["official_person_a_dob"], "1994-08-23")
        self.assertIn("pair_f253f21fa31bd", r)
        self.assertEqual(r["pair_f253f21fa31bd"]["official_person_b_dob"], "1988-09-07")


if __name__ == "__main__":
    unittest.main()
