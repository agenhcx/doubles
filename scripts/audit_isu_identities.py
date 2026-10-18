#!/usr/bin/env python3
"""Offline, non-destructive identity and DOB audit for ISU skating pairs.

Keep the original roster, biographies, and cached HTML unchanged.
Use only source-corroborated, profile-scoped identity links from small
versioned CSVs. This script does not compute BaZi or geocode birthplaces.

PowerShell (one line):
python .\scripts\audit_isu_identities.py --roster .\output\master\season_roster.csv --births .\output\bios\birth_candidates.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALIASES = ROOT / "data" / "adjudications" / "isu_bio_name_links_v1.csv"
DEFAULT_SPLITS = ROOT / "data" / "adjudications" / "isu_profile_id_splits_v1.csv"
PROFILE_RX = re.compile(r"^isufs\d+$", re.I)

LINK_FIELDS = [
    "profile_id", "side_on_profile", "observed_name", "roster_name",
    "original_person_id", "canonical_person_id", "date_of_birth",
    "place_of_birth_raw", "source_status", "name_match_method",
    "link_status", "source_profile_url"
]
PERSON_FIELDS = [
    "canonical_person_id", "roster_names", "disciplines", "seasons",
    "roster_profile_ids", "biography_profile_ids", "date_of_birth",
    "dob_status", "dob_source_count", "birth_places_raw", "birthplace_variant_count"
]
CONFLICT_FIELDS = [
    "canonical_person_id", "distinct_birth_dates", "profile_id",
    "side_on_profile", "date_of_birth", "observed_name", "source_profile_url"
]
ROSTER_EXTRA = [
    "canonical_person_a_id", "canonical_person_b_id",
    "canonical_pair_id", "identity_mapping_status"
]


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def profile_id(raw_url):
    if not raw_url:
        return ""
    stem = Path(urlsplit(raw_url).path).stem.lower()
    return stem if PROFILE_RX.fullmatch(stem) else ""


def norm(value):
    value = unicodedata.normalize("NFKD", (value or "").casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(sorted(re.findall(r"[a-z0-9]+", value)))


def joined(values):
    return "; ".join(sorted({v for v in values if v}))


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def valid_date(value):
    try:
        date = dt.date.fromisoformat(value)
        return value == date.isoformat() and 1850 <= date.year and date <= dt.date.today()
    except (TypeError, ValueError):
        return False


def roster_index(roster):
    positions = defaultdict(lambda: defaultdict(set))
    names = defaultdict(lambda: defaultdict(set))
    ids = set()
    profiles_by_person = defaultdict(set)
    for row in roster:
        pid = profile_id(row.get("profile_url", ""))
        for side, suffix in (("1", "a"), ("2", "b")):
            person = row.get("person_" + suffix + "_id", "")
            name = row.get("person_" + suffix + "_name", "")
            if not person or not name:
                raise ValueError("Missing ranked athlete identifier/name")
            ids.add(person)
            if pid:
                positions[(pid, side)][person].add(name)
                names[(pid, side)][person].add(name)
                profiles_by_person[person].add(pid)
    return positions, ids, profiles_by_person


def load_split_links(path, positions):
    mapping = {}
    seen = set()
    for item in read_csv(path):
        if item["evidence_status"] != "source_corroborated":
            raise ValueError("Unsupported split-link evidence status")
        key = (item["profile_id"].lower(), item["side_on_profile"])
        older, newer = item["canonical_person_id"], item["alternate_person_id"]
        if key in seen or older == newer:
            raise ValueError("Duplicate split link or self-map: " + repr(key))
        seen.add(key)
        available = positions.get(key, {})
        if older not in available or newer not in available:
            raise ValueError("Split IDs not on corresponding official profile side: " + repr(key))
        if norm(item["canonical_name"]) not in {norm(x) for x in available[older]}:
            raise ValueError("Canonical roster name differs: " + repr(key))
        if norm(item["alternate_name"]) not in {norm(x) for x in available[newer]}:
            raise ValueError("Alternate roster name differs: " + repr(key))
        if newer in mapping and mapping[newer] != older:
            raise ValueError("One alternate ID maps to different people")
        mapping[newer] = older
    for later in mapping:
        if mapping[later] in mapping:
            raise ValueError("Chained alias mapping not supported")
    return mapping


def load_bio_aliases(path, positions, split_map):
    aliases = {}
    for item in read_csv(path):
        if item["evidence_status"] != "source_corroborated":
            raise ValueError("Unsupported biography-name evidence status")
        key = (item["profile_id"].lower(), item["side_on_profile"])
        if key in aliases or not valid_date(item["expected_dob"]):
            raise ValueError("Duplicate alias link or invalid expected DOB: " + repr(key))
        original_id = item["roster_person_id"]
        available = positions.get(key, {})
        if original_id not in available:
            raise ValueError("Alias person not in matching ISU profile side: " + repr(key))
        if norm(item["roster_name"]) not in {norm(x) for x in available[original_id]}:
            raise ValueError("Alias roster name differs: " + repr(key))
        if not item["observed_name"]:
            raise ValueError("Alias source name is empty")
        aliases[key] = item
    return aliases


def audit(roster_path, births_path, aliases_path=DEFAULT_ALIASES,
          splits_path=DEFAULT_SPLITS, out_dir="output/identity"):
    roster = read_csv(roster_path)
    births = read_csv(births_path)
    positions, raw_ids, profiles_by_person = roster_index(roster)
    split_map = load_split_links(splits_path, positions)
    aliases = load_bio_aliases(aliases_path, positions, split_map)
    canonical = lambda person_id: split_map.get(person_id, person_id)

    # A profile ID is for a couple; resolve the individual using side 1/2.
    candidates = {}
    for key, members in positions.items():
        candidates[key] = {canonical(x) for x in members}

    # Canonical pair IDs reuse one existing pair ID rather than inventing an ID.
    pair_keys = defaultdict(list)
    for row in roster:
        k = (row["discipline"], canonical(row["person_a_id"]), canonical(row["person_b_id"]))
        pair_keys[k].append((row["season"], row["pair_id"]))
    pair_choices = {k: min(v)[1] for k, v in pair_keys.items()}

    mapped_roster, info = [], defaultdict(lambda: {
        "names": set(), "disciplines": set(), "seasons": set(), "profiles": set()
    })
    for row in roster:
        a, b = canonical(row["person_a_id"]), canonical(row["person_b_id"])
        k = (row["discipline"], a, b)
        enriched = dict(row)
        enriched.update({
            "canonical_person_a_id": a, "canonical_person_b_id": b,
            "canonical_pair_id": pair_choices[k],
            "identity_mapping_status": "source_corroborated_id" if a != row["person_a_id"] or b != row["person_b_id"] else "unchanged"
        })
        mapped_roster.append(enriched)
        for person, name in ((a, row["person_a_name"]), (b, row["person_b_name"])):
            entry = info[person]
            entry["names"].add(name)
            entry["disciplines"].add(row["discipline"])
            entry["seasons"].add(row["season"])
            if profile_id(row.get("profile_url", "")):
                entry["profiles"].add(profile_id(row["profile_url"]))

    links, unresolved = [], []
    seen_slots = set()
    for row in births:
        key = (row.get("profile_id", "").lower(), row.get("side_on_profile", ""))
        status, original_person = "unresolved", ""
        if key in seen_slots:
            status = "duplicate_profile_side"
        else:
            seen_slots.add(key)
            if len(candidates.get(key, set())) != 1:
                status = "profile_side_unavailable_or_ambiguous"
            elif row.get("status") == "exact_name_match" and row.get("person_id", ""):
                original_person = row["person_id"]
                status = "matched_roster_name"
            elif row.get("status") == "needs_review" and key in aliases:
                rule = aliases[key]
                if (norm(row.get("observed_name", "")) == norm(rule["observed_name"])
                        and row.get("date_of_birth") == rule["expected_dob"]):
                    original_person = rule["roster_person_id"]
                    status = "matched_source_reviewed_alias"
                else:
                    status = "manual_alias_evidence_mismatch"
            else:
                status = "unreviewed_bio_name"

        canonical_person = canonical(original_person) if original_person else ""
        if original_person and canonical_person not in candidates.get(key, set()):
            status = "person_profile_side_mismatch"
            canonical_person = ""
        if canonical_person and not valid_date(row.get("date_of_birth", "")):
            status = "invalid_or_missing_dob"
            canonical_person = ""

        item = {
            "profile_id": key[0], "side_on_profile": key[1],
            "observed_name": row.get("observed_name", ""),
            "roster_name": row.get("roster_name", "") or (
                aliases[key]["roster_name"] if key in aliases and canonical_person else ""),
            "original_person_id": original_person,
            "canonical_person_id": canonical_person,
            "date_of_birth": row.get("date_of_birth", ""),
            "place_of_birth_raw": row.get("place_of_birth_raw", ""),
            "source_status": row.get("status", ""),
            "name_match_method": row.get("name_match_method", ""),
            "link_status": status,
            "source_profile_url": row.get("profile_url", "")
        }
        links.append(item)
        if not canonical_person:
            unresolved.append(item)

    linked = defaultdict(list)
    for link in links:
        if link["canonical_person_id"]:
            linked[link["canonical_person_id"]].append(link)

    by_person, conflicts = [], []
    for person in sorted(info):
        hist = linked[person]
        dates = sorted({r["date_of_birth"] for r in hist if valid_date(r["date_of_birth"])})
        places = {r["place_of_birth_raw"] for r in hist if r["place_of_birth_raw"]}
        state = ("no_verified_bio" if not dates else
                 "consistent" if len(dates) == 1 else "dob_conflict")
        if len(dates) > 1:
            for link in hist:
                conflicts.append({
                    "canonical_person_id": person,
                    "distinct_birth_dates": joined(dates),
                    "profile_id": link["profile_id"],
                    "side_on_profile": link["side_on_profile"],
                    "date_of_birth": link["date_of_birth"],
                    "observed_name": link["observed_name"],
                    "source_profile_url": link["source_profile_url"]
                })
        fields = info[person]
        by_person.append({
            "canonical_person_id": person, "roster_names": joined(fields["names"]),
            "disciplines": joined(fields["disciplines"]),
            "seasons": joined(fields["seasons"]),
            "roster_profile_ids": joined(fields["profiles"]),
            "biography_profile_ids": joined(x["profile_id"] for x in hist),
            "date_of_birth": dates[0] if len(dates) == 1 else "",
            "dob_status": state, "dob_source_count": len(hist),
            "birth_places_raw": joined(places),
            "birthplace_variant_count": len(places)
        })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "identity_birth_links.csv", LINK_FIELDS, links)
    write_csv(out / "identity_unresolved.csv", LINK_FIELDS, unresolved)
    write_csv(out / "identity_dob_conflicts.csv", CONFLICT_FIELDS, conflicts)
    write_csv(out / "identity_canonical_people.csv", PERSON_FIELDS, by_person)
    write_csv(out / "identity_canonical_season_roster.csv",
              list(roster[0]) + ROSTER_EXTRA, mapped_roster)
    missing = sorted(set(candidates) - seen_slots)
    summary = {
        "scope": "2018-19 to 2025-26 ISU season roster only; non-destructive audit; no BaZi",
        "roster_rows": len(roster), "raw_person_ids": len(raw_ids),
        "canonical_person_ids": len(info),
        "canonical_pair_ids": len(pair_keys),
        "source_reviewed_id_links": len(split_map),
        "source_reviewed_bio_name_aliases": len(aliases),
        "bios_rows": len(births),
        "bios_linked_rows": len(links) - len(unresolved),
        "bios_unresolved_rows": len(unresolved),
        "unique_people_with_consistent_dob": sum(p["dob_status"] == "consistent" for p in by_person),
        "unique_people_without_verified_bio": sum(p["dob_status"] == "no_verified_bio" for p in by_person),
        "unique_people_with_dob_conflict": sum(p["dob_status"] == "dob_conflict" for p in by_person),
        "dob_conflict_source_rows": len(conflicts),
        "distinct_people_without_roster_profile": sum(not info[p]["profiles"] for p in info),
        "missing_bio_profile_sides": len(missing),
        "missing_bio_profile_sides_sample": [
            {"profile_id": p, "side": s} for p, s in missing[:20]
        ],
        "input_sha256": {str(Path(p)): digest(p) for p in (roster_path, births_path, aliases_path, splits_path)},
        "outputs": ["identity_birth_links.csv", "identity_unresolved.csv",
                    "identity_dob_conflicts.csv", "identity_canonical_people.csv",
                    "identity_canonical_season_roster.csv"],
        "limitations": [
            "No modification of original roster or athlete master",
            "Source-correlated identity mappings are reversible and traceable",
            "Raw birthplace strings are not geographic coordinates or hemisphere assignments",
            "Similar names on different official profile IDs are NOT merged automatically",
            "Multiple official profiles for the same person must have consistent DOBs"
        ]
    }
    (out / "identity_audit_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "raw_person_ids", "canonical_person_ids", "source_reviewed_id_links",
        "bios_linked_rows", "bios_unresolved_rows",
        "unique_people_with_consistent_dob", "unique_people_with_dob_conflict",
        "distinct_people_without_roster_profile"
    )}, ensure_ascii=False, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster", default="output/master/season_roster.csv")
    p.add_argument("--births", default="output/bios/birth_candidates.csv")
    p.add_argument("--aliases", default=str(DEFAULT_ALIASES))
    p.add_argument("--splits", default=str(DEFAULT_SPLITS))
    p.add_argument("--out", default="output/identity")
    opts = p.parse_args()
    audit(opts.roster, opts.births, opts.aliases, opts.splits, opts.out)


if __name__ == "__main__":
    main()
