#!/usr/bin/env python3
"""Find surname-plus-first-initial historic ISU identities that evade same-partner audit.

This is an OFFLINE candidate audit, NOT an identity merge. Link to full-name
historic pairs only when BOTH members independently match name structure,
member side, discipline and identical officially audited DOB. Source URLs and
original pair IDs are retained. No BaZi or outcome-based selection.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(".")
PEOPLE = Path("output/historic_dob/coverage/historic_dob_coverage_people_v1.csv")
PAIRS = Path("data/historic/v4/couples_v4.csv")
OUT = Path("output/historic_dob/initial_only_alias_audit")
FIELDS = [
    "discipline", "abbreviated_pair_id", "member_side",
    "abbreviated_person_id", "abbreviated_name",
    "matched_full_person_id", "matched_full_name",
    "abbreviated_official_dob", "full_name_official_dob",
    "original_full_pair_id", "original_full_pair_names",
    "abbreviated_pair_first_season", "abbreviated_pair_source_types",
    "abbreviated_official_source_urls", "full_name_official_source_urls",
    "structural_match_status", "review_status",
]
PAIR_FIELDS = [
    "discipline", "abbreviated_pair_id", "abbreviated_pair_names",
    "original_full_pair_id", "full_pair_names",
    "matching_abbreviated_member_count", "dob_agree_both_sides",
    "status",
]
INITIAL = re.compile(r"^([A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ' -]+)\s+([A-Z])$")


def read(path, needed):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        absent = set(needed) - set(reader.fieldnames or ())
        if absent:
            raise ValueError(f"{path}: columns missing {sorted(absent)}")
        return list(reader)


def output(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def simple(s):
    raw = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in raw if c.isalnum() and
                   not unicodedata.combining(c))


def abbrev(s):
    m = INITIAL.fullmatch(s.strip())
    if not m:
        return None
    return (simple(m.group(1)), m.group(2).lower())


def full_match(short_name, full_name):
    sig = abbrev(short_name)
    if not sig:
        return False
    tokens = full_name.split()
    if len(tokens) < 2:
        return False
    # Given-name-first and surname-first conventions are both possible.
    choices = ((tokens[0], tokens[1:]), (tokens[-1], tokens[:-1]))
    return any(given[:1].lower() == sig[1] and
               simple(" ".join(surname)) == sig[0]
               for given, surname in choices)


def find(people_path=PEOPLE, pairs_path=PAIRS, out_dir=OUT):
    people = read(people_path, ("audit_person_id", "original_historic_person_id",
                                "date_of_birth_primary_candidate",
                                "dob_coverage_status", "source_urls"))
    pairs = read(pairs_path, ("pair_id", "discipline", "person_a_id",
                              "person_b_id", "person_a_name", "person_b_name",
                              "first_season", "source_types"))
    if not people or not pairs:
        raise ValueError("Historic official DOB people and pair table required")
    dob_by_id = defaultdict(list)
    for p in people:
        dob_by_id[p["original_historic_person_id"]].append(p)

    def official(p_id):
        slots = dob_by_id.get(p_id, [])
        if len(slots) != 1:
            return None
        p = slots[0]
        if p["dob_coverage_status"] != "official_source_linked":
            return None
        dob = p["date_of_birth_primary_candidate"]
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", dob):
            return None
        return p

    people_by_role = defaultdict(dict)
    regular_pair_keys = {}
    abbreviations = []
    for p in pairs:
        d = p["discipline"]
        members = ((p["person_a_id"], p["person_a_name"]),
                   (p["person_b_id"], p["person_b_name"]))
        for role, (pid, name) in zip(("1", "2"), members):
            key = (d, role)
            if pid in people_by_role[key] and people_by_role[key][pid] != name:
                raise ValueError("Inconsistent published name for one original person ID")
            people_by_role[key][pid] = name
        if any(abbrev(name) for _, name in members):
            abbreviations.append(p)
        else:
            key = (d, p["person_a_id"], p["person_b_id"])
            if key in regular_pair_keys:
                raise ValueError("Repeated original full-name couple key")
            regular_pair_keys[key] = p

    candidates = {}
    for p in abbreviations:
        disc = p["discipline"]
        pair_candidates = []
        for role, pid, name in (
            ("1", p["person_a_id"], p["person_a_name"]),
            ("2", p["person_b_id"], p["person_b_name"]),
        ):
            if not abbrev(name):
                pair_candidates.append([(pid, name)])
                continue
            options = [
                (id_full, full_name) for id_full, full_name
                in people_by_role[(disc, role)].items()
                if id_full != pid and not abbrev(full_name) and
                full_match(name, full_name)
            ]
            pair_candidates.append(options)
        for ca, aname in pair_candidates[0]:
            for cb, bname in pair_candidates[1]:
                fp = regular_pair_keys.get((disc, ca, cb))
                if not fp:
                    continue
                key = (p["pair_id"], fp["pair_id"])
                candidates[key] = (p, fp, ((p["person_a_id"], p["person_a_name"], ca, aname),
                                             (p["person_b_id"], p["person_b_name"], cb, bname)))

    by_short = defaultdict(list)
    for key in candidates:
        by_short[key[0]].append(key[1])

    link_rows, pair_rows = [], []
    for (short_id, full_id), (short_pair, full_pair, sides) in sorted(candidates.items()):
        status_by_member = []
        for i, (short_person, short_name, full_person, full_name) in enumerate(sides):
            is_initial = bool(abbrev(short_name))
            if not is_initial:
                continue
            old, full = official(short_person), official(full_person)
            dob_ok = bool(old and full and
                          old["date_of_birth_primary_candidate"] ==
                          full["date_of_birth_primary_candidate"])
            status = ("OFFICIAL_DOB_AGREES_SAME_PAIR_STRUCTURE_REVIEW"
                      if dob_ok else "MISSING_OR_DISAGREEING_OFFICIAL_DOB_HOLD")
            if len(by_short[short_id]) > 1:
                status = "MULTIPLE_FULL_PAIR_CANDIDATES_HOLD"
            status_by_member.append(dob_ok)
            link_rows.append({
                "discipline": short_pair["discipline"],
                "abbreviated_pair_id": short_id,
                "member_side": str(i + 1),
                "abbreviated_person_id": short_person,
                "abbreviated_name": short_name,
                "matched_full_person_id": full_person,
                "matched_full_name": full_name,
                "abbreviated_official_dob": old["date_of_birth_primary_candidate"] if old else "",
                "full_name_official_dob": full["date_of_birth_primary_candidate"] if full else "",
                "original_full_pair_id": full_id,
                "original_full_pair_names": full_pair["person_a_name"] + " / " + full_pair["person_b_name"],
                "abbreviated_pair_first_season": short_pair["first_season"],
                "abbreviated_pair_source_types": short_pair["source_types"],
                "abbreviated_official_source_urls": old["source_urls"] if old else "",
                "full_name_official_source_urls": full["source_urls"] if full else "",
                "structural_match_status": "BOTH_PARTNERS_MATCH_HISTORIC_PAIR",
                "review_status": status,
            })
        pair_rows.append({
            "discipline": short_pair["discipline"],
            "abbreviated_pair_id": short_id,
            "abbreviated_pair_names": short_pair["person_a_name"] + " / " + short_pair["person_b_name"],
            "original_full_pair_id": full_id,
            "full_pair_names": full_pair["person_a_name"] + " / " + full_pair["person_b_name"],
            "matching_abbreviated_member_count": len(status_by_member),
            "dob_agree_both_sides": "YES" if len(status_by_member) == 2 and all(status_by_member) else "NO",
            "status": ("SOURCE_NAME_DOB_PAIR_CANDIDATE_NO_MERGE"
                       if len(status_by_member) == 2 and all(status_by_member) and
                       len(by_short[short_id]) == 1
                       else "HOLD_FOR_SOURCE_SPECIFIC_ID_REVIEW"),
        })

    out = Path(out_dir)
    output(out / "historic_initial_only_person_candidate_links_v1.csv", link_rows, FIELDS)
    output(out / "historic_initial_only_pair_candidate_groups_v1.csv", pair_rows, PAIR_FIELDS)
    statuses = Counter(r["review_status"] for r in link_rows)
    summary = {
        "stage": "historic_initial_only_alias_discovery_not_source_approved",
        "abbreviated_historic_pair_records": len(abbreviations),
        "abbreviated_person_candidate_rows": len(link_rows),
        "abbreviated_pair_candidate_groups": len(pair_rows),
        "unique_abbreviated_people_with_candidate": len(
            {r["abbreviated_person_id"] for r in link_rows}),
        "candidate_status_counts": dict(sorted(statuses.items())),
        "source_input_sha256": {
            str(people_path): digest(people_path),
            str(pairs_path): digest(pairs_path),
        },
        "limitations": [
            "Full-name candidates require same discipline/side, full pair and matching official DOB",
            "Same DOB and matching name abbreviation still require explicit source-specific identity review",
            "No original ID, ranking, event count or source record is rewritten",
            "Initial-only matching does not detect other spelling, transliteration or surname changes",
            "No BaZi, sampling or significance testing",
        ],
    }
    (out / "historic_initial_only_alias_manifest_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--people", type=Path, default=PEOPLE)
    parser.add_argument("--pairs", type=Path, default=PAIRS)
    parser.add_argument("--out", type=Path, default=OUT)
    a = parser.parse_args()
    find(a.people, a.pairs, a.out)


if __name__ == "__main__":
    main()
