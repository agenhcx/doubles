#!/usr/bin/env python3
"""Non-destructive v6 modern DOB source augmentation.

Apply a versioned, manually sourced ledger of 28 missing DOBs to the v5
canonical-name-ID coverage PREVIEW. Check input lineage, exact roster
member/partner, source URLs and dates; do NOT infer DOBs from name similarity.
No changes to masters, original Biography extracts or v5 outputs. Offline
validation does NOT refetch or independently verify web page content.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(".")
V5 = ROOT / "output/historic_dob/modern_dob_coverage_v5"
MANIFEST = V5 / "modern_dob_coverage_manifest_v5.json"
CANONICAL = V5 / "modern_canonical_dob_coverage_v5.csv"
MISSING = V5 / "modern_dob_missing_and_conflicts_v5.csv"
ROSTER = ROOT / "output/master/season_roster.csv"
LEDGER = ROOT / "data/adjudications/isu_modern_dob_official_missing_rescues_v6.csv"
OUTPUT = ROOT / "output/historic_dob/modern_dob_rescue_v6"

REQUIRED_LEDGER = [
    "canonical_person_id", "published_roster_name", "discipline",
    "roster_partner_name", "roster_member_side", "verified_date_of_birth",
    "official_printed_name", "primary_official_source_url",
    "identity_context_source_url", "source_tier", "review_status",
    "source_review_note",
]
ORIGINAL_FIELDS = [
    "canonical_person_id", "original_modern_person_ids", "published_names",
    "disciplines", "observed_seasons", "roster_rows", "profile_ids",
    "accepted_dob", "dob_status", "official_dob_source_urls",
    "dob_evidence_kinds", "accepted_source_record_count",
    "cross_discipline_status", "review_priority",
]
ADDED = [
    "pre_v6_dob_status", "v6_evidence_source_tier",
    "v6_official_printed_name", "v6_context_url", "v6_source_review_note",
]
ALLOWED_TIERS = {
    "ISU_SAME_PAIR_BIO", "ISU_SAME_PROFILE_NAME_VARIANT",
    "ISU_PREVIOUS_SINGLE_AND_PAIR_BIO",
    "NATIONAL_FEDERATION_ROSTER_PLUS_COMPETITION",
    "ISU_PREVIOUS_PARTNER_BIO", "ISU_SAME_PAIR_PROFILE_VARIANT",
}
ISU_HOSTS = {"results.isu.org", "www.isuresults.com",
             "isu-skating.com", "www.isu-skating.com"}
PROFILE_PATH = re.compile(r"^/bios/isufs[0-9]+\.htm$", re.IGNORECASE)


def read(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        cols = list(reader.fieldnames or [])
        absent = set(required) - set(cols)
        if absent:
            raise ValueError(f"{path}: required columns missing {sorted(absent)}")
        return list(reader), cols


def write(path, records, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pieces(value):
    return {p.strip() for p in (value or "").split(";") if p.strip()}


def joined(items):
    return "; ".join(sorted(set(x for x in items if x)))


def valid_date(value):
    try:
        parsed = date.fromisoformat(value)
        return bool(value and parsed.isoformat() == value and
                    1850 <= parsed.year <= date.today().year)
    except (ValueError, TypeError):
        return False


def allowed_url(url, tier):
    if not url:
        return False
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username or
            u.password or u.port is not None or u.query or u.fragment):
        return False
    if tier == "NATIONAL_FEDERATION_ROSTER_PLUS_COMPETITION":
        return (u.hostname == "fsrussia.ru" and
                u.path == "/files/docs/RUteam1516.pdf")
    if u.hostname in {"results.isu.org", "www.isuresults.com"}:
        return bool(PROFILE_PATH.fullmatch(u.path))
    if u.hostname in {"isu-skating.com", "www.isu-skating.com"}:
        return (u.path.startswith("/en/figure-skating/skaters/") and
                u.path.endswith("/"))
    return False


def context_url_ok(url):
    if not url:
        return True
    u = urlsplit(url)
    if (u.scheme != "https" or u.username or u.password or
            u.port is not None or u.query or u.fragment):
        return False
    return ((u.hostname in ISU_HOSTS and
             (bool(PROFILE_PATH.fullmatch(u.path)) or
              u.path.startswith("/en/figure-skating/skaters/"))) or
            (u.hostname == "fsrussia.ru" and
             u.path.startswith("/files/docs/competitons/") and
             u.path.endswith(".pdf")))


def audit(manifest_path=MANIFEST, canonical_path=CANONICAL,
          missing_path=MISSING, roster_path=ROSTER,
          ledger_path=LEDGER, out_dir=OUTPUT):
    with Path(manifest_path).open(encoding="utf-8") as stream:
        baseline = json.load(stream)
    if baseline.get("stage") != "modern_source_reviewed_dob_coverage_audit_v5_not_frozen":
        raise ValueError("Source manifest does not belong to modern DOB v5")
    expected_roster_hash = next(
        (h for p, h in baseline.get("input_sha256", {}).items()
         if p.replace("\\", "/").lower().endswith("output/master/season_roster.csv")),
        None)
    if expected_roster_hash != sha(roster_path):
        raise ValueError("Modern roster changed since v5 audit; rerun v5")
    canonical, columns = read(canonical_path, ORIGINAL_FIELDS)
    missing, _ = read(missing_path, ORIGINAL_FIELDS)
    roster, _ = read(roster_path, (
        "person_a_id", "person_b_id", "person_a_name", "person_b_name", "discipline"))
    ledger, _ = read(ledger_path, REQUIRED_LEDGER)
    if not all((canonical, missing, roster, ledger)):
        raise ValueError("One or more required v5/v6 files are empty")
    if (len(canonical) != baseline.get("canonical_modern_identity_name_ids") or
            len(missing) != baseline.get("canonical_missing_dob") or
            baseline.get("canonical_conflicting_dob") != 0):
        raise ValueError("Source v5 DOB summary no longer matches original reviewed inputs")

    roster_members = defaultdict(set)
    for r in roster:
        disc = r["discipline"]
        for ident, side, name, partner in (
            (r["person_a_id"], "1", r["person_a_name"], r["person_b_name"]),
            (r["person_b_id"], "2", r["person_b_name"], r["person_a_name"]),
        ):
            roster_members[(disc, ident)].add((side, name, partner))

    original = {}
    for rec in canonical:
        ident = rec["canonical_person_id"]
        if not ident or ident in original:
            raise ValueError("Repeated or empty canonical modern person ID in v5")
        original[ident] = rec
    missing_ids = set()
    for rec in missing:
        ident = rec["canonical_person_id"]
        if ident in missing_ids or ident not in original or rec["dob_status"] != "DOB_MISSING":
            raise ValueError("Missing queue contains duplicate, unknown or nonmissing person ID")
        if rec["accepted_dob"] or original[ident]["dob_status"] != "DOB_MISSING":
            raise ValueError("DOB v5 missing queue does not agree with original canonical row")
        missing_ids.add(ident)

    by_id = {}
    for r in ledger:
        ident = r["canonical_person_id"]
        if not ident or ident in by_id or ident not in missing_ids:
            raise ValueError("Curated source is duplicate, unknown, or no longer DOB missing")
        if (r["source_tier"] not in ALLOWED_TIERS or
                r["review_status"] != "source_reviewed_dob_evidence" or
                not valid_date(r["verified_date_of_birth"]) or
                not r["official_printed_name"] or
                len(r["source_review_note"].strip()) < 85 or
                not allowed_url(r["primary_official_source_url"], r["source_tier"]) or
                not context_url_ok(r["identity_context_source_url"])):
            raise ValueError("Incomplete or invalid source-specific curated DOB evidence for " + ident)
        if r["source_tier"] == "NATIONAL_FEDERATION_ROSTER_PLUS_COMPETITION":
            if (not r["identity_context_source_url"].startswith(
                    "https://fsrussia.ru/files/docs/competitons/") or
                    r["verified_date_of_birth"] != "1998-05-22"):
                raise ValueError("National federation Ragimov identity bridge missing")
        old = original[ident]
        if r["published_roster_name"] not in pieces(old["published_names"]):
            raise ValueError("Published name does not belong to v5 canonical identity: " + ident)
        if r["discipline"] not in pieces(old["disciplines"]):
            raise ValueError("Reviewed discipline disagrees with original modern identity")
        side = r["roster_member_side"]
        if (side, r["published_roster_name"], r["roster_partner_name"]) not in (
                roster_members.get((r["discipline"], ident), set())):
            if not any(
                (side, r["published_roster_name"], r["roster_partner_name"]) in
                roster_members.get((r["discipline"], orig), set())
                for orig in pieces(old["original_modern_person_ids"])
            ):
                raise ValueError("Source review does not match original roster role and partner")
        if r["source_tier"] == "ISU_SAME_PROFILE_NAME_VARIANT":
            primary = urlsplit(r["primary_official_source_url"]).path
            match = PROFILE_PATH.fullmatch(primary)
            if not match or primary.split("/")[-1].lower().removesuffix(".htm") not in pieces(old["profile_ids"]):
                raise ValueError("Bio name variant does not match exact original profile")
        by_id[ident] = r

    if set(by_id) != missing_ids:
        raise ValueError("Curated DOB ledger does not exactly cover the v5 missing-ID queue")
    output_rows = []
    audit_rows = []
    for old in canonical:
        rec = dict(old)
        ident = old["canonical_person_id"]
        if ident in by_id:
            r = by_id[ident]
            rec["pre_v6_dob_status"] = rec["dob_status"]
            rec["accepted_dob"] = r["verified_date_of_birth"]
            rec["dob_status"] = ("SOURCE_REVIEWED_NATIONAL_FEDERATION_DOB_PREVIEW"
                                 if r["source_tier"].startswith("NATIONAL_") else
                                 "SOURCE_REVIEWED_ISU_DOB_PREVIEW")
            rec["official_dob_source_urls"] = joined(
                pieces(rec["official_dob_source_urls"]) | {r["primary_official_source_url"]})
            rec["dob_evidence_kinds"] = joined(
                pieces(rec["dob_evidence_kinds"]) | {r["source_tier"]})
            rec["accepted_source_record_count"] = int(rec["accepted_source_record_count"]) + 1
            rec["review_priority"] = "NONE"
            rec["v6_evidence_source_tier"] = r["source_tier"]
            rec["v6_official_printed_name"] = r["official_printed_name"]
            rec["v6_context_url"] = r["identity_context_source_url"]
            rec["v6_source_review_note"] = r["source_review_note"]
            audit_rows.append({**r, "offline_identity_and_source_schema_check":
                               "PASSED_OFFLINE_SOURCE_NOT_REFETCHED"})
        output_rows.append(rec)
    statuses = Counter(r["dob_status"] for r in output_rows)
    missing_after = sum(not r["accepted_dob"] for r in output_rows)
    conflict_after = sum("CONFLICT" in r["dob_status"] for r in output_rows)
    if (len(output_rows) != len(canonical) or missing_after or conflict_after or
            len(audit_rows) != len(missing_ids)):
        raise ValueError("Source-augmented preview did not close expected DOB gaps")

    out = Path(out_dir)
    write(out / "modern_canonical_dob_source_augmented_v6.csv",
          output_rows, columns + ADDED)
    write(out / "modern_official_dob_rescue_adjudication_v6.csv",
          audit_rows, REQUIRED_LEDGER + ["offline_identity_and_source_schema_check"])
    report = {
        "stage": "modern_official_source_dob_coverage_v6_preview_not_frozen",
        "source_v5_canonical_name_id_count": len(canonical),
        "source_v5_direct_or_previously_curated_dob": baseline["canonical_with_one_source_linked_dob"],
        "source_v5_dob_missing": len(missing_ids),
        "v6_reviewed_source_rescue_rows": len(audit_rows),
        "v6_covered_canonical_name_id_slots": len(output_rows) - missing_after,
        "v6_remaining_missing_dob_slots": missing_after,
        "v6_dob_conflict_slots": conflict_after,
        "v6_dob_coverage_fraction": round((len(output_rows) - missing_after) / len(output_rows), 6),
        "v6_source_tier_counts": dict(sorted(Counter(r["source_tier"] for r in ledger).items())),
        "v6_national_federation_source_rows": sum(
            r["source_tier"].startswith("NATIONAL_") for r in ledger),
        "input_sha256": {str(p): sha(p) for p in (
            manifest_path, canonical_path, missing_path, roster_path, ledger_path)},
        "limitations": [
            "All 1036 are reviewed canonical name-ID slots, not necessarily 1036 independently proven natural people",
            "All 28 sources were manually reviewed; this offline script checks exact roster lineage, not fresh web page contents",
            "Russian federation source is marked separately from ISU biography evidence",
            "DOB from a re-used ISU profile or its mirror is not independent replication",
            "Source-augmented CSV only: original v5 source files, ranking records, historical data and masters are not modified",
            "Official date completeness in the reviewed roster does not imply full competition-entry or birthplace coverage",
            "No BaZi, null models, performance-conditioned selection or statistical claims",
        ],
    }
    (out / "modern_official_dob_rescue_manifest_v6.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--canonical", type=Path, default=CANONICAL)
    p.add_argument("--missing", type=Path, default=MISSING)
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--ledger", type=Path, default=LEDGER)
    p.add_argument("--out", type=Path, default=OUTPUT)
    args = p.parse_args()
    audit(args.manifest, args.canonical, args.missing, args.roster,
          args.ledger, args.out)


if __name__ == "__main__":
    main()
