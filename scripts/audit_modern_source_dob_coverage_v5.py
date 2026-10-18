#!/usr/bin/env python3
"""Conservative modern ISU official-DOB coverage QA after 14 reviewed name aliases.

Inputs remain immutable. Distinguish direct biography rows, eight manually
curated official ISU DOB rescue records and the independently reviewed
Alex LAPSKY discipline switch. Do not use historical DOB alone to fill
modern entries. Never auto-merge different people or compute BaZi.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROSTER = Path("output/master/season_roster.csv")
BIOS = Path("output/bios/birth_candidates.csv")
PREVIOUS = Path("data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv")
ADDITIONAL = Path("data/adjudications/isu_modern_same_profile_aliases_v1.csv")
RESCUES = Path("data/adjudications/isu_cross_era_modern_bio_dob_rescues_v1.csv")
CROSSDISC = Path("data/adjudications/isu_modern_cross_discipline_skater_v1.csv")
V4 = Path("output/historic_dob/cross_era_identity/modern_profile_v4/modern_profile_alias_source_manifest_v4.json")
OUT = Path("output/historic_dob/modern_dob_coverage_v5")
HOSTS = {"results.isu.org", "www.isuresults.com"}
PROFILE = re.compile(r"^/bios/(isufs[0-9]+)\.htm$", re.IGNORECASE)
DETAILS = [
    "canonical_person_id", "original_modern_person_ids", "published_names",
    "disciplines", "observed_seasons", "roster_rows", "profile_ids",
    "accepted_dob", "dob_status", "official_dob_source_urls",
    "dob_evidence_kinds", "accepted_source_record_count",
    "cross_discipline_status", "review_priority",
]
REJECTIONS = [
    "profile_id", "person_id", "status", "observed_name",
    "date_of_birth", "source_url", "issue",
]
PROFILE_GAPS = [
    "discipline", "profile_id", "side_on_profile", "roster_person_ids",
    "roster_names", "bios_row_present", "bio_exact_source_accepted",
    "status",
]


def load(path, keys):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(keys) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing CSV columns: {sorted(missing)}")
        return list(reader)


def output(path, rows, keys):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_date(s):
    try:
        d = date.fromisoformat(s)
        return bool(s and d.isoformat() == s and 1850 <= d.year <= date.today().year)
    except (TypeError, ValueError):
        return False


def profile_id(url):
    u = urlsplit(url or "")
    if (u.scheme not in ("http", "https") or u.hostname not in HOSTS
            or u.username or u.password or u.port is not None
            or u.query or u.fragment):
        return ""
    m = PROFILE.fullmatch(u.path)
    return m.group(1).lower() if m else ""


def official_source(url):
    u = urlsplit(url or "")
    if (u.scheme != "https" or u.username or u.password or
            u.port is not None or u.query or u.fragment):
        return False
    if u.hostname in HOSTS:
        return bool(PROFILE.fullmatch(u.path))
    if u.hostname in ("isu-skating.com", "www.isu-skating.com"):
        return u.path.startswith("/en/figure-skating/skaters/")
    return False


def join(values):
    return "; ".join(sorted(set(x for x in values if x)))


def audit(roster_path=ROSTER, bios_path=BIOS, previous_path=PREVIOUS,
          additional_path=ADDITIONAL, rescue_path=RESCUES,
          crossdisc_path=CROSSDISC, v4_path=V4, out_dir=OUT):
    paths = [roster_path, bios_path, previous_path, additional_path,
             rescue_path, crossdisc_path, v4_path]
    rows = load(roster_path, (
        "discipline", "person_a_id", "person_b_id", "person_a_name",
        "person_b_name", "pair_id", "season", "profile_url"))
    bios = load(bios_path, (
        "profile_id", "profile_url", "side_on_profile", "person_id",
        "observed_name", "date_of_birth", "status"))
    prior = load(previous_path, (
        "scope", "discipline", "canonical_person_id",
        "alternate_person_id", "evidence_status", "expected_dob"))
    extra = load(additional_path, (
        "discipline", "canonical_person_id", "alternate_person_id",
        "official_profile_id", "member_side", "date_of_birth",
        "evidence_status", "official_bio_url"))
    rescues = load(rescue_path, (
        "discipline", "modern_provisional_id", "modern_roster_name",
        "modern_partner_name", "source_profile_side", "expected_dob",
        "official_dob_source_url"))
    cross = load(crossdisc_path, (
        "person_id", "published_name", "discipline_a", "profile_id_a",
        "partner_a", "discipline_b", "profile_id_b", "partner_b",
        "official_date_of_birth", "official_url_a", "official_url_b",
        "review_status"))
    with Path(v4_path).open("r", encoding="utf-8") as f:
        prior_manifest = json.load(f)
    manifest_roster_hash = next(
        (v for k, v in prior_manifest.get("input_sha256", {}).items()
         if k.replace("\\", "/").lower().endswith("output/master/season_roster.csv")),
        None,
    )
    if manifest_roster_hash != digest(roster_path):
        raise ValueError("v4 modern profile manifest uses a different ranking roster")

    alias = {}
    aliases_by_disc = {}
    modern_prior = [r for r in prior if r["scope"] == "modern"]
    for r in modern_prior:
        if r["evidence_status"] != "source_reviewed_name_alias" or not valid_date(r["expected_dob"]):
            raise ValueError("Previously accepted modern alias is invalid")
        a, b = r["alternate_person_id"], r["canonical_person_id"]
        if a in alias:
            raise ValueError("Duplicated modern alias")
        alias[a] = b
        aliases_by_disc[a] = r["discipline"]
    for r in extra:
        if (r["evidence_status"] != "source_reviewed_same_profile_side" or
                not valid_date(r["date_of_birth"]) or
                not official_source(r["official_bio_url"]) or
                profile_id(r["official_bio_url"]) != r["official_profile_id"].lower()):
            raise ValueError("New reviewed modern name alias has malformed DOB or ISU profile")
        a, b = r["alternate_person_id"], r["canonical_person_id"]
        if a in alias:
            raise ValueError("Duplicated modern alias")
        alias[a] = b
        aliases_by_disc[a] = r["discipline"]
    if (len(modern_prior) != 6 or len(extra) != 8 or
            len(alias) != 14 or len(set(alias.values())) != 14 or
            set(alias).intersection(alias.values())):
        raise ValueError("Modern profile v4's 14 aliases are not disjoint and complete")

    modern = defaultdict(lambda: {
        "names": set(), "disciplines": set(), "original_ids": set(),
        "seasons": set(), "profiles": set(), "rows": set(),
    })
    roster_sides = defaultdict(lambda: {"ids": set(), "names": set()})
    memberships = defaultdict(set)
    raw_ids = set()
    for i, r in enumerate(rows):
        d = r["discipline"]
        if (not d or not r["person_a_id"] or not r["person_b_id"] or
                r["person_a_id"] == r["person_b_id"]):
            raise ValueError("Modern ranking has malformed pair members")
        pid = profile_id(r["profile_url"])
        for side, ident, name in (
            ("1", r["person_a_id"], r["person_a_name"]),
            ("2", r["person_b_id"], r["person_b_name"]),
        ):
            raw_ids.add(ident)
            memberships[(d, ident)].add((side, name, r["person_b_name"] if side == "1" else r["person_a_name"], pid))
            if ident in aliases_by_disc and aliases_by_disc[ident] != d:
                raise ValueError("Reviewed alias ID unexpectedly appears in a different discipline")
            canon = alias.get(ident, ident)
            modern[canon]["names"].add(name)
            modern[canon]["disciplines"].add(d)
            modern[canon]["original_ids"].add(ident)
            modern[canon]["seasons"].add(r["season"])
            modern[canon]["rows"].add(i)
            if pid:
                modern[canon]["profiles"].add(pid)
                roster_sides[(d, pid, side)]["ids"].add(ident)
                roster_sides[(d, pid, side)]["names"].add(name)
    if (len(modern) != prior_manifest.get("projected_unique_modern_person_name_ids") or
            len(raw_ids) != prior_manifest.get("modern_raw_name_ids")):
        raise ValueError("Modern name IDs differ from approved v4 identity projection")
    if any(a not in raw_ids or b not in raw_ids for a, b in alias.items()):
        raise ValueError("Source-reviewed alias does not belong to ranking roster")

    accepted = defaultdict(set)
    source_types = defaultdict(set)
    source_urls = defaultdict(set)
    direct_accepted_sides = set()
    observed_sides = set()
    rejected = []

    def add(ident, dob, uri, kind):
        canon = alias.get(ident, ident)
        if canon not in modern:
            raise ValueError("Official DOB evidence references unknown modern person")
        accepted[canon].add((dob, uri, kind))
        source_types[canon].add(kind)
        source_urls[canon].add(uri)

    for b in bios:
        id_, p, side = b["person_id"], b["profile_id"].lower(), b["side_on_profile"]
        status = b["status"]
        profile = profile_id(b["profile_url"])
        if p and side in ("1", "2"):
            observed_sides.add((p, side))
        issue = ""
        if status != "exact_name_match":
            issue = "BIO_NOT_EXACT_NAME_MATCH"
        elif (not valid_date(b["date_of_birth"]) or
                (b.get("name_match_method") or "exact") not in
                ("exact", "roster_confirmed_country_suffix")):
            issue = "BIO_DATE_OR_MATCH_METHOD_INVALID"
        elif (not id_ or id_ not in raw_ids or not profile or
                p != profile or side not in ("1", "2")):
            issue = "BIO_ID_PROFILE_OR_SIDE_MALFORMED"
        elif id_ not in roster_sides.get((
                next((d for d in modern[alias.get(id_, id_)]["disciplines"]
                      if id_ in roster_sides.get((d, p, side), {}).get("ids", set())), ""),
                p, side), {}).get("ids", set()):
            issue = "BIO_PROFILE_SIDE_NOT_IN_ORIGINAL_ROSTER"
        if issue:
            rejected.append({
                "profile_id": p, "person_id": id_, "status": status,
                "observed_name": b["observed_name"],
                "date_of_birth": b["date_of_birth"],
                "source_url": b["profile_url"], "issue": issue,
            })
            continue
        add(id_, b["date_of_birth"], b["profile_url"], "BIO_EXACT_ROSTER_PROFILE")
        direct_accepted_sides.add((p, side))

    curated_used = set()
    for r in rescues:
        d, id_, side = r["discipline"], r["modern_provisional_id"], r["source_profile_side"]
        marker = (d, id_)
        if marker in curated_used or not valid_date(r["expected_dob"]) or not official_source(r["official_dob_source_url"]):
            raise ValueError("Invalid or duplicate reviewed DOB rescue")
        curated_used.add(marker)
        if (side, r["modern_roster_name"], r["modern_partner_name"],
            next(iter(memberships.get(marker, {("", "", "", "")})))[3]) not in memberships.get(marker, set()):
            # Check exact roster side/name/partner, independent of biography URL.
            if not any((s, n, partner) == (
                    side, r["modern_roster_name"], r["modern_partner_name"])
                    for s, n, partner, _ in memberships.get(marker, set())):
                raise ValueError("Curated DOB rescue lacks a matching modern roster side/partner")
        add(id_, r["expected_dob"], r["official_dob_source_url"],
            "SOURCE_REVIEWED_BIO_RESCUE")

    approved_crossdisc = set()
    for r in cross:
        id_ = r["person_id"]
        if (id_ in approved_crossdisc or id_ not in raw_ids or
                r["review_status"] != "source_reviewed_same_skater_cross_discipline" or
                not valid_date(r["official_date_of_birth"]) or
                not official_source(r["official_url_a"]) or
                not official_source(r["official_url_b"]) or
                profile_id(r["official_url_a"]) != r["profile_id_a"] or
                profile_id(r["official_url_b"]) != r["profile_id_b"]):
            raise ValueError("Unreviewed or invalid cross-discipline skater source record")
        approved_crossdisc.add(id_)
        expected = (
            (r["discipline_a"], r["profile_id_a"], r["partner_a"]),
            (r["discipline_b"], r["profile_id_b"], r["partner_b"]),
        )
        if r["discipline_a"] == r["discipline_b"]:
            raise ValueError("Cross-discipline review actually contains one discipline")
        for d, prof, partner in expected:
            if not any(name == r["published_name"] and other == partner and link == prof
                       for _, name, other, link in memberships.get((d, id_), set())):
                raise ValueError("Official cross-discipline pairing absent from ranking roster")
        if set(modern[alias.get(id_, id_)]["disciplines"]) != {
                r["discipline_a"], r["discipline_b"]}:
            raise ValueError("Cross-discipline source member has unexpected disciplines")
        for url in (r["official_url_a"], r["official_url_b"]):
            add(id_, r["official_date_of_birth"], url,
                "SOURCE_REVIEWED_CROSS_DISCIPLINE_ISU")

    summary_rows, missing_rows = [], []
    crossdisc_unreviewed = []
    kinds = Counter()
    for canon, info in sorted(modern.items()):
        dates = {dob for dob, _, _ in accepted[canon]}
        multi = len(info["disciplines"]) > 1
        crossstatus = ("APPROVED_CROSS_DISCIPLINE" if multi and
                       info["original_ids"].intersection(approved_crossdisc)
                       else "UNREVIEWED_CROSS_DISCIPLINE_HOLD" if multi else "SINGLE_DISCIPLINE")
        if crossstatus == "UNREVIEWED_CROSS_DISCIPLINE_HOLD":
            crossdisc_unreviewed.append(canon)
        status = ("DOB_CONFLICT_HOLD" if len(dates) > 1 else
                  "DOB_MISSING" if not dates else
                  "DOB_PRESENT_CROSS_DISCIPLINE_REVIEW_HOLD"
                  if crossstatus == "UNREVIEWED_CROSS_DISCIPLINE_HOLD" else
                  "SOURCE_LINKED_DOB_IN_PREVIEW")
        if len(dates) > 1:
            priority = "DOB_SOURCE_CONFLICT"
        elif crossstatus == "UNREVIEWED_CROSS_DISCIPLINE_HOLD":
            priority = "CROSS_DISCIPLINE_IDENTITY_REVIEW"
        elif not dates and not info["profiles"]:
            priority = "MISSING_BIOGRAPHY_URL_IN_RANKING"
        elif not dates and not info["profiles"].intersection(
                set(p for p, side in observed_sides)):
            priority = "PROFILE_NOT_IN_BIOGRAPHY_EXTRACT"
        elif not dates:
            priority = "BIOGRAPHY_PERSON_MATCH_REVIEW"
        else:
            priority = "NONE"
        rec = {
            "canonical_person_id": canon,
            "original_modern_person_ids": join(info["original_ids"]),
            "published_names": join(info["names"]),
            "disciplines": join(info["disciplines"]),
            "observed_seasons": join(info["seasons"]),
            "roster_rows": len(info["rows"]),
            "profile_ids": join(info["profiles"]),
            "accepted_dob": next(iter(dates)) if len(dates) == 1 else "",
            "dob_status": status,
            "official_dob_source_urls": join(source_urls[canon]),
            "dob_evidence_kinds": join(source_types[canon]),
            "accepted_source_record_count": len(accepted[canon]),
            "cross_discipline_status": crossstatus,
            "review_priority": priority,
        }
        kinds[status] += 1
        summary_rows.append(rec)
        if priority != "NONE":
            missing_rows.append(rec)
    profile_gap_rows = []
    for (d, p, side), info in sorted(roster_sides.items()):
        observed = (p, side) in observed_sides
        accepted_side = (p, side) in direct_accepted_sides
        profile_gap_rows.append({
            "discipline": d, "profile_id": p, "side_on_profile": side,
            "roster_person_ids": join(info["ids"]),
            "roster_names": join(info["names"]),
            "bios_row_present": "YES" if observed else "NO",
            "bio_exact_source_accepted": "YES" if accepted_side else "NO",
            "status": ("EXACT_OFFICIAL_BIO" if accepted_side else
                       "BIO_SIDE_PRESENT_REQUIRES_REVIEW" if observed
                       else "BIO_SIDE_NOT_IN_EXTRACT"),
        })

    out = Path(out_dir)
    output(out / "modern_canonical_dob_coverage_v5.csv", summary_rows, DETAILS)
    output(out / "modern_dob_missing_and_conflicts_v5.csv", missing_rows, DETAILS)
    output(out / "modern_biography_source_rejections_v5.csv", rejected, REJECTIONS)
    output(out / "modern_biography_profile_side_gaps_v5.csv", profile_gap_rows, PROFILE_GAPS)
    report = {
        "stage": "modern_source_reviewed_dob_coverage_audit_v5_not_frozen",
        "source_modern_roster_rows": len(rows),
        "source_modern_name_ids": len(raw_ids),
        "approved_alias_rules": len(alias),
        "canonical_modern_identity_name_ids": len(modern),
        "canonical_with_one_source_linked_dob": kinds["SOURCE_LINKED_DOB_IN_PREVIEW"],
        "canonical_missing_dob": kinds["DOB_MISSING"],
        "canonical_conflicting_dob": kinds["DOB_CONFLICT_HOLD"],
        "cross_discipline_identities_source_reviewed": len(approved_crossdisc),
        "cross_discipline_identities_unreviewed": len(crossdisc_unreviewed),
        "canonical_coverage_fraction": round(kinds["SOURCE_LINKED_DOB_IN_PREVIEW"] / len(modern), 6),
        "accepted_direct_bio_rows": sum(1 for b in bios if b["status"] == "exact_name_match") -
                                    sum(1 for b in rejected if b["status"] == "exact_name_match"),
        "rejected_or_review_bio_rows": len(rejected),
        "manually_curated_dob_rescues": len(curated_used),
        "ranking_profile_sides": len(profile_gap_rows),
        "ranked_profile_sides_without_direct_accepted_bio": sum(
            r["bio_exact_source_accepted"] == "NO" for r in profile_gap_rows),
        "priority_queue_counts": dict(sorted(Counter(r["review_priority"] for r in missing_rows).items())),
        "dob_status_counts": dict(sorted(kinds.items())),
        "input_sha256": {str(path): digest(path) for path in paths},
        "limitations": [
            "Canonical ID counts are source-reviewed name-ID preview counts, not a verified census of natural people",
            "Exact biography DOB evidence is accepted only when matching the original roster profile/side",
            "Manual source-review DOB rescues are separate evidence and do not silently replace unmatched biography parses",
            "Two ISU-host URLs of the same profile do not represent independent DOB replication",
            "Cross-discipline same-name IDs are not assumed to be one person without explicit source audit",
            "No demographic/geographic birth-place inference, performance selection, BaZi or null model",
        ],
    }
    (out / "modern_dob_coverage_manifest_v5.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--bios", type=Path, default=BIOS)
    p.add_argument("--prior", type=Path, default=PREVIOUS)
    p.add_argument("--additional", type=Path, default=ADDITIONAL)
    p.add_argument("--rescues", type=Path, default=RESCUES)
    p.add_argument("--crossdisc", type=Path, default=CROSSDISC)
    p.add_argument("--modern-v4-manifest", type=Path, default=V4)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    audit(args.roster, args.bios, args.prior, args.additional, args.rescues,
          args.crossdisc, args.modern_v4_manifest, args.out)


if __name__ == "__main__":
    main()
