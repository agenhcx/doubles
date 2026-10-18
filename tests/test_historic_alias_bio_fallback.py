"""Offline QA for DOBs missed because ISU directory names were modernized."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_historic_alias_bio_fallback import audit
from audit_isu_identities import read_csv


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class HistoricAliasNameFallbackTests(unittest.TestCase):
    def setUp(self):
        ctx = tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.root = Path(ctx.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.src = self.root / "original_leads.csv"
        self.out = self.root / "output"
        def row(pair, side, old, published, dob, profile="isufs00004927", id_="x"):
            return {
                "historic_pair_id": pair, "discipline": "Ice Dance",
                "historic_person_id": id_, "side_on_profile": side,
                "historical_name": old, "published_name": published,
                "published_dob": dob, "profile_id": profile,
                "source_url": "https://www.isuresults.com/bios/" + profile + ".htm",
                "parse_status": ("dob_explicitly_bound_to_expected_name"
                                 if dob else "expected_name_not_in_header"),
                "prior_audited_dob": "",
                "historical_identity_link_status": "not_verified_directory_candidate_only",
            }
        self.rows = [
            row("pair1", "1", "Kristin FRASER", "Kristin FRASER-LUKANIN", "", id_="k"),
            row("pair1", "2", "Igor LUKANIN", "Igor LUKANIN", "1976-02-03", id_="i"),
            row("pair2", "1", "Alexa SCIMECA KNIERIM", "Alexa KNIERIM", "",
                profile="isufs00034201", id_="a1"),
            row("pair2", "2", "Chris KNIERIM", "Chris KNIERIM", "1987-11-05",
                profile="isufs00034201", id_="c"),
            row("pair3", "1", "Alexa SCIMECA", "Alexa KNIERIM", "",
                profile="isufs00034201", id_="a2"),
            row("pair3", "2", "Chris KNIERIM", "Chris KNIERIM", "1987-11-05",
                profile="isufs00034201", id_="c"),
            row("pair4", "1", "Emilia SIMONEN", "Katherine BOBAK", "",
                profile="isufs00012160", id_="e"),
            row("pair4", "2", "Matthew PENASSE", "Matthew PENASSE", "1988-09-07",
                profile="isufs00012160", id_="m"),
        ]
        (self.cache / "isufs00004927.html").write_text(
            """ICE DANCE Date of birth: 29.02.1980 Kristin FRASER
               Date of birth: 03.02.1976 Igor LUKANIN""", encoding="utf-8"
        )
        (self.cache / "isufs00034201.html").write_text(
            """PAIRS Date of birth: 10.06.1991 Alexa SCIMECA KNIERIM
               Date of birth: 05.11.1987 Chris KNIERIM""", encoding="utf-8"
        )
        (self.cache / "isufs00012160.html").write_text(
            """PAIRS Date of birth: 08.08.1994 Katherine BOBAK
               Date of birth: 07.09.1988 Matthew PENASSE""", encoding="utf-8"
        )
        self.save()

    def save(self):
        save_csv(self.src, self.rows)

    def test_salvages_only_explicit_historical_name_no_auto_identity_approval(self):
        before = self.src.read_bytes()
        report = audit(self.src, self.cache, self.out)
        self.assertEqual(report["source_lead_rows"], 8)
        self.assertEqual(report["historical_pairs"], 4)
        self.assertEqual(report["unique_official_profiles"], 3)
        self.assertEqual(report["original_official_profile_slots_with_dob"], 3)
        self.assertEqual(report["new_unique_official_slots_recovered"], 2)
        self.assertEqual(report["unique_official_profile_slots_with_a_labelled_dob"], 5)
        self.assertEqual(report["remaining_unique_profile_slots_without_labelled_dob"], 1)
        rows = read_csv(self.out / "historic_alias_source_name_fallback_leads.csv")
        lookup = {(r["historic_pair_id"], r["side_on_profile"]): r for r in rows}
        self.assertEqual(lookup["pair1", "1"]["historical_name_dob_candidate"], "1980-02-29")
        self.assertEqual(lookup["pair2", "1"]["historical_name_dob_candidate"], "1991-06-10")
        self.assertEqual(lookup["pair3", "1"]["historical_name_dob_candidate"], "")
        self.assertEqual(lookup["pair4", "1"]["historical_name_dob_candidate"], "")
        self.assertTrue(all(r["original_identity_status"] ==
                            "not_verified_directory_candidate_only" for r in rows))
        self.assertEqual(self.src.read_bytes(), before)
        self.assertEqual(report["review_rows"], 4)

    def test_legacy_second_skater_name_and_reverse_date_layout(self):
        self.rows = [
            {
                "historic_pair_id": "oldpair", "discipline": "Pair Skating",
                "historic_person_id": "olga", "side_on_profile": "1",
                "historical_name": "Olga BOGUSLAVSKA",
                "published_name": "Olga BOGUSLAVSKA",
                "published_dob": "1982-03-15",
                "profile_id": "isufs00006196",
                "source_url": "https://www.isuresults.com/bios/isufs00006196.htm",
                "parse_status": "dob_explicitly_bound_to_expected_name",
                "prior_audited_dob": "",
                "historical_identity_link_status": "not_verified_directory_candidate_only",
            },
            {
                "historic_pair_id": "oldpair", "discipline": "Pair Skating",
                "historic_person_id": "andrei", "side_on_profile": "2",
                "historical_name": "Andrei BROVENKO",
                "published_name": "Andrejs BROVENKO",
                "published_dob": "",
                "profile_id": "isufs00006196",
                "source_url": "https://www.isuresults.com/bios/isufs00006196.htm",
                "parse_status": "expected_name_not_in_header",
                "prior_audited_dob": "",
                "historical_identity_link_status": "not_verified_directory_candidate_only",
            },
        ]
        self.save()
        (self.cache / "isufs00006196.html").write_text(
            """PAIRS Date of birth: 15.03.1982 Olga BOGUSLAVSKA LAT
            Other fields Latvian historical archive
            Andrei BROVENKO 05.07.1983 Date of birth:
            Riga Place of birth: Other details""", encoding="utf-8"
        )
        result = audit(self.src, self.cache, self.out)
        self.assertEqual(result["new_unique_official_slots_recovered"], 1)
        self.assertEqual(result["remaining_unique_profile_slots_without_labelled_dob"], 0)
        rows = read_csv(self.out / "historic_alias_source_name_fallback_review.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["historical_name_dob_candidate"], "1983-07-05")
        self.assertEqual(rows[0]["historical_name_parse_method"],
                         "name_date_label_legacy")

    def test_missing_cache_is_explicit_and_never_treated_as_negative_dob(self):
        (self.cache / "isufs00004927.html").unlink()
        report = audit(self.src, self.cache, self.out)
        self.assertEqual(report["profiles_without_cached_html"], 1)
        self.assertIn("isufs00004927", report["missing_cache_profile_ids"])
        self.assertEqual(report["new_unique_official_slots_recovered"], 1)
        evidence = read_csv(self.out / "historic_alias_source_name_fallback_leads.csv")
        row = next(r for r in evidence if r["historic_pair_id"] == "pair1"
                   and r["side_on_profile"] == "1")
        self.assertEqual(row["historical_name_parse_status"], "cached_html_missing")

    def test_prior_dob_conflict_is_held_and_written_to_review(self):
        self.rows[0]["prior_audited_dob"] = "1980-02-28"
        self.save()
        report = audit(self.src, self.cache, self.out)
        self.assertEqual(report["review_status_counts"]["fallback_conflicts_with_prior_hold"], 1)
        review = read_csv(self.out / "historic_alias_source_name_fallback_review.csv")
        row = next(r for r in review if r["historic_pair_id"] == "pair1")
        self.assertEqual(row["date_comparison_to_prior"], "conflicts_with_prior")
        self.assertEqual(row["original_published_dob"], "")
        self.assertEqual(row["historical_name_dob_candidate"], "1980-02-29")

    def test_unofficial_sources_and_missing_pair_sides_rejected(self):
        self.rows[0]["source_url"] = "https://unofficial.example/figure-skating"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unapproved ISU source"):
            audit(self.src, self.cache, self.out)
        self.rows[0]["source_url"] = (
            "https://www.isuresults.com/bios/isufs00004927.htm"
        )
        self.rows.pop(1)
        self.save()
        with self.assertRaisesRegex(ValueError, "Incomplete source pair-side"):
            audit(self.src, self.cache, self.out)


if __name__ == "__main__":
    unittest.main()
