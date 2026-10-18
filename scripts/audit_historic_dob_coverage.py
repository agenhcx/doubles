#!/usr/bin/env python3
"""Conservative 2004–2018 ISU historic DOB coverage audit.

Combine the official historic biography audit, source-correlated alias
biographies, independently reviewed old source seeds and (optionally)
corroborated 2018+ same-pair leads. ALL identities stay provisional.
No original files are modified. No BaZi, matchmaking or null computation.

The one source-proven Arina USHAKOVA collision is represented by two
audited person slots; same-profile-side aliases are NOT merged.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, joined, read_csv, valid_date, write_csv

OFFICIAL_HOSTS = {
    "results.isu.org", "www.isuresults.com",
    "isu-skating.com", "www.isu-skating.com",
    "ffkm.ru", "www.ffkm.ru", "fsrussia.ru", "www.fsrussia.ru"
}
BASE = Path(__file__).resolve().parent.parent
PERSON_FIELDS = (
    "audit_person_id", "original_historic_person_id", "historic_name",
    "disciplines", "source_types", "official_dob_values", "same_pair_ranked_dob_values",
    "secondary_dob_values", "date_of_birth_primary_candidate",
    "date_of_birth_broad_candidate", "dob_coverage_status",
    "source_urls", "ranked_pair_link_status", "historic_pair_count",
)
PAIR_FIELDS = (
    "pair_id", "discipline", "person_a_id", "person_b_id",
    "audit_person_a_id", "audit_person_b_id", "person_a_name",
    "person_b_name", "person_a_primary_dob", "person_b_primary_dob",
    "primary_dob_members", "broad_dob_members",
    "pair_dob_status", "observed_seasons", "identified_event_count",
)
CONFLICT_FIELDS = (
    "audit_person_id", "original_historic_person_id", "source_types",
    "official_dob_values", "same_pair_ranked_dob_values", "secondary_dob_values",
    "source_urls", "conflict_reason"
)


def fields(rows, required, name):
    if not rows:
        raise ValueError(name + " has no rows")
    missing = set(required) - set(rows[0])
    if missing:
        raise ValueError(name + " missing columns " + repr(sorted(missing)))


def src_is_official(url):
    u = urlsplit(url)
    return (u.scheme in {"http", "https"} and u.hostname in OFFICIAL_HOSTS
            and u.username is None and u.password is None
            and u.port is None and not u.query and not u.fragment)


def split_values(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def coverage(
    athletes_path="data/historic/v4/athletes_v4.csv",
    pairs_path="data/historic/v4/couples_v4.csv",
    direct_path="output/historic_dob/identity/historic_audited_people.csv",
    alias_path="output/historic_dob/alias_pair_identity/historic_alias_correlated_dob_leads.csv",
    seed_path="data/adjudications/isu_historic_primary_dob_seed_v2.csv",
    external_path="data/adjudications/isu_historic_external_dob_leads_v1.csv",
    historic_links_path="output/historic_dob/historic_identity_dob_candidates.csv",
    unresolved_path="output/historic_dob/alias_pair_identity/historic_alias_unresolved_pair_review.csv",
    collisions_path="output/historic_dob/alias_pair_identity/historic_alias_profile_side_collisions.csv",
    out_dir="output/historic_dob/coverage",
):
    paths = [Path(x) for x in (
        athletes_path, pairs_path, direct_path, alias_path, seed_path,
        external_path, historic_links_path, unresolved_path, collisions_path
    )]
    original, pairs, direct, aliases, seeds, external, oldlinks, pending, collisions = [
        read_csv(path) for path in paths
    ]
    fields(original, ("person_id", "name_display", "disciplines"), "historic athletes")
    fields(pairs, ("pair_id", "person_a_id", "person_b_id", "discipline",
                   "person_a_name", "person_b_name"), "historic pair roster")
    fields(direct, ("audit_person_id", "original_historic_person_ids", "disciplines",
                    "date_of_birth_candidate", "dob_status"), "historic official biographies")
    fields(aliases, ("historic_person_id", "historic_pair_id", "discipline",
                     "profile_side", "date_of_birth_candidate", "identity_evidence_status",
                     "source_url"), "reviewed ISU alias-pair evidence")
    fields(seeds, ("historic_person_id", "date_of_birth", "source_url",
                   "evidence_status"), "hand-reviewed official DOB seeds")
    fields(external, ("historic_person_id", "date_of_birth_lead", "source_url",
                      "source_tier"), "additional DOB sources")
    fields(oldlinks, ("historic_person_id", "match_status", "ranked_dob_candidate",
                      "identical_pair_support"), "cross-era matching queue")
    fields(pending, ("historic_pair_id", "pair_identity_status"), "unresolved pairs")
    fields(collisions, ("profile_id", "side_on_profile",
                        "historic_person_ids"), "duplicate-profile-side audit")

    original_by_id = {}
    for r in original:
        person = r["person_id"]
        if not person or person in original_by_id:
            raise ValueError("Duplicate or blank original historic person ID")
        original_by_id[person] = r
    pair_by_id = {}
    adjacent = defaultdict(set)
    for r in pairs:
        pair_id = r["pair_id"]
        a, b = r["person_a_id"], r["person_b_id"]
        if (not pair_id or pair_id in pair_by_id or a == b or
                a not in original_by_id or b not in original_by_id):
            raise ValueError("Duplicate/malformed historic pair")
        pair_by_id[pair_id] = r
        adjacent[a].add(pair_id)
        adjacent[b].add(pair_id)

    # An original ID can split into multiple audited identities. The current
    # known case separates ice dance and pair skating; never choose a split
    # identity by birthday alone.
    slots = {}
    by_original = defaultdict(set)
    for r in direct:
        aid = r["audit_person_id"]
        orig_ids = split_values(r["original_historic_person_ids"])
        if (not aid or aid in slots or len(orig_ids) != 1
                or orig_ids[0] not in original_by_id):
            raise ValueError("Audited person ID or original-ID lineage invalid")
        orig_id = orig_ids[0]
        slots[aid] = {
            "original": orig_id, "disciplines": set(split_values(r["disciplines"])),
            "official": set(), "ranked_pair": set(), "secondary": set(),
            "sources": set(), "urls": set(), "ranked": set(),
        }
        by_original[orig_id].add(aid)
        for source_profile in split_values(r.get("source_profile_ids", "")):
            if not source_profile.startswith("isufs") or not source_profile[5:].isdigit():
                raise ValueError("Invalid source profile ID in historic biography audit")
            slots[aid]["urls"].add(
                "https://results.isu.org/bios/" + source_profile + ".htm"
            )
        state, dob = r["dob_status"], r["date_of_birth_candidate"]
        if state == "consistent_source_candidate":
            if not valid_date(dob):
                raise ValueError("Direct ISU source has inconsistent DOB status")
            slots[aid]["official"].add(dob)
            slots[aid]["sources"].add("historic_pair_profile")
        elif state not in {
            "no_parseable_dob", "name_variant_requires_review",
            "source_dob_conflict", "identity_split_unresolved"
        }:
            raise ValueError("Unknown historic direct DOB status " + state)
        # When a source has a conflict, retain all reported dates for
        # conflict accounting, not as accepted DOBs.
        for other in split_values(r.get("source_dob_values", "")):
            if not valid_date(other):
                raise ValueError("Invalid date in official historic source")
            if state == "source_dob_conflict":
                slots[aid]["official"].add(other)
                slots[aid]["sources"].add("conflicted_historic_pair_profile")
    for orig_id in original_by_id:
        if orig_id not in by_original:
            slots[orig_id] = {
                "original": orig_id,
                "disciplines": set(split_values(original_by_id[orig_id]["disciplines"])),
                "official": set(), "ranked_pair": set(), "secondary": set(),
                "sources": set(), "urls": set(), "ranked": set(),
            }
            by_original[orig_id].add(orig_id)

    def resolve(original_id, discipline=None):
        identities = by_original.get(original_id, set())
        if not identities:
            raise ValueError("Source references unknown historic person " + original_id)
        if len(identities) == 1:
            return next(iter(identities))
        if discipline:
            relevant = [aid for aid in identities
                        if discipline in slots[aid]["disciplines"]]
            if len(relevant) == 1:
                return relevant[0]
        return None

    deferred = []
    def register(original_id, kind, dob, url="", discipline=None,
                 source_marker="", pair_id=""):
        if not valid_date(dob):
            raise ValueError("Invalid referenced source DOB: " + str(dob))
        aid = resolve(original_id, discipline)
        if aid is None:
            deferred.append((original_id, kind, dob, pair_id))
            return
        if url and not src_is_official(url) and kind != "secondary":
            raise ValueError("Non-official URL supplied as primary DOB source")
        rec = slots[aid]
        rec[kind].add(dob)
        rec["sources"].add(source_marker or kind)
        if url:
            rec["urls"].add(url)

    allowed_alias = {
        "dual_names_source_attested_pair",
        "manual_official_source_pair",
        "source_reviewed_alias_exception_pair"
    }
    for r in aliases:
        if r["identity_evidence_status"] not in allowed_alias:
            raise ValueError("Unapproved historic alias identity evidence")
        pair_id = r["historic_pair_id"]
        if pair_id not in pair_by_id:
            raise ValueError("Alias source references unknown historical pair")
        pr = pair_by_id[pair_id]
        if r["discipline"] != pr["discipline"]:
            raise ValueError("Alias source discipline mismatch")
        side = r["profile_side"]
        if side not in {"1", "2"}:
            raise ValueError("Alias source side invalid")
        expected_person = pr["person_a_id"] if side == "1" else pr["person_b_id"]
        if r["historic_person_id"] != expected_person:
            raise ValueError("Alias source person disagrees with historical pair")
        register(expected_person, "official", r["date_of_birth_candidate"],
                 r["source_url"], pr["discipline"],
                 "historic_source_linked_alias", pair_id)
    for r in seeds:
        if r["evidence_status"] != "manually_checked_source":
            raise ValueError("Official primary seed is not reviewed")
        register(r["historic_person_id"], "official", r["date_of_birth"],
                 r["source_url"], source_marker="official_primary_seed")

    for r in external:
        if not r["date_of_birth_lead"]:
            continue
        tier = r["source_tier"]
        kind = ("official" if tier.startswith("primary_isu_") else
                "secondary" if tier.startswith("independent_") else None)
        if kind is None:
            raise ValueError("Unrecognized independent DOB source tier " + tier)
        if kind == "secondary" and urlsplit(r["source_url"]).hostname not in {
            "www.olympedia.org", "olympedia.org"
        }:
            raise ValueError("Secondary DOB evidence not from allowed source")
        register(r["historic_person_id"], kind, r["date_of_birth_lead"],
                 r["source_url"], source_marker="historic_external_" + tier)
    for r in oldlinks:
        orig_id = r["historic_person_id"]
        if orig_id not in original_by_id:
            raise ValueError("Cross-era leads include unknown historic person")
        if r["match_status"] == "exact_name_same_pair" and r["ranked_dob_candidate"]:
            if not r["identical_pair_support"]:
                raise ValueError("Cross-era same-pair DOB without pair corroboration")
            register(orig_id, "ranked_pair", r["ranked_dob_candidate"],
                     source_marker="cross_era_same_pair_ranked_profile")
        elif r["match_status"] == "exact_name_only" and r["ranked_dob_candidate"]:
            aid = resolve(orig_id)
            if aid:
                slots[aid]["ranked"].add("name_only_not_admissible")

    person_output, conflicts, missing = [], [], []
    for aid, rec in sorted(slots.items()):
        orig = rec["original"]
        official, ranked_dates, secondary = (
            sorted(rec["official"]), sorted(rec["ranked_pair"]),
            sorted(rec["secondary"])
        )
        evidence_union = set(official) | set(ranked_dates)
        strict = official[0] if len(official) == 1 and len(evidence_union) == 1 else ""
        broad = (next(iter(evidence_union)) if len(evidence_union) == 1 else "")
        if len(evidence_union) > 1:
            state = "cross_source_conflict_hold"
        elif strict:
            state = "official_source_linked"
        elif broad:
            state = "ranked_same_pair_only_review"
        elif secondary:
            state = "secondary_only_review"
        else:
            state = "dob_not_found"
        row = {
            "audit_person_id": aid, "original_historic_person_id": orig,
            "historic_name": original_by_id[orig]["name_display"],
            "disciplines": joined(rec["disciplines"]),
            "source_types": joined(rec["sources"]),
            "official_dob_values": joined(official),
            "same_pair_ranked_dob_values": joined(ranked_dates),
            "secondary_dob_values": joined(secondary),
            "date_of_birth_primary_candidate": strict,
            "date_of_birth_broad_candidate": broad,
            "dob_coverage_status": state, "source_urls": joined(rec["urls"]),
            "ranked_pair_link_status": joined(rec["ranked"]),
            "historic_pair_count": len(adjacent[orig]),
        }
        person_output.append(row)
        if state == "cross_source_conflict_hold":
            conflicts.append({
                "audit_person_id": aid, "original_historic_person_id": orig,
                "source_types": row["source_types"],
                "official_dob_values": row["official_dob_values"],
                "same_pair_ranked_dob_values": row["same_pair_ranked_dob_values"],
                "secondary_dob_values": row["secondary_dob_values"],
                "source_urls": row["source_urls"],
                "conflict_reason": "Incompatible source DOBs or uncertain identity",
            })
        elif not strict:
            missing.append(row)

    people_by_aid = {r["audit_person_id"]: r for r in person_output}
    pairs_output = []
    for pair_id, row in sorted(pair_by_id.items()):
        disc = row["discipline"]
        a, b = row["person_a_id"], row["person_b_id"]
        ar, br = resolve(a, disc), resolve(b, disc)
        ap = people_by_aid.get(ar, {})
        bp = people_by_aid.get(br, {})
        primary = sum(bool(q.get("date_of_birth_primary_candidate"))
                      for q in (ap, bp))
        broad_count = sum(bool(q.get("date_of_birth_broad_candidate"))
                          for q in (ap, bp))
        status = ("identity_split_ambiguous" if not ar or not br else
                  "both" if primary == 2 else
                  "one" if primary == 1 else "neither")
        pairs_output.append({
            "pair_id": pair_id, "discipline": disc,
            "person_a_id": a, "person_b_id": b,
            "audit_person_a_id": ar or "", "audit_person_b_id": br or "",
            "person_a_name": row["person_a_name"],
            "person_b_name": row["person_b_name"],
            "person_a_primary_dob": ap.get("date_of_birth_primary_candidate", ""),
            "person_b_primary_dob": bp.get("date_of_birth_primary_candidate", ""),
            "primary_dob_members": primary, "broad_dob_members": broad_count,
            "pair_dob_status": status,
            "observed_seasons": row.get("observed_seasons", ""),
            "identified_event_count": row.get("identified_event_count", ""),
        })

    pending_ids = {r["historic_pair_id"] for r in pending}
    if len(pending_ids) != len(pending) or not pending_ids <= set(pair_by_id):
        raise ValueError("Unresolved pair list is duplicated or not historic")
    pending_pairs = [r for r in pairs_output if r["pair_id"] in pending_ids]
    if any(r["pair_identity_status"] != "unverified_directory_identity_candidate"
           for r in pending):
        raise ValueError("Unresolved pair list contains an approved identity")

    collision_rows = []
    for r in collisions:
        ids = split_values(r["historic_person_ids"])
        if len(ids) < 2 or any(x not in original_by_id for x in ids):
            raise ValueError("Bad collision original-ID references")
        collision_rows.append({
            "profile_id": r["profile_id"], "side_on_profile": r["side_on_profile"],
            "original_historic_ids": r["historic_person_ids"],
            "status": "candidate_duplicate_ids_not_merged",
        })

    stat = Counter(r["dob_coverage_status"] for r in person_output)
    pair_count = Counter(r["pair_dob_status"] for r in pairs_output)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_dob_coverage_people_v1.csv", PERSON_FIELDS, person_output)
    write_csv(out / "historic_dob_missing_priority_v1.csv", PERSON_FIELDS,
              sorted(missing, key=lambda x: (-int(x["historic_pair_count"]),
                                              x["audit_person_id"])))
    write_csv(out / "historic_dob_coverage_pairs_v1.csv", PAIR_FIELDS, pairs_output)
    write_csv(out / "historic_dob_source_conflicts_v1.csv", CONFLICT_FIELDS, conflicts)
    write_csv(out / "historic_unresolved_pair_dob_v1.csv", PAIR_FIELDS, pending_pairs)
    write_csv(out / "historic_candidate_duplicate_ids_v1.csv",
              ["profile_id", "side_on_profile", "original_historic_ids", "status"],
              collision_rows)

    input_hashes = {str(path): digest(path) for path in paths}
    report = {
        "stage": "historic_dob_coverage_audit_not_frozen_no_bazi",
        "historical_original_provisional_ids": len(original_by_id),
        "historical_audit_identity_slots_before_alias_merges": len(slots),
        "confirmed_homonym_splits_extra_slots": len(slots) - len(original_by_id),
        "historical_pairs": len(pairs_output),
        "identity_coverage_counts": dict(sorted(stat.items())),
        "official_primary_dob_candidates": stat["official_source_linked"],
        "ranked_same_pair_only_candidates_not_promoted": stat[
            "ranked_same_pair_only_review"
        ],
        "secondary_only_candidates_not_promoted": stat["secondary_only_review"],
        "no_usable_dob_evidence": stat["dob_not_found"],
        "source_dob_conflict_holds": stat["cross_source_conflict_hold"],
        "missing_primary_dob_slots": len(missing),
        "pair_primary_dob_counts": dict(sorted(pair_count.items())),
        "pairs_with_both_primary_dobs": pair_count["both"],
        "unresolved_alias_pairs": len(pending_pairs),
        "unresolved_alias_pairs_with_both_primary_dobs": sum(
            int(r["primary_dob_members"]) == 2 for r in pending_pairs
        ),
        "unresolved_alias_pairs_with_one_primary_dob": sum(
            int(r["primary_dob_members"]) == 1 for r in pending_pairs
        ),
        "unresolved_alias_pairs_with_no_primary_dob": sum(
            int(r["primary_dob_members"]) == 0 for r in pending_pairs
        ),
        "source_profile_side_alias_collision_candidates": len(collision_rows),
        "unscoped_source_rows_deferred_for_homonym_split": len(deferred),
        "input_sha256": input_hashes,
        "limitations": [
            "910 original historical IDs are not 910 independently verified people",
            "Cross-era name+same-pair links are candidates, not primary DOBs",
            "Secondary sources are leads, not accepted primary DOBs",
            "A reviewed homonym split increases audit slots while candidate alias duplicates remain unmerged",
            "Unresolved pair identity links do not imply missing birthdays",
            "Full DOB coverage in selected historical events does not equal all skating entrants",
            "No astrological features, significance tests, or null models calculated",
        ],
    }
    (out / "historic_dob_coverage_manifest_v1.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        k: report[k] for k in (
            "historical_original_provisional_ids",
            "historical_audit_identity_slots_before_alias_merges",
            "historical_pairs", "identity_coverage_counts",
            "pair_primary_dob_counts", "missing_primary_dob_slots",
            "unresolved_alias_pairs_with_both_primary_dobs",
            "source_profile_side_alias_collision_candidates",
        )
    }, indent=2, ensure_ascii=False))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--athletes", default="data/historic/v4/athletes_v4.csv")
    p.add_argument("--pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--direct", default="output/historic_dob/identity/historic_audited_people.csv")
    p.add_argument("--aliases", default="output/historic_dob/alias_pair_identity/historic_alias_correlated_dob_leads.csv")
    p.add_argument("--seed", default="data/adjudications/isu_historic_primary_dob_seed_v2.csv")
    p.add_argument("--external", default="data/adjudications/isu_historic_external_dob_leads_v1.csv")
    p.add_argument("--historic-links", default="output/historic_dob/historic_identity_dob_candidates.csv")
    p.add_argument("--unresolved", default="output/historic_dob/alias_pair_identity/historic_alias_unresolved_pair_review.csv")
    p.add_argument("--collisions", default="output/historic_dob/alias_pair_identity/historic_alias_profile_side_collisions.csv")
    p.add_argument("--out", default="output/historic_dob/coverage")
    args = p.parse_args()
    coverage(args.athletes, args.pairs, args.direct, args.aliases, args.seed,
             args.external, args.historic_links, args.unresolved, args.collisions, args.out)


if __name__ == "__main__":
    main()
