#!/usr/bin/env python3
"""Collect public ISU couple biographies: DOB and place candidates only; NO BaZi.

Conservative: never merge or assign DOB without an exact, normalized skater
name match to the season roster. Reports all unmatched and incomplete pages.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from audit_v4 import norm
from collect_isu_seasons import configure_session

PROFILE_PATTERN = re.compile(r"/bios/(isufs\d+)\.htm$", re.I)
DATE_PATTERN = re.compile(r"\b([0-3]?\d\.[01]?\d\.(?:19|20)\d{2})\b")
BIRTH_LABEL = re.compile(r"\bDate of birth\s*:\s*", re.I)
PLACE_LABEL = re.compile(r"\bPlace of birth\s*:\s*", re.I)
PLACE_END = re.compile(r"\b(?:Height|Home town|Profession|Hobbies|Start sk\.|Coach|Internet / Social Media|Former Partners|Practice|Music|Personal Best|Season Best|International Competition)\s*:", re.I)
NATION_CODES = frozenset("ARM AUS AUT AZE BEL BLR BRA CAN CHN CRO CYP CZE DEN ESP EST FIN FRA GBR GEO GER GRE HKG HUN INA IND IRL ISL ISR ITA JPN KAZ KOR LAT LTU MAS MEX NED NOR NZL PHI POL PRK ROU RSA RUS SGP SLO SRB SUI SVK SWE TPE TUR UKR USA UZB".split())
PROFILE_FIELDS = ["profile_id","profile_url","status","sections_found","exact_matches","error","cached"]
CAND_FIELDS = ["profile_id","profile_url","side_on_profile","observed_name","person_id","roster_name","date_of_birth","place_of_birth_raw","status"]


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_bio(html):
    """Extract up to two public biographical sections in reading order.

    Works with older and newer ISU formats where the DOB row may be split
    across table cells. Never assume a particular DOM table.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    flat = clean(soup.get_text(" ", strip=True))
    matches = list(BIRTH_LABEL.finditer(flat))
    out = []
    for i, m in enumerate(matches[:2]):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(flat)
        section = flat[m.end():end]
        place = PLACE_LABEL.search(section)
        first = section[:place.start()] if place else section[:180]
        dob = DATE_PATTERN.search(first)
        name = clean(first[dob.end():]) if dob else ""
        if name and name.split()[-1] in NATION_CODES:
            name = clean(name.rsplit(" ", 1)[0])
        birth_date = ""
        if dob:
            try:
                parsed = dt.datetime.strptime(dob.group(1), "%d.%m.%Y").date()
                if parsed <= dt.date.today() and parsed.year >= 1850:
                    birth_date = parsed.isoformat()
            except ValueError:
                pass
        birthplace = ""
        if place:
            right = section[place.end():]
            boundary = PLACE_END.search(right)
            birthplace = clean(right[:boundary.start()] if boundary else right[:180])
        if len(name.split()) < 2 or len(name) > 90:
            name = ""
        out.append({"observed_name": name, "date_of_birth": birth_date,
                    "place_of_birth_raw": birthplace,
                    "status": "parsed" if name and birth_date else "incomplete"})
    return out


def collect_profiles(season_roster):
    seen = defaultdict(lambda: defaultdict(set))
    with Path(season_roster).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            m = PROFILE_PATTERN.search(urlsplit(row.get("profile_url", "")).path)
            if not m:
                continue
            ident = m.group(1).lower()
            for side in ("a", "b"):
                pid = row.get("person_" + side + "_id", "")
                name = row.get("person_" + side + "_name", "")
                if name and pid:
                    seen[ident][norm(name)].add((pid, name))
    return dict(seen)


