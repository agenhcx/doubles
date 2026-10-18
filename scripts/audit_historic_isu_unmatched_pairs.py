#!/usr/bin/env python3
"""Rank review-only ISU biography index leads for unmatched historical pairs.

Input is already cached ISU biography INDEX entries: ~2,007 official pairs.
No biography downloads, DOB inference, automatic identity linking or BaZi.

A matched partner can be an identity anchor; the other name may differ due
to transliteration, surname changes, or dataset abbreviations. This program
does NOT assume that a single shared partner proves an identity.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, norm, read_csv, write_csv

HOSTS = {"results.isu.org", "www.isuresults.com"}
PROFILE_RE = re.compile(r"^isufs\d+$", re.I)
CAND_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_a_id", "historic_person_b_id",
    "historic_person_a_name", "historic_person_b_name",
    "prior_index_match_status", "candidate_rank", "candidate_profile_id",
    "candidate_person_a_name", "candidate_person_b_name",
    "candidate_a_name_similarity", "candidate_b_name_similarity",
    "matched_anchor_side", "lead_category", "identity_review_status",
    "candidate_profile_url", "index_url"
]
QUEUE_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_a_name",
    "historic_person_b_name", "prior_index_match_status",
    "candidate_count", "top_candidate_profile_id", "top_candidate_lead_category",
    "identity_review_status"
]
def required(rows, columns, label):
    if not rows:
        raise ValueError(label + " is empty")
    absent = set(columns) - rows[0]
    if absent:
        raise ValueError(label + " missing required columns: " + repr(sorted(absent)))


def similarity(a, b):
    # For candidate ranking ONLY; never infer identity from the numerical score.
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def lead_status(old, row):
    """Produce a non-verifying priority class for an official index lead."""
    aa = norm(old["historic_person_a_name"]) == norm(row["person_a_name"])
    bb = norm(old["historic_person_b_name"]) == norm(row["person_b_name"])
    a_score = similarity(old["historic_person_a_name"], row["person_a_name"])
    b_score = similarity(old["historic_person_b_name"], row["person_b_name"])
    if aa and bb:
        # If the earlier "exact" directory parser missed one, report it for QA.
        return "two_exact_names_index_disagreement", "both", a_score, b_score
    if aa:
        return "anchor_a_exact_partner_variant", "A", a_score, b_score
    if bb:
        return "anchor_b_exact_partner_variant", "B", a_score, b_score
    if min(a_score, b_score) >= 0.82:
        return "both_names_similarity_only", "none", a_score, b_score
    return "", "", a_score, b_score


def build_alias_queue(
    unmatched_path="output/historic_dob/isu_index/historic_pair_official_index_links.csv",
    index_path="output/historic_dob/isu_index/official_index_couple_inventory.csv",
    out_dir="output/historic_dob/isu_index/alias_review",
    max_candidates=5,
):
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    unmatched = read_csv(unmatched_path)
    index = read_csv(index_path)
    required(unmatched, (
        "historic_pair_id", "discipline", "historic_person_a_id", "historic_person_b_id",
        "historic_person_a_name", "historic_person_b_name", "index_match_status"
    ), "historic source pair links")
    required(index, (
        "discipline", "index_profile_id", "person_a_name", "person_b_name",
        "profile_url", "index_url"
    ), "ISU official index inventory")

    seen_profiles, by_disc = {}, defaultdict(list)
    for record in index:
        prof = record["index_profile_id"].lower()
        parsed = urlsplit(record["profile_url"])
        if not PROFILE_RE.fullmatch(prof):
            raise ValueError("Invalid official index profile identifier")
        if (parsed.hostname not in HOSTS or
                Path(parsed.path).stem.lower() != prof):
            raise ValueError("Index lead must be an official ISU biography URL")
        if (record["discipline"], prof) in seen_profiles:
            raise ValueError("Repeated official profile in index: " + prof)
        seen_profiles[(record["discipline"], prof)] = True
        by_disc[record["discipline"]].append(record)

    pending = [x for x in unmatched
               if x["index_match_status"] != "exact_couple_profile"]
    if not pending:
        raise ValueError("No unmatched historic pairs to examine")
    if len({x["historic_pair_id"] for x in pending}) != len(pending):
        raise ValueError("Repeated historical pair ID in unmatched queue")

    candidates, queue, statuses = [], [], Counter()
    counts = Counter()
    for pair in pending:
        scored = []
        for record in by_disc.get(pair["discipline"], []):
            cat, side, sim_a, sim_b = lead_status(pair, record)
            if not cat:
                continue
            # Sorting is for manual review convenience; numerical similarity
            # is not a statistical compatibility metric or identity proof.
            anchor = 1 if side in {"A", "B", "both"} else 0
            priority = 0 if side == "both" else 1 if anchor else 2
            secondary = min(sim_a, sim_b) if anchor else (sim_a + sim_b) / 2
            scored.append((priority, -secondary, record["index_profile_id"], record,
                           cat, side, sim_a, sim_b))
        scored.sort(key=lambda x: (x[0], x[1], x[2]))
        counts[len(scored)] += 1
        picked = scored[:max_candidates]
        status = pair["index_match_status"]
        statuses[status] += 1
        for rank, scored_item in enumerate(picked, 1):
            _, _, _, r, cat, side, sa, sb = scored_item
            candidates.append({
                "historic_pair_id": pair["historic_pair_id"],
                "discipline": pair["discipline"],
                "historic_person_a_id": pair["historic_person_a_id"],
                "historic_person_b_id": pair["historic_person_b_id"],
                "historic_person_a_name": pair["historic_person_a_name"],
                "historic_person_b_name": pair["historic_person_b_name"],
                "prior_index_match_status": status,
                "candidate_rank": rank, "candidate_profile_id": r["index_profile_id"],
                "candidate_person_a_name": r["person_a_name"],
                "candidate_person_b_name": r["person_b_name"],
                "candidate_a_name_similarity": round(sa, 4),
                "candidate_b_name_similarity": round(sb, 4),
                "matched_anchor_side": side, "lead_category": cat,
                "identity_review_status": "not_verified_candidate_only",
                "candidate_profile_url": r["profile_url"],
                "index_url": r["index_url"]
            })
        queue.append({
            "historic_pair_id": pair["historic_pair_id"],
            "discipline": pair["discipline"],
            "historic_person_a_name": pair["historic_person_a_name"],
            "historic_person_b_name": pair["historic_person_b_name"],
            "prior_index_match_status": status,
            "candidate_count": len(scored),
            "top_candidate_profile_id": picked[0][3]["index_profile_id"] if picked else "",
            "top_candidate_lead_category": picked[0][4] if picked else "",
            "identity_review_status": "not_verified_candidate_only",
        })
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_pair_alias_review_candidates.csv", CAND_FIELDS, candidates)
    write_csv(out / "historic_unmatched_pair_inventory.csv", QUEUE_FIELDS, queue)
    summary = {
        "scope": "Source-directory leads for unmatched selected historic ISU pairs",
        "status": "identity_review_only_no_verified_dob",
        "historic_unmatched_pairs": len(pending),
        "previous_status_counts": dict(sorted(statuses.items())),
        "pairs_with_any_directory_candidate": sum(q["candidate_count"] > 0 for q in queue),
        "pairs_without_directory_candidate": sum(q["candidate_count"] == 0 for q in queue),
        "candidate_rows_emitted": len(candidates),
        "candidate_categories": dict(sorted(Counter(c["lead_category"] for c in candidates).items())),
        "max_candidates_per_pair": max_candidates,
        "input_sha256": {
            str(unmatched_path): digest(unmatched_path),
            str(index_path): digest(index_path),
        },
        "limitations": [
            "Official directory leads are not DOBs or identity confirmations",
            "A shared partner does not prove the other partner's identity",
            "Scores are name-only reviewer priorities, not statistical evidence",
            "Only candidates in the directory are considered",
            "No original roster, DOB data or adjudications are modified",
            "No astrology, calendar-null or skater-pool analysis",
        ],
    }
    (out / "historic_pair_alias_review_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs", default="output/historic_dob/isu_index/historic_pair_official_index_links.csv")
    p.add_argument("--index", default="output/historic_dob/isu_index/official_index_couple_inventory.csv")
    p.add_argument("--out", default="output/historic_dob/isu_index/alias_review")
    p.add_argument("--max-candidates", type=int, default=5)
    a = p.parse_args()
    build_alias_queue(a.pairs, a.index, a.out, a.max_candidates)


if __name__ == "__main__":
    main()
