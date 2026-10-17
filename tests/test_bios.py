"""No-network regression tests for ISU biography parser and profile identity joins."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from collect_isu_biographies import parse_bio,collect_profiles


class BiographyParsingTests(unittest.TestCase):
    def test_two_birthdates_places_and_names(self):
        html="""<html><body><table><tr><td>Ice Dance</td></tr>
        <tr><td>Date of birth:</td><td>02.07.1992</td><td>Madison CHOCK</td></tr>
        <tr><td>Place of birth:</td><td>Redondo Beach, CA</td></tr>
        <tr><td>Height:</td><td>157 cm</td></tr>
        <tr><td>Date of birth:</td><td>23.02.1989</td><td>Evan BATES</td></tr>
        <tr><td>Place of birth:</td><td>Ann Arbor, MI</td></tr>
        <tr><td>Height:</td><td>187 cm</td></tr></table></body></html>"""
        rows=parse_bio(html)
        self.assertEqual(len(rows),2)
        self.assertEqual([x["date_of_birth"] for x in rows],["1992-07-02","1989-02-23"])
        self.assertEqual([x["observed_name"] for x in rows],["Madison CHOCK","Evan BATES"])
        self.assertEqual([x["place_of_birth_raw"] for x in rows],["Redondo Beach, CA","Ann Arbor, MI"])

    def test_invalid_date_does_not_become_a_candidate(self):
        html="""<html>Ice Dance Date of birth: 31.02.2001 Person ALPHA
        Place of birth: Canada Height: 170 cm
        Date of birth: 01.01.2002 Person BETA Place of birth: France Height: 180 cm</html>"""
        rows=parse_bio(html)
        self.assertEqual(rows[0]["date_of_birth"],"")
        self.assertEqual(rows[0]["status"],"incomplete")
        self.assertEqual(rows[1]["date_of_birth"],"2002-01-01")

    def test_profile_id_de_duplicates_hosts_and_years(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"season_roster.csv"
            rows=[
                dict(profile_url="https://results.isu.org/bios/isufs00013665.htm",
                     person_a_id="personA",person_a_name="Madison CHOCK",
                     person_b_id="personB",person_b_name="Evan BATES"),
                dict(profile_url="http://www.isuresults.com/bios/isufs00013665.htm",
                     person_a_id="personA",person_a_name="CHOCK Madison",
                     person_b_id="personB",person_b_name="BATES Evan")]
            with path.open("w",newline="",encoding="utf-8") as fp:
                w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            profiles=collect_profiles(path)
            self.assertEqual(len(profiles),1)
            self.assertEqual(len(profiles["isufs00013665"]),2)
            self.assertEqual({p for p,_ in profiles["isufs00013665"]["chock madison"]},{"personA"})


if __name__=="__main__":
    unittest.main()
