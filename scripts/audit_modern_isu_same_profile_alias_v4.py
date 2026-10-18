#!/usr/bin/env python3
"""Versioned modern ISU Biography-ID/side alias projection (8 new + 6 prior).

Use the locked 2018-26 season-ranking input to detect when one ISU
biography member-side is assigned multiple provisional name-derived IDs.
Apply ONLY existing six source-reviewed modern alias rules plus eight
new source-reviewed per-profile rules. Preserve every source ranking row,
pair ID, season and original name, and never add ranking/event metrics.

The cross-era v3 candidate edge file is rekeyed as a preview only.
No birthdate inference, statistical test, BaZi, master mutation or sample freeze.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

MODERN = Path("output/master/season_roster.csv")
OLD_RULES = Path("data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv")
NEW_RULES = Path("data/adjudications/isu_modern_same_profile_aliases_v1.csv")
V3_MANIFEST = Path("output/historic_dob/cross_era_identity/ambiguity_source_v3/cross_era_source_reviewed_identity_manifest_v1.json")
V3_CROSS = Path("output/historic_dob/cross_era_identity/ambiguity_source_v3/source_reviewed_cross_era_canonical_candidates_v1.csv")
OUT = Path("output/historic_dob/cross_era_identity/modern_profile_v4")
HOSTS = {"results.isu.org", "www.isuresults.com"}
PROFILE = re.compile(r"^/bios/(isufs\d+)\.htm$", re.IGNORECASE)

FIELDS = [
    "rule_id", "discipline", "official_profile_id", "member_side",
    "canonical_person_id", "alternate_person_id",
    "canonical_published_name", "alternate_published_name",
    "date_of_birth", "official_bio_url", "evidence_status",
    "source_review_note",
]
PERSON_FIELDS = [
    "discipline", "original_modern_person_id", "canonical_modern_person_id",
    "original_published_names", "seasons", "official_profile_ids",
    "reviewed_alias_rule_id", "identity_projection_status",
]
PAIR_FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "original_pair_ids", "season_ranking_rows",
    "observed_seasons", "official_profile_ids", "status",
]
COLLISION_FIELDS = [
    "discipline", "official_profile_id", "member_side",
    "original_person_ids", "published_names", "seasons",
    "source_reviewed_rule_ids", "review_status",
]
CROSS_FIELDS = [
    "discipline", "historic_projected_id",
    "prior_modern_person_id_v3", "new_modern_person_id_v4",
    "historic_dob", "modern_official_dob",
    "original_candidate_edge_count", "original_modern_person_ids",
    "old_modern_published_names", "all_source_reviewed_modern_names",
    "source_reviewed_rule_ids", "cross_era_identity_status",
]


def read(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing required fields {sorted(missing)}")
        return list(reader)


def write(path, records, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split(v):
    return {x.strip() for x in (v or "").split(";") if x.strip()}


def join(seq):
    return "; ".join(sorted(set(x for x in seq if x)))


def profile_id(s):
    p = urlsplit(s or "")
    if p.hostname not in HOSTS or p.username or p.password or p.port is not None:
        return None
    m = PROFILE.fullmatch(p.path)
    return m.group(1).lower() if m else None


def official_profile(s, expected):
    p = urlsplit(s)
    return (p.scheme == "https" and p.hostname in HOSTS and
            not p.username and not p.password and p.port is None and
            not p.query and not p.fragment and
            profile_id(s) == expected.lower())


def date_ok(s):
    try:
        return bool(s) and date.fromisoformat(s).isoformat() == s
    except (TypeError, ValueError):
        return False


def audit(modern_path=MODERN, previous_rules_path=OLD_RULES,
          new_rules_path=NEW_RULES, v3_manifest_path=V3_MANIFEST,
          v3_cross_path=V3_CROSS, out_dir=OUT):
    roster = read(modern_path, (
        "discipline", "pair_id", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name", "season", "profile_url"))
    prior = read(previous_rules_path, (
        "rule_id", "scope", "discipline", "canonical_person_id",
        "alternate_person_id", "evidence_status", "expected_dob"))
    extra = read(new_rules_path, FIELDS)
    cross = read(v3_cross_path, (
        "discipline", "historic_projected_id", "modern_provisional_id",
        "historic_dob", "modern_official_dob", "original_candidate_edge_count",
        "modern_names", "original_modern_person_ids",
        "source_reviewed_rule_ids", "cross_era_identity_status"))
    if not all((roster, prior, extra, cross)):
        raise ValueError("One of the four required source tables is empty")
    with Path(v3_manifest_path).open(encoding="utf-8") as f:
        history = json.load(f)
    old_hash = next((
        v for k, v in history.get("source_hashes", {}).items()
        if k.replace("\\", "/").lower().endswith("output/master/season_roster.csv")
    ), None)
    if old_hash != sha(modern_path):
        raise ValueError("Modern roster changed since v3 reviewed cross-era projection")
    if history.get("normalized_cross_era_candidate_groups") != len(cross):
        raise ValueError("v3 cross-era preview row count differs from its verified manifest")

    profiles = defaultdict(lambda: defaultdict(lambda: {
        "names": set(), "seasons": set()}))
    member = defaultdict(lambda: {"names": set(), "seasons": set(), "profiles": set()})
    raw_ids = set()
    raw_pairs = set()
    for row in roster:
        d, a, b = row["discipline"], row["person_a_id"], row["person_b_id"]
        if not d or not a or not b or a == b or not row["pair_id"]:
            raise ValueError("Modern ranking contains a malformed team or missing ID")
        raw_pairs.add((d, a, b))
        prof = profile_id(row["profile_url"])
        for side, id_, name in (("1", a, row["person_a_name"]),
                                ("2", b, row["person_b_name"])):
            raw_ids.add(id_)
            member[(d, id_)]["names"].add(name)
            member[(d, id_)]["seasons"].add(row["season"])
            if prof:
                member[(d, id_)]["profiles"].add(prof)
                entry = profiles[(d, prof, side)][id_]
                entry["names"].add(name)
                entry["seasons"].add(row["season"])
    # A current ISU duo profile ID/side collision is not itself approval;
    # the approved ledger must cover each affected original ID explicitly.
    collisions = {
        key: ids for key, ids in profiles.items() if len(ids) > 1
    }

    modern_alias = {}
    rule_for_alternate = {}
    modern_prior = [r for r in prior if r["scope"] == "modern"]
    if len(modern_prior) != 6 or len(extra) != 8:
        raise ValueError("Expected exactly 6 existing and 8 new source-reviewed modern alias links")
    for r in modern_prior:
        if r["evidence_status"] != "source_reviewed_name_alias":
            raise ValueError("Prior alias was not source-reviewed")
        a, b = r["alternate_person_id"], r["canonical_person_id"]
        if ((r["discipline"], a) not in member or
                (r["discipline"], b) not in member or not date_ok(r["expected_dob"])):
            raise ValueError("Prior alias person IDs or source DOB absent")
        if a in modern_alias:
            raise ValueError("Prior modern alias repeated")
        modern_alias[a] = b
        rule_for_alternate[a] = r["rule_id"]

    new_rule_ids = set()
    for r in extra:
        key = (r["discipline"], r["official_profile_id"].lower(), r["member_side"])
        alt, canon = r["alternate_person_id"], r["canonical_person_id"]
        if (r["rule_id"] in new_rule_ids or
                r["evidence_status"] != "source_reviewed_same_profile_side" or
                r["member_side"] not in {"1", "2"} or
                not re.fullmatch(r"isufs\d+", r["official_profile_id"], re.I) or
                not date_ok(r["date_of_birth"]) or
                not official_profile(r["official_bio_url"], r["official_profile_id"]) or
                len(r["source_review_note"].strip()) < 70):
            raise ValueError("Malformed or unreviewed official modern Biography-side rule")
        new_rule_ids.add(r["rule_id"])
        matching = profiles.get(key)
        if (not matching or set(matching) != {alt, canon} or
                r["canonical_published_name"] not in matching[canon]["names"] or
                r["alternate_published_name"] not in matching[alt]["names"]):
            raise ValueError("Source-reviewed name/role/profile differs from modern roster")
        if (alt in modern_alias or canon in modern_alias or
                alt in modern_alias.values() or canon in modern_alias.values()):
            raise ValueError("Repeated or chained modern identity aliases")
        modern_alias[alt] = canon
        rule_for_alternate[alt] = r["rule_id"]

    if len(modern_alias) != 14 or len(set(modern_alias.values())) != 14:
        raise ValueError("Expected fourteen disjoint source-reviewed modern alias ID mappings")
    resolved = []
    for (disc, prof, side), ids in sorted(collisions.items()):
        canon = {modern_alias.get(id_, id_) for id_ in ids}
        if len(canon) != 1:
            raise ValueError("Same-Biography-side duplicate remains without a reviewed identity mapping")
        rules = {rule_for_alternate[id_] for id_ in ids if id_ in rule_for_alternate}
        resolved.append({
            "discipline": disc, "official_profile_id": prof, "member_side": side,
            "original_person_ids": join(ids),
            "published_names": join(n for x in ids.values() for n in x["names"]),
            "seasons": join(s for x in ids.values() for s in x["seasons"]),
            "source_reviewed_rule_ids": join(rules),
            "review_status": "SOURCE_REVIEWED_SAME_PROFILE_SIDE_ALIAS_IN_PREVIEW",
        })

    by_person_id = defaultdict(list)
    for (disc, id_), entry in member.items():
        by_person_id[id_].append((disc, entry))
    person_preview = []
    for id_, occurrences in sorted(by_person_id.items()):
        for disc, entry in occurrences:
            person_preview.append({
                "discipline": disc,
                "original_modern_person_id": id_,
                "canonical_modern_person_id": modern_alias.get(id_, id_),
                "original_published_names": join(entry["names"]),
                "seasons": join(entry["seasons"]),
                "official_profile_ids": join(entry["profiles"]),
                "reviewed_alias_rule_id": rule_for_alternate.get(id_, ""),
                "identity_projection_status": (
                    "SOURCE_REVIEWED_ALIAS_TO_CANONICAL_PREVIEW" if id_ in modern_alias
                    else "UNCHANGED_PROVISIONAL_MODERN_NAME_ID"),
            })

    canonical_pairs = defaultdict(list)
    for row in roster:
        a = modern_alias.get(row["person_a_id"], row["person_a_id"])
        b = modern_alias.get(row["person_b_id"], row["person_b_id"])
        if a == b:
            raise ValueError("Modern source alias would create self-pair")
        canonical_pairs[(row["discipline"], a, b)].append(row)
    pairs_output = [{
        "discipline": d, "projected_person_a_id": a,
        "projected_person_b_id": b,
        "original_pair_ids": join(x["pair_id"] for x in items),
        "season_ranking_rows": len(items),
        "observed_seasons": join(x["season"] for x in items),
        "official_profile_ids": join(
            profile_id(x["profile_url"]) for x in items),
        "status": "SOURCE_REVIEWED_MODERN_ID_PREVIEW_NO_RANK_AGGREGATION",
    } for (d, a, b), items in sorted(canonical_pairs.items())]

    revised_cross = []
    rekeyed = set()
    for r in cross:
        canon = modern_alias.get(r["modern_provisional_id"], r["modern_provisional_id"])
        key = (r["discipline"], r["historic_projected_id"], canon)
        if key in rekeyed:
            raise ValueError("v4 source review creates duplicate cross-era candidate edge requiring new adjudication")
        rekeyed.add(key)
        merged_names = set(split(r["modern_names"]))
        merged_names.update(member.get((r["discipline"], canon), {}).get("names", set()))
        revised_cross.append({
            "discipline": r["discipline"],
            "historic_projected_id": r["historic_projected_id"],
            "prior_modern_person_id_v3": r["modern_provisional_id"],
            "new_modern_person_id_v4": canon,
            "historic_dob": r["historic_dob"],
            "modern_official_dob": r["modern_official_dob"],
            "original_candidate_edge_count": r["original_candidate_edge_count"],
            "original_modern_person_ids": r["original_modern_person_ids"],
            "old_modern_published_names": r["modern_names"],
            "all_source_reviewed_modern_names": join(merged_names),
            "source_reviewed_rule_ids": join(
                split(r["source_reviewed_rule_ids"]) |
                ({rule_for_alternate[r["modern_provisional_id"]]}
                 if r["modern_provisional_id"] in rule_for_alternate else set())),
            "cross_era_identity_status": "NAME_ALIAS_ONLY_CROSS_ERA_REMAINS_CANDIDATE",
        })
    if len(revised_cross) != len(cross):
        raise ValueError("Cross-era review edges unexpectedly added or lost")

    out = Path(out_dir)
    write(out / "modern_same_profile_collision_review_v1.csv", resolved, COLLISION_FIELDS)
    write(out / "modern_source_reviewed_person_id_projection_v4.csv", person_preview, PERSON_FIELDS)
    write(out / "modern_source_reviewed_pair_preview_v4.csv", pairs_output, PAIR_FIELDS)
    write(out / "cross_era_modern_alias_source_preview_v4.csv", revised_cross, CROSS_FIELDS)
    report = {
        "stage": "modern_isu_profile_side_source_reviewed_alias_v4_not_frozen",
        "ranking_source_rows_unchanged": len(roster),
        "modern_raw_name_ids": len(raw_ids),
        "modern_source_reviewed_alias_rules": len(modern_alias),
        "modern_aliases_from_existing_cross_era_v3": len(modern_prior),
        "additional_profile_side_source_reviewed_aliases": len(extra),
        "modern_profile_side_duplicate_id_groups": len(collisions),
        "modern_profile_side_groups_after_review_with_unresolved_id_collision": 0,
        "projected_unique_modern_person_name_ids": len({modern_alias.get(i, i) for i in raw_ids}),
        "original_modern_pair_name_groups": len(raw_pairs),
        "projected_modern_pair_groups": len(pairs_output),
        "source_v3_cross_era_candidate_edges": len(cross),
        "source_v4_rekeyed_cross_era_candidate_edges": len(revised_cross),
        "input_sha256": {str(p): sha(p) for p in (
            modern_path, previous_rules_path, new_rules_path,
            v3_manifest_path, v3_cross_path)},
        "limitations": [
            "Every modern name ID remains in an original source ranking row; alias changes are reversible previews",
            "The single source-side Biography and DOB evidence is not independent replication",
            "Profile ID plus member-side is only a candidate generator; every alias applied here is source-reviewed",
            "Other cross-profile aliases and same-name homonyms can remain undiscovered",
            "All rankings and scores remain untouched and are NOT aggregated here",
            "The cross-era 183 rekeyed edges still require identity/cohort QA",
            "No astrology, performance-based sample selection or statistical inference",
        ],
    }
    (out / "modern_profile_alias_source_manifest_v4.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modern", type=Path, default=MODERN)
    p.add_argument("--prior", type=Path, default=OLD_RULES)
    p.add_argument("--new", type=Path, default=NEW_RULES)
    p.add_argument("--v3-manifest", type=Path, default=V3_MANIFEST)
    p.add_argument("--v3-cross", type=Path, default=V3_CROSS)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    audit(a.modern, a.prior, a.new, a.v3_manifest, a.v3_cross, a.out)


if __name__ == "__main__":
    main()
