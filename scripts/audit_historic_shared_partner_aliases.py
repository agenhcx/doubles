#!/usr/bin/env python3
"""Audit 2004–2018 historic ISU athlete aliases through SHARED PARTNERS + DOB.

This is a conservative evidence index and a reversible projection, NOT a
frozen cohort or a destructive modification of existing person/pair IDs.

Rules:
 - Candidates: two distinct historic IDs with the same position/discipline,
   the same real historic partner ID, and identical official day-level DOB.
 - Acceptance: only explicitly source-reviewed versioned adjudication CSV,
   with pair/provenance constraints and identical official DOB.
 - Ambiguous homonyms split by earlier source audit remain separate.
 - Pair groups retain all original pair IDs. No event counts or ranks are
   summed, and pair observations are not assumed statistically independent.
 - No BaZi, date randomization, outcome selection, network access, or writes
   to the existing master.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, joined, read_csv, valid_date, write_csv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = ROOT / "data/adjudications/isu_historic_shared_partner_id_merges_v3.csv"
HOSTS = {"results.isu.org", "www.isuresults.com", "isu-skating.com",
         "www.isu-skating.com"}
CAND_FIELDS = [
    "discipline", "audit_person_a_id", "audit_person_b_id",
    "historic_person_a_id", "historic_person_b_id",
    "historic_name_a", "historic_name_b", "shared_dob",
    "shared_partner_ids", "shared_partner_names",
    "historic_pair_ids_a", "historic_pair_ids_b",
    "name_similarity_review_only", "identity_review_status",
    "source_review_url", "review_note"
]
PERSON_FIELDS = [
    "projected_person_id", "audit_person_ids", "original_historic_person_ids",
    "historic_names", "date_of_birth", "source_person_rows",
    "status"
]
PAIR_FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "original_pair_ids", "original_pair_rows", "original_pair_names",
    "original_pair_seasons", "pair_group_status",
    "event_count_aggregation_status"
]


def check(rows, keys, name):
    if not rows:
        raise ValueError(name + " is empty")
    missing = set(keys) - set(rows[0])
    if missing:
        raise ValueError(name + " missing columns " + repr(sorted(missing)))


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", s))


def audit(
    people_path="output/historic_dob/coverage/historic_dob_coverage_people_v1.csv",
    pairs_path="data/historic/v4/couples_v4.csv",
    rules_path=DEFAULT_RULES,
    out_dir="output/historic_dob/shared_partner_identity",
):
    paths = [Path(p) for p in (people_path, pairs_path, rules_path)]
    people, pairs, rules = [read_csv(p) for p in paths]
    check(people, ("audit_person_id", "original_historic_person_id",
                   "historic_name", "disciplines", "date_of_birth_primary_candidate",
                   "dob_coverage_status"), "Audited historic DOB people")
    check(pairs, ("pair_id", "discipline", "person_a_id", "person_b_id",
                  "person_a_name", "person_b_name", "first_season",
                  "observed_seasons"), "Historical couples")
    check(rules, ("canonical_person_id", "alternate_person_id",
                  "expected_dob", "discipline", "shared_partner_person_id",
                  "canonical_pair_id", "alternate_pair_id",
                  "official_profile_id", "profile_side", "official_source_url",
                  "corroborating_source_url", "evidence_status",
                  "identity_note"), "Source-reviewed identity merges")

    people_by_audit = {}
    person_candidates = defaultdict(list)
    for p in people:
        aid, orig = p["audit_person_id"], p["original_historic_person_id"]
        if not aid or aid in people_by_audit or not orig:
            raise ValueError("Blank or duplicated audited identity ID")
        dob = p["date_of_birth_primary_candidate"]
        status = p["dob_coverage_status"]
        if status not in {
            "official_source_linked", "ranked_same_pair_only_review",
            "secondary_only_review", "dob_not_found",
            "cross_source_conflict_hold"
        }:
            raise ValueError("Unknown historical source DOB status")
        if dob:
            if status != "official_source_linked" or not valid_date(dob):
                raise ValueError("Non-official or invalid DOB in primary source field")
        elif status == "official_source_linked":
            raise ValueError("Official source-linked person unexpectedly lacks DOB")
        people_by_audit[aid] = p
        for discipline in p["disciplines"].split(";"):
            disc = discipline.strip()
            if disc:
                person_candidates[(orig, disc)].append(aid)

    indexed_pairs = {}
    pair_audit_members = {}
    partner_groups = defaultdict(list)
    original_names = defaultdict(set)
    for pair in pairs:
        pid, disc = pair["pair_id"], pair["discipline"]
        a, b = pair["person_a_id"], pair["person_b_id"]
        if not pid or pid in indexed_pairs or a == b:
            raise ValueError("Repeated pair ID or self-pair")
        mapped = []
        for person_id in (a, b):
            candidates = person_candidates.get((person_id, disc), [])
            if len(candidates) != 1:
                raise ValueError("Original person/discipline resolves to an ambiguous audited ID: "
                                 + person_id + "/" + disc)
            mapped.append(candidates[0])
        indexed_pairs[pid] = pair
        pair_audit_members[pid] = tuple(mapped)
        for role in ("a", "b"):
            other = "b" if role == "a" else "a"
            person_id, partner_id = pair["person_" + role + "_id"], pair["person_" + other + "_id"]
            name = pair["person_" + role + "_name"]
            original_names[person_id].add(name)
            partner_groups[(disc, role, partner_id)].append({
                "audit_id": mapped[0 if role == "a" else 1],
                "original_id": person_id, "name": name,
                "partner_name": pair["person_" + other + "_name"],
                "pair_id": pid,
            })

    # Find candidates regardless of their original index-name match
    # status; false matches must never be coerced into genuine identities.
    proposals = {}
    comparisons, unequal_dates = 0, 0
    for (disc, role, partner_id), entries in partner_groups.items():
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                if a["original_id"] == b["original_id"]:
                    continue
                comparisons += 1
                ad = people_by_audit[a["audit_id"]]["date_of_birth_primary_candidate"]
                bd = people_by_audit[b["audit_id"]]["date_of_birth_primary_candidate"]
                if not ad or not bd or ad != bd:
                    unequal_dates += 1
                    continue
                # Stable ordering independent of which historic alias was first.
                left, right = sorted((a["audit_id"], b["audit_id"]))
                key = (disc, left, right)
                if key not in proposals:
                    proposals[key] = {
                        "members": {}, "date": ad,
                        "shared_partners": set(), "partner_names": set(),
                        "pairs": defaultdict(set),
                    }
                evidence = proposals[key]
                for person in (a, b):
                    evidence["members"][person["audit_id"]] = (
                        person["original_id"], person["name"]
                    )
                    evidence["pairs"][person["audit_id"]].add(person["pair_id"])
                evidence["shared_partners"].add(partner_id)
                evidence["partner_names"].add(a["partner_name"])
                evidence["partner_names"].add(b["partner_name"])

    mapped_rules, used_rules = {}, set()
    for r in rules:
        canon, alternate = r["canonical_person_id"], r["alternate_person_id"]
        if (canon == alternate or canon not in people_by_audit or
                alternate not in people_by_audit):
            raise ValueError("Reviewed alias IDs missing or identical")
        if alternate in mapped_rules:
            raise ValueError("Duplicate reviewed alternate identity")
        if r["evidence_status"] != "source_reviewed_same_person":
            raise ValueError("Reviewed alias source flag is unsupported")
        if not valid_date(r["expected_dob"]):
            raise ValueError("Reviewed alias DOB invalid")
        for x in (canon, alternate):
            audited = people_by_audit[x]
            if audited["date_of_birth_primary_candidate"] != r["expected_dob"]:
                raise ValueError("Source-reviewed identity DOB disagrees with official audit: " + x)
            if r["discipline"] not in split_disc(audited["disciplines"]):
                raise ValueError("Reviewed identity discipline differs from historical source")
            if audited["original_historic_person_id"] != x:
                raise ValueError("Reviewed alias cannot target a split/ambiguous original ID")
        cp, ap = indexed_pairs.get(r["canonical_pair_id"]), indexed_pairs.get(r["alternate_pair_id"])
        if cp is None or ap is None:
            raise ValueError("Reviewed identity links reference unknown original pairs")
        sides = []
        for row, member in ((cp, canon), (ap, alternate)):
            if row["discipline"] != r["discipline"]:
                raise ValueError("Reviewed alias historic pair discipline mismatch")
            if member == row["person_a_id"]:
                other = row["person_b_id"]
                role = "a"
            elif member == row["person_b_id"]:
                other = row["person_a_id"]
                role = "b"
            else:
                raise ValueError("Reviewed person ID not present in cited historical pair")
            if other != r["shared_partner_person_id"]:
                raise ValueError("Reviewed alias does not share exact historic partner")
            sides.append(role)
        if len(set(sides)) != 1:
            raise ValueError("Reviewed aliases changed member role between partner pairs")
        profile = r["official_profile_id"].lower()
        url = urlsplit(r["official_source_url"])
        if (not re.fullmatch(r"isufs[0-9]+", profile)
                or url.scheme != "https" or url.hostname not in HOSTS
                or url.path.lower() != f"/bios/{profile}.htm"
                or url.username or url.password or url.port is not None
                or url.query or url.fragment):
            raise ValueError("Reviewed alias is not attached to a valid official ISU biography")
        other_url = urlsplit(r["corroborating_source_url"])
        if (other_url.scheme != "https" or other_url.hostname not in HOSTS
                or other_url.username is not None or other_url.password is not None
                or other_url.port is not None or other_url.query or other_url.fragment
                or not other_url.path.startswith(("/results/", "/events/", "/en/", "/bios/"))):
            raise ValueError("Reviewed alias corroboration is not an approved ISU source")
        expected_side = "1" if sides[0] == "a" else "2"
        if r["profile_side"] != expected_side:
            raise ValueError("Reviewed official side differs from historical pair member role")
        key = (r["discipline"], *sorted((canon, alternate)))
        if key not in proposals:
            raise ValueError("Reviewed alias has no same-partner, same-DOB historic evidence")
        used_rules.add(key)
        mapped_rules[alternate] = (canon, r)

    if any(k in mapped_rules for k in
           (v[0] for v in mapped_rules.values())):
        raise ValueError("Chained official alias merges require explicit independent review")

    rows = []
    for (disc, aa, bb), p in sorted(proposals.items()):
        a_id, a_name = p["members"][aa]
        b_id, b_name = p["members"][bb]
        reviewed = (disc, aa, bb) in used_rules
        matched_rule = None
        if reviewed:
            matched_rule = next(
                rule for _, rule in mapped_rules.values()
                if rule["discipline"] == disc and
                set((rule["canonical_person_id"], rule["alternate_person_id"])) == set((aa, bb))
            )
        rows.append({
            "discipline": disc, "audit_person_a_id": aa,
            "audit_person_b_id": bb,
            "historic_person_a_id": a_id, "historic_person_b_id": b_id,
            "historic_name_a": a_name, "historic_name_b": b_name,
            "shared_dob": p["date"],
            "shared_partner_ids": joined(p["shared_partners"]),
            "shared_partner_names": joined(p["partner_names"]),
            "historic_pair_ids_a": joined(p["pairs"][aa]),
            "historic_pair_ids_b": joined(p["pairs"][bb]),
            "name_similarity_review_only": round(
                SequenceMatcher(None, norm_name(a_name), norm_name(b_name)).ratio(), 4
            ),
            "identity_review_status": (
                "source_reviewed_reversible_merge"
                if reviewed else "candidate_same_partner_same_dob_not_merged"
            ),
            "source_review_url": (
                matched_rule["official_source_url"] if matched_rule else ""
            ),
            "review_note": (
                matched_rule["identity_note"] if matched_rule
                else "Same partner and official DOB are identity leads, not independent identity proof"
            ),
        })
    rows.sort(key=lambda x: (
        x["identity_review_status"] != "source_reviewed_reversible_merge",
        -float(x["name_similarity_review_only"]), x["audit_person_a_id"],
        x["audit_person_b_id"],
    ))

    projected_members = defaultdict(list)
    for audit_id, item in people_by_audit.items():
        normalized = mapped_rules[audit_id][0] if audit_id in mapped_rules else audit_id
        projected_members[normalized].append(item)
    people_preview = []
    for canonical, members in sorted(projected_members.items()):
        dates = {r["date_of_birth_primary_candidate"] for r in members}
        if len(dates) != 1 or "" in dates:
            raise ValueError("Projected identity has missing or conflicting official DOBs")
        people_preview.append({
            "projected_person_id": canonical,
            "audit_person_ids": joined(r["audit_person_id"] for r in members),
            "original_historic_person_ids": joined(
                r["original_historic_person_id"] for r in members),
            "historic_names": joined(r["historic_name"] for r in members),
            "date_of_birth": next(iter(dates)),
            "source_person_rows": len(members),
            "status": "source_reviewed_id_alias_group" if len(members) > 1
                      else "unchanged_audit_identity",
        })

    grouped_pairs = defaultdict(list)
    for pair_id, row in indexed_pairs.items():
        a, b = pair_audit_members[pair_id]
        aa = mapped_rules[a][0] if a in mapped_rules else a
        bb = mapped_rules[b][0] if b in mapped_rules else b
        if aa == bb:
            raise ValueError("Approved alias merges would create a self-partner")
        grouped_pairs[(row["discipline"], aa, bb)].append(row)
    pair_preview = []
    for (disc, aa, bb), items in sorted(grouped_pairs.items()):
        ids = sorted(r["pair_id"] for r in items)
        pair_preview.append({
            "discipline": disc, "projected_person_a_id": aa,
            "projected_person_b_id": bb,
            "original_pair_ids": joined(ids),
            "original_pair_rows": len(items),
            "original_pair_names": joined(
                r["person_a_name"] + " / " + r["person_b_name"] for r in items
            ),
            "original_pair_seasons": joined(
                season for r in items for season in split_disc(r["observed_seasons"])
            ),
            "pair_group_status": (
                "multiple_history_pair_ids_source_reviewed" if len(items) > 1
                else "unique_original_pair_id"
            ),
            "event_count_aggregation_status": "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP",
        })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_shared_partner_same_dob_candidates_v1.csv", CAND_FIELDS, rows)
    write_csv(out / "historic_reviewed_person_id_preview_v1.csv", PERSON_FIELDS, people_preview)
    write_csv(out / "historic_reviewed_pair_groups_preview_v1.csv", PAIR_FIELDS, pair_preview)

    tally = Counter(x["identity_review_status"] for x in rows)
    report = {
        "stage": "historic_partner_dob_alias_audit_not_a_frozen_cohort",
        "input_audited_person_slots": len(people_by_audit),
        "input_original_pair_ids": len(indexed_pairs),
        "possible_same_partner_same_official_dob_alias_groups": len(rows),
        "source_reviewed_alias_groups": tally["source_reviewed_reversible_merge"],
        "additional_alias_groups_for_review": tally["candidate_same_partner_same_dob_not_merged"],
        "different_or_missing_dob_shared_partner_comparisons_not_merged": unequal_dates,
        "source_reviewed_reversible_merges_applied_to_preview_only": len(mapped_rules),
        "projected_person_identity_slots": len(people_preview),
        "projected_unique_pair_groups": len(pair_preview),
        "pair_groups_with_multiple_old_pair_ids": sum(
            len(v) > 1 for v in grouped_pairs.values()),
        "identity_groups_with_multiple_old_person_ids": sum(
            len(v) > 1 for v in projected_members.values()),
        "inputs_sha256": {str(p): digest(p) for p in paths},
        "limitations": [
            "All outputs are a reversible QA preview, not a frozen analysis sample",
            "The same partner and DOB are not by themselves identity proof",
            "Only explicitly source-reviewed links in the selected adjudication CSV are applied; further candidates remain separate",
            "Event counts and season ranking positions are not aggregated",
            "Same-name different-person homonyms remain split by their audited IDs",
            "Same-person aliases not sharing an identical original partner may remain undiscovered",
            "The sample covers selected historic skating events only, not all entrants",
            "No BaZi, null-model simulation, outcome selection or original master edits",
        ],
    }
    (out / "historic_shared_partner_alias_manifest_v1.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def split_disc(value):
    return {x.strip() for x in (value or "").split(";") if x.strip()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--people", default="output/historic_dob/coverage/historic_dob_coverage_people_v1.csv")
    p.add_argument("--pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--reviewed", default=str(DEFAULT_RULES))
    p.add_argument("--out", default="output/historic_dob/shared_partner_identity")
    args = p.parse_args()
    audit(args.people, args.pairs, args.reviewed, args.out)


if __name__ == "__main__":
    main()
