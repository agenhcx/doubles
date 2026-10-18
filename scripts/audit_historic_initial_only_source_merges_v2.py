#!/usr/bin/env python3
"""Source-reviewed reversible v2 historic identity projection: six initial-only pairs.

Apply ONLY the six explicitly source-reviewed official ISU evidence rows to
the existing historical shared-partner v3 preview. Preserve all original
pair/person/event IDs, DOB provenance, scores and seasons. Do not aggregate
event counts. Requires prior complete v3 preview and initial-only candidate
audit. Offline checks validate lineage; no live ISU page fetches.
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
V3_PEOPLE = Path("output/historic_dob/shared_partner_identity/historic_reviewed_person_id_preview_v1.csv")
V3_PAIRS = Path("output/historic_dob/shared_partner_identity/historic_reviewed_pair_groups_preview_v1.csv")
INITIAL_PEOPLE = Path("output/historic_dob/initial_only_alias_audit/historic_initial_only_person_candidate_links_v1.csv")
INITIAL_PAIRS = Path("output/historic_dob/initial_only_alias_audit/historic_initial_only_pair_candidate_groups_v1.csv")
ORIGINAL_PAIRS = Path("data/historic/v4/couples_v4.csv")
RULES = Path("data/adjudications/isu_historic_initial_only_pair_merges_v1.csv")
OUTPUT = Path("output/historic_dob/shared_partner_identity/initial_only_v2")

PERSON_FIELDS = [
    "projected_person_id", "audit_person_ids", "original_historic_person_ids",
    "historic_names", "date_of_birth", "source_person_rows", "status",
]
PAIR_FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "original_pair_ids", "original_pair_rows", "original_pair_names",
    "original_pair_seasons", "pair_group_status",
    "event_count_aggregation_status",
]
REVIEW_FIELDS = [
    "discipline", "abbreviated_pair_id", "full_pair_id", "member_side",
    "alternate_person_id", "canonical_person_id", "date_of_birth",
    "alternate_name", "canonical_name", "official_profile_url",
    "official_event_results_url", "source_printed_name",
    "adjudication_status", "review_note",
]
LEDGER_FIELDS = [
    "discipline", "abbreviated_pair_id", "full_pair_id",
    "abbreviated_person_a_id", "full_person_a_id", "expected_dob_a",
    "abbreviated_person_b_id", "full_person_b_id", "expected_dob_b",
    "official_profile_id", "official_profile_url",
    "official_event_results_url", "evidence_status",
    "source_observed_name_a", "source_observed_name_b", "review_note",
]


def read(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns {sorted(missing)}")
        return list(reader)


def write(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parts(x):
    return {s.strip() for s in (x or "").split(";") if s.strip()}


def join(seq):
    return "; ".join(sorted(set(x for x in seq if x)))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_dob(value):
    try:
        return bool(value) and date.fromisoformat(value).isoformat() == value
    except (TypeError, ValueError):
        return False


def official_bio(url, profile_id):
    p = urlsplit(url)
    return (p.scheme == "https" and
            p.hostname in ("results.isu.org", "www.isuresults.com") and
            not p.username and not p.password and p.port is None and
            not p.query and not p.fragment and
            bool(re.fullmatch(r"isufs\d+", profile_id.lower())) and
            p.path.lower() == f"/bios/{profile_id.lower()}.htm")


def official_result(url):
    p = urlsplit(url)
    return (p.scheme == "https" and
            p.hostname in ("results.isu.org", "www.isuresults.com") and
            not p.username and not p.password and p.port is None and
            not p.query and not p.fragment and
            bool(re.fullmatch(
                r"/results/(?:owg2014|fc2009)/CAT00[34]RS\.HTM", p.path,
                re.IGNORECASE)))


def audit(people_path=V3_PEOPLE, pairs_path=V3_PAIRS,
          initial_people_path=INITIAL_PEOPLE, initial_pairs_path=INITIAL_PAIRS,
          originals_path=ORIGINAL_PAIRS, rules_path=RULES, out_dir=OUTPUT):
    people = read(people_path, PERSON_FIELDS)
    pairs = read(pairs_path, PAIR_FIELDS)
    candidates = read(initial_people_path, (
        "discipline", "abbreviated_pair_id", "member_side",
        "abbreviated_person_id", "abbreviated_name",
        "matched_full_person_id", "matched_full_name",
        "abbreviated_official_dob", "full_name_official_dob",
        "original_full_pair_id", "review_status", "structural_match_status",
    ))
    candidate_pairs = read(initial_pairs_path, (
        "discipline", "abbreviated_pair_id", "original_full_pair_id",
        "matching_abbreviated_member_count", "dob_agree_both_sides", "status",
    ))
    old_pairs = read(originals_path, (
        "pair_id", "discipline", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name",
    ))
    rules = read(rules_path, LEDGER_FIELDS)
    if not all((people, pairs, candidates, candidate_pairs, old_pairs, rules)):
        raise ValueError("A required source-reviewed input is empty")

    person_by_id = {}
    for p in people:
        pid = p["projected_person_id"]
        if not pid or pid in person_by_id or not valid_dob(p["date_of_birth"]):
            raise ValueError("Repeated projected person ID or invalid audited DOB")
        if str(len(parts(p["audit_person_ids"]))) != p["source_person_rows"]:
            raise ValueError("v3 audited person lineage count disagrees")
        person_by_id[pid] = p

    original_pair_by_id = {}
    for p in old_pairs:
        if not p["pair_id"] or p["pair_id"] in original_pair_by_id:
            raise ValueError("Repeated original historic pair ID")
        original_pair_by_id[p["pair_id"]] = p

    oldgroup_by_pair = {}
    old_keys = set()
    for p in pairs:
        key = (p["discipline"], p["projected_person_a_id"],
               p["projected_person_b_id"])
        if key in old_keys or any(x not in person_by_id for x in key[1:]):
            raise ValueError("Duplicate v3 projected pair or unknown person")
        old_keys.add(key)
        group_ids = parts(p["original_pair_ids"])
        if not group_ids or str(len(group_ids)) != p["original_pair_rows"]:
            raise ValueError("Invalid original pair ID lineage")
        for original_id in group_ids:
            if original_id in oldgroup_by_pair or original_id not in original_pair_by_id:
                raise ValueError("Repeated or unknown original pair ID in v3 preview")
            oldgroup_by_pair[original_id] = p

    if len(oldgroup_by_pair) != len(original_pair_by_id):
        raise ValueError("v3 pair preview does not map every original historic pair ID")

    cand_by_key = {}
    for c in candidates:
        k = (c["discipline"], c["abbreviated_pair_id"],
             c["original_full_pair_id"], c["member_side"])
        if k in cand_by_key:
            raise ValueError("Repeated initial-only candidate review edge")
        cand_by_key[k] = c
    pair_candidates = {}
    for c in candidate_pairs:
        k = (c["discipline"], c["abbreviated_pair_id"], c["original_full_pair_id"])
        if k in pair_candidates:
            raise ValueError("Duplicate candidate pair")
        pair_candidates[k] = c

    mapping = {}
    used_pair_review = set()
    reviewed = []
    for rule in rules:
        disc, short, full = (
            rule["discipline"], rule["abbreviated_pair_id"], rule["full_pair_id"])
        key = (disc, short, full)
        if key in used_pair_review:
            raise ValueError("Repeated reviewed initial-only pair")
        used_pair_review.add(key)
        if rule["evidence_status"] != "source_reviewed_same_couple_and_members":
            raise ValueError("Rule is not explicitly source-reviewed")
        if (not official_bio(rule["official_profile_url"], rule["official_profile_id"])
                or not official_result(rule["official_event_results_url"])
                or not rule["source_observed_name_a"] or not rule["source_observed_name_b"]
                or len(rule["review_note"]) < 65):
            raise ValueError("Reviewed rule lacks valid source-specific ISU evidence")
        candidate = pair_candidates.get(key)
        if (candidate is None or candidate["matching_abbreviated_member_count"] != "2" or
                candidate["dob_agree_both_sides"] != "YES" or
                candidate["status"] != "SOURCE_NAME_DOB_PAIR_CANDIDATE_NO_MERGE"):
            raise ValueError("Reviewed pair has no complete initial-only discovery anchor")
        old_short, old_full = original_pair_by_id.get(short), original_pair_by_id.get(full)
        if not old_short or not old_full or old_short["discipline"] != disc or old_full["discipline"] != disc:
            raise ValueError("Reviewed original pair IDs or discipline differ from source")
        short_members = (old_short["person_a_id"], old_short["person_b_id"])
        full_members = (old_full["person_a_id"], old_full["person_b_id"])

        for side in ("a", "b"):
            position = "1" if side == "a" else "2"
            alt = rule[f"abbreviated_person_{side}_id"]
            canon = rule[f"full_person_{side}_id"]
            dob = rule[f"expected_dob_{side}"]
            if (not alt or not canon or alt == canon or not valid_dob(dob) or
                    alt != short_members[int(position) - 1] or
                    canon != full_members[int(position) - 1]):
                raise ValueError("Initial-only rule disagrees with original member side")
            evidence = cand_by_key.get((*key, position))
            if (evidence is None or
                    evidence["abbreviated_person_id"] != alt or
                    evidence["matched_full_person_id"] != canon or
                    evidence["abbreviated_name"] != old_short[f"person_{side}_name"] or
                    evidence["matched_full_name"] != old_full[f"person_{side}_name"] or
                    evidence["abbreviated_official_dob"] != dob or
                    evidence["full_name_official_dob"] != dob or
                    evidence["structural_match_status"] != "BOTH_PARTNERS_MATCH_HISTORIC_PAIR" or
                    evidence["review_status"] != "OFFICIAL_DOB_AGREES_SAME_PAIR_STRUCTURE_REVIEW"):
                raise ValueError("Candidate evidence conflicts with reviewed pair or DOB")
            if alt not in person_by_id or canon not in person_by_id:
                raise ValueError("Reviewed athlete absent from v3 identity preview")
            pa, pc = person_by_id[alt], person_by_id[canon]
            if (pa["date_of_birth"] != dob or pc["date_of_birth"] != dob or
                    len(parts(pa["audit_person_ids"])) != 1 or
                    len(parts(pc["audit_person_ids"])) != 1):
                raise ValueError("Non-singleton prior identity or DOB source disagreement")
            if (alt in mapping or alt in mapping.values() or
                    canon in mapping or canon in mapping.values()):
                raise ValueError("Chained, shared or repeated initial-only identity merge")
            mapping[alt] = canon
            reviewed.append({
                "discipline": disc, "abbreviated_pair_id": short,
                "full_pair_id": full, "member_side": position,
                "alternate_person_id": alt, "canonical_person_id": canon,
                "date_of_birth": dob,
                "alternate_name": old_short[f"person_{side}_name"],
                "canonical_name": old_full[f"person_{side}_name"],
                "official_profile_url": rule["official_profile_url"],
                "official_event_results_url": rule["official_event_results_url"],
                "source_printed_name": rule[f"source_observed_name_{side}"],
                "adjudication_status": "SOURCE_REVIEWED_REVERSIBLE_ALIAS_IN_V2_PREVIEW",
                "review_note": rule["review_note"],
            })

        old_sa, old_sb = oldgroup_by_pair[short], oldgroup_by_pair[full]
        if ((old_sa["projected_person_a_id"], old_sa["projected_person_b_id"]) != short_members
                or (old_sb["projected_person_a_id"], old_sb["projected_person_b_id"]) != full_members
                or old_sa is old_sb):
            raise ValueError("v3 group identity changed or original short/full pair already coalesced")

    if len(mapping) != 2 * len(rules):
        raise ValueError("Every reviewed pair must contribute exactly two distinct ID mappings")

    merged_people = defaultdict(list)
    for p in people:
        original_id = p["projected_person_id"]
        merged_people[mapping.get(original_id, original_id)].append(p)
    people_new = []
    for canonical, items in sorted(merged_people.items()):
        dates = {x["date_of_birth"] for x in items}
        if len(dates) != 1:
            raise ValueError("Approved alias creates a DOB collision")
        old_ids = {t for x in items for t in parts(x["audit_person_ids"])}
        original_ids = {t for x in items for t in parts(x["original_historic_person_ids"])}
        if len(old_ids) != sum(int(x["source_person_rows"]) for x in items):
            raise ValueError("Approved person lineage overlaps existing audited slots")
        people_new.append({
            "projected_person_id": canonical,
            "audit_person_ids": join(old_ids),
            "original_historic_person_ids": join(original_ids),
            "historic_names": join(t for x in items for t in parts(x["historic_names"])),
            "date_of_birth": next(iter(dates)),
            "source_person_rows": sum(int(x["source_person_rows"]) for x in items),
            "status": ("source_reviewed_initial_only_alias_v2"
                       if len(items) > 1 else items[0]["status"]),
        })

    grouped_pairs = defaultdict(list)
    for p in pairs:
        key = (
            p["discipline"],
            mapping.get(p["projected_person_a_id"], p["projected_person_a_id"]),
            mapping.get(p["projected_person_b_id"], p["projected_person_b_id"]),
        )
        if key[1] == key[2]:
            raise ValueError("Approved alias creates self-pair")
        grouped_pairs[key].append(p)
    pairs_new = []
    for (disc, a, b), group in sorted(grouped_pairs.items()):
        origin = {t for x in group for t in parts(x["original_pair_ids"])}
        if len(origin) != sum(int(x["original_pair_rows"]) for x in group):
            raise ValueError("Approved pair lineage overlaps original pair IDs")
        pairs_new.append({
            "discipline": disc, "projected_person_a_id": a,
            "projected_person_b_id": b, "original_pair_ids": join(origin),
            "original_pair_rows": len(origin),
            "original_pair_names": join(
                t for x in group for t in parts(x["original_pair_names"])),
            "original_pair_seasons": join(
                t for x in group for t in parts(x["original_pair_seasons"])),
            "pair_group_status": (
                "multiple_history_pair_ids_source_reviewed"
                if len(origin) > 1 else "unique_original_pair_id"),
            "event_count_aggregation_status": "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP",
        })

    if (len(people_new) != len(people) - len(mapping) or
            len(pairs_new) != len(pairs) - len(rules) or
            sum(int(p["original_pair_rows"]) for p in pairs_new) != len(original_pair_by_id)):
        raise ValueError("v2 preview identity/pair lineage has unexpected count changes")

    out = Path(out_dir)
    write(out / "historic_reviewed_person_id_preview_v2.csv", people_new, PERSON_FIELDS)
    write(out / "historic_reviewed_pair_groups_preview_v2.csv", pairs_new, PAIR_FIELDS)
    write(out / "historic_initial_only_source_adjudication_v2.csv", reviewed, REVIEW_FIELDS)
    report = {
        "stage": "historical_source_reviewed_initial_only_v2_preview_not_frozen",
        "input_v3_person_identity_slots": len(people),
        "input_v3_pair_groups": len(pairs),
        "original_historic_pair_ids_preserved": len(original_pair_by_id),
        "source_reviewed_initial_only_pair_aliases": len(rules),
        "source_reviewed_initial_only_person_aliases": len(mapping),
        "projected_v2_identity_slots": len(people_new),
        "projected_v2_unique_pair_groups": len(pairs_new),
        "projected_v2_multi_original_id_pair_groups": sum(
            int(p["original_pair_rows"]) > 1 for p in pairs_new),
        "inputs_sha256": {str(p): digest(p) for p in (
            people_path, pairs_path, initial_people_path, initial_pairs_path,
            originals_path, rules_path)},
        "limitations": [
            "This is a reversible preview based on official biography and results already source-reviewed; pages are not refetched by the offline script",
            "Original person/pair IDs, DOB evidence and source event records remain untouched",
            "A same-ISU-source DOB match is not an independent replicated measurement",
            "No event counts or cross-era season ranking points are aggregated",
            "Must rerun original event collision audit against the projected v2 pair preview",
            "Other non-shared-partner, cross-era and homonym ambiguities are not settled",
            "No BaZi, significance test, null model or outcome-based sample selection",
        ],
    }
    (out / "historic_initial_only_v2_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v3-people", type=Path, default=V3_PEOPLE)
    p.add_argument("--v3-pairs", type=Path, default=V3_PAIRS)
    p.add_argument("--initial-people", type=Path, default=INITIAL_PEOPLE)
    p.add_argument("--initial-pairs", type=Path, default=INITIAL_PAIRS)
    p.add_argument("--original-pairs", type=Path, default=ORIGINAL_PAIRS)
    p.add_argument("--rules", type=Path, default=RULES)
    p.add_argument("--out", type=Path, default=OUTPUT)
    a = p.parse_args()
    audit(a.v3_people, a.v3_pairs, a.initial_people, a.initial_pairs,
          a.original_pairs, a.rules, a.out)


if __name__ == "__main__":
    main()
