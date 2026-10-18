#!/usr/bin/env python3
"""Offline, non-destructive DOB completeness report for canonical ISU pairs.

Run after audit_isu_identities.py. Does not fetch webpages, geocode, infer DOB,
calculate BaZi, or write to the original ranking and identity master tables.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from audit_isu_identities import read_csv, write_csv, valid_date, joined

PERSON_FIELDS = [
    "canonical_person_id", "roster_names", "dob_status", "roster_rows",
    "pair_count", "seasons", "disciplines", "partners", "pair_ids",
    "ranking_source_urls", "existing_profile_urls", "followup_status"
]
PAIR_FIELDS = [
    "canonical_pair_id", "discipline", "person_a_id", "person_b_id",
    "person_a_names", "person_b_names", "person_a_dob_status",
    "person_b_dob_status", "missing_members", "roster_rows", "seasons",
    "levels", "profile_linked_rows", "ranking_source_urls",
    "followup_status"
]
SEASON_FIELDS = [
    "season", "level", "discipline", "unique_pairs", "pairs_both_dob",
    "pairs_one_dob", "pairs_no_dob", "fraction_pairs_both_dob"
]


def required(rows, names, label):
    if not rows:
        raise ValueError(label + " is empty")
    absent = set(names) - rows[0].keys()
    if absent:
        raise ValueError(label + " is missing columns: " + joined(absent))


def build_coverage(people_path, roster_path, out_dir="output/identity"):
    people_rows = read_csv(people_path)
    roster = read_csv(roster_path)
    required(people_rows, ("canonical_person_id", "roster_names",
                           "date_of_birth", "dob_status"), "canonical people")
    required(roster, ("canonical_pair_id", "discipline", "season", "level",
                      "canonical_person_a_id", "canonical_person_b_id",
                      "person_a_name", "person_b_name", "source_url",
                      "profile_url"), "canonical season roster")

    people = {}
    for entry in people_rows:
        person = entry["canonical_person_id"]
        if not person or person in people:
            raise ValueError("Blank or duplicate canonical person ID")
        status, dob = entry["dob_status"], entry["date_of_birth"]
        if status not in ("consistent", "dob_conflict", "no_verified_bio"):
            raise ValueError("Unknown DOB status for " + person)
        if (status == "consistent") != bool(dob):
            raise ValueError("DOB value contradicts status for " + person)
        if dob and not valid_date(dob):
            raise ValueError("Invalid canonical DOB for " + person)
        people[person] = entry

    person_use = defaultdict(lambda: {
        "rows": 0, "pairs": set(), "seasons": set(), "disciplines": set(),
        "partners": set(), "source_urls": set(), "profiles": set()
    })
    pairs = {}
    season_pairs = defaultdict(dict)
    ranking_rows_with_both_dob = 0

    for item in roster:
        disc, pair = item["discipline"], item["canonical_pair_id"]
        a, b = item["canonical_person_a_id"], item["canonical_person_b_id"]
        if not pair or not disc or not a or not b or a == b:
            raise ValueError("Missing or invalid canonical pair/members")
        if a not in people or b not in people:
            raise ValueError("Canonical roster references unknown person")
        key = (disc, pair)
        members = (a, b)
        if key not in pairs:
            pairs[key] = {
                "members": members, "rows": 0, "seasons": set(),
                "levels": set(), "a_names": set(), "b_names": set(),
                "profile_rows": 0, "source_urls": set()
            }
        rec = pairs[key]
        if rec["members"] != members:
            raise ValueError("One canonical pair ID has inconsistent members")
        statuses = [people[m]["dob_status"] for m in members]
        both = statuses.count("consistent") == 2
        if both:
            ranking_rows_with_both_dob += 1

        rec["rows"] += 1
        rec["seasons"].add(item["season"])
        rec["levels"].add(item["level"])
        rec["a_names"].add(item["person_a_name"])
        rec["b_names"].add(item["person_b_name"])
        if item["profile_url"]:
            rec["profile_rows"] += 1
        rec["source_urls"].add(item["source_url"])

        cohort = (item["season"], item["level"], disc)
        # One pair may appear in multiple seasons or both junior/senior.
        # A pair-season-level is counted once within its cohort.
        season_pairs[cohort][key] = statuses.count("consistent")

        for person, partner in ((a, b), (b, a)):
            usage = person_use[person]
            usage["rows"] += 1
            usage["pairs"].add(pair)
            usage["seasons"].add(item["season"])
            usage["disciplines"].add(disc)
            usage["partners"].add(partner)
            usage["source_urls"].add(item["source_url"])
            if item["profile_url"]:
                usage["profiles"].add(item["profile_url"])

    if set(people) != set(person_use):
        raise ValueError("Canonical people and roster membership disagree")

    missing_people = []
    for person, rec in people.items():
        if rec["dob_status"] == "consistent":
            continue
        use = person_use[person]
        missing_people.append({
            "canonical_person_id": person,
            "roster_names": rec["roster_names"],
            "dob_status": rec["dob_status"],
            "roster_rows": use["rows"],
            "pair_count": len(use["pairs"]),
            "seasons": joined(use["seasons"]),
            "disciplines": joined(use["disciplines"]),
            "partners": joined(people[p]["roster_names"] for p in use["partners"]),
            "pair_ids": joined(use["pairs"]),
            "ranking_source_urls": joined(use["source_urls"]),
            "existing_profile_urls": joined(use["profiles"]),
            "followup_status": "needs_official_dob_evidence"
        })
    missing_people.sort(key=lambda r: (-int(r["roster_rows"]),
                                       -int(r["pair_count"]),
                                       r["canonical_person_id"]))

    missing_pairs = []
    pair_counter = Counter()
    discipline_counter = defaultdict(Counter)
    for (disc, pair), record in sorted(pairs.items()):
        a, b = record["members"]
        sa, sb = people[a]["dob_status"], people[b]["dob_status"]
        missing_count = (sa != "consistent") + (sb != "consistent")
        pair_counter[missing_count] += 1
        discipline_counter[disc][missing_count] += 1
        if not missing_count:
            continue
        missing_pairs.append({
            "canonical_pair_id": pair, "discipline": disc,
            "person_a_id": a, "person_b_id": b,
            "person_a_names": joined(record["a_names"]),
            "person_b_names": joined(record["b_names"]),
            "person_a_dob_status": sa, "person_b_dob_status": sb,
            "missing_members": missing_count, "roster_rows": record["rows"],
            "seasons": joined(record["seasons"]),
            "levels": joined(record["levels"]),
            "profile_linked_rows": record["profile_rows"],
            "ranking_source_urls": joined(record["source_urls"]),
            "followup_status": "needs_official_dob_evidence"
        })
    missing_pairs.sort(key=lambda r: (-int(r["missing_members"]),
                                      -int(r["roster_rows"]),
                                      r["canonical_pair_id"]))

    by_season = []
    for (season, level, disc), table in sorted(season_pairs.items()):
        c = Counter(table.values())
        total = len(table)
        by_season.append({
            "season": season, "level": level, "discipline": disc,
            "unique_pairs": total,
            "pairs_both_dob": c[2],
            "pairs_one_dob": c[1],
            "pairs_no_dob": c[0],
            "fraction_pairs_both_dob": round(c[2] / total, 8)
        })

    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "dob_missing_people.csv", PERSON_FIELDS, missing_people)
    write_csv(output / "dob_missing_pairs.csv", PAIR_FIELDS, missing_pairs)
    write_csv(output / "dob_coverage_by_season.csv", SEASON_FIELDS, by_season)

    total_pairs = len(pairs)
    summary = {
        "scope": "2018-19 to 2025-26 ranked ISU ice dance/pair skating pairs only",
        "canonical_people": len(people),
        "people_with_consistent_dob": sum(r["dob_status"] == "consistent" for r in people.values()),
        "people_without_consistent_dob": len(missing_people),
        "people_with_dob_conflict": sum(r["dob_status"] == "dob_conflict" for r in people.values()),
        "canonical_pairs": total_pairs,
        "pairs_both_dob": pair_counter[0],
        "pairs_one_dob": pair_counter[1],
        "pairs_no_dob": pair_counter[2],
        "fraction_pairs_both_dob": round(pair_counter[0] / total_pairs, 8),
        "ranking_rows": len(roster),
        "ranking_rows_both_dob": ranking_rows_with_both_dob,
        "incomplete_pair_breakdown": {
            discipline: {
                "both_dob": counts[0], "one_dob": counts[1],
                "no_dob": counts[2]
            } for discipline, counts in sorted(discipline_counter.items())
        },
        "outputs": ["dob_missing_people.csv", "dob_missing_pairs.csv",
                    "dob_coverage_by_season.csv"],
        "limitations": [
            "Ranked pairs are not all international or national entrants",
            "The same skater may participate in multiple pair/season rows",
            "A linked official DOB is not an independently reverified DOB",
            "No missing DOB has been guessed and no data source is overwritten",
            "The missing-person queue is a completeness audit, not a performance-selected sample"
        ]
    }
    (output / "dob_coverage_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--people", default="output/identity/identity_canonical_people.csv")
    parser.add_argument("--roster", default="output/identity/identity_canonical_season_roster.csv")
    parser.add_argument("--out", default="output/identity")
    args = parser.parse_args()
    build_coverage(args.people, args.roster, args.out)


if __name__ == "__main__":
    main()
