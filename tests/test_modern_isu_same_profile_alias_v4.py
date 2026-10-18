"""Synthetic tests of source-reviewed 8+6 modern ISU profile-side alias projection."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_modern_isu_same_profile_alias_v4 import audit, read


def save(p, rows):
    with Path(p).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ModernProfileAliasV4Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.modern = base / "modern.csv"
        self.prior = base / "prior.csv"
        self.new = base / "new.csv"
        self.v3manifest = base / "v3.json"
        self.cross = base / "cross.csv"
        self.out = base / "out"
        self.roster = []
        self.old_rules = []
        self.extra = []

        def entry(pid, who, member, profile, season):
            return {
                "pair_id": pid, "discipline": "Ice Dance",
                "person_a_id": who, "person_b_id": member,
                "person_a_name": who, "person_b_name": member,
                "season": season,
                "profile_url": f"https://results.isu.org/bios/{profile}.htm",
            }

        for i in range(6):
            old, canon, partner = f"old{i}", f"canon{i}", f"partner{i}"
            p_old = f"isufs{i+100:08d}"
            p_new = p_old if i < 4 else f"isufs{i+200:08d}"
            self.roster.extend([
                entry(f"pOld{i}", old, partner, p_old, "2018-19"),
                entry(f"pNew{i}", canon, partner, p_new, "2021-22"),
            ])
            self.old_rules.append({
                "rule_id": f"M{i}", "scope": "modern",
                "discipline": "Ice Dance", "alternate_person_id": old,
                "canonical_person_id": canon, "anchor_person_id": f"h{i}",
                "expected_dob": "1995-01-01",
                "evidence_status": "source_reviewed_name_alias",
            })

        for i in range(8):
            old, canon, partner = f"extraOld{i}", f"extraNew{i}", f"extraPartner{i}"
            profile = f"isufs{i+300:08d}"
            self.roster.extend([
                entry(f"eOld{i}", old, partner, profile, "2018-19"),
                entry(f"eNew{i}", canon, partner, profile, "2021-22"),
            ])
            self.extra.append({
                "rule_id": f"P{i}", "discipline": "Ice Dance",
                "official_profile_id": profile, "member_side": "1",
                "canonical_person_id": canon, "alternate_person_id": old,
                "canonical_published_name": canon,
                "alternate_published_name": old,
                "date_of_birth": "1996-06-07",
                "official_bio_url":
                    f"https://results.isu.org/bios/{profile}.htm",
                "evidence_status": "source_reviewed_same_profile_side",
                "source_review_note": "The same ISU biography ID and the same member side repeatedly identify this individual with the same partner in different seasons.",
            })
        self.cross_edges = [{
            "discipline": "Ice Dance", "historic_projected_id": "hA",
            "modern_provisional_id": "extraOld0",
            "historic_dob": "1996-06-07", "modern_official_dob": "1996-06-07",
            "original_candidate_edge_count": "1",
            "modern_names": "extraOld0",
            "original_modern_person_ids": "extraOld0",
            "source_reviewed_rule_ids": "",
            "cross_era_identity_status": "UNCHANGED_CROSS_ERA_IDENTITY_CANDIDATE",
        }]
        self.save()

    def save(self):
        save(self.modern, self.roster)
        save(self.prior, self.old_rules)
        save(self.new, self.extra)
        save(self.cross, self.cross_edges)
        self.v3manifest.write_text(json.dumps({
            "source_hashes": {"output/master/season_roster.csv":
                              hashlib.sha256(self.modern.read_bytes()).hexdigest()},
            "normalized_cross_era_candidate_groups": len(self.cross_edges),
        }), encoding="utf-8")

    def run_audit(self):
        return audit(self.modern, self.prior, self.new,
                     self.v3manifest, self.cross, self.out)

    def test_twelve_bio_side_collisions_all_reviewed_and_projected(self):
        roster_before = self.modern.read_bytes()
        s = self.run_audit()
        self.assertEqual(s["modern_raw_name_ids"], 42)
        self.assertEqual(s["modern_profile_side_duplicate_id_groups"], 12)
        self.assertEqual(s["additional_profile_side_source_reviewed_aliases"], 8)
        self.assertEqual(s["modern_source_reviewed_alias_rules"], 14)
        self.assertEqual(s["projected_unique_modern_person_name_ids"], 28)
        self.assertEqual(s["projected_modern_pair_groups"], 14)
        self.assertEqual(s["ranking_source_rows_unchanged"], 28)
        self.assertEqual(self.modern.read_bytes(), roster_before)
        cross = read(self.out / "cross_era_modern_alias_source_preview_v4.csv",
                     ("new_modern_person_id_v4",))
        self.assertEqual(cross[0]["new_modern_person_id_v4"], "extraNew0")

    def test_wrong_profile_member_side_rejected(self):
        self.extra[0]["member_side"] = "2"
        self.save()
        with self.assertRaisesRegex(ValueError, "name/role/profile differs"):
            self.run_audit()

    def test_unreviewed_new_alias_cannot_merge(self):
        self.extra[0]["evidence_status"] = "candidate"
        self.save()
        with self.assertRaisesRegex(ValueError, "Malformed or unreviewed"):
            self.run_audit()

    def test_roster_sha_lineage_is_checked(self):
        self.modern.write_bytes(self.modern.read_bytes() + b" \n")
        with self.assertRaisesRegex(ValueError, "Modern roster changed"):
            self.run_audit()

    def test_current_source_ledger_has_eight_distinct_profile_side_rules(self):
        rules = read(
            ROOT / "data/adjudications/isu_modern_same_profile_aliases_v1.csv",
            ("rule_id", "official_profile_id", "member_side",
             "canonical_person_id", "alternate_person_id"))
        self.assertEqual(len(rules), 8)
        self.assertEqual(len({r["alternate_person_id"] for r in rules}), 8)
        self.assertEqual(len({(r["official_profile_id"], r["member_side"])
                              for r in rules}), 8)


if __name__ == "__main__":
    unittest.main()
