#!/usr/bin/env python3
"""Source-adjudicated resolution preview for 7 known cross-era alias components.

Six MODERN name-ID aliases and one HISTORIC cross-partner alias are
source-reviewed in a versioned ledger. The input 190 historic-modern
candidate edges retain their raw lineage. Neither cross-era matching
nor pair/event performance is promoted into a scientific cohort.

Runs fully offline; webpage evidence is documented, NOT re-fetched here.
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
LEDGER = Path("data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv")
EDGES = Path("output/historic_dob/cross_era_identity/historical_v2/official_bio_rescue/historic_modern_identity_source_augmented_v1.csv")
BIO_MANIFEST = Path("output/historic_dob/cross_era_identity/historical_v2/official_bio_rescue/historic_modern_bio_rescue_manifest_v1.json")
MODERN = Path("output/master/season_roster.csv")
HIST_PEOPLE = Path("output/historic_dob/shared_partner_identity/initial_only_v2/historic_reviewed_person_id_preview_v2.csv")
HIST_PAIRS = Path("output/historic_dob/shared_partner_identity/initial_only_v2/historic_reviewed_pair_groups_preview_v2.csv")
OUT = Path("output/historic_dob/cross_era_identity/ambiguity_source_v3")
HOSTS = {"results.isu.org", "www.isuresults.com", "isu-skating.com", "www.isu-skating.com"}
LEDGER_FIELDS = [
    "rule_id", "scope", "discipline", "canonical_person_id",
    "alternate_person_id", "anchor_person_id", "expected_dob",
    "canonical_published_name", "alternate_published_name",
    "official_profile_url", "corroborating_official_url",
    "evidence_status", "review_note",
]
EDGE_KEYS = [
    "discipline", "historic_projected_id", "modern_provisional_id",
    "historic_names", "modern_names", "historic_dob", "modern_official_dob",
    "modern_bio_urls", "modern_profile_urls", "modern_seasons",
    "cross_era_same_pair", "identity_review_status", "ambiguity_status",
]
HIST_PERSON_FIELDS = [
    "projected_person_id", "audit_person_ids", "original_historic_person_ids",
    "historic_names", "date_of_birth", "source_person_rows", "status",
]
HIST_PAIR_FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "original_pair_ids", "original_pair_rows", "original_pair_names",
    "original_pair_seasons", "pair_group_status",
    "event_count_aggregation_status",
]
GROUP_FIELDS = [
    "discipline", "historic_projected_id", "modern_provisional_id",
    "historic_dob", "modern_official_dob",
    "original_historic_person_ids", "original_modern_person_ids",
    "historic_names", "modern_names", "original_candidate_edge_count",
    "original_candidate_statuses", "original_ambiguity_statuses",
    "cross_era_same_pair_evidence", "source_reviewed_rule_ids",
    "source_urls", "cross_era_identity_status",
]
MODERN_PAIR_FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "original_modern_pair_ids", "original_season_roster_rows",
    "seasons", "profile_urls", "note",
]


def read(path, fields):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if set(fields) - set(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {sorted(set(fields) - set(reader.fieldnames or []))}")
        return list(reader)


def write(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pieces(v):
    return {x.strip() for x in (v or "").split(";") if x.strip()}


def join(values):
    return "; ".join(sorted(set(x for x in values if x)))


def date_ok(s):
    try:
        return bool(s) and date.fromisoformat(s).isoformat() == s
    except (TypeError, ValueError):
        return False


def official_url(url, bio=False):
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in HOSTS or
            p.username is not None or p.password is not None or
            p.port is not None or p.query or p.fragment or not p.path):
        return False
    if not bio:
        return True
    return bool(re.fullmatch(r"/bios/isufs\d+\.htm", p.path, re.I))


def audit(edges_path=EDGES, modern_path=MODERN, people_path=HIST_PEOPLE,
          pairs_path=HIST_PAIRS, ledger_path=LEDGER,
          bio_manifest_path=BIO_MANIFEST, out_dir=OUT):
    edges = read(edges_path, EDGE_KEYS)
    modern = read(modern_path, (
        "pair_id", "discipline", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name", "season", "profile_url"))
    historic = read(people_path, HIST_PERSON_FIELDS)
    historic_pairs = read(pairs_path, HIST_PAIR_FIELDS)
    rules = read(ledger_path, LEDGER_FIELDS)
    if not all((edges, modern, historic, historic_pairs, rules)):
        raise ValueError("All five source tables must be nonempty")
    with Path(bio_manifest_path).open(encoding="utf-8") as f:
        bio_summary = json.load(f)
    roster_sha = next((
        value for key, value in bio_summary.get("inputs_sha256", {}).items()
        if key.replace("\\", "/").lower().endswith("output/master/season_roster.csv")
    ), None)
    if roster_sha != sha(modern_path):
        raise ValueError("Source-augmented input lineage uses a different season roster")
    if (bio_summary.get("cross_era_candidate_edges_unchanged") != len(edges) or
            bio_summary.get("remaining_modern_dob_missing_edges") != 0):
        raise ValueError("Cross-era DOB rescue manifest and current candidate evidence disagree")

    hist_by_id = {}
    for p in historic:
        id_ = p["projected_person_id"]
        if not id_ or id_ in hist_by_id or not date_ok(p["date_of_birth"]):
            raise ValueError("Historical v2 projected people invalid or duplicated")
        if str(len(pieces(p["audit_person_ids"]))) != p["source_person_rows"]:
            raise ValueError("Historic prior person lineage is inconsistent")
        hist_by_id[id_] = p

    modern_names = defaultdict(set)
    modern_profiles = defaultdict(set)
    modern_ids = set()
    raw_modern_pairs = set()
    for row in modern:
        a, b, disc = row["person_a_id"], row["person_b_id"], row["discipline"]
        if not a or not b or a == b or not row["pair_id"] or not disc:
            raise ValueError("Malformed modern roster person or pair")
        raw_modern_pairs.add((disc, a, b))
        for person, name in ((a, row["person_a_name"]), (b, row["person_b_name"])):
            modern_ids.add(person)
            modern_names[(disc, person)].add(name)
            modern_profiles[(disc, person)].add(row["profile_url"])

    lookup = {}
    for e in edges:
        key = (e["discipline"], e["historic_projected_id"], e["modern_provisional_id"])
        if key in lookup or not all(key):
            raise ValueError("Cross-era input has duplicate or blank raw candidate edge")
        if (e["historic_projected_id"] not in hist_by_id or
                e["modern_provisional_id"] not in modern_ids or
                not date_ok(e["historic_dob"]) or
                e["modern_official_dob"] != e["historic_dob"] or
                hist_by_id[e["historic_projected_id"]]["date_of_birth"] != e["historic_dob"]):
            raise ValueError("Cross-era candidate ID or DOB evidence inconsistent with audited people")
        lookup[key] = e

    modern_aliases = {}
    historic_aliases = {}
    rule_ids = set()
    approved_edges = set()
    rule_by_normalized = defaultdict(set)
    for rule in rules:
        scope, disc = rule["scope"], rule["discipline"]
        canonical, alternate = rule["canonical_person_id"], rule["alternate_person_id"]
        anchor, dob = rule["anchor_person_id"], rule["expected_dob"]
        if (scope not in {"modern", "historic"} or not rule["rule_id"] or
                rule["rule_id"] in rule_ids or not disc or
                not canonical or not alternate or canonical == alternate or
                not date_ok(dob) or not rule["canonical_published_name"] or
                not rule["alternate_published_name"] or
                not official_url(rule["official_profile_url"], bio=True) or
                not official_url(rule["corroborating_official_url"]) or
                len(rule["review_note"].strip()) < 80):
            raise ValueError("Invalid or underspecified source-specific alias review rule")
        rule_ids.add(rule["rule_id"])
        expectation = ("source_reviewed_name_alias" if scope == "modern"
                       else "source_reviewed_cross_partner_alias")
        if rule["evidence_status"] != expectation:
            raise ValueError("Unreviewed identity link is forbidden")
        if scope == "modern":
            if ((disc, canonical) not in modern_names or
                    (disc, alternate) not in modern_names or
                    canonical in modern_aliases or alternate in modern_aliases or
                    canonical in modern_aliases.values() or alternate in modern_aliases.values()):
                raise ValueError("Modern identity alias missing, duplicated or chained")
            if (rule["canonical_published_name"] not in modern_names[(disc, canonical)] or
                    rule["alternate_published_name"] not in modern_names[(disc, alternate)]):
                raise ValueError("Reviewed name is not present for exact modern roster ID")
            first, second = (disc, anchor, canonical), (disc, anchor, alternate)
            source_a, source_b = lookup.get(first), lookup.get(second)
            if (anchor not in hist_by_id or not source_a or not source_b or
                    source_a["ambiguity_status"] != "HISTORIC_TO_MULTIPLE_MODERN_IDS" or
                    source_b["ambiguity_status"] != "HISTORIC_TO_MULTIPLE_MODERN_IDS"):
                raise ValueError("Modern rule lacks two matching ambiguous cross-era leads")
            modern_aliases[alternate] = canonical
        else:
            if (canonical not in hist_by_id or alternate not in hist_by_id or
                    canonical in historic_aliases or alternate in historic_aliases or
                    canonical in historic_aliases.values() or alternate in historic_aliases.values()):
                raise ValueError("Historic identity alias missing, duplicated or chained")
            if (rule["canonical_published_name"] not in pieces(hist_by_id[canonical]["historic_names"]) or
                    rule["alternate_published_name"] not in pieces(hist_by_id[alternate]["historic_names"])):
                raise ValueError("Reviewed historic names are absent from source preview")
            first, second = (disc, canonical, anchor), (disc, alternate, anchor)
            source_a, source_b = lookup.get(first), lookup.get(second)
            if ((disc, anchor) not in modern_names or not source_a or not source_b or
                    source_a["ambiguity_status"] != "MODERN_TO_MULTIPLE_HISTORIC_IDS" or
                    source_b["ambiguity_status"] != "MODERN_TO_MULTIPLE_HISTORIC_IDS"):
                raise ValueError("Historic rule lacks two matching ambiguous cross-era leads")
            historic_aliases[alternate] = canonical
        if (hist_by_id[anchor]["date_of_birth"] != dob if scope == "modern"
                else any(hist_by_id[x]["date_of_birth"] != dob for x in (canonical, alternate))):
            raise ValueError("Reviewed source DOB conflicts with historical evidence")
        if any(x["modern_official_dob"] != dob for x in (source_a, source_b)):
            raise ValueError("Reviewed source DOB conflicts with modern biography")
        if rule["official_profile_url"] not in pieces(source_a["modern_bio_urls"]):
            raise ValueError("Primary official biography does not match canonical modern source side")
        approved_edges.update((first, second))
        rule_by_normalized[(disc, hist_by_id[anchor]["projected_person_id"] if scope == "modern"
                            else canonical,
                            canonical if scope == "modern" else anchor)].add(rule["rule_id"])

    actual_ambiguous = {key for key, row in lookup.items()
                        if row["ambiguity_status"] not in {"", "NONE"}}
    if actual_ambiguous != approved_edges:
        raise ValueError("Ambiguous graph contains missing/unreviewed or extra source-approved edges")
    if len(modern_aliases) + len(historic_aliases) != len(rules):
        raise ValueError("Rule count does not agree with unique alias targets")

    # Preserve all 190 input edges; normalize only source-approved alias IDs.
    normalized = defaultdict(list)
    for key, e in lookup.items():
        disc, h, m = key
        new_key = (disc, historic_aliases.get(h, h), modern_aliases.get(m, m))
        normalized[new_key].append(e)

    result_edges = []
    for (disc, h, m), items in sorted(normalized.items()):
        dates = {r["historic_dob"] for r in items}
        if len(dates) != 1 or {r["modern_official_dob"] for r in items} != dates:
            raise ValueError("Canonical grouped cross-era edges disagree on DOB")
        original_alias_edges = sum(x["ambiguity_status"] not in ("", "NONE") for x in items)
        result_edges.append({
            "discipline": disc,
            "historic_projected_id": h, "modern_provisional_id": m,
            "historic_dob": next(iter(dates)), "modern_official_dob": next(iter(dates)),
            "original_historic_person_ids": join(x["historic_projected_id"] for x in items),
            "original_modern_person_ids": join(x["modern_provisional_id"] for x in items),
            "historic_names": join(t for x in items for t in pieces(x["historic_names"])),
            "modern_names": join(t for x in items for t in pieces(x["modern_names"])),
            "original_candidate_edge_count": len(items),
            "original_candidate_statuses": join(x["identity_review_status"] for x in items),
            "original_ambiguity_statuses": join(x["ambiguity_status"] for x in items),
            "cross_era_same_pair_evidence": "YES" if any(
                x["cross_era_same_pair"] == "YES" for x in items) else "NO",
            "source_reviewed_rule_ids": join(
                rule["rule_id"] for rule in rules
                if (rule["scope"] == "modern" and rule["discipline"] == disc and
                    rule["anchor_person_id"] == h and rule["canonical_person_id"] == m) or
                   (rule["scope"] == "historic" and rule["discipline"] == disc and
                    rule["canonical_person_id"] == h and rule["anchor_person_id"] == m)),
            "source_urls": join(t for x in items for t in pieces(x["modern_bio_urls"])),
            "cross_era_identity_status": (
                "SOURCE_REVIEWED_ALIAS_GROUPED_CROSS_ERA_STILL_CANDIDATE"
                if original_alias_edges else "UNCHANGED_CROSS_ERA_IDENTITY_CANDIDATE"),
        })

    person_groups = defaultdict(list)
    for p in historic:
        person_groups[historic_aliases.get(p["projected_person_id"],
                                          p["projected_person_id"])].append(p)
    historic_new = []
    for canon, originals in sorted(person_groups.items()):
        dates = {p["date_of_birth"] for p in originals}
        if len(dates) != 1:
            raise ValueError("Historic canonical ID would merge incompatible dates")
        audit_ids = [t for p in originals for t in pieces(p["audit_person_ids"])]
        old_ids = [t for p in originals for t in pieces(p["original_historic_person_ids"])]
        if len(audit_ids) != len(set(audit_ids)):
            raise ValueError("Historic canonical identity lineage has overlapping audited slots")
        historic_new.append({
            "projected_person_id": canon, "audit_person_ids": join(audit_ids),
            "original_historic_person_ids": join(old_ids),
            "historic_names": join(t for p in originals for t in pieces(p["historic_names"])),
            "date_of_birth": next(iter(dates)),
            "source_person_rows": sum(int(p["source_person_rows"]) for p in originals),
            "status": ("source_reviewed_cross_partner_alias_v3"
                       if len(originals) > 1 else originals[0]["status"]),
        })

    hist_pair_groups = defaultdict(list)
    for p in historic_pairs:
        a, b, disc = p["projected_person_a_id"], p["projected_person_b_id"], p["discipline"]
        if a not in hist_by_id or b not in hist_by_id or a == b:
            raise ValueError("Historical v2 pair refers to unknown persons")
        aa, bb = historic_aliases.get(a, a), historic_aliases.get(b, b)
        if aa == bb:
            raise ValueError("Cross-partner historic alias creates self-pair")
        hist_pair_groups[(disc, aa, bb)].append(p)
    new_hist_pairs = []
    all_original_pair_ids = set()
    for (disc, a, b), groups in sorted(hist_pair_groups.items()):
        orig = [t for p in groups for t in pieces(p["original_pair_ids"])]
        if len(orig) != len(set(orig)) or set(orig) & all_original_pair_ids:
            raise ValueError("Repeated original historic pair ID after alias projection")
        all_original_pair_ids.update(orig)
        new_hist_pairs.append({
            "discipline": disc, "projected_person_a_id": a, "projected_person_b_id": b,
            "original_pair_ids": join(orig), "original_pair_rows": len(orig),
            "original_pair_names": join(t for p in groups for t in pieces(p["original_pair_names"])),
            "original_pair_seasons": join(t for p in groups for t in pieces(p["original_pair_seasons"])),
            "pair_group_status": ("multiple_history_pair_ids_source_reviewed"
                                  if len(orig) > 1 else "unique_original_pair_id"),
            "event_count_aggregation_status": "NOT_AGGREGATED_REQUIRES_EVENT_ID_DEDUP",
        })

    modern_group = defaultdict(list)
    for r in modern:
        d, a, b = r["discipline"], modern_aliases.get(r["person_a_id"], r["person_a_id"]), (
            modern_aliases.get(r["person_b_id"], r["person_b_id"]))
        if a == b:
            raise ValueError("Modern alias mapping creates self-pair")
        modern_group[(d, a, b)].append(r)
    new_modern_pairs = [{
        "discipline": d, "projected_person_a_id": a, "projected_person_b_id": b,
        "original_modern_pair_ids": join(r["pair_id"] for r in items),
        "original_season_roster_rows": len(items),
        "seasons": join(r["season"] for r in items),
        "profile_urls": join(r["profile_url"] for r in items),
        "note": "NAME_ALIAS_PROJECTION_ONLY_NO_RANK_OR_POINT_AGGREGATION"
    } for (d, a, b), items in sorted(modern_group.items())]

    if (len(result_edges) != len(edges) - len(rules) or
            len(historic_new) != len(historic) - len(historic_aliases) or
            sum(int(x["original_pair_rows"]) for x in new_hist_pairs) !=
            sum(int(x["original_pair_rows"]) for x in historic_pairs)):
        raise ValueError("Alias projection produced unexpected lineage counts")
    remaining_ambiguous_components = sum(
        len(items) > 1 and not all(x["ambiguity_status"] not in ("", "NONE") for x in items)
        for items in normalized.values())
    if remaining_ambiguous_components:
        raise ValueError("Alias groups contain unexplained ambiguity components")
    out = Path(out_dir)
    write(out / "source_reviewed_cross_era_canonical_candidates_v1.csv", result_edges, GROUP_FIELDS)
    write(out / "historical_source_reviewed_person_preview_v3.csv", historic_new, HIST_PERSON_FIELDS)
    write(out / "historical_source_reviewed_pair_preview_v3.csv", new_hist_pairs, HIST_PAIR_FIELDS)
    write(out / "modern_source_reviewed_pair_preview_v1.csv", new_modern_pairs, MODERN_PAIR_FIELDS)
    write(out / "source_reviewed_alias_rules_applied_v1.csv", rules, LEDGER_FIELDS)

    manifest = {
        "stage": "cross_era_ambiguity_source_reviewed_graph_projection_not_frozen",
        "input_cross_era_candidate_edges": len(edges),
        "input_ambiguous_candidate_edges": len(actual_ambiguous),
        "approved_source_identity_rules": len(rules),
        "approved_modern_name_id_aliases": len(modern_aliases),
        "approved_historic_cross_partner_aliases": len(historic_aliases),
        "normalized_cross_era_candidate_groups": len(result_edges),
        "collapsed_duplicate_candidate_edges": len(edges) - len(result_edges),
        "known_ambiguous_edges_left_without_source_rule": len(actual_ambiguous - approved_edges),
        "historic_v2_person_slots": len(historic),
        "projected_historic_v3_person_slots": len(historic_new),
        "historic_v2_pair_groups": len(historic_pairs),
        "projected_historic_v3_pair_groups": len(new_hist_pairs),
        "historic_original_pair_ids_preserved": len(all_original_pair_ids),
        "modern_raw_name_id_count": len(modern_ids),
        "projected_modern_name_id_count": len({modern_aliases.get(i, i) for i in modern_ids}),
        "modern_raw_pair_groups": len(raw_modern_pairs),
        "projected_modern_pair_groups": len(new_modern_pairs),
        "modern_season_roster_rows_unchanged": len(modern),
        "normalized_groups_with_two_source_candidate_edges": sum(
            r["original_candidate_edge_count"] == 2 for r in result_edges),
        "source_hashes": {str(p): sha(p) for p in (
            edges_path, modern_path, people_path, pairs_path, ledger_path, bio_manifest_path)},
        "limitations": [
            "Seven aliases were individually source-reviewed; this offline script does not refetch official biographies",
            "183 normalized cross-era edges are NOT 183 independently confirmed natural people",
            "All 190 original cross-era candidate edges, season ranking rows, original IDs and DOB sources remain unmodified",
            "The modern rank/points and historic event counts are not summed, re-ranked or statistically analyzed",
            "Other historical-modern aliases may remain undiscovered despite zero unresolved edges in this specific review queue",
            "Re-run historic event collision audit against historical_source_reviewed_pair_preview_v3.csv",
            "No BaZi features, selection on performance, null modeling or sample freeze",
        ],
    }
    (out / "cross_era_source_reviewed_identity_manifest_v1.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--edges", type=Path, default=EDGES)
    p.add_argument("--modern", type=Path, default=MODERN)
    p.add_argument("--people", type=Path, default=HIST_PEOPLE)
    p.add_argument("--pairs", type=Path, default=HIST_PAIRS)
    p.add_argument("--ledger", type=Path, default=LEDGER)
    p.add_argument("--bio-manifest", type=Path, default=BIO_MANIFEST)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    audit(a.edges, a.modern, a.people, a.pairs, a.ledger, a.bio_manifest, a.out)


if __name__ == "__main__":
    main()
