"""Synthetic regression checks for non-destructive historic alias event audit."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_historic_alias_event_collisions_v1 import audit, read


def save(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricEventAliasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.preview = root / "teams.csv"
        self.events = root / "events.csv"
        self.out = root / "out"
        self.teams = [{
            "discipline": "Ice Dance", "projected_person_a_id": "a",
            "projected_person_b_id": "b", "original_pair_ids": "p1; p2",
            "original_pair_rows": "2"
        }]
        self.events_rows = [{
            "pair_id": pid, "pair_event_id": peid, "discipline": "Ice Dance",
            "event_id": "2017|Worlds|Ice Dance", "season": "2017",
            "event": "Worlds", "rank": rank, "score_as_reported": "150.0",
            "result_status": "ranked", "source_urls": "https://results.isu.org/example",
            "rank_source_conflict": ""
        } for pid, peid, rank in (("p1", "e1", "3"), ("p2", "e2", "3"))]
        self.save()

    def save(self):
        save(self.preview, self.teams)
        save(self.events, self.events_rows)

    def test_matching_duplicate_event_preview_without_original_changes(self):
        original = self.events.read_bytes()
        report = audit(self.preview, self.events, self.out)
        self.assertEqual(report["original_pair_event_records"], 2)
        self.assertEqual(report["projected_distinct_pair_event_groups"], 1)
        self.assertEqual(report["event_collision_groups"], 1)
        self.assertEqual(report["extra_source_pair_event_records_in_collision_groups"], 1)
        self.assertEqual(report["value_agree_collision_groups"], 1)
        self.assertEqual(self.events.read_bytes(), original)
        rows = read(self.out / "historic_alias_event_collision_review_v1.csv",
                    ("review_status",))
        self.assertEqual(rows[0]["review_status"],
                         "MULTIPLE_ORIGINAL_EVENTS_VALUES_AGREE_REVIEW")

    def test_conflicting_rank_retained_for_review(self):
        self.events_rows[1]["rank"] = "4"
        self.save()
        report = audit(self.preview, self.events, self.out)
        self.assertEqual(report["field_conflict_groups"], 1)

    def test_unmapped_original_pair_rejected(self):
        self.events_rows[1]["pair_id"] = "unknown"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unmapped pair"):
            audit(self.preview, self.events, self.out)

    def test_duplicate_original_event_id_rejected(self):
        self.events_rows[1]["pair_event_id"] = "e1"
        self.save()
        with self.assertRaisesRegex(ValueError, "Repeated original pair_event_id"):
            audit(self.preview, self.events, self.out)


if __name__ == "__main__":
    unittest.main()
