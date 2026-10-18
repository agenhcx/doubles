#!/usr/bin/env python3
"""Collect official ISU birthdate leads for unmatched historical pair aliases.

The input is a *review queue*, not approved cross-era identity links. Every
profile's published skater names are used to bind DOBs to the OFFICIAL side.
Do not silently apply the source dates to historical athletes: aliases with
the same partner may be unrelated people.

Seven separately reviewed source pairs are skipped here, including a false
top-1 directory candidate (Emilia SIMONEN vs Katherine BOBAK).
No BaZi, performance filtering, geocoding, or historic master edits.

PowerShell:
python .\scripts\collect_historic_alias_isu_bios.py --limit 20 --proxy http://127.0.0.1:10808
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import requests

from audit_isu_identities import digest, norm, read_csv, valid_date, write_csv
from collect_historic_isu_biographies import alternate_end_order, parse_pair_profile
from collect_isu_biographies import download_profile
from collect_isu_seasons import configure_session

PROFILES = {"results.isu.org", "www.isuresults.com"}
OFFICIAL = PROFILES | {"isu-skating.com", "www.isu-skating.com"}
PROFILE_RE = re.compile(r"^isufs\d+$", re.I)
PROFILE_FIELDS = [
    "profile_id", "profile_url", "associated_historic_pairs",
    "published_name_a", "published_name_b", "retrieval_status",
    "explicitly_bound_dates", "cache_hit", "error"
]
LEAD_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_id",
    "side_on_profile", "historical_name", "published_name", "published_dob",
    "profile_id", "source_url", "parse_status", "parse_method",
    "historical_identity_link_status", "prior_audited_dob",
    "prior_dob_consistency", "review_reason", "candidate_rank"
]
MANUAL_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_a_id",
    "historic_person_b_id", "historic_person_a_name",
    "historic_person_b_name", "official_person_a_name",
    "official_person_b_name", "official_person_a_dob",
    "official_person_b_dob", "official_profile_id",
    "official_person_a_source_url", "official_person_b_source_url",
    "provenance_status", "identity_basis", "evidence_note",
]


def nonempty(rows, cols, description):
    if not rows:
        raise ValueError(description + " is empty")
    missing = set(cols) - set(rows[0])
    if missing:
        raise ValueError(description + " missing required columns " + repr(sorted(missing)))


def checked_manual_pairs(path):
    rules = read_csv(path)
    nonempty(rules, MANUAL_FIELDS, "Official manual pair leads")
    claimed, people = set(), set()
    for r in rules:
        pid = r["historic_pair_id"]
        if not pid or pid in claimed:
            raise ValueError("Missing or repeated reviewed pair ID")
        claimed.add(pid)
        if not r["historic_person_a_id"] or not r["historic_person_b_id"]:
            raise ValueError("Reviewed source has missing member")
        if r["historic_person_a_id"] == r["historic_person_b_id"]:
            raise ValueError("Reviewed pair has identical member IDs")
        for side in ("a", "b"):
            if not valid_date(r[f"official_person_{side}_dob"]):
                raise ValueError("Invalid manually reviewed official DOB")
            if not r[f"official_person_{side}_name"] or not r[f"historic_person_{side}_name"]:
                raise ValueError("Official pair has missing name")
            link = urlsplit(r[f"official_person_{side}_source_url"])
            if link.scheme != "https" or link.hostname not in OFFICIAL:
                raise ValueError("Untrusted manual DOB source")
        if r["provenance_status"] not in {
            "reviewed_official_couple", "reviewed_separate_official_skater_sources"
        }:
            raise ValueError("Unapproved manually reviewed identity basis")
        if r["official_profile_id"]:
            ident = r["official_profile_id"].lower()
            if not PROFILE_RE.fullmatch(ident):
                raise ValueError("Invalid reviewed official profile ID")
            for side in ("a", "b"):
                if Path(urlsplit(r[f"official_person_{side}_source_url"]).path).stem.lower() != ident:
                    raise ValueError("Reviewed source profile differs from ID")
    return {r["historic_pair_id"]: r for r in rules}


def validate_manual_against_historic(manual_pairs, historic_pairs_path):
    """Verify hand-reviewed pair-to-person IDs against unchanged v4 roster."""
    original = read_csv(historic_pairs_path)
    nonempty(original, (
        "pair_id", "discipline", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name"
    ), "Historical v4 couples")
    indexed = {}
    for row in original:
        if not row["pair_id"] or row["pair_id"] in indexed:
            raise ValueError("Duplicate/blank historical v4 pair identifier")
        indexed[row["pair_id"]] = row
    for pair_id, evidence in manual_pairs.items():
        if pair_id not in indexed:
            raise ValueError("Reviewed official pair not in historical roster")
        original_pair = indexed[pair_id]
        fields = [
            ("discipline", "discipline"),
            ("historic_person_a_id", "person_a_id"),
            ("historic_person_b_id", "person_b_id"),
            ("historic_person_a_name", "person_a_name"),
            ("historic_person_b_name", "person_b_name")
        ]
        for evidence_field, historic_field in fields:
            if evidence[evidence_field] != original_pair[historic_field]:
                raise ValueError("Reviewed pair contradicts historical member identity")
    return len(manual_pairs)


def prepare_jobs(candidate_path, manual_pairs, *, max_rank=1):
    candidates = read_csv(candidate_path)
    nonempty(candidates, (
        "historic_pair_id", "historic_person_a_id", "historic_person_b_id",
        "historic_person_a_name", "historic_person_b_name",
        "candidate_rank", "candidate_profile_id",
        "candidate_person_a_name", "candidate_person_b_name",
        "candidate_profile_url", "discipline"
    ), "ISU index alias candidates")
    pair_rows = defaultdict(list)
    for r in candidates:
        pair_rows[r["historic_pair_id"]].append(r)
    missing_manual = set(manual_pairs) - set(pair_rows)
    # Six zero-candidate pairs are expected, while the Emilia/Penasse
    # manual source supersedes a known FALSE matched-partner directory hit.
    if len(missing_manual) > 6:
        raise ValueError("Too many reviewed manual pair IDs absent from queue")

    jobs = {}
    selected_pairs, declined_pairs = set(), set()
    for pair_id, rows in pair_rows.items():
        if pair_id in manual_pairs:
            manual = manual_pairs[pair_id]
            if any(r["historic_person_a_id"] != manual["historic_person_a_id"]
                   or r["historic_person_b_id"] != manual["historic_person_b_id"]
                   or r["discipline"] != manual["discipline"] for r in rows):
                raise ValueError("Manual source and index candidate identity disagree")
            declined_pairs.add(pair_id)
            continue
        available = sorted(rows, key=lambda x: int(x["candidate_rank"]))
        chosen = next((r for r in available
                       if int(r["candidate_rank"]) <= max_rank), None)
        if chosen is None:
            continue
        if int(chosen["candidate_rank"]) != 1:
            raise ValueError("First available candidate should be rank 1")
        pid = chosen["candidate_profile_id"].lower()
        if not PROFILE_RE.fullmatch(pid):
            raise ValueError("Invalid official profile ID in alias queue")
        url = urlsplit(chosen["candidate_profile_url"])
        if url.hostname not in PROFILES or Path(url.path).stem.lower() != pid:
            raise ValueError("Untrusted directory biography lead")
        published = (chosen["candidate_person_a_name"],
                     chosen["candidate_person_b_name"])
        if not all(published):
            raise ValueError("Candidate profile lacks published athlete names")
        if pid not in jobs:
            jobs[pid] = {
                "profile_id": pid,
                "url": chosen["candidate_profile_url"],
                "names": published,
                "linked_pairs": [],
            }
        if tuple(norm(x) for x in published) != tuple(
            norm(x) for x in jobs[pid]["names"]
        ):
            raise ValueError("Contradictory skater names for one official profile")
        jobs[pid]["linked_pairs"].append(chosen)
        selected_pairs.add(pair_id)
    return jobs, selected_pairs, declined_pairs


def previous_dobs(path):
    if path is None:
        return {}
    rows = read_csv(path)
    nonempty(rows, (
        "original_historic_person_ids", "date_of_birth_candidate", "dob_status"
    ), "Previous historical identity audit")
    result = defaultdict(set)
    for row in rows:
        if row["dob_status"] == "consistent_source_candidate":
            dob = row["date_of_birth_candidate"]
            if not valid_date(dob):
                raise ValueError("Invalid prior audited DOB")
            for person in row["original_historic_person_ids"].split(";"):
                if person.strip():
                    result[person.strip()].add(dob)
    return result


def run(
    candidate_path="output/historic_dob/isu_index/alias_review/historic_pair_alias_review_candidates.csv",
    manual_path="data/adjudications/isu_historic_manual_pair_dobs_v1.csv",
    prior_path="output/historic_dob/identity/historic_audited_people.csv",
    cache_dir="cache/isu_bios",
    out_dir="output/historic_dob/alias_biographies",
    *, limit=20, max_rank=1, offline=False, refresh=False, proxy=None,
    no_env_proxy=False, timeout=20, delay=0.3,
    historic_pairs_path="data/historic/v4/couples_v4.csv"
):
    if limit < 0 or max_rank < 1:
        raise ValueError("Nonnegative limit and positive rank required")
    manual = checked_manual_pairs(manual_path)
    validate_manual_against_historic(manual, historic_pairs_path)
    jobs, pairs, declined = prepare_jobs(candidate_path, manual,
                                         max_rank=max_rank)
    if not jobs:
        raise ValueError("No candidate biographies after removing reviewed pairs")
    previous = previous_dobs(prior_path)
    order = alternate_end_order(jobs)
    chosen = order[:limit] if limit else order
    session = configure_session(proxy, no_env_proxy)
    inventory, leads = [], []
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    for index, pid in enumerate(chosen, 1):
        job = jobs[pid]
        inv = {
            "profile_id": pid, "profile_url": job["url"],
            "associated_historic_pairs": "; ".join(sorted({
                r["historic_pair_id"] for r in job["linked_pairs"]
            })),
            "published_name_a": job["names"][0],
            "published_name_b": job["names"][1],
            "retrieval_status": "fetch_failed", "explicitly_bound_dates": 0,
            "cache_hit": False, "error": ""
        }
        parsed = ()
        try:
            html, cached = download_profile(
                session, pid, Path(cache_dir), offline=offline,
                refresh=refresh, timeout=timeout
            )
            inv["cache_hit"] = cached
            parsed = parse_pair_profile(html, *job["names"])
            inv["explicitly_bound_dates"] = sum(
                bool(p["date_of_birth"]) for p in parsed
            )
            inv["retrieval_status"] = (
                "two_dates_bound" if inv["explicitly_bound_dates"] == 2
                else "needs_biography_layout_review"
            )
            print(f"[ALIAS BIO {index}/{len(chosen)}] {pid} "
                  f"{inv['explicitly_bound_dates']}/2 cached={cached}",
                  flush=True)
        except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
            inv["error"] = type(exc).__name__ + ": " + str(exc)[:300]
            parsed = (
                dict(date_of_birth="", parse_method="",
                     parse_status="fetch_failed"),
                dict(date_of_birth="", parse_method="",
                     parse_status="fetch_failed"),
            )
            print(f"[ALIAS ERROR {index}/{len(chosen)}] {pid}: {inv['error']}",
                  file=sys.stderr, flush=True)
        inventory.append(inv)
        for pair in job["linked_pairs"]:
            for side, observation in zip(("a", "b"), parsed):
                hist_id = pair[f"historic_person_{side}_id"]
                history_name = pair[f"historic_person_{side}_name"]
                official_name = pair[f"candidate_person_{side}_name"]
                dob = observation["date_of_birth"]
                reference_dates = previous.get(hist_id, set())
                reference = (next(iter(reference_dates))
                             if len(reference_dates) == 1 else "")
                if len(reference_dates) > 1:
                    consistency = "ambiguous_historical_id_prior_dobs"
                elif dob and reference:
                    consistency = ("agree_with_prior" if dob == reference
                                   else "conflict_with_prior_review")
                elif dob:
                    consistency = "no_audited_dob_for_historic_person"
                else:
                    consistency = "no_published_dob_extracted"
                reasons = []
                if norm(history_name) != norm(official_name):
                    reasons.append("historic_name_differs_from_official")
                if observation["parse_status"] != "dob_explicitly_bound_to_expected_name":
                    reasons.append(observation["parse_status"])
                if consistency in {"conflict_with_prior_review",
                                   "ambiguous_historical_id_prior_dobs"}:
                    reasons.append(consistency)
                if not dob:
                    reasons.append("missing_source_dob")
                leads.append({
                    "historic_pair_id": pair["historic_pair_id"],
                    "discipline": pair["discipline"],
                    "historic_person_id": hist_id,
                    "side_on_profile": "1" if side == "a" else "2",
                    "historical_name": history_name,
                    "published_name": official_name,
                    "published_dob": dob,
                    "profile_id": pid, "source_url": job["url"],
                    "parse_status": observation["parse_status"],
                    "parse_method": observation["parse_method"],
                    "historical_identity_link_status": (
                        "not_verified_directory_candidate_only"
                    ),
                    "prior_audited_dob": reference,
                    "prior_dob_consistency": consistency,
                    "review_reason": "; ".join(reasons),
                    "candidate_rank": pair["candidate_rank"]
                })
        if (index % 10 == 0 or index == len(chosen)):
            write_csv(out / "historic_alias_bio_inventory.csv", PROFILE_FIELDS, inventory)
            write_csv(out / "historic_alias_dob_leads.csv", LEAD_FIELDS, leads)
        if not offline and not inv["cache_hit"] and delay:
            time.sleep(delay)

    review = [r for r in leads if r["review_reason"]]
    write_csv(out / "historic_alias_bio_review.csv", LEAD_FIELDS, review)
    counter = Counter(r["retrieval_status"] for r in inventory)
    consistency = Counter(r["prior_dob_consistency"] for r in leads)
    summary = {
        "scope": "Potential alias profile DOB sources; no historic identity inferred or joined",
        "status": "official_birthdate_leads_unverified_historic_aliases",
        "initial_pairs_with_candidates": len(pairs) + len(declined),
        "manual_source_pair_rows_excluded": len(declined),
        "manual_source_total": len(manual),
        "source_profiles_available": len(jobs),
        "profiles_attempted": len(inventory),
        "profiles_both_dobs_bound": counter["two_dates_bound"],
        "profiles_needing_layout_review": counter["needs_biography_layout_review"],
        "profiles_fetch_failed": counter["fetch_failed"],
        "cache_hits": sum(bool(r["cache_hit"]) for r in inventory),
        "official_profile_person_slots": 2 * len(inventory),
        "slots_with_published_dob": sum(int(r["explicitly_bound_dates"]) for r in inventory),
        "source_lead_rows": len(leads),
        "review_lead_rows": len(review),
        "agreement_with_existing_audited_dob": consistency["agree_with_prior"],
        "disagreement_with_existing_audited_dob": consistency["conflict_with_prior_review"],
        "prior_audited_dob_unknown": consistency["no_audited_dob_for_historic_person"],
        "source_dob_missing": consistency["no_published_dob_extracted"],
        "input_sha256": {
            str(candidate_path): digest(candidate_path),
            str(manual_path): digest(manual_path),
            str(historic_pairs_path): digest(historic_pairs_path),
            **({str(prior_path): digest(prior_path)}
               if prior_path is not None else {})
        },
        "limitations": [
            "Each official side/date belongs to the published athlete, NOT automatically the historically named person",
            "A partner's matching name alone does not prove the other identity",
            "One known false directory profile was excluded by a manually reviewed official source",
            "Six originally absent directory links are separately sourced by reviewed official pages",
            "All proposed historic-to-official alias identities require independent source adjudication",
            "An unknown, conflicted or partial source date is never fabricated",
            "No BaZi or partner significance testing",
        ],
    }
    (out / "historic_alias_bio_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", default="output/historic_dob/isu_index/alias_review/historic_pair_alias_review_candidates.csv")
    p.add_argument("--manual", default="data/adjudications/isu_historic_manual_pair_dobs_v1.csv")
    p.add_argument("--prior", default="output/historic_dob/identity/historic_audited_people.csv")
    p.add_argument("--historic-pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--cache", default="cache/isu_bios")
    p.add_argument("--out", default="output/historic_dob/alias_biographies")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--max-rank", type=int, default=1)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--delay", type=float, default=0.3)
    a = p.parse_args()
    result = run(a.candidates, a.manual, a.prior, a.cache, a.out,
                 limit=a.limit, max_rank=a.max_rank,
                 offline=a.offline, refresh=a.refresh, proxy=a.proxy,
                 no_env_proxy=a.no_env_proxy, timeout=a.timeout, delay=a.delay,
                 historic_pairs_path=a.historic_pairs)
    return 2 if result["profiles_fetch_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
