"""No-network regressions for legacy and modern official ISU couple biographies."""
import argparse
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_isu_identities import read_csv
from collect_historic_isu_biographies import (
    alternate_end_order, official_jobs, parse_pair_profile, run
)


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


MODERN = """<html><body>PAIRS
 Date of birth: 01.01.2000 Alice ONE USA Place of birth: City
 Height: 150 cm Date of birth: 02.02.1998 Bob TWO USA Place of birth: City
 Personal Best Total Score 180.10 05.03.2011</body></html>"""

LEGACY = """<html><body>ICE DANCING
 Date of birth: 01.01.2000 Alice ONE USA Country Place of birth:
 Height: 156 cm Home town: Somewhere Student Profession:
 Other partner Bob TWO 02.02.1998 Date of birth:
 Hobbies: Music Personal Best Total Score 140.12 30.01.2014
 </body></html>"""


class HistoricalBiographyTests(unittest.TestCase):
    def test_modern_forward_layout(self):
        a, b = parse_pair_profile(MODERN, "Alice ONE", "Bob TWO")
        self.assertEqual(a["date_of_birth"], "2000-01-01")
        self.assertEqual(b["date_of_birth"], "1998-02-02")
        self.assertEqual(a["parse_method"], "label_date_name")
        self.assertEqual(b["parse_method"], "label_date_name")

    def test_older_isu_reversed_second_skater_layout(self):
        a, b = parse_pair_profile(LEGACY, "Alice ONE", "Bob TWO")
        self.assertEqual([a["date_of_birth"], b["date_of_birth"]],
                         ["2000-01-01", "1998-02-02"])
        self.assertEqual(b["parse_method"], "name_date_label_legacy")

    def test_name_and_date_must_be_adjacent_to_date_of_birth_label(self):
        html = """<html>PAIRS
        Date of birth: 01.01.2000 Alice ONE
        Date of birth: 02.02.1998 Different PERSON
        Bob TWO skated in 2011 and was born 02.02.1998.
        Personal Best Total Score 190.00 02.02.1998
        </html>"""
        a, b = parse_pair_profile(html, "Alice ONE", "Bob TWO")
        self.assertEqual(a["date_of_birth"], "2000-01-01")
        self.assertEqual(b["date_of_birth"], "")
        self.assertEqual(b["parse_status"], "name_present_without_bound_dob")

    def test_conflicting_labelled_dates_are_never_accepted(self):
        html = """Date of birth: 01.01.2000 Alice ONE Height: 158 cm
        Date of birth: 01.01.2001 Alice ONE Country: CAN
        Date of birth: 02.02.1998 Bob TWO"""
        a, b = parse_pair_profile(html, "Alice ONE", "Bob TWO")
        self.assertEqual(a["parse_status"], "conflicting_labelled_dates_on_page")
        self.assertEqual(a["date_of_birth"], "")
        self.assertEqual(b["date_of_birth"], "1998-02-02")

    def test_official_profile_id_required_and_duplicate_identity_rejected(self):
        pair = dict(
            historic_pair_id="hpair1", index_match_status="exact_couple_profile",
            exact_profile_ids="isufs00000001",
            exact_profile_urls="https://results.isu.org/bios/isufs00000001.htm",
            historic_person_a_id="a", historic_person_b_id="b",
            historic_person_a_name="Alice ONE", historic_person_b_name="Bob TWO"
        )
        jobs = official_jobs([pair])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(alternate_end_order({
            "isufs00000005": {}, "isufs00000002": {}, "isufs00000009": {}
        }), ["isufs00000002", "isufs00000009", "isufs00000005"])
        another = dict(pair, historic_pair_id="hpair2", historic_person_b_id="c")
        with self.assertRaisesRegex(ValueError, "conflicting historic members"):
            official_jobs([pair, another])

    def test_offline_cached_two_profiles_and_cross_profile_conflict(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            pairs = root / "exact.csv"
            cache = root / "cache"
            seed = root / "primary_seed.csv"
            out = root / "out"
            records = [
                dict(historic_pair_id="old1", index_match_status="exact_couple_profile",
                     exact_profile_ids="isufs00000001",
                     exact_profile_urls="https://results.isu.org/bios/isufs00000001.htm",
                     historic_person_a_id="a", historic_person_b_id="b",
                     historic_person_a_name="Alice ONE", historic_person_b_name="Bob TWO"),
                dict(historic_pair_id="old2", index_match_status="exact_couple_profile",
                     exact_profile_ids="isufs00000002",
                     exact_profile_urls="https://www.isuresults.com/bios/isufs00000002.htm",
                     historic_person_a_id="a", historic_person_b_id="c",
                     historic_person_a_name="Alice ONE", historic_person_b_name="Carl THREE"),
            ]
            save(pairs, records)
            with seed.open("w", encoding="utf-8") as fp:
                fp.write("historic_person_id,date_of_birth,evidence_status\n")
                fp.write("a,2000-01-01,manually_checked_source\n")
            cache.mkdir()
            (cache / "isufs00000001.html").write_text(LEGACY, encoding="utf-8")
            page2 = """Date of birth: 01.01.2000 Alice ONE CAN
            Date of birth: 03.03.1997 Carl THREE CAN"""
            (cache / "isufs00000002.html").write_text(page2, encoding="utf-8")
            args = argparse.Namespace(
                pairs=str(pairs), seed=str(seed), cache=str(cache),
                out=str(out), limit=0, offline=True, refresh=False,
                proxy=None, no_env_proxy=True, timeout=5, delay=0,
            )
            report = run(args)
            self.assertEqual(report["unique_profiles_in_queue"], 2)
            self.assertEqual(report["cache_hits"], 2)
            self.assertEqual(report["profiles_both_dobs_bound"], 2)
            self.assertEqual(report["slots_with_explicitly_bound_dob"], 4)
            persons = {x["historic_person_id"]: x for x in
                       read_csv(out / "historic_isu_person_dob_candidates.csv")}
            self.assertEqual(persons["a"]["source_count"], "2")
            self.assertEqual(persons["a"]["dob_status"], "consistent_profile_candidate")
            self.assertEqual(persons["c"]["date_of_birth_candidate"], "1997-03-03")
            self.assertEqual(len(read_csv(out / "historic_isu_bio_review.csv")), 0)

            page2 = """Date of birth: 01.01.2001 Alice ONE CAN
            Date of birth: 03.03.1997 Carl THREE CAN"""
            (cache / "isufs00000002.html").write_text(page2, encoding="utf-8")
            report = run(args)
            persons = {x["historic_person_id"]: x for x in
                       read_csv(out / "historic_isu_person_dob_candidates.csv")}
            self.assertEqual(persons["a"]["dob_status"], "cross_profile_dob_conflict")
            self.assertEqual(persons["a"]["date_of_birth_candidate"], "")
            self.assertEqual(report["person_dob_status_counts"]["cross_profile_dob_conflict"], 1)


if __name__ == "__main__":
    unittest.main()
