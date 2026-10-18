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

    def test_legacy_name_order_reversal_without_dob_swap(self):
        # Historic ranking and official bio for isufs00000472:
        # FUSAR POLI Barbara vs Barbara FUSAR POLI; 2nd DOB precedes label.
        html = """<html><body>ICE DANCING
        Date of birth: 06.02.1972 Barbara FUSAR POLI ITA
        Sesto San Giovanni Place of birth: Height: 168 cm
        Other biographic fields ITA Milan Place of birth:
        Maurizio MARGAGLIO 16.11.1974 Date of birth: internet
        Personal Best Total Score 183.46 20.02.2006
        </body></html>"""
        a, b = parse_pair_profile(
            html, "FUSAR POLI Barbara", "MARGAGLIO Maurizio")
        self.assertEqual((a["date_of_birth"], b["date_of_birth"]),
                         ("1972-02-06", "1974-11-16"))
        self.assertEqual(a["observed_name"], "Barbara FUSAR POLI")
        self.assertEqual(b["observed_name"], "Maurizio MARGAGLIO")
        self.assertEqual(a["parse_method"], "label_date_name_name_rotation")
        self.assertEqual(b["parse_method"], "name_date_label_legacy_name_rotation")
        self.assertEqual(a["parse_status"], "dob_bound_to_rotated_name_review")
        self.assertEqual(b["parse_status"], "dob_bound_to_rotated_name_review")

    def test_rotated_name_still_requires_adjacent_dob_label(self):
        html = """<html>ICE DANCING Barbara FUSAR POLI was born
        on 06.02.1972 and won several medals.
        Maurizio MARGAGLIO 16.11.1974 score history
        Personal Best 183.46 20.02.2006</html>"""
        a, b = parse_pair_profile(
            html, "FUSAR POLI Barbara", "MARGAGLIO Maurizio")
        self.assertEqual(a["date_of_birth"], "")
        self.assertEqual(b["date_of_birth"], "")
        self.assertEqual(a["parse_status"], "name_present_without_bound_dob")
        self.assertEqual(b["parse_status"], "name_present_without_bound_dob")

    def test_opposite_rotations_with_conflicting_birthdays_are_held(self):
        html = """<html>ICE DANCING
        Date of birth: 06.02.1972 Barbara FUSAR POLI
        Date of birth: 07.02.1972 Barbara FUSAR POLI
        Maurizio MARGAGLIO 16.11.1974 Date of birth:</html>"""
        a, b = parse_pair_profile(
            html, "FUSAR POLI Barbara", "MARGAGLIO Maurizio")
        self.assertEqual(a["date_of_birth"], "")
        self.assertEqual(a["parse_status"], "conflicting_labelled_dates_on_page")
        self.assertEqual(b["date_of_birth"], "1974-11-16")

    def test_cached_reversed_name_profile_is_counted_but_held_for_review(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pair_file = root / "pairs.csv"
            source = root / "cache"
            seed = root / "seed.csv"
            out = root / "out"
            save(pair_file, [dict(
                historic_pair_id="pair_italy", index_match_status="exact_couple_profile",
                exact_profile_ids="isufs00000472",
                exact_profile_urls="https://www.isuresults.com/bios/isufs00000472.htm",
                historic_person_a_id="barbara", historic_person_b_id="maurizio",
                historic_person_a_name="FUSAR POLI Barbara",
                historic_person_b_name="MARGAGLIO Maurizio",
            )])
            seed.write_text("historic_person_id,date_of_birth,evidence_status\n",
                            encoding="utf-8")
            source.mkdir()
            (source / "isufs00000472.html").write_text("""<html>ICE DANCING
                Date of birth: 06.02.1972 Barbara FUSAR POLI ITA
                Place of birth: Sesto San Giovanni Height: 168 cm
                Place of birth: Milan
                Maurizio MARGAGLIO 16.11.1974 Date of birth:
                Hobbies: internet</html>""", encoding="utf-8")
            opts = argparse.Namespace(
                pairs=str(pair_file), seed=str(seed), cache=str(source),
                out=str(out), limit=0, offline=True, refresh=False,
                proxy=None, no_env_proxy=True, timeout=5, delay=0,
            )
            summary = run(opts)
            self.assertEqual(summary["profiles_both_dobs_bound"], 1)
            self.assertEqual(summary["slots_with_explicitly_bound_dob"], 2)
            self.assertEqual(summary["review_rows"], 2)
            self.assertEqual(summary["person_dob_status_counts"]["name_order_review"], 2)
            records = read_csv(out / "historic_isu_person_dob_candidates.csv")
            self.assertTrue(all(row["date_of_birth_candidate"] == "" for row in records))
            self.assertEqual({row["distinct_dates"] for row in records},
                             {"1972-02-06", "1974-11-16"})

    def test_hyphenated_surname_matches_official_space_variant_as_review(self):
        # Exact name tokens; only the hyphen is rendered as a space on
        # two actual ISU biography pages.
        html = """<html>Pairs Date of birth: 04.01.2000 Lana PETRANOVIC
        Date of birth: 21.03.1993 Antonio SOUZA KORDEIRU
        Personal Best Score 155.80 21.03.2017</html>"""
        a, b = parse_pair_profile(
            html, "Lana PETRANOVIC", "Antonio SOUZA-KORDEIRU"
        )
        self.assertEqual(a["date_of_birth"], "2000-01-04")
        self.assertEqual(b["date_of_birth"], "1993-03-21")
        self.assertEqual(b["parse_method"], "label_date_name_punctuation_variant")
        self.assertEqual(b["parse_status"], "dob_bound_to_punctuation_variant_review")
        self.assertEqual(b["observed_name"], "Antonio SOUZA KORDEIRU")

    def test_second_hyphenated_surname_and_unlabelled_date_guard(self):
        html = """<html>Ice Dance Date of birth: 13.06.1997 Tina GARABEDIAN
        Date of birth: 06.12.1991 Simon PROULX SENECAL
        Personal Best 07.01.2018</html>"""
        _, b = parse_pair_profile(
            html, "Tina GARABEDIAN", "Simon PROULX-SENECAL"
        )
        self.assertEqual(b["date_of_birth"], "1991-12-06")
        self.assertEqual(b["parse_status"], "dob_bound_to_punctuation_variant_review")
        no_label = """<html>Simon PROULX SENECAL 06.12.1991
        Personal Best Total Score 182.22</html>"""
        _, n = parse_pair_profile(
            no_label, "Tina GARABEDIAN", "Simon PROULX-SENECAL"
        )
        self.assertEqual(n["date_of_birth"], "")

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
            reviews = read_csv(out / "historic_isu_bio_review.csv")
            conflicted = [r for r in reviews if r["historic_person_id"] == "a"]
            self.assertEqual(len(conflicted), 2)
            self.assertTrue(all("cross_profile_or_seed_conflict" in r["review_reason"]
                                for r in conflicted))
            self.assertEqual(report["people_with_dob_conflict"], 1)


if __name__ == "__main__":
    unittest.main()
