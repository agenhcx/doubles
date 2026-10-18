"""Offline QA for cumulative 2004-2018 skating DOB coverage.

Avoid treating same-partner calendar links and Olympedia as primary, or
merging same-name/same-profile provisional IDs automatically.
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from audit_historic_dob_coverage import coverage
from audit_isu_identities import read_csv, valid_date


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class HistoricCumulativeDobCoverageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.athletes = root / "athletes.csv"
        self.pairs = root / "pairs.csv"
        self.direct = root / "direct.csv"
        self.aliases = root / "aliases.csv"
        self.seed = root / "seed.csv"
        self.external = root / "external.csv"
        self.oldlinks = root / "oldlinks.csv"
        self.pending = root / "pending.csv"
        self.collisions = root / "collisions.csv"
        self.out = root / "out"
        self.priority = root / "priority_official.csv"
        self.ath = [
            dict(person_id="h1", name_display="Arina USHAKOVA",
                 disciplines="Ice Dance; Pair Skating"),
            dict(person_id="h2", name_display="Sergei KAREV", disciplines="Pair Skating"),
            dict(person_id="h3", name_display="Maxim NEKRASOV", disciplines="Ice Dance"),
            dict(person_id="h4", name_display="Elena EXAMPLE", disciplines="Ice Dance"),
            dict(person_id="h5", name_display="Jong SAMPLE", disciplines="Pair Skating"),
            dict(person_id="h6", name_display="Andrew CALENDAR", disciplines="Pair Skating"),
        ]
        def pair(pid, d, a, b):
            return dict(
                pair_id=pid, discipline=d, person_a_id=a, person_b_id=b,
                person_a_name=next(x["name_display"] for x in self.ath if x["person_id"] == a),
                person_b_name=next(x["name_display"] for x in self.ath if x["person_id"] == b),
                observed_seasons="2014-2015", identified_event_count="2",
            )
        self.pair_rows = [
            pair("pair-old", "Pair Skating", "h1", "h2"),
            pair("pair-young", "Ice Dance", "h1", "h3"),
            pair("pair-alias", "Ice Dance", "h4", "h3"),
            pair("pair-calendar", "Pair Skating", "h6", "h2"),
            pair("pair-secondary", "Pair Skating", "h5", "h2"),
        ]
        self.direct_rows = [
            dict(audit_person_id="arina_pairs", original_historic_person_ids="h1",
                 disciplines="Pair Skating", dob_status="consistent_source_candidate",
                 date_of_birth_candidate="1989-12-18", source_dob_values="1989-12-18",
                 source_profile_ids="isufs00008744"),
            dict(audit_person_id="arina_dance", original_historic_person_ids="h1",
                 disciplines="Ice Dance", dob_status="consistent_source_candidate",
                 date_of_birth_candidate="2002-06-27", source_dob_values="2002-06-27",
                 source_profile_ids="isufs00101140"),
            dict(audit_person_id="h2", original_historic_person_ids="h2",
                 disciplines="Pair Skating", dob_status="consistent_source_candidate",
                 date_of_birth_candidate="1986-03-31", source_dob_values="1986-03-31",
                 source_profile_ids="isufs00008744"),
            dict(audit_person_id="h3", original_historic_person_ids="h3",
                 disciplines="Ice Dance", dob_status="consistent_source_candidate",
                 date_of_birth_candidate="2000-09-27", source_dob_values="2000-09-27",
                 source_profile_ids="isufs00101140"),
        ]
        self.alias_rows = [dict(
            historic_person_id="h4", historic_pair_id="pair-alias",
            discipline="Ice Dance", profile_side="1",
            date_of_birth_candidate="2001-02-03",
            identity_evidence_status="dual_names_source_attested_pair",
            source_url="http://www.isuresults.com/bios/isufs00001002.htm",
        )]
        self.seed_rows = [dict(
            historic_person_id="h4", date_of_birth="2001-02-03",
            source_url="https://results.isu.org/bios/isufs00001002.htm",
            evidence_status="manually_checked_source"
        )]
        self.external_rows = [dict(
            historic_person_id="h5", date_of_birth_lead="1988-01-03",
            source_url="https://www.olympedia.org/athletes/12345",
            source_tier="independent_historical_secondary"
        )]
        self.oldlink_rows = [dict(
            historic_person_id=x["person_id"],
            match_status=("exact_name_same_pair" if x["person_id"] == "h6" else
                          "exact_name_only" if x["person_id"] == "h5" else
                          "unmatched_full_name"),
            ranked_dob_candidate=("1990-01-04" if x["person_id"] == "h6" else
                                   "1988-01-03" if x["person_id"] == "h5" else ""),
            identical_pair_support=("pair-calendar" if x["person_id"] == "h6" else ""),
        ) for x in self.ath]
        self.pending_rows = [dict(
            historic_pair_id="pair-calendar",
            pair_identity_status="unverified_directory_identity_candidate"
        ), dict(
            historic_pair_id="pair-secondary",
            pair_identity_status="unverified_directory_identity_candidate"
        )]
        self.collision_rows = [dict(
            profile_id="isufs00001002", side_on_profile="1",
            historic_person_ids="h4; h6"
        )]
        self.save_all()

    def save_all(self):
        for path, rows in (
            (self.athletes, self.ath), (self.pairs, self.pair_rows),
            (self.direct, self.direct_rows), (self.aliases, self.alias_rows),
            (self.seed, self.seed_rows), (self.external, self.external_rows),
            (self.oldlinks, self.oldlink_rows), (self.pending, self.pending_rows),
            (self.collisions, self.collision_rows),
        ):
            save(path, rows)

    def audit(self):
        return coverage(
            self.athletes, self.pairs, self.direct, self.aliases,
            self.seed, self.external, self.oldlinks, self.pending,
            self.collisions, self.out
        )

    def test_split_official_alias_calendar_secondary_and_pair_coverage(self):
        raw = self.athletes.read_bytes()
        result = self.audit()
        self.assertEqual(result["historical_original_provisional_ids"], 6)
        self.assertEqual(result["historical_audit_identity_slots_before_alias_merges"], 7)
        self.assertEqual(result["confirmed_homonym_splits_extra_slots"], 1)
        self.assertEqual(result["official_primary_dob_candidates"], 5)
        self.assertEqual(result["ranked_same_pair_only_candidates_not_promoted"], 1)
        self.assertEqual(result["secondary_only_candidates_not_promoted"], 1)
        self.assertEqual(result["source_dob_conflict_holds"], 0)
        self.assertEqual(result["pairs_with_both_primary_dobs"], 3)
        self.assertEqual(result["missing_primary_dob_slots"], 2)
        self.assertEqual(result["unresolved_alias_pairs_with_one_primary_dob"], 2)
        self.assertEqual(result["source_profile_side_alias_collision_candidates"], 1)
        self.assertEqual(raw, self.athletes.read_bytes())
        persons = {r["audit_person_id"]: r for r in
                   read_csv(self.out / "historic_dob_coverage_people_v1.csv")}
        self.assertEqual(persons["arina_pairs"]["date_of_birth_primary_candidate"],
                         "1989-12-18")
        self.assertEqual(persons["arina_dance"]["date_of_birth_primary_candidate"],
                         "2002-06-27")
        self.assertEqual(persons["h4"]["date_of_birth_primary_candidate"],
                         "2001-02-03")
        self.assertEqual(persons["h5"]["date_of_birth_primary_candidate"], "")
        self.assertEqual(persons["h5"]["secondary_dob_values"], "1988-01-03")
        self.assertEqual(persons["h6"]["date_of_birth_broad_candidate"], "1990-01-04")
        self.assertEqual(persons["h6"]["date_of_birth_primary_candidate"], "")

    def test_conflicting_primaries_do_not_get_promoted(self):
        self.seed_rows[0]["date_of_birth"] = "2001-02-04"
        self.save_all()
        result = self.audit()
        self.assertEqual(result["source_dob_conflict_holds"], 1)
        self.assertEqual(result["missing_primary_dob_slots"], 3)
        self.assertEqual(len(read_csv(
            self.out / "historic_dob_source_conflicts_v1.csv")), 1)
        missing_ids = {
            row["audit_person_id"] for row in
            read_csv(self.out / "historic_dob_missing_priority_v1.csv")
        }
        self.assertIn("h4", missing_ids)
        persons = {r["audit_person_id"]: r for r in
                   read_csv(self.out / "historic_dob_coverage_people_v1.csv")}
        self.assertEqual(persons["h4"]["date_of_birth_primary_candidate"], "")
        self.assertIn("2001-02-03", persons["h4"]["official_dob_values"])

    def test_unscoped_same_person_homonym_lead_cannot_be_applied(self):
        self.oldlink_rows[0]["match_status"] = "exact_name_same_pair"
        self.oldlink_rows[0]["ranked_dob_candidate"] = "2002-06-27"
        self.oldlink_rows[0]["identical_pair_support"] = "pair-young"
        self.save_all()
        result = self.audit()
        self.assertEqual(result["unscoped_source_rows_deferred_for_homonym_split"], 1)
        self.assertEqual(result["source_dob_conflict_holds"], 0)

    def test_untrusted_source_or_wrong_historic_member_rejected(self):
        self.alias_rows[0]["source_url"] = "https://impostor.example/bios/isufs00001002.htm"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "Non-official URL"):
            self.audit()
        self.alias_rows[0]["source_url"] = "https://results.isu.org/bios/isufs00001002.htm"
        self.alias_rows[0]["historic_person_id"] = "h5"
        self.save_all()
        with self.assertRaisesRegex(ValueError, "person disagrees"):
            self.audit()

    def test_unknown_original_identity_or_duplicate_source_person_rejected(self):
        self.ath.append(dict(self.ath[0]))
        self.save_all()
        with self.assertRaisesRegex(ValueError, "Duplicate or blank original"):
            self.audit()

    def source_priority(self, dob="1990-01-04"):
        return dict(
            historic_person_id="h6", historic_name="Andrew CALENDAR",
            date_of_birth=dob, official_observed_name="Andrew CALENDAR",
            source_url="https://results.isu.org/bios/isufs00012345.htm",
            historic_pair_id="pair-calendar",
            historic_partner_name="Sergei KAREV", discipline="Pair Skating",
            identity_basis="official_same_pair_biography",
            evidence_status="source_corroborated_official",
            review_note="Direct official birthdate with same pair context"
        )

    def audit_priority(self):
        return coverage(
            self.athletes, self.pairs, self.direct, self.aliases,
            self.seed, self.external, self.oldlinks, self.pending,
            self.collisions, self.out, self.priority
        )

    def test_priority_official_dob_promotes_matching_ranked_candidate(self):
        save(self.priority, [self.source_priority()])
        snapshot = self.athletes.read_bytes()
        report = self.audit_priority()
        self.assertEqual(report["priority_official_source_records"], 1)
        self.assertEqual(report["priority_official_unique_historic_ids"], 1)
        self.assertEqual(report["official_primary_dob_candidates"], 6)
        self.assertEqual(report["ranked_same_pair_only_candidates_not_promoted"], 0)
        self.assertEqual(report["missing_primary_dob_slots"], 1)
        self.assertEqual(report["pairs_with_both_primary_dobs"], 4)
        self.assertEqual(snapshot, self.athletes.read_bytes())
        people = {x["audit_person_id"]: x for x in
                  read_csv(self.out / "historic_dob_coverage_people_v1.csv")}
        self.assertEqual(people["h6"]["date_of_birth_primary_candidate"], "1990-01-04")
        self.assertIn("isufs00012345", people["h6"]["source_urls"])

    def test_priority_official_date_disagreement_is_a_conflict_not_an_overwrite(self):
        save(self.priority, [self.source_priority("1990-01-05")])
        report = self.audit_priority()
        self.assertEqual(report["source_dob_conflict_holds"], 1)
        self.assertEqual(report["missing_primary_dob_slots"], 2)
        conflict = read_csv(self.out / "historic_dob_source_conflicts_v1.csv")
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0]["audit_person_id"], "h6")

    def test_priority_pair_member_or_partner_identity_mismatch_rejected(self):
        row = self.source_priority()
        row["historic_partner_name"] = "Different PARTNER"
        save(self.priority, [row])
        with self.assertRaisesRegex(ValueError, "partnership/discipline mismatch"):
            self.audit_priority()
        row["historic_partner_name"] = "Sergei KAREV"
        row["historic_person_id"] = "h5"
        save(self.priority, [row])
        with self.assertRaisesRegex(ValueError, "not in referenced historic pair"):
            self.audit_priority()

    def test_priority_untrusted_official_domain_and_repeated_id_rejected(self):
        row = self.source_priority()
        row["source_url"] = "https://results.isu.org.evil.example/bios/isufs00012345.htm"
        save(self.priority, [row])
        with self.assertRaisesRegex(ValueError, "not a trusted official ISU"):
            self.audit_priority()
        row["source_url"] = "https://results.isu.org/bios/isufs00012345.htm"
        save(self.priority, [row, dict(row)])
        with self.assertRaisesRegex(ValueError, "Duplicated reviewed priority"):
            self.audit_priority()

    def test_reviewed_priority_catalog_uses_real_historic_ids_and_official_urls(self):
        original = {r["person_id"]: r for r in
                    read_csv(ROOT / "data/historic/v4/athletes_v4.csv")}
        pairs = {r["pair_id"]: r for r in
                 read_csv(ROOT / "data/historic/v4/couples_v4.csv")}
        evidence = read_csv(ROOT /
            "data/adjudications/isu_historic_priority_dob_sources_v1.csv")
        self.assertEqual(len(evidence), 43)
        self.assertEqual(len({r["historic_person_id"] for r in evidence}), 43)
        for item in evidence:
            self.assertIn(item["historic_person_id"], original)
            self.assertEqual(item["historic_name"],
                             original[item["historic_person_id"]]["name_display"])
            self.assertIn(item["historic_pair_id"], pairs)
            pair = pairs[item["historic_pair_id"]]
            self.assertIn(item["historic_person_id"], {
                pair["person_a_id"], pair["person_b_id"]})
            self.assertEqual(item["historic_partner_name"],
                pair["person_b_name"] if item["historic_person_id"] ==
                pair["person_a_id"] else pair["person_a_name"])
            self.assertTrue(item["source_url"].startswith("https://"))
            self.assertTrue(valid_date(item["date_of_birth"]))

    def test_real_historic_source_has_expected_schema_and_source_tiers(self):
        p = ROOT / "data/adjudications/isu_historic_external_dob_leads_v1.csv"
        evidence = read_csv(p)
        self.assertEqual(len(evidence), 2)
        self.assertEqual({r["source_tier"] for r in evidence}, {
            "primary_isu_separate_singles_biography",
            "independent_historical_secondary"
        })


if __name__ == "__main__":
    unittest.main()
