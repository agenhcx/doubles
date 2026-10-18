#!/usr/bin/env python3
"""Collect historical ISU pair biographies from source-matched index profiles.

Conservative DOB parsing for both forward and reversed historical layouts.
A date belongs to a person only if the complete expected name is adjacent
to an explicit Date of birth label plus full date.

Downloads/cache happen on the user's machine. Original historic masters,
DOB supplement tables and current-season canonical athletes are unchanged.
No BaZi, geocoding, imputed birth dates or outcome-based sampling.

One-line PowerShell:
python .\scripts\collect_historic_isu_biographies.py --limit 20 --proxy http://127.0.0.1:10808
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from audit_isu_identities import digest, norm, read_csv, write_csv
from collect_isu_biographies import download_profile
from collect_isu_seasons import configure_session

PROFILE_RE = re.compile(r"^isufs\d+$", re.I)
DATE = r"([0-3]?\d\.[01]?\d\.(?:18|19|20)\d{2})"
BIRTH_LABEL = r"\bDate\s+of\s+birth\s*:"
PROFILE_FIELDS = [
    "profile_id", "profile_url", "historic_pair_ids",
    "person_a_id", "person_b_id", "status", "parsed_members",
    "cached", "error"
]
CAND_FIELDS = [
    "profile_id", "historic_pair_ids", "historic_person_id",
    "side_on_profile", "historic_name", "observed_name",
    "date_of_birth", "parse_method", "parse_status",
    "seed_dob", "seed_consistency", "source_url"
]
PERSON_FIELDS = [
    "historic_person_id", "historic_names", "source_profile_ids",
    "distinct_dates", "date_of_birth_candidate", "source_count",
    "primary_seed_dob", "dob_status"
]


def fold(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip()


def name_rx(value):
    name = fold(value)
    if not name or len(name.split()) < 2:
        raise ValueError("Expected full athlete name")
    return r"(?<!\w)" + r"\s+".join(re.escape(x) for x in name.split()) + r"(?!\w)"


def parse_member(flat, expected_name):
    """Extract ONLY explicitly labelled DOBs beside this exact full name.

    Forward:  Date of birth: 04.10.1985 Dan ZHANG ...
    Reversed: Alexander SHAKALOV 26.03.1982 Date of birth: ...
    Multiple contradictory dates or unbound names are review-only.
    """
    target = name_rx(expected_name)
    forward = re.compile(BIRTH_LABEL + r"\s*" + DATE + r"\s+" + target, re.I)
    reverse = re.compile(target + r"\s+" + DATE + r"\s+" + BIRTH_LABEL, re.I)
    dates = defaultdict(set)
    for pattern, method in ((forward, "label_date_name"),
                            (reverse, "name_date_label_legacy")):
        for match in pattern.finditer(flat):
            try:
                value = dt.datetime.strptime(match.group(1), "%d.%m.%Y").date()
                if dt.date(1850, 1, 1) <= value <= dt.date.today():
                    dates[value.isoformat()].add(method)
            except ValueError:
                continue
    if not dates:
        status = "name_present_without_bound_dob" if re.search(target, flat, re.I) else "expected_name_not_in_header"
        return {"date_of_birth": "", "parse_method": "",
                "parse_status": status, "observed_name": expected_name}
    if len(dates) > 1:
        return {"date_of_birth": "", "parse_method": "",
                "parse_status": "conflicting_labelled_dates_on_page",
                "observed_name": expected_name}
    date_value = next(iter(dates))
    return {"date_of_birth": date_value,
            "parse_method": "; ".join(sorted(dates[date_value])),
            "parse_status": "dob_explicitly_bound_to_expected_name",
            "observed_name": expected_name}


def parse_pair_profile(html, name_a, name_b):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Only the biographical header, never dates in standings/competition notes.
    text = fold(soup.get_text(" ", strip=True))[:3500]
    a, b = parse_member(text, name_a), parse_member(text, name_b)
    return a, b


def official_jobs(pair_rows):
    jobs = {}
    for row in pair_rows:
        if row.get("index_match_status") != "exact_couple_profile":
            continue
        id_field = row.get("exact_profile_ids", "")
        ids = [x.strip().lower() for x in id_field.split(";") if x.strip()]
        if len(ids) != 1 or not PROFILE_RE.fullmatch(ids[0]):
            raise ValueError("A supposed exact couple has no unique official profile ID")
        ident = ids[0]
        a, b = row["historic_person_a_id"], row["historic_person_b_id"]
        aname, bname = row["historic_person_a_name"], row["historic_person_b_name"]
        if not a or not b or a == b or not aname or not bname:
            raise ValueError("Historic couple has invalid members")
        source_urls = [x.strip() for x in row.get("exact_profile_urls", "").split(";") if x.strip()]
        if len(source_urls) != 1:
            raise ValueError("Missing or multiple source profile URLs for " + ident)
        url = source_urls[0]
        parsed = urlsplit(url)
        if parsed.hostname not in {"results.isu.org", "www.isuresults.com"} or (
            parsed.path.lower() != f"/bios/{ident}.htm"
        ):
            raise ValueError("Untrusted or mismatched official profile link")
        if ident not in jobs:
            jobs[ident] = {
                "profile_id": ident, "profile_url": url,
                "person_a_id": a, "person_b_id": b,
                "person_a_name": aname, "person_b_name": bname,
                "historic_pair_ids": set(),
            }
        prev = jobs[ident]
        if (prev["person_a_id"] != a or prev["person_b_id"] != b
                or norm(prev["person_a_name"]) != norm(aname)
                or norm(prev["person_b_name"]) != norm(bname)):
            raise ValueError("One official profile maps to conflicting historic members")
        prev["historic_pair_ids"].add(row["historic_pair_id"])
    return jobs


def alternate_end_order(jobs):
    """Deterministic diverse-era pilot: low/high official ID interleaved."""
    ordered = sorted(jobs, key=lambda ident: int(ident[5:]))
    mixed = []
    left, right = 0, len(ordered) - 1
    while left <= right:
        mixed.append(ordered[left])
        if left != right:
            mixed.append(ordered[right])
        left += 1
        right -= 1
    return mixed


def checked_seed(path):
    result = {}
    if not Path(path).exists():
        raise FileNotFoundError("Official historic DOB seed missing: " + str(path))
    for row in read_csv(path):
        person = row["historic_person_id"]
        date = row["date_of_birth"]
        if person in result or not person:
            raise ValueError("Duplicate or empty official historic seed person")
        if row.get("evidence_status") != "manually_checked_source" or not date:
            raise ValueError("Unchecked or blank DOB in official source seed")
        result[person] = date
    return result


def persist(out, profiles, candidates):
    write_csv(out / "historic_isu_bio_inventory.csv", PROFILE_FIELDS, profiles)
    write_csv(out / "historic_isu_bio_candidates.csv", CAND_FIELDS, candidates)


def summarize_people(candidates, seed):
    groups = defaultdict(list)
    for row in candidates:
        groups[row["historic_person_id"]].append(row)
    records = []
    for pid, rows in sorted(groups.items()):
        values = sorted({r["date_of_birth"] for r in rows if r["date_of_birth"]})
        prior = seed.get(pid, "")
        if len(values) > 1:
            status, date = "cross_profile_dob_conflict", ""
        elif values and prior and values[0] != prior:
            status, date = "official_seed_dob_conflict", ""
        elif values:
            status, date = "consistent_profile_candidate", values[0]
        else:
            status, date = "no_parseable_dob", ""
        records.append({
            "historic_person_id": pid,
            "historic_names": "; ".join(sorted({r["historic_name"] for r in rows})),
            "source_profile_ids": "; ".join(sorted({r["profile_id"] for r in rows})),
            "distinct_dates": "; ".join(values),
            "date_of_birth_candidate": date,
            "source_count": len(rows),
            "primary_seed_dob": prior,
            "dob_status": status,
        })
    return records


def run(args):
    input_path = Path(args.pairs)
    seed_path = Path(args.seed)
    queue = read_csv(input_path)
    if not queue:
        raise ValueError("Official historical pair match queue is empty")
    jobs = official_jobs(queue)
    order = alternate_end_order(jobs)
    selected = order[:args.limit] if args.limit else order
    seed = checked_seed(seed_path)
    session = configure_session(args.proxy, args.no_env_proxy)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    inventory, candidates = [], []

    for n, ident in enumerate(selected, 1):
        task = jobs[ident]
        inv = {
            "profile_id": ident, "profile_url": task["profile_url"],
            "historic_pair_ids": "; ".join(sorted(task["historic_pair_ids"])),
            "person_a_id": task["person_a_id"],
            "person_b_id": task["person_b_id"],
            "status": "fetch_failed", "parsed_members": 0,
            "cached": False, "error": "",
        }
        sides = []
        try:
            html, cached = download_profile(
                session, ident, Path(args.cache), offline=args.offline,
                refresh=args.refresh, timeout=args.timeout,
            )
            inv["cached"] = cached
            parsed = parse_pair_profile(
                html, task["person_a_name"], task["person_b_name"]
            )
            for i, (person, name, observation) in enumerate(zip(
                (task["person_a_id"], task["person_b_id"]),
                (task["person_a_name"], task["person_b_name"]), parsed
            ), 1):
                dob = observation["date_of_birth"]
                prior = seed.get(person, "")
                state = ("conflict_with_primary_seed" if dob and prior and dob != prior
                         else "agrees_with_primary_seed" if dob and prior else
                         "no_prior_primary_seed")
                sides.append({
                    "profile_id": ident,
                    "historic_pair_ids": inv["historic_pair_ids"],
                    "historic_person_id": person, "side_on_profile": i,
                    "historic_name": name,
                    "observed_name": observation["observed_name"],
                    "date_of_birth": dob,
                    "parse_method": observation["parse_method"],
                    "parse_status": observation["parse_status"],
                    "seed_dob": prior, "seed_consistency": state,
                    "source_url": task["profile_url"],
                })
            inv["parsed_members"] = sum(bool(x["date_of_birth"]) for x in sides)
            inv["status"] = "both_dobs_bound" if inv["parsed_members"] == 2 else "needs_layout_review"
            print(f"[HIST BIO {n}/{len(selected)}] {ident}: {inv['parsed_members']}/2 DOBs"
                  f"  cached={cached}", flush=True)
        except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
            inv["error"] = type(exc).__name__ + ": " + str(exc)[:400]
            print(f"[HIST FAIL {n}/{len(selected)}] {ident}: {inv['error']}",
                  file=sys.stderr, flush=True)
            for i, (person, name) in enumerate((
                (task["person_a_id"], task["person_a_name"]),
                (task["person_b_id"], task["person_b_name"])
            ), 1):
                sides.append({
                    "profile_id": ident, "historic_pair_ids": inv["historic_pair_ids"],
                    "historic_person_id": person, "side_on_profile": i,
                    "historic_name": name, "observed_name": "",
                    "date_of_birth": "", "parse_method": "",
                    "parse_status": "fetch_failed",
                    "seed_dob": seed.get(person, ""), "seed_consistency": "",
                    "source_url": task["profile_url"],
                })
        inventory.append(inv)
        candidates.extend(sides)
        if n % 10 == 0 or n == len(selected):
            persist(out, inventory, candidates)
        if not args.offline and not inv["cached"] and args.delay:
            time.sleep(args.delay)

    per_person = summarize_people(candidates, seed)
    write_csv(out / "historic_isu_person_dob_candidates.csv", PERSON_FIELDS, per_person)
    need_review = [x for x in candidates
                   if x["parse_status"] != "dob_explicitly_bound_to_expected_name"
                   or x["seed_consistency"] == "conflict_with_primary_seed"]
    write_csv(out / "historic_isu_bio_review.csv", CAND_FIELDS, need_review)
    stats = Counter(x["status"] for x in inventory)
    pstats = Counter(x["dob_status"] for x in per_person)
    summary = {
        "scope": "Only source-matched official historical pair profiles; DOB candidates, no master edits",
        "exact_couple_input_rows": len(queue),
        "unique_profiles_in_queue": len(jobs),
        "profiles_selected": len(selected),
        "profiles_attempted": len(inventory),
        "profiles_both_dobs_bound": stats["both_dobs_bound"],
        "profiles_needing_layout_review": stats["needs_layout_review"],
        "profiles_fetch_failed": stats["fetch_failed"],
        "cache_hits": sum(bool(x["cached"]) for x in inventory),
        "source_person_slots": len(candidates),
        "slots_with_explicitly_bound_dob": sum(bool(x["date_of_birth"]) for x in candidates),
        "distinct_historic_people_in_pilot": len(per_person),
        "person_dob_status_counts": dict(sorted(pstats.items())),
        "review_rows": len(need_review),
        "parsed_methods": dict(sorted(Counter(x["parse_method"]
                              for x in candidates if x["parse_method"]).items())),
        "offline": bool(args.offline),
        "limit": args.limit,
        "input_sha256": {
            str(input_path): digest(input_path),
            str(seed_path): digest(seed_path),
        },
        "limitations": [
            "The official biography INDEX match does not verify a source DOB",
            "Only explicit name/date-label adjacency is parsed; unresolved layouts are review-only",
            "A historical athlete may appear in several couples; dates must agree before promotion",
            "An exact name on a pair page is source-correlated identity, not second-source verification",
            "Official seed conflicts are retained for adjudication and never overwritten",
            "The historic input is selected events, not complete ISU participant coverage",
            "No BaZi, performance analysis, or cohort exclusions based on astrological features"
        ],
    }
    (out / "historic_isu_bio_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "unique_profiles_in_queue", "profiles_selected", "profiles_both_dobs_bound",
        "profiles_needing_layout_review", "profiles_fetch_failed",
        "slots_with_explicitly_bound_dob", "distinct_historic_people_in_pilot",
        "review_rows", "parsed_methods"
    )}, ensure_ascii=False, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs", default="output/historic_dob/isu_index/historic_exact_pair_profile_queue.csv")
    p.add_argument("--seed", default="data/adjudications/isu_historic_primary_dob_seed_v2.csv")
    p.add_argument("--cache", default="cache/isu_bios")
    p.add_argument("--out", default="output/historic_dob/biographies")
    p.add_argument("--limit", type=int, default=20,
                   help="Pilot batch size; 0 selects all matched profiles")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--delay", type=float, default=0.4)
    args = p.parse_args()
    if args.limit < 0:
        p.error("--limit must be >= 0")
    result = run(args)
    return 2 if result["profiles_fetch_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
