"""Run from repo root: python -m unittest discover -s tests -v"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from collect_isu_seasons import parse_page
from build_master_roster import merge

class IsuPageTests(unittest.TestCase):
    def test_2025_senior(self):
        text=(ROOT/"tests/fixtures/isu_2025_sample.html").read_text(encoding="utf-8")
        a=parse_page(text,season="2025-26",level="senior",discipline="Ice Dance",url="https://results.isu.org/ws/wr2025-26/wrdance.htm")
        self.assertEqual(len(a),3)
        self.assertEqual(a[0]["nation"],"GBR")
        self.assertEqual(a[1]["person_b"],"Guillaume CIZERON")
        self.assertEqual(a[0]["points"],"2473")
    def test_2018_old_table(self):
        text=(ROOT/"tests/fixtures/isu_2018_sample.html").read_text(encoding="utf-8")
        a=parse_page(text,season="2018-19",level="senior",discipline="Pair Skating",url="https://results.isu.org/ws/wr2018-19/wrpairs.htm")
        self.assertEqual(len(a),2)
        self.assertEqual(a[0]["person_a"],"Evgenia TARASOVA")
        self.assertEqual(a[1]["nation"],"CHN")
    def test_invalid_login_page_fails(self):
        with self.assertRaisesRegex(ValueError,"ranking"):
            parse_page("<html><body>Please log in</body></html>",season="2025-26",level="senior",discipline="Ice Dance",url="https://example.com")

class RosterMergeTests(unittest.TestCase):
    def test_existing_ids_and_roster_nonloss(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)
            rows=[{
                "season":"2025-26","season_start_year":"2025","level":"senior","discipline":"Ice Dance",
                "rank":"1","points":"2473","person_a":"Lilah FEAR","person_b":"Lewis GIBSON",
                "nation":"GBR","name_as_published":"Lilah FEAR / Lewis GIBSON",
                "source_url":"https://results.isu.org/ws/wr2025-26/wrdance.htm",
                "profile_url":"", "status":"parsed_provisional"},
                {"season":"2025-26","season_start_year":"2025","level":"junior","discipline":"Pair Skating",
                "rank":"1","points":"1034","person_a":"Ava KEMP","person_b":"Yohnatan ELIZAROV",
                "nation":"CAN","name_as_published":"Ava KEMP / Yohnatan ELIZAROV",
                "source_url":"https://results.isu.org/ws/wr2025-26/wrjuniorpairs.htm",
                "profile_url":"", "status":"parsed_provisional"}]
            f=directory/"ranking.csv"
            with f.open("w",encoding="utf-8-sig",newline="") as fp:
                w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            summary=merge(ROOT/"data/historic/v4",f,directory/"result")
            self.assertGreaterEqual(summary["unique_couples_including_rankings"],553)
            self.assertGreaterEqual(summary["unique_athletes_including_rankings"],910)
            with (ROOT/"data/historic/v4/couples_v4.csv").open(encoding="utf-8-sig") as fp:
                hist={r["pair_id"] for r in csv.DictReader(fp)}
            with (directory/"result/couples_master.csv").open(encoding="utf-8-sig") as fp:
                actual={r["pair_id"] for r in csv.DictReader(fp)}
            self.assertTrue(hist.issubset(actual))
            with (directory/"result/season_roster.csv").open(encoding="utf-8-sig") as fp:
                rank_rows=list(csv.DictReader(fp))
            self.assertEqual(len(rank_rows),2)
            self.assertTrue(all(x["source_type"]=="isu_season_ranking" for x in rank_rows))
            self.assertEqual(summary["historic_unique_couples"],553)
            self.assertEqual(summary["historic_unique_athletes"],910)

if __name__=="__main__":
    unittest.main()
