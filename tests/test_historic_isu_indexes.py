"""Offline tests for direct ISU biography-index crosslinking."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from audit_historic_isu_indexes import parse_index, crosslink
from audit_isu_identities import read_csv


def save_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricIndexTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.pairs = root / "pairs.csv"
        self.out = root / "result"
        self.rows = [
            dict(pair_id="p1", discipline="Ice Dance", person_a_id="a",
                 person_b_id="b", person_a_name="Anna CAPPELLINI",
                 person_b_name="Luca LANOTTE", identified_event_count="5"),
            dict(pair_id="p2", discipline="Pair Skating", person_a_id="c",
                 person_b_id="d", person_a_name="Dan ZHANG",
                 person_b_name="Hao ZHANG", identified_event_count="6"),
            dict(pair_id="p3", discipline="Ice Dance", person_a_id="b",
                 person_b_id="a", person_a_name="Luca LANOTTE",
                 person_b_name="Anna CAPPELLINI", identified_event_count="2"),
            dict(pair_id="p4", discipline="Ice Dance", person_a_id="a",
                 person_b_id="e", person_a_name="Anna CAPPELLINI",
                 person_b_name="Erik UNKNOWN", identified_event_count="1"),
        ]
        save_csv(self.pairs, self.rows)
        self.ice_html = """<html><h1>Figure Skating Biographies</h1>
        <a href="isufs00008719.htm">Anna CAPPELLINI / Luca LANOTTE</a>
        <a href="https://other.example/bios/isufs00009999.htm">Anna CAPPELLINI / Erik UNKNOWN</a>
        <a href="isufs00010000.htm">Janine OTHER / Marie PARTNER</a></html>"""
        self.pair_html = """<html><h1>Figure Skating Biographies</h1>
        <a href="https://www.isuresults.com/bios/isufs00003604.htm">Dan ZHANG / Hao ZHANG</a>
        </html>"""

    def test_index_parse_accepts_official_profile_links_only(self):
        links = parse_index(
            self.ice_html, "Ice Dance",
            "https://www.isuresults.com/bios/fsbiosdance.htm"
        )
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["index_profile_id"], "isufs00008719")
        self.assertEqual(links[0]["person_b_name"], "Luca LANOTTE")

    def test_crosslink_exact_reversed_and_partial_without_master_updates(self):
        input_before = self.pairs.read_bytes()
        entries = parse_index(
            self.ice_html, "Ice Dance",
            "https://www.isuresults.com/bios/fsbiosdance.htm"
        ) + parse_index(
            self.pair_html, "Pair Skating",
            "https://www.isuresults.com/bios/fsbiospairs.htm"
        )
        result = crosslink(self.pairs, entries, self.out)
        self.assertEqual(result["historic_couples"], 4)
        self.assertEqual(result["exact_pair_profiles_for_followup"], 2)
        self.assertEqual(self.pairs.read_bytes(), input_before)
        rows = {r["historic_pair_id"]: r for r in
                read_csv(self.out / "historic_pair_official_index_links.csv")}
        self.assertEqual(rows["p1"]["index_match_status"], "exact_couple_profile")
        self.assertEqual(rows["p2"]["exact_profile_ids"], "isufs00003604")
        self.assertEqual(rows["p3"]["index_match_status"], "reversed_member_order_review")
        self.assertEqual(rows["p4"]["index_match_status"], "one_partner_indexed")

    def test_missing_title_or_unsupported_discipline_rejected(self):
        with self.assertRaisesRegex(ValueError, "title missing"):
            parse_index(
                "<a href='isufs00003604.htm'>Dan ZHANG / Hao ZHANG</a>",
                "Pair Skating", "https://www.isuresults.com/bios/fsbiospairs.htm"
            )
        with self.assertRaisesRegex(ValueError, "Unsupported discipline"):
            parse_index(self.pair_html, "Singles", "https://www.isuresults.com/bios/fsbiospairs.htm")

    def test_duplicate_profile_with_conflicting_couple_names_rejected(self):
        entries = parse_index(
            self.ice_html, "Ice Dance",
            "https://www.isuresults.com/bios/fsbiosdance.htm"
        )
        entries.append(dict(entries[0], person_b_name="Different PERSON"))
        with self.assertRaisesRegex(ValueError, "contradictory"):
            crosslink(self.pairs, entries, self.out)


if __name__ == "__main__":
    unittest.main()
