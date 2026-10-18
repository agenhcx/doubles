#!/usr/bin/env python3
"""Cross-check historic ISU pairs against the public official biography index.

Only 2 index HTML pages are downloaded (one for Ice Dance, one for Pairs).
The output is an identity/profile-link candidate list, NOT a verified DOB.
Do not alter historic/master roster, infer missing dates, or compute BaZi.

One-line PowerShell:
python .\scripts\audit_historic_isu_indexes.py --proxy http://127.0.0.1:10808
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from audit_isu_identities import digest, norm, read_csv, write_csv
from collect_isu_seasons import configure_session

INDEX_FILES = {
    "Ice Dance": "fsbiosdance.htm",
    "Pair Skating": "fsbiospairs.htm",
}
HOSTS = ("www.isuresults.com", "results.isu.org")
PROFILE_RE = re.compile(r"^/bios/(isufs\d+)\.htm$", re.I)
ENTRY_FIELDS = [
    "discipline", "index_profile_id", "person_a_name", "person_b_name",
    "profile_url", "index_url", "match_scope"
]
PAIR_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_a_id",
    "historic_person_b_id", "historic_person_a_name",
    "historic_person_b_name", "index_match_status",
    "exact_profile_ids", "exact_profile_urls", "reversed_profile_ids",
    "candidate_a_profile_ids", "candidate_b_profile_ids",
    "matched_a_name_count", "matched_b_name_count",
    "historical_event_count", "review_required"
]


def clean(txt):
    return re.sub(r"\s+", " ", txt or "").strip()


def split_couple(text):
    if text.count("/") != 1:
        return None
    a, b = (clean(x) for x in text.split("/", 1))
    # Two tokens per full name for a conservative match; initial-only forms
    # will be handled later by person-context review.
    if not a or not b or len(a) > 100 or len(b) > 100:
        return None
    if len(norm(a).split()) < 2 or len(norm(b).split()) < 2:
        return None
    return (a, b)


def parse_index(html, discipline, index_url):
    """Extract direct official couple-profile anchors, ignoring other links."""
    if discipline not in INDEX_FILES:
        raise ValueError("Unsupported discipline " + str(discipline))
    soup = BeautifulSoup(html, "html.parser")
    flat = clean(soup.get_text(" ", strip=True)).lower()
    if "figure skating biographies" not in flat:
        raise ValueError("ISU index page title missing")
    rows = {}
    for a in soup.select("a[href]"):
        pair = split_couple(a.get_text(" ", strip=True))
        if not pair:
            continue
        link = urljoin(index_url, a["href"].strip())
        parsed = urlsplit(link)
        m = PROFILE_RE.fullmatch(parsed.path)
        if parsed.scheme != "https" and parsed.scheme != "http":
            continue
        if parsed.hostname not in HOSTS or not m:
            continue
        ident = m.group(1).lower()
        key = (ident, norm(pair[0]), norm(pair[1]))
        rows[key] = {
            "discipline": discipline, "index_profile_id": ident,
            "person_a_name": pair[0], "person_b_name": pair[1],
            "profile_url": link, "index_url": index_url,
            "match_scope": "official_index_only_not_dob_verified",
        }
    if len(rows) < 1:
        raise ValueError("ISU biography index has no usable couple links")
    return list(rows.values())


def download_index(session, discipline, cache, *, offline=False,
                   refresh=False, timeout=25):
    base = INDEX_FILES[discipline]
    cache_path = Path(cache) / base
    if cache_path.exists() and not refresh:
        html = cache_path.read_text(encoding="utf-8")
        return html, f"https://www.isuresults.com/bios/{base}", True
    if offline:
        raise FileNotFoundError("Missing cache " + str(cache_path))
    errors = []
    for host in HOSTS:
        url = f"https://{host}/bios/{base}"
        try:
            response = session.get(url, timeout=(5, timeout))
            response.raise_for_status()
            html = response.content.decode(response.encoding or "utf-8", errors="replace")
            parse_index(html, discipline, url)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(html, encoding="utf-8")
            return html, url, False
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{host}: {type(exc).__name__}: {str(exc)[:160]}")
    raise RuntimeError("; ".join(errors))


def crosslink(historic_pairs_path, index_entries, out_dir="output/historic_dob/isu_index"):
    """Match *both* full member names and their order to historic pairs."""
    historic_pairs_path = Path(historic_pairs_path)
    historic = read_csv(historic_pairs_path)
    if not historic:
        raise ValueError("Historic couples roster is empty")
    if not index_entries:
        raise ValueError("No official index entries")

    direct = defaultdict(list)
    reverse = defaultdict(list)
    individuals_a = defaultdict(set)
    individuals_b = defaultdict(set)
    distinct = {}
    for item in index_entries:
        d = item["discipline"]
        pid = item["index_profile_id"]
        a, b = norm(item["person_a_name"]), norm(item["person_b_name"])
        key = (d, pid)
        if key in distinct and distinct[key] != (a, b):
            raise ValueError("One official profile ID has contradictory pair names")
        distinct[key] = (a, b)
        direct[(d, a, b)].append(item)
        reverse[(d, b, a)].append(item)
        individuals_a[(d, a)].add(pid)
        individuals_b[(d, b)].add(pid)

    records = []
    tally = Counter()
    for r in historic:
        d = r["discipline"]
        if d not in INDEX_FILES:
            raise ValueError("Unsupported historical discipline: " + d)
        a, b = norm(r["person_a_name"]), norm(r["person_b_name"])
        exact = direct.get((d, a, b), [])
        flipped = reverse.get((d, a, b), [])
        side_a = individuals_a.get((d, a), set())
        side_b = individuals_b.get((d, b), set())
        exact_ids = {p["index_profile_id"] for p in exact}
        if len(exact_ids) == 1:
            status = "exact_couple_profile"
        elif len(exact_ids) > 1:
            status = "multiple_exact_profiles"
        elif flipped:
            status = "reversed_member_order_review"
        elif side_a and side_b:
            status = "both_names_separately_indexed"
        elif side_a or side_b:
            status = "one_partner_indexed"
        else:
            status = "no_direct_name_match"
        tally[status] += 1
        records.append({
            "historic_pair_id": r["pair_id"], "discipline": d,
            "historic_person_a_id": r["person_a_id"],
            "historic_person_b_id": r["person_b_id"],
            "historic_person_a_name": r["person_a_name"],
            "historic_person_b_name": r["person_b_name"],
            "index_match_status": status,
            "exact_profile_ids": "; ".join(sorted(exact_ids)),
            "exact_profile_urls": "; ".join(sorted({p["profile_url"] for p in exact})),
            "reversed_profile_ids": "; ".join(sorted({p["index_profile_id"] for p in flipped})),
            "candidate_a_profile_ids": "; ".join(sorted(side_a)),
            "candidate_b_profile_ids": "; ".join(sorted(side_b)),
            "matched_a_name_count": len(side_a),
            "matched_b_name_count": len(side_b),
            "historical_event_count": r.get("identified_event_count", ""),
            "review_required": "YES",
        })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda x: (
        x["index_match_status"] != "exact_couple_profile",
        -(int(x["historical_event_count"])
          if x["historical_event_count"].isdigit() else 0),
        x["historic_pair_id"],
    ))
    exact_records = [r for r in records
                     if r["index_match_status"] == "exact_couple_profile"]
    write_csv(out / "historic_pair_official_index_links.csv", PAIR_FIELDS, records)
    write_csv(out / "historic_exact_pair_profile_queue.csv", PAIR_FIELDS, exact_records)
    write_csv(out / "official_index_couple_inventory.csv", ENTRY_FIELDS, index_entries)
    summary = {
        "scope": "Selected 2004-2018 ISU historical pairs versus current official biography indexes",
        "status": "crosslink_candidates_only_not_verified_birthdates",
        "historic_couples": len(historic),
        "official_index_entries": len(index_entries),
        "official_index_profile_ids": len(distinct),
        "pair_match_counts": dict(sorted(tally.items())),
        "exact_pair_profiles_for_followup": len(exact_records),
        "source_sha256": {str(historic_pairs_path): digest(historic_pairs_path)},
        "limitations": [
            "Index completeness across historical seasons is unknown",
            "Exact pair names and roles identify a profile candidate, not an accepted DOB",
            "Different transliterations and spelling changes require separate review",
            "Older official biography HTML can reverse the name and DOB order",
            "Only official index pages are downloaded; individual biographies are not fetched",
            "No original CSV is edited, no birth date filled, and no BaZi computed",
        ],
    }
    (out / "historic_isu_index_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        k: summary[k] for k in (
            "historic_couples", "official_index_entries",
            "official_index_profile_ids", "exact_pair_profiles_for_followup",
            "pair_match_counts",
        )
    }, indent=2, ensure_ascii=False))
    return summary


def run(args):
    session = configure_session(args.proxy, args.no_env_proxy)
    fetched = []
    inventory = []
    for discipline in INDEX_FILES:
        try:
            html, url, cached = download_index(
                session, discipline, args.cache, offline=args.offline,
                refresh=args.refresh, timeout=args.timeout,
            )
            rows = parse_index(html, discipline, url)
            fetched.extend(rows)
            inventory.append({
                "discipline": discipline, "source_url": url,
                "status": "ok", "entries": len(rows), "cached": cached,
            })
            print(f"[INDEX] {discipline}: {len(rows)} profiles cached={cached}", flush=True)
        except (requests.RequestException, OSError, RuntimeError, ValueError) as exc:
            inventory.append({
                "discipline": discipline,
                "source_url": "",
                "status": "failed", "entries": 0,
                "cached": False, "error": f"{type(exc).__name__}: {str(exc)[:350]}",
            })
            print(f"[FAIL] {discipline}: {exc}", file=sys.stderr, flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index_source_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    if any(item["status"] != "ok" for item in inventory):
        raise RuntimeError("Index fetch failed; output preserved, but no partial cohort audit")
    return crosslink(args.historic_pairs, fetched, args.out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historic-pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--cache", default="cache/isu_bio_indexes")
    p.add_argument("--out", default="output/historic_dob/isu_index")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--timeout", type=int, default=25)
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
