#!/usr/bin/env python3
"""Audit historic ISU profile DOBs and conservatively separate proven homonyms.

Input is the raw, two-per-profile candidate CSV from the local historical ISU
biography collector. Source-reviewed profile/side splits live in a small
versioned adjudication CSV. Original historical person IDs are never edited.

No network requests, BaZi, DOB imputation or master-table mutation.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, norm, read_csv, valid_date, write_csv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = ROOT / "data" / "adjudications" / "isu_historic_homonym_splits_v1.csv"
LINK_FIELDS = [
    "audit_person_id", "historic_person_id", "profile_id",
    "side_on_profile", "discipline", "historic_name",
    "observed_name", "source_dob", "parse_status", "identity_status",
    "source_url", "review_reason"
]
PERSON_FIELDS = [
    "audit_person_id", "original_historic_person_ids", "disciplines",
    "observed_names", "source_profile_ids", "source_rows", "source_dob_values",
    "date_of_birth_candidate", "dob_status", "identity_status"
]
OFFICIAL_HOSTS = {"results.isu.org", "www.isuresults.com"}


def checked_rows(path, label):
    rows = read_csv(path)
    if not rows:
        raise ValueError(label + " is empty")
    return rows


def read_rules(path):
    rules, split_people = {}, set()
    for row in checked_rows(path, "Homonym split rules"):
        person, profile, side = (
            row["historic_person_id"], row["profile_id"].lower(),
            row["side_on_profile"]
        )
        key = (person, profile, side)
        if key in rules or not row["audit_person_id"] or not row["expected_name"]:
            raise ValueError("Duplicate or malformed homonym rule: " + repr(key))
        if row["evidence_status"] != "source_corroborated":
            raise ValueError("Homonym mapping is not source reviewed")
        if not valid_date(row["expected_dob"]):
            raise ValueError("Invalid official homonym DOB")
        if urlsplit(row["official_source_url"]).hostname not in OFFICIAL_HOSTS:
            raise ValueError("Unapproved official profile host")
        if Path(urlsplit(row["official_source_url"]).path).stem.lower() != profile:
            raise ValueError("Profile URL differs from homonym rule ID")
        rules[key] = row
        split_people.add(person)
    by_id = defaultdict(set)
    for k, row in rules.items():
        by_id[k[0]].add(row["audit_person_id"])
    if any(len(ids) < 2 for ids in by_id.values()):
        raise ValueError("Each homonym split must name two or more identities")
    # The same reviewed athlete may legitimately have several official
    # profiles, but audit IDs must never cross original historical IDs.
    identity_owners = defaultdict(set)
    for (historic, _, _), row in rules.items():
        identity_owners[row["audit_person_id"]].add(historic)
    if any(len(v) > 1 for v in identity_owners.values()):
        raise ValueError("One audit identity assigned to different original people")
    return rules, split_people


def pair_sources(path):
    pairs = {}
    for row in checked_rows(path, "Historic pairs"):
        if not row["pair_id"] or row["pair_id"] in pairs:
            raise ValueError("Duplicate or empty historical pair")
        pairs[row["pair_id"]] = row
    return pairs


def audit(
    candidates_path="output/historic_dob/biographies/historic_isu_bio_candidates.csv",
    pairs_path="data/historic/v4/couples_v4.csv",
    rules_path=DEFAULT_RULES,
    out_dir="output/historic_dob/identity",
):
    paths = [Path(candidates_path), Path(pairs_path), Path(rules_path)]
    sources = checked_rows(paths[0], "Historic source observations")
    pairs = pair_sources(paths[1])
    rules, split_people = read_rules(paths[2])

    links, seen_slots = [], set()
    covered_rules = set()
    observed_rules = set()
    for source in sources:
        original, profile, side = (
            source["historic_person_id"], source["profile_id"].lower(),
            source["side_on_profile"]
        )
        key = (original, profile, side)
        slot = (profile, side)
        if slot in seen_slots:
            raise ValueError("Duplicate source profile position: " + repr(slot))
        seen_slots.add(slot)
        if side not in {"1", "2"}:
            raise ValueError("Unexpected side on profile")
        if not original or not source["source_url"]:
            raise ValueError("Missing source identity/provenance")
        source_parts = urlsplit(source["source_url"])
        if (source_parts.hostname not in OFFICIAL_HOSTS
                or Path(source_parts.path).stem.lower() != profile):
            raise ValueError("Untrusted or mismatched raw source link")
        pair_ids = [x.strip() for x in source["historic_pair_ids"].split(";") if x.strip()]
        if not pair_ids:
            raise ValueError("Missing historic pair provenance")
        disciplines = set()
        for pair_id in pair_ids:
            if pair_id not in pairs:
                raise ValueError("Unknown historical pair: " + pair_id)
            pair = pairs[pair_id]
            expected = pair["person_a_id"] if side == "1" else pair["person_b_id"]
            if expected != original:
                raise ValueError("Historic pair/profile identity mismatch: " + repr(key))
            disciplines.add(pair["discipline"])
        if len(disciplines) != 1:
            raise ValueError("One source position references multiple disciplines")
        discipline = next(iter(disciplines))
        dob = source.get("date_of_birth", "")
        if dob and not valid_date(dob):
            raise ValueError("Invalid labelled DOB in historical candidate")
        audit_id = original
        identity_state = "original_provisional"
        reasons = []
        if original in split_people:
            rule = rules.get(key)
            if rule is None:
                audit_id = "unresolved:" + original + ":" + profile + ":" + side
                identity_state = "homonym_split_rule_missing"
                reasons.append(identity_state)
            elif (rule["discipline"] != discipline
                  or norm(rule["expected_name"]) != norm(source["historic_name"])
                  or not dob or dob != rule["expected_dob"]):
                observed_rules.add(key)
                audit_id = "unresolved:" + original + ":" + profile + ":" + side
                identity_state = "homonym_evidence_mismatch"
                reasons.append(identity_state)
            else:
                observed_rules.add(key)
                covered_rules.add(key)
                audit_id = rule["audit_person_id"]
                identity_state = "source_reviewed_homonym_split"

        if source["parse_status"] != "dob_explicitly_bound_to_expected_name":
            reasons.append(source["parse_status"])
        if source.get("seed_consistency") == "conflict_with_primary_seed":
            reasons.append("source_conflicts_with_seed")
        links.append({
            "audit_person_id": audit_id, "historic_person_id": original,
            "profile_id": profile, "side_on_profile": side,
            "discipline": discipline,
            "historic_name": source["historic_name"],
            "observed_name": source["observed_name"],
            "source_dob": dob,
            "parse_status": source["parse_status"],
            "identity_status": identity_state,
            "source_url": source["source_url"],
            "review_reason": "; ".join(sorted(set(reasons))),
        })

    not_observed = set(rules) - observed_rules
    if not_observed:
        raise ValueError(
            "One or more reviewed homonym profiles are absent or inconsistent: "
            + repr(sorted(not_observed)[:3])
        )

    members = defaultdict(list)
    for row in links:
        members[row["audit_person_id"]].append(row)

    projected, conflicts = [], []
    for identity, observations in sorted(members.items()):
        dates = sorted({x["source_dob"] for x in observations if x["source_dob"]})
        bad_identity = any(x["identity_status"].startswith("homonym_")
                           for x in observations)
        name_variants = any(x["parse_status"] != "dob_explicitly_bound_to_expected_name"
                            for x in observations)
        if bad_identity:
            status, accept = "identity_split_unresolved", ""
        elif len(dates) > 1:
            status, accept = "source_dob_conflict", ""
        elif not dates:
            status, accept = "no_parseable_dob", ""
        elif name_variants and not any(
            x["parse_status"] == "dob_explicitly_bound_to_expected_name"
            for x in observations
        ):
            status, accept = "name_variant_requires_review", ""
        else:
            status, accept = "consistent_source_candidate", dates[0]
        if status in ("source_dob_conflict", "identity_split_unresolved"):
            for row in observations:
                conflicts.append(dict(
                    row, review_reason="; ".join(
                        x for x in (row["review_reason"], status) if x
                    ),
                ))
        projected.append({
            "audit_person_id": identity,
            "original_historic_person_ids": "; ".join(sorted({
                x["historic_person_id"] for x in observations
            })),
            "disciplines": "; ".join(sorted({
                x["discipline"] for x in observations
            })),
            "observed_names": "; ".join(sorted({
                x["observed_name"] for x in observations if x["observed_name"]
            })),
            "source_profile_ids": "; ".join(sorted({
                x["profile_id"] for x in observations
            })),
            "source_rows": len(observations),
            "source_dob_values": "; ".join(dates),
            "date_of_birth_candidate": accept,
            "dob_status": status,
            "identity_status": (
                "source_reviewed_homonym_split"
                if all(x["identity_status"] == "source_reviewed_homonym_split"
                       for x in observations)
                else "provisional_unmodified"
            ),
        })

    # Report every non-accepted record, including normal-looking source
    # rows whose profile ID is shared by a known ambiguous historical name.
    review_rows = [row for row in links if row["review_reason"]]
    extra_keys = {(r["profile_id"], r["side_on_profile"]) for r in review_rows}
    for row in conflicts:
        key = (row["profile_id"], row["side_on_profile"])
        if key not in extra_keys:
            review_rows.append(row)
            extra_keys.add(key)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_source_identity_links.csv", LINK_FIELDS, links)
    write_csv(out / "historic_audited_people.csv", PERSON_FIELDS, projected)
    write_csv(out / "historic_identity_review.csv", LINK_FIELDS, review_rows)

    stat = Counter(x["dob_status"] for x in projected)
    summary = {
        "stage": "historic_profile_identity_audit_not_frozen",
        "source_person_slots": len(sources),
        "source_orig_person_ids": len({x["historic_person_id"] for x in links}),
        "source_audited_person_ids": len(projected),
        "official_homonym_split_original_ids": len(split_people),
        "official_homonym_split_profiles": len(covered_rules),
        "homonym_split_evidence_mismatches": len(observed_rules - covered_rules),
        "identities_with_agreeing_dobs": stat["consistent_source_candidate"],
        "identities_with_source_conflicts": stat["source_dob_conflict"],
        "identities_needing_name_review": stat["name_variant_requires_review"],
        "identities_without_dob": stat["no_parseable_dob"],
        "identities_with_unresolved_split": stat["identity_split_unresolved"],
        "review_source_rows": len(review_rows),
        "person_status_breakdown": dict(sorted(stat.items())),
        "input_sha256": {str(p): digest(p) for p in paths},
        "limitations": [
            "Reviewed homonym mappings are profile/side specific and do not alter raw historic IDs",
            "A consistent official-profile date is a candidate pending broader roster QA",
            "Name punctuation/order variants are held for explicit review",
            "No dates inferred from a missing field, a nationality or another athlete",
            "Other homonyms without contradictory DOBs may still exist",
            "No astrology features, performance selection, or master edits",
        ],
    }
    (out / "historic_identity_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", default="output/historic_dob/biographies/historic_isu_bio_candidates.csv")
    p.add_argument("--pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--homonyms", default=str(DEFAULT_RULES))
    p.add_argument("--out", default="output/historic_dob/identity")
    a = p.parse_args()
    audit(a.candidates, a.pairs, a.homonyms, a.out)


if __name__ == "__main__":
    main()
