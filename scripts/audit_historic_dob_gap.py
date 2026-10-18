#!/usr/bin/env python3
"""Audit the 2004-2018 ISU historical DOB gap before any additional scraping.

Match *candidates* against the already-audited 2018-2026 roster using complete
normalized names and (where possible) the same published skating partnership.
All cross-era matches remain reviewable, never silently added to a master file.

No web requests, BaZi, demographic/geographic guesses or master mutation.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_isu_identities import digest, joined, norm, read_csv, valid_date, write_csv

FIELDS = [
    "historic_person_id", "historic_name", "historic_name_variants",
    "discipline", "historic_nations", "identified_competitions",
    "historic_partner_names", "historic_pair_ids", "match_status",
    "ranked_canonical_id", "ranked_roster_names", "ranked_dob_candidate",
    "ranking_profile_ids", "supplemental_dob_url",
    "identical_pair_support", "possible_partner_alias_ids",
    "is_abbreviated", "review_required"
]
PRIORITY = {
    "exact_name_same_pair": 0, "exact_name_only": 1,
    "partner_alias_suggestion": 2, "ambiguous_full_name": 3,
    "unmatched_full_name": 4, "abbreviated_or_incomplete_name": 5
}


def name_options(row, field, variant_field=None, delim=None):
    names = [row.get(field, "")]
    if variant_field:
        raw = row.get(variant_field, "")
        names.extend(raw.split(delim) if delim else raw.split(";"))
    return {s.strip() for s in names if s.strip()}


def safe_name(name):
    # Initial-only records such as "DAVIDOVICH A" are NOT reliable IDs.
    parts = re.findall(r"[a-z0-9]+", norm(name))
    return len(parts) >= 2 and all(len(x) >= 2 for x in parts)


def historic_candidates(
    old_people_path="data/historic/v4/athletes_v4.csv",
    old_pairs_path="data/historic/v4/couples_v4.csv",
    new_people_path="output/identity/supplemental/identity_canonical_people_supplemented.csv",
    new_roster_path="output/identity/identity_canonical_season_roster.csv",
    out_dir="output/historic_dob",
):
    paths = list(map(Path, (old_people_path, old_pairs_path, new_people_path, new_roster_path)))
    old_people, old_pairs, new_people, new_roster = [read_csv(p) for p in paths]
    if not all((old_people, old_pairs, new_people, new_roster)):
        raise ValueError("Input empty: historical and ranked data are all required")

    old_index = {}
    for row in old_people:
        pid = row["person_id"]
        if not pid or pid in old_index:
            raise ValueError("Duplicate or blank historical athlete ID")
        old_index[pid] = row

    canonical = {}
    ranked_names = defaultdict(set)
    for row in new_people:
        pid = row["canonical_person_id"]
        if not pid or pid in canonical:
            raise ValueError("Duplicate or blank canonical athlete ID")
        if row.get("dob_status") != "consistent" or not valid_date(row.get("date_of_birth", "")):
            raise ValueError("Incomplete ranked DOB; complete source audit first: " + pid)
        canonical[pid] = row
        for name in name_options(row, "roster_names"):
            if safe_name(name):
                ranked_names[norm(name)].add(pid)

    rank_pairs = set()
    rank_neighbors = defaultdict(set)
    for row in new_roster:
        d = row["discipline"]
        a, b = row["canonical_person_a_id"], row["canonical_person_b_id"]
        if a not in canonical or b not in canonical or a == b:
            raise ValueError("Ranked pair references unknown person")
        rank_pairs.add((d, a, b))
        rank_neighbors[(d, "a", a)].add(b)
        rank_neighbors[(d, "b", b)].add(a)

    old_partner_ids = defaultdict(set)
    old_pair_ids = defaultdict(set)
    for row in old_pairs:
        a, b = row["person_a_id"], row["person_b_id"]
        if a not in old_index or b not in old_index or a == b:
            raise ValueError("Historical pair has invalid person IDs")
        old_partner_ids[a].add(b)
        old_partner_ids[b].add(a)
        old_pair_ids[a].add(row["pair_id"])
        old_pair_ids[b].add(row["pair_id"])

    matched = {}
    has_safe_name = {}
    for pid, row in old_index.items():
        variants = name_options(row, "name_display", "name_variants", " | ")
        safe = {v for v in variants if safe_name(v)}
        has_safe_name[pid] = bool(safe)
        matched[pid] = set().union(*(ranked_names.get(norm(v), set()) for v in safe)) if safe else set()

    same_pair_support = defaultdict(set)
    alias_suggestions = defaultdict(set)
    for row in old_pairs:
        d, a, b = row["discipline"], row["person_a_id"], row["person_b_id"]
        if len(matched[a]) == len(matched[b]) == 1:
            ca, cb = next(iter(matched[a])), next(iter(matched[b]))
            if (d, ca, cb) in rank_pairs:
                same_pair_support[a].add(row["pair_id"])
                same_pair_support[b].add(row["pair_id"])

        # The unchanged partner can propose an alias, but never approve one.
        if len(matched[a]) == 1 and not matched[b]:
            ca = next(iter(matched[a]))
            alias_suggestions[b].update(rank_neighbors.get((d, "a", ca), set()))
        if len(matched[b]) == 1 and not matched[a]:
            cb = next(iter(matched[b]))
            alias_suggestions[a].update(rank_neighbors.get((d, "b", cb), set()))

    rows = []
    counts = Counter()
    for pid, row in sorted(old_index.items()):
        options = matched[pid]
        pair_support = same_pair_support.get(pid, set())
        if not has_safe_name[pid]:
            status = "abbreviated_or_incomplete_name"
        elif len(options) > 1:
            status = "ambiguous_full_name"
        elif len(options) == 1 and pair_support:
            status = "exact_name_same_pair"
        elif len(options) == 1:
            status = "exact_name_only"
        elif alias_suggestions[pid]:
            status = "partner_alias_suggestion"
        else:
            status = "unmatched_full_name"
        counts[status] += 1

        cp = next(iter(options)) if len(options) == 1 else ""
        verified = canonical.get(cp, {})
        partners = old_partner_ids.get(pid, set())
        rows.append({
            "historic_person_id": pid,
            "historic_name": row["name_display"],
            "historic_name_variants": row.get("name_variants", ""),
            "discipline": row["disciplines"],
            "historic_nations": row.get("represented_nations", ""),
            "identified_competitions": row.get("distinct_identified_competitions", ""),
            "historic_partner_names": joined(old_index[p]["name_display"] for p in partners),
            "historic_pair_ids": joined(old_pair_ids.get(pid, set())),
            "match_status": status,
            "ranked_canonical_id": cp,
            "ranked_roster_names": verified.get("roster_names", ""),
            "ranked_dob_candidate": verified.get("date_of_birth", ""),
            "ranking_profile_ids": verified.get("biography_profile_ids", ""),
            "supplemental_dob_url": verified.get("supplemental_source_url", ""),
            "identical_pair_support": joined(pair_support),
            "possible_partner_alias_ids": joined(alias_suggestions.get(pid, set())),
            "is_abbreviated": "YES" if not has_safe_name[pid] else "NO",
            "review_required": "YES",
        })

    # Sort with high-evidence links first, then competition count within tiers.
    rows.sort(key=lambda x: (
        PRIORITY[x["match_status"]],
        -(int(x["identified_competitions"]) if x["identified_competitions"].isdigit() else 0),
        x["historic_person_id"]
    ))
    already = [r for r in rows if r["match_status"] == "exact_name_same_pair"]
    queue = [r for r in rows if r["match_status"] != "exact_name_same_pair"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_identity_dob_candidates.csv", FIELDS, rows)
    write_csv(out / "historic_same_pair_candidates.csv", FIELDS, already)
    write_csv(out / "historic_dob_followup_queue.csv", FIELDS, queue)

    report = {
        "scope": "Selected 2004-2018 historical ISU event data, not all entrants",
        "status": "identity_candidates_not_frozen_no_dob_master_updates",
        "historical_people": len(old_people),
        "historical_pairs": len(old_pairs),
        "ranked_people_with_dob": len(new_people),
        "matched_historic_people_any_full_name": sum(len(v) == 1 for v in matched.values()),
        "same_pair_correlated_dob_candidates": counts["exact_name_same_pair"],
        "name_only_dob_candidates_need_review": counts["exact_name_only"],
        "identity_status_counts": dict(sorted(counts.items())),
        "followup_people": len(queue),
        "input_sha256": {str(p): digest(p) for p in paths},
        "limitations": [
            "The historical list is drawn from selected ISU events, not all skaters",
            "Historical names with initials cannot be safely auto-resolved",
            "Exact names alone are candidates, not identity confirmations",
            "A shared historical/ranked pair gives stronger linkage but not independent DOB verification",
            "Former-partner suggestions are NEVER treated as proven identity",
            "No BaZi and no mutation of master data or original athlete IDs",
        ],
    }
    (out / "historic_dob_gap_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in (
        "historical_people", "historical_pairs",
        "matched_historic_people_any_full_name",
        "same_pair_correlated_dob_candidates",
        "name_only_dob_candidates_need_review", "followup_people",
        "identity_status_counts"
    )}, ensure_ascii=False, indent=2))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historic-people", default="data/historic/v4/athletes_v4.csv")
    p.add_argument("--historic-pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--ranked-people", default="output/identity/supplemental/identity_canonical_people_supplemented.csv")
    p.add_argument("--ranked-roster", default="output/identity/identity_canonical_season_roster.csv")
    p.add_argument("--out", default="output/historic_dob")
    args = p.parse_args()
    historic_candidates(args.historic_people, args.historic_pairs,
                        args.ranked_people, args.ranked_roster, args.out)


if __name__ == "__main__":
    main()
