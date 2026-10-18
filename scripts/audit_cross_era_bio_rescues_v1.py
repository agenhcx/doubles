#!/usr/bin/env python3
"""Audit 8+ source-reviewed modern ISU DOB misses without rewriting any master.

This verifies identity/partner lineage and exact historic DOB against a
manual ISU evidence ledger, then writes a separate source-augmented preview.
The validator does NOT fetch websites or independently attest page contents.
No auto-merges, competition-result aggregation, or BaZi calculations.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(".")
DEFAULT_REVIEW = Path("output/historic_dob/cross_era_identity/historic_modern_identity_review_v1.csv")
DEFAULT_MANIFEST = Path("output/historic_dob/cross_era_identity/historic_modern_cross_era_manifest_v1.json")
DEFAULT_ROSTER = Path("output/master/season_roster.csv")
DEFAULT_SOURCES = Path("data/adjudications/isu_cross_era_modern_bio_dob_rescues_v1.csv")
DEFAULT_OUT = Path("output/historic_dob/cross_era_identity/official_bio_rescue")
SOURCE_COLS = [
    "discipline", "historic_projected_id", "modern_provisional_id",
    "modern_roster_name", "modern_partner_name", "source_profile_side",
    "expected_dob", "source_printed_name", "official_dob_source_url",
    "official_context_url", "source_review_note",
]
HOSTS = {
    "results.isu.org", "www.isuresults.com",
    "isu-skating.com", "www.isu-skating.com",
}
MISSING = {
    "NAME_MATCH_MODERN_DOB_MISSING_REVIEW",
    "SAME_PAIR_MODERN_DOB_MISSING_REVIEW",
}
ADDED = [
    "pre_rescue_review_status", "curated_dob_source_url",
    "curated_source_printed_name", "curated_context_url",
    "curated_review_note", "dob_evidence_origin",
]


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_csv(p, required):
    with Path(p).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        absent = set(required) - set(cols)
        if absent:
            raise ValueError(f"{p}: missing columns {sorted(absent)}")
        return list(reader), list(cols)


def write_csv(p, data, cols):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def valid_date(s):
    try:
        return date.fromisoformat(s).isoformat() == s and bool(s)
    except (ValueError, TypeError):
        return False


def source_url_ok(s, primary):
    if not s and not primary:
        return True
    u = urlsplit(s)
    if (u.scheme != "https" or u.hostname not in HOSTS or
            u.username is not None or u.password is not None or
            u.port is not None or u.query or u.fragment):
        return False
    if not primary:
        return bool(u.path and u.path != "/")
    if u.hostname in {"results.isu.org", "www.isuresults.com"}:
        return bool(re.fullmatch(r"/bios/isufs[0-9]+\.htm", u.path, re.I))
    return bool(re.fullmatch(
        r"/en/figure-skating/skaters/pairs/[a-z0-9-]+/", u.path))


def split_values(s):
    return {v.strip() for v in (s or "").split(";") if v.strip()}


def audit(review_path=DEFAULT_REVIEW, manifest_path=DEFAULT_MANIFEST,
          roster_path=DEFAULT_ROSTER, source_path=DEFAULT_SOURCES,
          out_dir=DEFAULT_OUT):
    review, review_fields = read_csv(review_path, (
        "discipline", "historic_projected_id", "modern_provisional_id",
        "historic_dob", "modern_official_dob", "modern_bio_urls",
        "cross_era_same_pair", "evidence_flags", "identity_review_status",
        "ambiguity_status"))
    roster, _ = read_csv(roster_path, (
        "discipline", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name", "season", "profile_url"))
    sources, _ = read_csv(source_path, SOURCE_COLS)
    if not review or not roster or not sources:
        raise ValueError("Cross-era review, modern roster and official source ledger must not be empty")
    with Path(manifest_path).open(encoding="utf-8") as f:
        previous_manifest = json.load(f)
    hashes = {k.replace("\\", "/").lower(): v
              for k, v in previous_manifest.get("inputs_sha256", {}).items()}
    original_roster_hash = next(
        (v for k, v in hashes.items() if k.endswith("output/master/season_roster.csv")),
        None)
    if not original_roster_hash or original_roster_hash != digest(roster_path):
        raise ValueError("Cross-era manifest roster SHA disagrees with current modern roster; rerun v1")
    if previous_manifest.get("historic_modern_person_candidate_edges") != len(review):
        raise ValueError("Original cross-era review row count disagrees with its manifest")

    indexed = {}
    for i, r in enumerate(review):
        key = (r["discipline"], r["historic_projected_id"],
               r["modern_provisional_id"])
        if not all(key) or key in indexed:
            raise ValueError("Duplicate or incomplete historic-modern candidate")
        indexed[key] = i

    roster_lookup = {}
    for r in roster:
        for side, name, partner, pid in (
            ("1", r["person_a_name"], r["person_b_name"], r["person_a_id"]),
            ("2", r["person_b_name"], r["person_a_name"], r["person_b_id"]),
        ):
            key = (r["discipline"], pid)
            roster_lookup.setdefault(key, set()).add((side, name, partner))

    additional = []
    seen = set()
    for s in sources:
        key = (s["discipline"], s["historic_projected_id"],
               s["modern_provisional_id"])
        if not all(key) or key in seen:
            raise ValueError("Blank or repeated review ledger key")
        seen.add(key)
        if key not in indexed:
            raise ValueError("Curated source is not scoped to an existing cross-era candidate: " + repr(key))
        original = review[indexed[key]]
        if (original["identity_review_status"] not in MISSING or
                original["modern_official_dob"]):
            raise ValueError("Curated source may only repair a genuinely missing modern DOB")
        if (not valid_date(s["expected_dob"]) or
                original["historic_dob"] != s["expected_dob"]):
            raise ValueError("Curated DOB differs from audited historical DOB")
        if (not source_url_ok(s["official_dob_source_url"], True) or
                not source_url_ok(s["official_context_url"], False)):
            raise ValueError("Malformed or non-ISU official source URL")
        if (not s["source_printed_name"] or
                len(s["source_review_note"].strip()) < 45):
            raise ValueError("Source-specific observed name and review note required")
        if s["source_profile_side"] not in {"1", "2"}:
            raise ValueError("Invalid source member side")
        members = roster_lookup.get((s["discipline"], s["modern_provisional_id"]), set())
        if (s["source_profile_side"], s["modern_roster_name"],
                s["modern_partner_name"]) not in members:
            raise ValueError("Source-side/name/partner contradict modern ranking record")

        updated = review[indexed[key]]
        updated["pre_rescue_review_status"] = updated["identity_review_status"]
        updated["modern_official_dob"] = s["expected_dob"]
        updated["modern_bio_urls"] = "; ".join(sorted(
            split_values(updated["modern_bio_urls"]) | {s["official_dob_source_url"]}))
        updated["evidence_flags"] = "; ".join(sorted(
            split_values(updated["evidence_flags"]) |
            {"SOURCE_REVIEWED_ISU_BIO_NAME_VARIANT"}))
        updated["identity_review_status"] = (
            "SOURCE_REVIEWED_DOB_AGREES_AND_SAME_PAIR_REVIEW"
            if updated["cross_era_same_pair"] == "YES" else
            "SOURCE_REVIEWED_DOB_AGREES_IDENTITY_REVIEW")
        updated["curated_dob_source_url"] = s["official_dob_source_url"]
        updated["curated_source_printed_name"] = s["source_printed_name"]
        updated["curated_context_url"] = s["official_context_url"]
        updated["curated_review_note"] = s["source_review_note"]
        updated["dob_evidence_origin"] = "MANUALLY_CURATED_OFFICIAL_ISU_BIO"
        additional.append({**s, "local_audit_status":
                           "LINEAGE_AND_DATE_VALIDATED_PAGE_NOT_REFETCHED"})

    columns = review_fields + [x for x in ADDED if x not in review_fields]
    out = Path(out_dir)
    write_csv(out / "historic_modern_identity_source_augmented_v1.csv", review, columns)
    write_csv(out / "historic_modern_curated_bio_rescue_audit_v1.csv",
              additional, SOURCE_COLS + ["local_audit_status"])
    missing_after = sum(not r["modern_official_dob"] for r in review)
    counts = Counter(r["identity_review_status"] for r in review)
    stats = {
        "stage": "historic_modern_bio_rescue_preview_not_a_frozen_cohort",
        "cross_era_candidate_edges_unchanged": len(review),
        "original_modern_dob_missing_edges": missing_after + len(additional),
        "source_reviewed_dob_rescue_edges": len(additional),
        "remaining_modern_dob_missing_edges": missing_after,
        "dob_present_after_source_review": len(review) - missing_after,
        "cross_era_ambiguous_edges_still_held": sum(
            r["ambiguity_status"] != "NONE" for r in review),
        "review_status_counts": dict(sorted(counts.items())),
        "inputs_sha256": {
            str(review_path): digest(review_path),
            str(manifest_path): digest(manifest_path),
            str(roster_path): digest(roster_path),
            str(source_path): digest(source_path),
        },
        "limitations": [
            "Manual ISU page content was reviewed when creating the versioned ledger, NOT refetched by this offline script",
            "DOB filling changes only a separate preview, never original bio CSV, master, or historic source",
            "A matching date from the same original ISU record is NOT independent corroboration",
            "An evidence edge with DOB agreement is not an approved cross-era real-person identity merger",
            "One-to-many ambiguities and graph clusters remain held for review",
            "No performance-based selection, result-count aggregation, BaZi, or null model",
        ],
    }
    (out / "historic_modern_bio_rescue_manifest_v1.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--modern", type=Path, default=DEFAULT_ROSTER)
    p.add_argument("--curated", type=Path, default=DEFAULT_SOURCES)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = p.parse_args()
    audit(a.review, a.manifest, a.modern, a.curated, a.out)


if __name__ == "__main__":
    main()
