"""Synthetic offline regression tests for modern ISU DOB coverage v5."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_modern_source_dob_coverage_v5 import audit, load


def write_csv(path, records):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


class ModernDobCoverageTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        self.paths = [root / x for x in (
            "ranking.csv", "births.csv", "prior.csv", "new.csv",
            "rescues.csv", "crossdisc.csv", "v4_manifest.json", "out")]
        (self.roster, self.bios, self.prior, self.new,
         self.rescues, self.crossdisc, self.manifest, self.out) = self.paths
        self.ranking = []
        self.prior_rules = []
        self.new_rules = []

        for n in range(14):
            prof = f"isufs{1000+n:08d}"
            old, canon, partner = f"old_{n}", f"canon_{n}", f"partner_{n}"
            for yr, a, name in (
                ("2018-19", old, f"Old Name {n}"),
                ("2022-23", canon, f"Canonical Name {n}"),
            ):
                self.ranking.append(dict(
                    discipline="Ice Dance", person_a_id=a,
                    person_b_id=partner, person_a_name=name,
                    person_b_name=f"Partner {n}", pair_id=f"pair_{yr}_{n}",
                    season=yr, profile_url=f"https://results.isu.org/bios/{prof}.htm"))
            if n < 6:
                self.prior_rules.append(dict(
                    scope="modern", discipline="Ice Dance",
                    alternate_person_id=old, canonical_person_id=canon,
                    expected_dob="1998-01-01",
                    evidence_status="source_reviewed_name_alias"))
            else:
                self.new_rules.append(dict(
                    discipline="Ice Dance", alternate_person_id=old,
                    canonical_person_id=canon, official_profile_id=prof,
                    member_side="1", date_of_birth="1998-01-01",
                    official_bio_url=f"https://results.isu.org/bios/{prof}.htm",
                    evidence_status="source_reviewed_same_profile_side"))

        def extra(pid, disc, other, profile, season):
            self.ranking.append(dict(
                discipline=disc, person_a_id=other, person_b_id=pid,
                person_a_name=other, person_b_name=pid,
                pair_id=f"pair_{disc}_{season}_{other}",
                season=season,
                profile_url=f"https://results.isu.org/bios/{profile}.htm"))
        extra("alex", "Ice Dance", "Sophia BUSHELL", "isufs00111279", "2022-23")
        extra("alex", "Pair Skating", "Zarah WOOD", "isufs00119902", "2025-26")
        self.ranking.append(dict(
            discipline="Pair Skating", person_a_id="lonely", person_b_id="other",
            person_a_name="Unlisted SKATER", person_b_name="Another SKATER",
            pair_id="no_profile", season="2024-25", profile_url=""))

        def birth(pid, profile, dob, side="1", status="exact_name_match"):
            return dict(profile_id=profile,
                        profile_url=f"https://results.isu.org/bios/{profile}.htm",
                        side_on_profile=side, observed_name=pid, person_id=pid,
                        date_of_birth=dob, status=status,
                        name_match_method="exact")
        self.bios_rows = [
            birth("old_0", "isufs00001000", "1998-01-01"),
            birth("old_2", "isufs00001002", "1998-01-01"),
            birth("canon_2", "isufs00001002", "1998-01-02"),
            birth("alex", "isufs00111279", "2003-03-09", "2"),
            birth("alex", "isufs00119902", "2003-03-09", "2"),
        ]
        self.rescue_rows = [dict(
            discipline="Ice Dance", modern_provisional_id="old_1",
            modern_roster_name="Old Name 1", modern_partner_name="Partner 1",
            source_profile_side="1", expected_dob="1998-01-01",
            official_dob_source_url="https://results.isu.org/bios/isufs00001001.htm")]
        self.cross_rows = [dict(
            person_id="alex", published_name="alex",
            discipline_a="Ice Dance", profile_id_a="isufs00111279",
            partner_a="Sophia BUSHELL",
            discipline_b="Pair Skating", profile_id_b="isufs00119902",
            partner_b="Zarah WOOD", official_date_of_birth="2003-03-09",
            official_url_a="https://results.isu.org/bios/isufs00111279.htm",
            official_url_b="https://results.isu.org/bios/isufs00119902.htm",
            review_status="source_reviewed_same_skater_cross_discipline"))
        self.save()

    def save(self):
        for path, table in (
            (self.roster, self.ranking),
            (self.bios, self.bios_rows),
            (self.prior, self.prior_rules),
            (self.new, self.new_rules),
            (self.rescues, self.rescue_rows),
            (self.crossdisc, self.cross_rows)):
            write_csv(path, table)
        all_ids = {r[key] for r in self.ranking for key in ("person_a_id", "person_b_id")}
        self.manifest.write_text(json.dumps({
            "input_sha256": {
                r"output\master\season_roster.csv":
                    hashlib.sha256(self.roster.read_bytes()).hexdigest(),
            },
            "projected_unique_modern_person_name_ids": len(all_ids) - 14,
            "modern_raw_name_ids": len(all_ids),
        }), encoding="utf-8")

    def run_audit(self):
        return audit(self.roster, self.bios, self.prior, self.new,
                     self.rescues, self.crossdisc, self.manifest, self.out)

    def test_source_coverage_conflicts_missing_and_verified_discipline_switch(self):
        original_roster = self.roster.read_bytes()
        result = self.run_audit()
        self.assertEqual(result["approved_alias_rules"], 14)
        self.assertEqual(result["cross_discipline_identities_source_reviewed"], 1)
        self.assertEqual(result["cross_discipline_identities_unreviewed"], 0)
        self.assertEqual(result["canonical_conflicting_dob"], 1)
        self.assertGreater(result["canonical_missing_dob"], 0)
        self.assertEqual(result["manually_curated_dob_rescues"], 1)
        self.assertEqual(self.roster.read_bytes(), original_roster)
        rows = load(self.out / "modern_canonical_dob_coverage_v5.csv",
                    ("canonical_person_id", "dob_status"))
        keyed = {r["canonical_person_id"]: r for r in rows}
        self.assertEqual(keyed["canon_0"]["accepted_dob"], "1998-01-01")
        self.assertEqual(keyed["canon_1"]["accepted_dob"], "1998-01-01")
        self.assertEqual(keyed["canon_2"]["dob_status"], "DOB_CONFLICT_HOLD")
        self.assertEqual(keyed["alex"]["cross_discipline_status"],
                         "APPROVED_CROSS_DISCIPLINE")
        self.assertEqual(keyed["alex"]["accepted_dob"], "2003-03-09")
        self.assertEqual(keyed["lonely"]["review_priority"],
                         "MISSING_BIOGRAPHY_URL_IN_RANKING")

    def test_bio_wrong_profile_side_is_review_not_promoted(self):
        self.bios_rows[0]["side_on_profile"] = "2"
        self.save()
        s = self.run_audit()
        self.assertGreater(s["rejected_or_review_bio_rows"], 0)
        rejected = load(self.out / "modern_biography_source_rejections_v5.csv",
                        ("issue",))
        self.assertIn("BIO_PROFILE_SIDE_NOT_IN_ORIGINAL_ROSTER",
                      {r["issue"] for r in rejected})

    def test_cross_discipline_partner_mismatch_rejected(self):
        self.cross_rows[0]["partner_b"] = "Another PARTNER"
        self.save()
        with self.assertRaisesRegex(ValueError, "cross-discipline pairing absent"):
            self.run_audit()

    def test_reject_stale_roster_hash(self):
        self.roster.write_bytes(self.roster.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "different ranking roster"):
            self.run_audit()

    def test_source_ledger_has_reviewed_lapsky_switch(self):
        rows = load(ROOT / "data/adjudications/isu_modern_cross_discipline_skater_v1.csv",
                    ("person_id", "discipline_a", "discipline_b",
                     "official_date_of_birth"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["person_id"], "person_91c889ad86ae8")
        self.assertEqual(rows[0]["official_date_of_birth"], "2003-03-09")


if __name__ == "__main__":
    unittest.main()
