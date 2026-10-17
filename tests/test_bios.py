"""No-network regression tests for ISU biography parser and profile identity joins."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from collect_isu_biographies import parse_bio,collect_profiles,match_profile_name


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

    def test_surname_matching_a_nation_code_is_preserved(self):
        # SUI is both the skater's actual surname and the ISO code for Switzerland.
        html="""<html><body><table>
        <tr><td>Date of birth:</td><td>18.07.1995</td><td>Wenjing SUI</td></tr>
        <tr><td>Place of birth:</td><td>Harbin</td></tr>
        <tr><td>Height:</td><td>154 cm</td><td>CHN</td></tr>
        <tr><td>Date of birth:</td><td>06.08.1992</td><td>Cong HAN</td></tr>
        <tr><td>Place of birth:</td><td>Harbin</td></tr>
        <tr><td>Height:</td><td>170 cm</td><td>CHN</td></tr>
        </table></body></html>"""
        rows=parse_bio(html)
        self.assertEqual([r["observed_name"] for r in rows],["Wenjing SUI","Cong HAN"])
        self.assertEqual([r["date_of_birth"] for r in rows],["1995-07-18","1992-08-06"])
        self.assertTrue(all(r["status"]=="parsed" for r in rows))

    def test_bio_country_code_resolved_only_against_unique_roster(self):
        # Country is a separate table cell in some older ISU biographies;
        # flattened text appends it to the name.
        html="""<html><body><table>
        <tr><td>Date of birth:</td><td>12.04.1989</td><td>Kaitlyn WEAVER</td><td>CAN</td></tr>
        <tr><td>Place of birth:</td><td>Houston USA</td></tr>
        <tr><td>Height:</td><td>169 cm</td></tr>
        <tr><td>Date of birth:</td><td>25.02.1987</td><td>Andrew POJE</td><td>CAN</td></tr>
        <tr><td>Place of birth:</td><td>Waterloo, ON</td></tr>
        <tr><td>Height:</td><td>190 cm</td></tr>
        </table></body></html>"""
        rows=parse_bio(html)
        self.assertEqual([r["observed_name"] for r in rows],
                         ["Kaitlyn WEAVER CAN", "Andrew POJE CAN"])
        roster={
            "kaitlyn weaver":{("p_weaver","Kaitlyn WEAVER")},
            "andrew poje":{("p_poje","Andrew POJE")},
        }
        self.assertEqual(match_profile_name(rows[0]["observed_name"],roster),
                         ("p_weaver","Kaitlyn WEAVER","roster_confirmed_country_suffix"))
        self.assertEqual(match_profile_name(rows[1]["observed_name"],roster),
                         ("p_poje","Andrew POJE","roster_confirmed_country_suffix"))
        self.assertEqual(match_profile_name("Kaitlyn WEAVER CAN", {}),
                         ("","","unmatched"))

    def test_country_code_surname_prefers_full_exact_and_ambiguous_remains_review(self):
        roster={
            "sui wenjing":{("p_sui","Wenjing SUI")},
            "kaitlyn weaver":{("p1","Kaitlyn WEAVER"),("p2","WEAVER Kaitlyn")},
        }
        self.assertEqual(match_profile_name("Wenjing SUI",roster),
                         ("p_sui","Wenjing SUI","exact"))
        self.assertEqual(match_profile_name("Kaitlyn WEAVER CAN",roster),
                         ("","","ambiguous"))

    def test_missing_second_birthplace_keeps_name_from_older_profile(self):
        # The real ISU profile isufs00104674 has a DOB and name for Min CHOE
        # but no Place of birth row. The next field is "Personal Best" (no colon).
        html="""<html><body>Ice Dance
        Date of birth: 26.11.1989 Yong Myong PHYO PRK
        Place of birth: Pyongyang Height: 159 cm
        Date of birth: 18.11.1990 Min CHOE PRK
        Personal Best Total Score 91.64 05.08.2018
        ISU CS Asian Open Figure Skating Trophy 2018
        </body></html>"""
        rows=parse_bio(html)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["observed_name"],"Yong Myong PHYO PRK")
        self.assertEqual(rows[1]["observed_name"],"Min CHOE PRK")
        self.assertEqual(rows[1]["date_of_birth"],"1990-11-18")
        self.assertEqual(rows[1]["place_of_birth_raw"],"")
        self.assertEqual(rows[1]["status"],"parsed")
        roster={"choe min":{("p_choe","Min CHOE")}}
        self.assertEqual(match_profile_name(rows[1]["observed_name"], roster),
                         ("p_choe","Min CHOE","roster_confirmed_country_suffix"))

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
