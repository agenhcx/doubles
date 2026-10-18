#!/usr/bin/env python3
"""Build a non-destructive, date-complete ISU ranked-pairs *candidate* cohort.

Two explicit observational units:
  1) distinct pair, counted once across seasons;
  2) pair-season-level ranking appearance, not an event result.

No BaZi, calendar null, geocoding, network access or updates to master files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from audit_isu_identities import digest, joined, read_csv, valid_date, write_csv

PAIR_FIELDS = [
    "discipline", "canonical_pair_id", "person_a_id", "person_b_id",
    "person_a_names", "person_b_names", "person_a_dob", "person_b_dob",
    "absolute_dob_gap_days", "first_season", "last_season",
    "distinct_ranking_seasons", "levels", "represented_nations",
    "ranking_rows", "profile_ids", "ranking_source_urls"
]
SEASON_FIELDS = [
    "season", "level", "discipline", "canonical_pair_id",
    "person_a_id", "person_b_id", "person_a_dob", "person_b_dob",
    "rank_in_season", "ranking_points", "nation",
    "ranking_source_url", "profile_url"
]
PERSON_FIELDS = [
    "canonical_person_id", "roster_names", "date_of_birth",
    "number_of_distinct_partners", "distinct_pair_ids", "disciplines",
    "seasons", "ranking_rows"
]


def require_fields(rows, required, label):
    if not rows:
        raise ValueError(label + " is empty")
    missing = set(required).difference(rows[0])
    if missing:
        raise ValueError(label + " missing: " + joined(missing))


def build_cohort(people_path, roster_path, out_dir="output/cohort"):
    people_path, roster_path, out_dir = map(Path, (people_path, roster_path, out_dir))
    # Read before writing any files; invalid data should not overwrite a prior
    # successful candidate cohort.
    people_rows = read_csv(people_path)
    ranking_rows = read_csv(roster_path)
    require_fields(people_rows, (
        "canonical_person_id", "roster_names", "date_of_birth", "dob_status"
    ), "canonical people")
    require_fields(ranking_rows, (
        "canonical_pair_id", "canonical_person_a_id", "canonical_person_b_id",
        "season", "discipline", "level", "rank", "ranking_points",
        "person_a_name", "person_b_name", "nation", "source_url", "profile_url"
    ), "canonical ranking roster")

    people = {}
    for r in people_rows:
        pid = r["canonical_person_id"]
        if not pid or pid in people:
            raise ValueError("Duplicate or blank canonical person ID")
        if r["dob_status"] != "consistent" or not valid_date(r["date_of_birth"]):
            raise ValueError("Incomplete/conflicting DOB for canonical person: " + pid)
        people[pid] = r

    pairs = {}
    appearances = []
    seen_appearances = set()
    person_pairs = defaultdict(set)
    person_rows = Counter()
    person_seasons = defaultdict(set)
    person_disciplines = defaultdict(set)
    member_roles = defaultdict(set)

    for r in ranking_rows:
        discipline, pairid = r["discipline"], r["canonical_pair_id"]
        a, b = r["canonical_person_a_id"], r["canonical_person_b_id"]
        season, level = r["season"], r["level"]
        if discipline not in {"Ice Dance", "Pair Skating"}:
            raise ValueError("Unknown discipline: " + discipline)
        if level not in {"senior", "junior"} or not (
            len(season) == 7 and season[4] == "-"
            and season[:4].isdigit() and season[5:].isdigit()
        ):
            raise ValueError("Invalid season or category")
        if not pairid or not a or not b or a == b:
            raise ValueError("Invalid pair/member ID")
        if a not in people or b not in people:
            raise ValueError("Ranking row refers to missing person")
        if not r["source_url"]:
            raise ValueError("Missing ranking provenance")
        k = (discipline, pairid)
        members = (a, b)
        obs_key = (discipline, pairid, season, level)
        if obs_key in seen_appearances:
            raise ValueError("Duplicate pair-season-level ranking observation")
        seen_appearances.add(obs_key)
        if k in pairs and pairs[k]["members"] != members:
            raise ValueError("Same canonical pair ID maps to different members")
        if k not in pairs:
            pairs[k] = {
                "members": members, "a_names": set(), "b_names": set(),
                "seasons": set(), "levels": set(), "nations": set(),
                "source_urls": set(), "profiles": set(), "count": 0
            }
        item = pairs[k]
        item["count"] += 1
        item["a_names"].add(r["person_a_name"])
        item["b_names"].add(r["person_b_name"])
        item["seasons"].add(season)
        item["levels"].add(level)
        if r["nation"]:
            item["nations"].add(r["nation"])
        item["source_urls"].add(r["source_url"])
        if r["profile_url"]:
            item["profiles"].add(r["profile_url"])

        for person, role in ((a, "A"), (b, "B")):
            person_pairs[person].add(k)
            person_rows[person] += 1
            person_seasons[person].add(season)
            person_disciplines[person].add(discipline)
            member_roles[person].add(role)

        appearances.append({
            "season": season, "level": level, "discipline": discipline,
            "canonical_pair_id": pairid, "person_a_id": a, "person_b_id": b,
            "person_a_dob": people[a]["date_of_birth"],
            "person_b_dob": people[b]["date_of_birth"],
            "rank_in_season": r["rank"], "ranking_points": r["ranking_points"],
            "nation": r["nation"], "ranking_source_url": r["source_url"],
            "profile_url": r["profile_url"],
        })

    if set(people) != set(person_pairs):
        raise ValueError("Some canonical people have no ranking appearance")
    pair_export = []
    for (discipline, pairid), rec in sorted(pairs.items()):
        a, b = rec["members"]
        da, db = people[a]["date_of_birth"], people[b]["date_of_birth"]
        gap = abs((dt.date.fromisoformat(da) - dt.date.fromisoformat(db)).days)
        seasons = sorted(rec["seasons"])
        pair_export.append({
            "discipline": discipline, "canonical_pair_id": pairid,
            "person_a_id": a, "person_b_id": b,
            "person_a_names": joined(rec["a_names"]),
            "person_b_names": joined(rec["b_names"]),
            "person_a_dob": da, "person_b_dob": db,
            "absolute_dob_gap_days": gap,
            "first_season": seasons[0], "last_season": seasons[-1],
            "distinct_ranking_seasons": len(seasons),
            "levels": joined(rec["levels"]),
            "represented_nations": joined(rec["nations"]),
            "ranking_rows": rec["count"],
            "profile_ids": joined(rec["profiles"]),
            "ranking_source_urls": joined(rec["source_urls"])
        })

    person_export = [
        {
            "canonical_person_id": pid, "roster_names": people[pid]["roster_names"],
            "date_of_birth": people[pid]["date_of_birth"],
            "number_of_distinct_partners": len(person_pairs[pid]),
            "distinct_pair_ids": joined(k[1] for k in person_pairs[pid]),
            "disciplines": joined(person_disciplines[pid]),
            "seasons": joined(person_seasons[pid]),
            "ranking_rows": person_rows[pid],
        }
        for pid in sorted(people)
    ]
    appearances.sort(key=lambda r: (r["season"], r["discipline"], r["level"], r["canonical_pair_id"]))
    multi_partner = [r for r in person_export if r["number_of_distinct_partners"] > 1]

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "ranked_pairs": out_dir / "isu_ranked_pairs_candidate_v1.csv",
        "ranked_pair_seasons": out_dir / "isu_ranked_pair_seasons_candidate_v1.csv",
        "multi_partner": out_dir / "isu_multi_partner_athletes_v1.csv",
    }
    write_csv(paths["ranked_pairs"], PAIR_FIELDS, pair_export)
    write_csv(paths["ranked_pair_seasons"], SEASON_FIELDS, appearances)
    write_csv(paths["multi_partner"], PERSON_FIELDS, multi_partner)

    summary = {
        "status": "QA_candidate_not_frozen",
        "scope": "2018-19 through 2025-26 ISU season rankings (not all entrants)",
        "unique_athletes_with_dob": len(people),
        "unique_ranked_pairs": len(pair_export),
        "ranking_pair_season_level_rows": len(appearances),
        "pairs_by_discipline": dict(sorted(Counter(r["discipline"] for r in pair_export).items())),
        "people_in_multiple_pairs": len(multi_partner),
        "max_number_of_pairs_per_person": max(len(s) for s in person_pairs.values()),
        "people_seen_on_both_roster_sides": sum(len(s) > 1 for s in member_roles.values()),
        "observation_units": {
            "primary_candidate": "one row per canonical pair (regardless of season)",
            "secondary_descriptive": "one row per pair-season-level ranking appearance",
            "not_independent": "pairs may share an athlete and must not be treated as independent dyads",
        },
        "input_sha256": {
            str(people_path): digest(people_path),
            str(roster_path): digest(roster_path),
        },
        "output_sha256": {k: digest(path) for k, path in paths.items()},
        "limitations": [
            "Full DOB coverage is conditional on inclusion in ISU season ranking pages",
            "Competition results and ranking appearances are distinct units",
            "Multiple pairs can share one skater; naive per-pair p-values are invalid",
            "No compatibility score, fate features, birth time, geocoding or null model computed",
            "Data collection and eligibility criteria require independent review before freezing",
        ],
    }
    (out_dir / "isu_ranked_cohort_candidate_manifest_v1.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        k: summary[k] for k in (
            "status", "unique_athletes_with_dob", "unique_ranked_pairs",
            "ranking_pair_season_level_rows", "people_in_multiple_pairs",
            "max_number_of_pairs_per_person", "people_seen_on_both_roster_sides",
        )
    }, indent=2, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--people", default="output/identity/supplemental/identity_canonical_people_supplemented.csv"
    )
    parser.add_argument(
        "--roster", default="output/identity/identity_canonical_season_roster.csv"
    )
    parser.add_argument("--out", default="output/cohort")
    options = parser.parse_args()
    build_cohort(options.people, options.roster, options.out)


if __name__ == "__main__":
    main()
