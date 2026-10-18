"""Synthetic tests for historic surname-plus-initial paired-name audit."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_historic_initial_only_aliases_v1 import find, read, abbrev, full_match


def write(p, records):
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


class HistoricInitialAliasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.people, self.pairs, self.out = [root / x for x in
                                            ("people.csv", "pairs.csv", "out")]
        def person(id, dob):
            return {
                "audit_person_id": id, "original_historic_person_id": id,
                "date_of_birth_primary_candidate": dob,
                "dob_coverage_status": "official_source_linked",
                "source_urls": "https://results.isu.org/bios/isufs00011111.htm",
            }
        self.persons = [
            person("s1", "1995-04-29"), person("s2", "1992-09-25"),
            person("a1", "1995-04-29"), person("a2", "1992-09-25"),
        ]
        def pair(id, a, b, an, bn):
            return {
                "pair_id": id, "discipline": "Ice Dance", "person_a_id": a,
                "person_b_id": b, "person_a_name": an, "person_b_name": bn,
                "first_season": "2013-2014", "source_types": "gh_historic_event",
            }
        self.pair_rows = [
            pair("short", "s1", "s2", "SINITSINA V", "ZHIGANSHIN R"),
            pair("full", "a1", "a2", "Victoria SINITSINA", "Ruslan ZHIGANSHIN"),
        ]
        self.save()

    def save(self):
        write(self.people, self.persons)
        write(self.pairs, self.pair_rows)

    def test_strict_initial_matching_and_non_destructive_pair_bridge(self):
        self.assertEqual(abbrev("SINITSINA V"), ("sinitsina", "v"))
        self.assertTrue(full_match("DELLA MONICA N", "Nicole DELLA MONICA"))
        self.assertTrue(full_match("MOORE-TOWERS K", "Kirsten MOORE-TOWERS"))
        self.assertFalse(full_match("SINITSINA V", "Diana SINITSINA"))
        old = self.pairs.read_bytes()
        stats = find(self.people, self.pairs, self.out)
        self.assertEqual(stats["abbreviated_historic_pair_records"], 1)
        self.assertEqual(stats["abbreviated_person_candidate_rows"], 2)
        self.assertEqual(stats["abbreviated_pair_candidate_groups"], 1)
        self.assertEqual(self.pairs.read_bytes(), old)
        links = read(self.out / "historic_initial_only_person_candidate_links_v1.csv",
                     ("review_status",))
        self.assertTrue(all(r["review_status"] ==
                            "OFFICIAL_DOB_AGREES_SAME_PAIR_STRUCTURE_REVIEW"
                            for r in links))

    def test_different_official_birthdates_are_not_accepted(self):
        self.persons[2]["date_of_birth_primary_candidate"] = "1995-04-30"
        self.save()
        stats = find(self.people, self.pairs, self.out)
        self.assertEqual(stats["abbreviated_person_candidate_rows"], 2)
        links = read(self.out / "historic_initial_only_person_candidate_links_v1.csv",
                     ("review_status",))
        self.assertIn("MISSING_OR_DISAGREEING_OFFICIAL_DOB_HOLD",
                      {r["review_status"] for r in links})
        pairs = read(self.out / "historic_initial_only_pair_candidate_groups_v1.csv",
                     ("status",))
        self.assertEqual(pairs[0]["status"], "HOLD_FOR_SOURCE_SPECIFIC_ID_REVIEW")

    def test_no_full_pair_bridge_no_candidate_merge(self):
        self.pair_rows[1]["person_b_name"] = "Another SKATER"
        self.save()
        stats = find(self.people, self.pairs, self.out)
        self.assertEqual(stats["abbreviated_pair_candidate_groups"], 0)


if __name__ == "__main__":
    unittest.main()
