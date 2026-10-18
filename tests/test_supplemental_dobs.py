"""No-network tests for conservative supplemental ISU DOB application."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from apply_isu_supplemental_dobs import apply_supplemental_dobs
from audit_isu_identities import read_csv


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class SupplementalDobTests(unittest.TestCase):
    def setUp(self):
        ctx = tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        base = Path(ctx.name)
        self.people = base / "people.csv"
        self.evidence = base / "evidence.csv"
        self.out = base / "out"
        self.people_rows = [
            dict(canonical_person_id="p1", roster_names="Karina AKAPOVA",
                 date_of_birth="", dob_status="no_verified_bio"),
            dict(canonical_person_id="p2", roster_names="Sam HERBERT",
                 date_of_birth="", dob_status="no_verified_bio"),
            dict(canonical_person_id="p3", roster_names="Alice SMITH",
                 date_of_birth="2000-01-01", dob_status="consistent"),
        ]
        self.sources = [
            dict(canonical_person_id="p1", roster_name="Karina AKAPOVA",
                 date_of_birth="2003-06-16", official_observed_name="Karina AKOPOVA",
                 evidence_status="official_isu_checked",
                 source_url="https://www.isuresults.com/bios/isufs00107342.htm",
                 identity_basis="same_pair_name_variant",
                 evidence_note="same partner"),
            dict(canonical_person_id="p2", roster_name="Sam HERBERT",
                 date_of_birth="", official_observed_name="Sam HERBERT",
                 evidence_status="pending_primary_source",
                 source_url="https://example.com/unknown",
                 identity_basis="unconfirmed", evidence_note="no official date"),
        ]
        self.save()

    def save(self):
        write_rows(self.people, self.people_rows)
        write_rows(self.evidence, self.sources)

    def test_accept_official_hold_pending_preserve_original(self):
        before = self.people.read_bytes()
        result = apply_supplemental_dobs(self.people, self.evidence, self.out)
        self.assertEqual(result["new_official_dobs_accepted"], 1)
        self.assertEqual(result["pending_primary_verification"], 1)
        self.assertEqual(result["people_with_consistent_dob_after"], 2)
        self.assertEqual(self.people.read_bytes(), before)
        rows = {r["canonical_person_id"]: r for r in read_csv(
            self.out / "identity_canonical_people_supplemented.csv")}
        self.assertEqual(rows["p1"]["date_of_birth"], "2003-06-16")
        self.assertEqual(rows["p1"]["dob_status"], "consistent")
        self.assertEqual(rows["p2"]["date_of_birth"], "")
        self.assertEqual(rows["p2"]["supplemental_source_url"], "")

    def test_unknown_or_wrong_roster_name_rejected(self):
        self.sources[0]["roster_name"] = "Karina DIFFERENT"
        self.save()
        with self.assertRaisesRegex(ValueError, "identity/name mismatch"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)

    def test_nonofficial_source_cannot_auto_fill(self):
        self.sources[0]["source_url"] = "https://unofficial.example.org/bio"
        self.save()
        with self.assertRaisesRegex(ValueError, "not on ISU"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)

    def test_official_federation_pdf_accepted_and_keeps_cyrillic_name(self):
        self.people_rows[1]["roster_names"] = "Daniil RAGIMOV"
        self.sources[1] = dict(
            canonical_person_id="p2", roster_name="Daniil RAGIMOV",
            date_of_birth="1998-05-22",
            official_observed_name="Рагимов Даниил Алексеевич",
            evidence_status="official_federation_checked",
            source_url="https://fsrussia.ru/files/docs/RUteam1516.pdf",
            identity_basis="former_pair_russian_federation_team_roster",
            evidence_note="Signed federation team roster",
        )
        self.save()
        result = apply_supplemental_dobs(self.people, self.evidence, self.out)
        self.assertEqual(result["new_official_dobs_accepted"], 2)
        self.assertEqual(result["pending_primary_verification"], 0)
        self.assertEqual(result["people_with_consistent_dob_after"], 3)
        records = {r["canonical_person_id"]: r for r in
                   read_csv(self.out / "identity_canonical_people_supplemented.csv")}
        self.assertEqual(records["p2"]["date_of_birth"], "1998-05-22")
        self.assertEqual(records["p2"]["supplemental_evidence_status"],
                         "official_federation_checked")

    def test_false_federation_source_rejected(self):
        self.sources[0]["evidence_status"] = "official_federation_checked"
        self.save()
        with self.assertRaisesRegex(ValueError, "not on approved skating federation"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)

    def test_non_pdf_federation_source_rejected(self):
        self.sources[0]["evidence_status"] = "official_federation_checked"
        self.sources[0]["source_url"] = "https://ffkm.ru/athletes/profile.html"
        self.save()
        with self.assertRaisesRegex(ValueError, "official PDF"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)

    def test_existing_dob_disagreement_rejected(self):
        self.people_rows[0]["dob_status"] = "consistent"
        self.people_rows[0]["date_of_birth"] = "2003-06-15"
        self.save()
        with self.assertRaisesRegex(ValueError, "contradicts existing"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)

    def test_pending_candidate_date_must_not_be_populated(self):
        self.sources[1]["date_of_birth"] = "1998-05-22"
        self.save()
        with self.assertRaisesRegex(ValueError, "Pending source must not"):
            apply_supplemental_dobs(self.people, self.evidence, self.out)


if __name__ == "__main__":
    unittest.main()