def download_profile(session, ident, cache, offline=False, refresh=False, timeout=15):
    path = cache / (ident + ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), True
    if offline:
        raise FileNotFoundError("No cached biography: " + ident)
    failures = []
    for host in ("results.isu.org", "www.isuresults.com"):
        url = f"https://{host}/bios/{ident}.htm"
        try:
            resp = session.get(url, timeout=(5, timeout))
            resp.raise_for_status()
            html = resp.content.decode(resp.encoding or "utf-8", errors="replace")
            visible_text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
            if len(html) < 200 or "date of birth" not in visible_text:
                raise ValueError("Not a usable biography")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            return html, False
        except (requests.exceptions.RequestException, ValueError) as exc:
            failures.append(f"{host}: {type(exc).__name__}: {str(exc)[:140]}")
    raise RuntimeError("; ".join(failures))


def save_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def run(args):
    profiles = collect_profiles(args.roster)
    keys = sorted(profiles)
    if args.limit:
        keys = keys[:args.limit]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session = configure_session(args.proxy, args.no_env_proxy)
    inventory, candidates = [], []
    for index, ident in enumerate(keys):
        url = f"https://results.isu.org/bios/{ident}.htm"
        item = {"profile_id": ident, "profile_url": url, "status": "error",
                "sections_found": 0, "exact_matches": 0, "error": "", "cached": False}
        try:
            html, cached = download_profile(session, ident, Path(args.cache),
                                            offline=args.offline, refresh=args.refresh,
                                            timeout=args.timeout)
            item["cached"] = cached
            entries = parse_bio(html)
            item["sections_found"] = len(entries)
            for i, p in enumerate(entries):
                n = norm(p["observed_name"]) if p["observed_name"] else ""
                matches = profiles[ident].get(n, set()) if n else set()
                matches = {x[0]: x[1] for x in matches}
                status = "exact_name_match" if len(matches) == 1 and p["date_of_birth"] else "needs_review"
                pid = next(iter(matches)) if len(matches) == 1 else ""
                if status == "exact_name_match":
                    item["exact_matches"] += 1
                candidates.append({"profile_id": ident, "profile_url": url,
                                   "side_on_profile": i + 1,
                                   "observed_name": p["observed_name"],
                                   "person_id": pid, "roster_name": matches.get(pid, ""),
                                   "date_of_birth": p["date_of_birth"],
                                   "place_of_birth_raw": p["place_of_birth_raw"],
                                   "status": status})
            item["status"] = "ok" if len(entries) == 2 else "incomplete"
            print(f"[BIO] {ident}: {len(entries)} sections, {item['exact_matches']} exact matches", flush=True)
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            print(f"[FAIL] {ident}: {item['error']}", file=sys.stderr, flush=True)
        inventory.append(item)
        save_csv(out / "biography_inventory.csv", inventory, PROFILE_FIELDS)
        save_csv(out / "birth_candidates.csv", candidates, CAND_FIELDS)
        if item["status"] == "error" and "ProxyError" in item["error"]:
            print("[STOP] Proxy connectivity error. Stopping pilot.", file=sys.stderr, flush=True)
            break
        if not args.offline and args.delay > 0:
            time.sleep(args.delay)
    summary = {"profiles_available": len(profiles), "profiles_requested": len(keys),
               "profiles_attempted": len(inventory),
               "profiles_ok": sum(x["status"] == "ok" for x in inventory),
               "profiles_incomplete": sum(x["status"] == "incomplete" for x in inventory),
               "profiles_failed": sum(x["status"] == "error" for x in inventory),
               "birth_candidates": len(candidates),
               "exact_name_and_date_matches": sum(x["status"] == "exact_name_match" for x in candidates),
               "limitations": ["Only public ISU profile biographies are used",
                               "Candidate DOBs are not merged into athlete master automatically",
                               "Names are matched conservatively to the known profile and roster",
                               "Place-of-birth text is not geocoded or hemisphere-classified"]}
    (out / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if summary["profiles_failed"] else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster", default="output/master/season_roster.csv")
    p.add_argument("--out", default="output/bios")
    p.add_argument("--cache", default="cache/isu_bios")
    p.add_argument("--limit", type=int, default=10,
                   help="Default safety pilot is 10 profiles; use --limit 0 for all")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--delay", type=float, default=.4)
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
