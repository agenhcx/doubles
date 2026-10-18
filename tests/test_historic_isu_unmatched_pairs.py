"""No-network review tests for ISU historical pair index alias leads."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from audit_historic_isu_unmatched_pairs import build_alias_queue, lead_status
from audit_isu_identities import read_csv


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricUnmatchedPairTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.pairs = root / "historical_pairs.csv"
        self.index = root / "official_index.csv"
        self.out = root / "out"
        self.pair_rows = [
            dict(
                historic_pair_id="hp1", discipline="Ice Dance",
                historic_person_a_id="a1", historic_person_b_id="b1",
                historic_person_a_name="Alisa PEARSON",
                historic_person_b_name="Roger YOUNG",
                index_match_status="one_partner_indexed",
            ),
            dict(
                historic_pair_id="hp2", discipline="Pair Skating",
                historic_person_a_id="a2", historic_person_b_id="b2",
                historic_person_a_name="Molly JONES",
                historic_person_b_name="Daniel SMITH",
                index_match_status="no_direct_name_match",
            ),
            dict(
                historic_pair_id="hp3", discipline="Pair Skating",
                historic_person_a_id="a3", historic_person_b_id="b3",
                historic_person_a_name="Alina ZZZZ",
                historic_person_b_name="Charles YYYY",
                index_match_status="no_direct_name_match",
            ),
            dict(
                historic_pair_id="hp4", discipline="Ice Dance",
                historic_person_a_id="a4", historic_person_b_id="b4",
                historic_person_a_name="Anna OLD", historic_person_b_name="Bob OLD",
                index_match_status="exact_couple_profile",
            ),
        ]
        def record(d, ident, a, b):
            return dict(
                discipline=d, index_profile_id=ident,
                person_a_name=a, person_b_name=b,
                profile_url="https://results.isu.org/bios/" + ident + ".htm",
                index_url="https://results.isu.org/bios/index.htm",
            )
        self.index_rows = [
            record("Ice Dance", "isufs00001001", "Alysa PEARSON", "Roger YOUNG"),
            record("Ice Dance", "isufs00001002", "Amber OTHER", "Roger YOUNG"),
            record("Pair Skating", "isufs00001003", "Mollie JONES", "Daniel SMYTH"),
            record("Ice Dance", "isufs00001004", "Anna OLD", "Bob OLD"),
        ]
        self.save()

    def save(self):
        save(self.pairs, self.pair_rows)
        save(self.index, self.index_rows)

    def test_anchor_and_two_fuzzy_review_queue_keeps_all_unmatched_pairs(self):
        before = self.pairs.read_bytes()
        report = build_alias_queue(self.pairs, self.index, self.out, max_candidates=5)
        self.assertEqual(report["historic_unmatched_pairs"], 3)
        self.assertEqual(report["pairs_with_any_directory_candidate"], 2)
        self.assertEqual(report["pairs_without_directory_candidate"], 1)
        queue = {r["historic_pair_id"]: r for r in
                 read_csv(self.out / "historic_unmatched_pair_inventory.csv")}
        self.assertEqual(queue["hp1"]["top_candidate_profile_id"], "isufs00001001")
        self.assertEqual(queue["hp1"]["top_candidate_lead_category"],
                         "anchor_b_exact_partner_variant")
        self.assertEqual(queue["hp2"]["top_candidate_lead_category"],
                         "both_names_similarity_only")
        self.assertEqual(queue["hp3"]["candidate_count"], "0")
        self.assertEqual(self.pairs.read_bytes(), before)
        candidates = read_csv(self.out / "historic_pair_alias_review_candidates.csv")
        self.assertGreaterEqual(len(candidates), 2)
        self.assertTrue(all(r["identity_review_status"] ==
                            "not_verified_candidate_only" for r in candidates))

    def test_max_candidates_limits_row_count_not_unmatched_inventory(self):
        result = build_alias_queue(self.pairs, self.index, self.out, max_candidates=1)
        self.assertEqual(result["historic_unmatched_pairs"], 3)
        self.assertEqual(result["candidate_rows_emitted"], 2)

    def test_wrong_external_host_rejected(self):
        self.index_rows[0]["profile_url"] = "https://unofficial.example/bios/isufs00001001.htm"
        self.save()
        with self.assertRaisesRegex(ValueError, "official ISU biography URL"):
            build_alias_queue(self.pairs, self.index, self.out)

    def test_shared_partner_is_not_approved_identity(self):
        historical = dict(historic_person_a_name="Alisa PEARSON",
                          historic_person_b_name="Roger YOUNG")
        official = dict(person_a_name="Unrelated PERSON",
                        person_b_name="Roger YOUNG")
        status, matched_side, _, _ = lead_status(historical, official)
        self.assertEqual(status, "anchor_b_exact_partner_variant")
        self.assertEqual(matched_side, "B")
        self.assertNotEqual(status, "verified_identity")


if __name__ == "__main__":
    unittest.main()
