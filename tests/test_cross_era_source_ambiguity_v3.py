"""Synthetic regression tests: source-approved ambiguous ISU identity graph v3."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_cross_era_source_ambiguity_v3 import audit, read


def save(path, records):
    with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


class CrossEraAmbiguityV3Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.edges, self.modern, self.people, self.pairs, self.rules, self.manifest, self.out = (
            (root / p) for p in (
                "edges.csv", "modern.csv", "people.csv", "pairs.csv",
                "rules.csv", "rescue_manifest.json", "out"))

        def person(pid, name, dob):
            return {
                "projected_person_id": pid, "audit_person_ids": pid,
                "original_historic_person_ids": pid, "historic_names": name,
                "date_of_birth": dob, "source_person_rows": "1",
                "status": "unchanged_audit_identity",
            }
        self.historical = [
            person("hA", "Old A", "1990-01-05"),
            person("hB", "Older B", "1993-03-21"),
            person("hC", "Newer B", "1993-03-21"),
            person("hp", "Other PARTNER", "1990-10-10"),
        ]
        def hist_pair(pid, a, b):
            return {
                "discipline": "Pair Skating",
                "projected_person_a_id": a, "projected_person_b_id": b,
                "original_pair_ids": pid, "original_pair_rows": "1",
                "original_pair_names": a + " / " + b,
                "original_pair_seasons": "2016-2017",
                "pair_group_status": "unique_original_pair_id",
                "event_count_aggregation_status": "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP",
            }
        self.hpairs = [hist_pair("hp1", "hA", "hp"),
                       hist_pair("hp2", "hB", "hp"),
                       hist_pair("hp3", "hC", "hp")]

        def mpair(pid, a, name):
            return {
                "pair_id": pid, "discipline": "Pair Skating",
                "person_a_id": a, "person_b_id": "p",
                "person_a_name": name, "person_b_name": "Modern PARTNER",
                "season": "2019-20",
                "profile_url": "https://results.isu.org/bios/isufs00001234.htm",
            }
        self.mseason = [mpair("m1", "mA", "New Name"),
                        mpair("m2", "mAold", "Old Name"),
                        mpair("m3", "mB", "Modern B")]

        def edge(hid, mid, dob, ambig, url):
            return {
                "discipline": "Pair Skating",
                "historic_projected_id": hid,
                "modern_provisional_id": mid,
                "historic_names": ("Old A" if hid == "hA"
                                   else "Older B" if hid == "hB" else "Newer B"),
                "modern_names": {
                    "mA": "New Name", "mAold": "Old Name",
                    "mB": "Modern B"}[mid],
                "historic_dob": dob, "modern_official_dob": dob,
                "modern_bio_urls": url, "modern_profile_urls": url,
                "modern_seasons": "2019-20",
                "cross_era_same_pair": "NO",
                "identity_review_status": "DOB_AGREES_IDENTITY_REVIEW",
                "ambiguity_status": ambig,
            }
        aurl = "https://results.isu.org/bios/isufs00001234.htm"
        burl = "https://results.isu.org/bios/isufs00004567.htm"
        self.candidates = [
            edge("hA", "mA", "1990-01-05", "HISTORIC_TO_MULTIPLE_MODERN_IDS", aurl),
            edge("hA", "mAold", "1990-01-05", "HISTORIC_TO_MULTIPLE_MODERN_IDS", aurl),
            edge("hB", "mB", "1993-03-21", "MODERN_TO_MULTIPLE_HISTORIC_IDS", burl),
            edge("hC", "mB", "1993-03-21", "MODERN_TO_MULTIPLE_HISTORIC_IDS", burl),
        ]
        self.alias_rules = [{
            "rule_id": "MTEST", "scope": "modern", "discipline": "Pair Skating",
            "canonical_person_id": "mA", "alternate_person_id": "mAold",
            "anchor_person_id": "hA", "expected_dob": "1990-01-05",
            "canonical_published_name": "New Name",
            "alternate_published_name": "Old Name",
            "official_profile_url": aurl, "corroborating_official_url": aurl,
            "evidence_status": "source_reviewed_name_alias",
            "review_note": "Official paired ISU biography confirms that earlier and later published names identify the same athlete and exact matching birth date.",
        }, {
            "rule_id": "HTEST", "scope": "historic", "discipline": "Pair Skating",
            "canonical_person_id": "hC", "alternate_person_id": "hB",
            "anchor_person_id": "mB", "expected_dob": "1993-03-21",
            "canonical_published_name": "Newer B",
            "alternate_published_name": "Older B",
            "official_profile_url": burl, "corroborating_official_url": burl,
            "evidence_status": "source_reviewed_cross_partner_alias",
            "review_note": "Older official source explicitly records this new athlete name as the former partner of the earlier historic skater, with matching full DOB.",
        }]
        self.save()

    def save(self):
        for path, rows in (
            (self.edges, self.candidates), (self.modern, self.mseason),
            (self.people, self.historical), (self.pairs, self.hpairs),
            (self.rules, self.alias_rules)):
            save(path, rows)
        manifest = {
            "cross_era_candidate_edges_unchanged": len(self.candidates),
            "remaining_modern_dob_missing_edges": 0,
            "inputs_sha256": {
                "output\\master\\season_roster.csv": hashlib.sha256(
                    self.modern.read_bytes()).hexdigest(),
            },
        }
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")

    def run_audit(self):
        return audit(self.edges, self.modern, self.people, self.pairs,
                     self.rules, self.manifest, self.out)

    def test_reversible_normalization_without_source_mutations(self):
        old_edges, old_roster = self.edges.read_bytes(), self.modern.read_bytes()
        report = self.run_audit()
        self.assertEqual(report["input_cross_era_candidate_edges"], 4)
        self.assertEqual(report["input_ambiguous_candidate_edges"], 4)
        self.assertEqual(report["normalized_cross_era_candidate_groups"], 2)
        self.assertEqual(report["approved_source_identity_rules"], 2)
        self.assertEqual(report["projected_historic_v3_person_slots"], 3)
        self.assertEqual(report["projected_modern_name_id_count"], 3)
        self.assertEqual(report["modern_season_roster_rows_unchanged"], 3)
        self.assertEqual(self.edges.read_bytes(), old_edges)
        self.assertEqual(self.modern.read_bytes(), old_roster)
        rows = read(
            self.out / "source_reviewed_cross_era_canonical_candidates_v1.csv",
            ("original_candidate_edge_count",))
        self.assertEqual({int(r["original_candidate_edge_count"]) for r in rows}, {2})
        self.assertTrue(all(
            r["cross_era_identity_status"] ==
            "SOURCE_REVIEWED_ALIAS_GROUPED_CROSS_ERA_STILL_CANDIDATE" for r in rows))

    def test_wrong_date_cannot_link_ids(self):
        self.alias_rules[1]["expected_dob"] = "1993-03-22"
        self.save()
        with self.assertRaisesRegex(ValueError, "DOB conflicts"):
            self.run_audit()

    def test_missing_reviewed_identity_source_rejected(self):
        self.alias_rules[0]["evidence_status"] = "candidate_only"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unreviewed identity link"):
            self.run_audit()

    def test_unreviewed_ambiguity_cannot_be_silently_dropped(self):
        self.alias_rules = self.alias_rules[:1]
        self.save()
        with self.assertRaisesRegex(ValueError, "unreviewed or extra"):
            self.run_audit()

    def test_reject_input_roster_changed_after_birthdate_audit(self):
        self.modern.write_bytes(self.modern.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "different season roster"):
            self.run_audit()

    def test_current_ledger_is_seven_explicit_source_reviews(self):
        rows = read(
            ROOT / "data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv",
            ("rule_id", "scope", "canonical_person_id",
             "alternate_person_id", "official_profile_url"))
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(r["scope"] == "modern" for r in rows), 6)
        self.assertEqual(sum(r["scope"] == "historic" for r in rows), 1)
        self.assertEqual(len({(r["scope"], r["alternate_person_id"]) for r in rows}), 7)
        self.assertTrue(all(r["official_profile_url"].startswith(
            "https://results.isu.org/bios/") for r in rows))


if __name__ == "__main__":
    unittest.main()
