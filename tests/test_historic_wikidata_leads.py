"""No-network tests for historic Wikidata P569 lead collection."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from collect_historic_wikidata_leads import (
    best_query, birthdates_with_day_precision, cache_search_path,
    entity_cache_path, is_skater_entity, run,
)
from audit_isu_identities import read_csv


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def claim(date, precision=11, rank="normal"):
    return {"rank": rank, "mainsnak": {
        "datavalue": {"value": {"time": date, "precision": precision}}
    }}


class HistoricWikidataTests(unittest.TestCase):
    def test_p569_requires_day_precision_and_nondeprecated_date(self):
        e = {"claims": {"P569": [
            claim("+1995-02-15T00:00:00Z"),
            claim("+1995-01-01T00:00:00Z", precision=9),
            claim("+1995-03-03T00:00:00Z", rank="deprecated"),
            claim("+1995-02-30T00:00:00Z"),
        ]}}
        self.assertEqual(birthdates_with_day_precision(e), ["1995-02-15"])

    def test_detects_two_conflicting_exact_dates_and_figure_skater(self):
        e = {"claims": {
            "P569": [claim("+1997-05-04T00:00:00Z"),
                     claim("+1997-05-05T00:00:00Z")],
            "P106": [{"rank": "normal", "mainsnak": {
                "datavalue": {"value": {"id": "Q13219587"}}}}],
        }}
        self.assertEqual(len(birthdates_with_day_precision(e)), 2)
        self.assertTrue(is_skater_entity(e))

    def test_abbreviated_name_not_submitted(self):
        self.assertEqual(best_query({
            "historic_name": "DAVIDOVICH A",
            "historic_name_variants": "A DAVIDOVICH"
        }), "")
        self.assertEqual(best_query({
            "historic_name": "D. SOMETHING",
            "historic_name_variants": "David SOMETHING"
        }), "David SOMETHING")

    def test_offline_cached_lead_never_becomes_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "queue.csv"
            cache = root / "cache"
            out = root / "output"
            r = {
                "historic_person_id": "hist1",
                "historic_name": "Alisa AGAFONOVA",
                "historic_name_variants": "Alisa AGAFONOVA",
                "historic_partner_names": "Alper UCAR",
                "match_status": "unmatched_full_name",
                "identified_competitions": "4"
            }
            write_csv(path, [r])
            search = cache_search_path(cache, "Alisa AGAFONOVA")
            search.parent.mkdir(parents=True, exist_ok=True)
            search.write_text(json.dumps({"search": [
                {"id": "Q111111", "label": "Alisa Agafonova",
                 "description": "figure skater"}]}), encoding="utf-8")
            ep = entity_cache_path(cache, "Q111111")
            ep.parent.mkdir(parents=True, exist_ok=True)
            ep.write_text(json.dumps({"claims": {"P569": [
                claim("+1991-01-15T00:00:00Z")]}}), encoding="utf-8")
            summary = run(path, cache, out, offline=True, limit=1)
            self.assertEqual(summary["candidate_item_rows"], 1)
            self.assertEqual(summary["items_with_day_precision_dob"], 1)
            self.assertEqual(summary["search_errors"], 0)
            rows = read_csv(out / "historic_wikidata_dob_leads.csv")
            self.assertEqual(rows[0]["wikidata_birthdates_day_precision"], "1991-01-15")
            self.assertIn("unverified", rows[0]["evidence_status"])

    def test_offline_missing_cache_is_failure_not_no_result(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "queue.csv"
            write_csv(path, [{
                "historic_person_id": "hist1", "historic_name": "Alisa AGAFONOVA",
                "historic_name_variants": "Alisa AGAFONOVA",
                "historic_partner_names": "Alper UCAR",
                "match_status": "unmatched_full_name",
                "identified_competitions": "1"
            }])
            report = run(path, root / "cache", root / "output", offline=True)
            self.assertEqual(report["search_errors"], 1)
            self.assertEqual(report["searches_ok"], 0)
            self.assertEqual(report["no_wikidata_results"], 0)


if __name__ == "__main__":
    unittest.main()
