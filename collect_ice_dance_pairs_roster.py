#!/usr/bin/env python3
"""Collect ice-dance and pair-skating roster, without computing Bazi.

Inputs:
  1. Public results CSVs from Jessica Zhu's 2005–2018 GitHub dataset
     (online or from a manually downloaded GitHub source ZIP).
  2. Public fsresults.info historical couples index (paginated; optional).
  3. User-supplied pilot records (--pilot-csv, optional).

All observations retain source links and identity uncertainty. Outputs: CSV and JSON.
This is a roster DISCOVERY pipeline, not a claim of exhaustive ISU coverage.

Run (single line):
  python collect_ice_dance_pairs_roster.py --source both --out skating_roster
Offline source ZIP:
  python collect_ice_dance_pairs_roster.py --source github --repo-zip figure-skating-analysis-master.zip --out skating_roster
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import urljoin
import zipfile

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Please install dependencies: python -m pip install requests beautifulsoup4")

GITHUB_REPO = "mengyazhu96/figure-skating-analysis"
GITHUB_TREE = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/master?recursive=1"
FSRESULTS = "https://fsresults.info/couples"
HEADERS = {"User-Agent": "AcademicFigureSkatingRosterResearch/0.1 (polite archival lookup; no login)"}
OBS_FIELDS = ["source_type", "season", "event", "event_date", "discipline", "name_as_published", "person_a", "person_b", "nation", "rank", "score", "catalog_season_text", "catalog_competitions", "record_status", "identity_flag", "source_url"]


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def norm(s):
    x = unicodedata.normalize("NFKD", clean(s)).casefold()
    x = "".join(c for c in x if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", x).strip()


def norm_disc(raw):
    x = clean(raw).lower()
    if "ice dance" in x or x in ("dance", "d"):
        return "Ice Dance"
    if x in ("pairs", "pair", "pair skating", "p"):
        return "Pair Skating"
    return None


def parse_name(raw):
    parts = re.split(r"\s+/\s+", clean(raw), maxsplit=1)
    if len(parts) != 2 or not all(parts):
        return clean(raw), "", "bad_slash_split"
    return parts[0], parts[1], ""


def flag_name(a, b):
    joined = (a + " " + b).casefold()
    if any(v in joined for v in (" solo ", "sc of ", " fsc", " skating club", "club")) or "," in joined:
        return "manual_review_club_or_solo"
    if not a or not b or norm(a) == norm(b):
        return "manual_review_name"
    return "provisional_exact_name"


def norm_pair_key(disc, a, b):
    return (disc,) + tuple(sorted((norm(a), norm(b))))


def season_from_path(path):
    m = re.match(r"^(\d\d)(\d\d)/", path)
    if not m:
        return ""
    a = 2000 + int(m.group(1)) if int(m.group(1)) <= 50 else 1900 + int(m.group(1))
    b = 2000 + int(m.group(2)) if int(m.group(2)) <= 50 else 1900 + int(m.group(2))
    return f"{a}-{b}"


def obs(source_type, disc, raw, nation="", event="", date="", rank="", score="", url="", season="", catalog_season="", competition_count=""):
    a, b, split_flag = parse_name(raw)
    if not disc:
        return None
    return dict(source_type=source_type, season=season, event=event, event_date=date,
                discipline=disc, name_as_published=clean(raw), person_a=a, person_b=b,
                nation=clean(nation), rank=clean(rank), score=clean(score),
                catalog_season_text=catalog_season, catalog_competitions=competition_count,
                record_status="observed", identity_flag=split_flag or flag_name(a, b), source_url=url)


def parse_results_csv(text, path):
    disc = "Ice Dance" if path.endswith("ice_dance_results.csv") else "Pair Skating"
    season = season_from_path(path)
    source_url = f"https://github.com/{GITHUB_REPO}/blob/master/{path}"
    result = []
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        name = r.get("Name") or r.get("name")
        if not name:
            continue
        o = obs("gh_historic_event", disc, name, r.get("Nation", ""),
                r.get("Event", ""), r.get("Date", ""), r.get("Rank", ""),
                r.get("Points", ""), source_url, season)
        if o:
            result.append(o)
    return result


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    if os.environ.get("GITHUB_TOKEN"):
        s.headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    return s


def get_text(s, url, cachefile, refresh=False, timeout=45):
    cachefile.parent.mkdir(parents=True, exist_ok=True)
    if cachefile.exists() and not refresh:
        return cachefile.read_text(encoding="utf-8")
    error = None
    for retry in range(4):
        try:
            r = s.get(url, timeout=timeout)
            if r.status_code == 429 or r.status_code in (500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            cachefile.write_text(r.text, encoding="utf-8")
            return r.text
        except Exception as e:
            error = e
            time.sleep(min(2 ** retry, 8))
    raise RuntimeError(f"download failed {url}: {error}")


def collect_github_zip(path, records, inventory):
    with zipfile.ZipFile(path) as archive:
        paths = [p for p in archive.namelist() if re.search(r"/\d{4}/[^/]+/(ice_dance|pairs)_results\.csv$", p)]
        for full_path in paths:
            m = re.search(r"/(\d{4}/[^/]+/(?:ice_dance|pairs)_results\.csv)$", full_path)
            repo_path = m.group(1) if m else full_path
            try:
                data = archive.read(full_path).decode("utf-8-sig", errors="replace")
                item = parse_results_csv(data, repo_path)
                records.extend(item)
                inventory.append(["github_offline_zip", repo_path, "ok", len(item), "", str(path)])
            except Exception as exc:
                inventory.append(["github_offline_zip", repo_path, "error", 0, str(exc), str(path)])
    return len(paths)


def collect_github_online(s, cache, records, inventory, refresh=False, delay=0.3):
    tree = json.loads(get_text(s, GITHUB_TREE, cache / "github_tree.json", refresh))
    paths = [item["path"] for item in tree.get("tree", []) if re.match(r"^\d{4}/[^/]+/(ice_dance|pairs)_results\.csv$", item["path"])]
    if not paths:
        raise RuntimeError("GitHub tree contains no matching result CSVs; check tree response")
    if tree.get("truncated"):
        print("WARNING: GitHub recursive tree was truncated: coverage may be incomplete", file=sys.stderr)
    print(f"GitHub: discovered {len(paths)} event result CSVs", flush=True)
    for i, path in enumerate(paths, 1):
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/master/{path}"
        try:
            data = get_text(s, url, cache / "github" / path, refresh)
            item = parse_results_csv(data, path)
            records.extend(item)
            inventory.append(["github_historic", path, "ok", len(item), "", url])
        except Exception as exc:
            inventory.append(["github_historic", path, "error", 0, str(exc)[:400], url])
        if i % 25 == 0 or i == len(paths):
            print(f"GitHub {i}/{len(paths)} files; {len(records)} observations", flush=True)
        if delay and i < len(paths):
            time.sleep(delay)


def collect_catalog(s, cache, records, inventory, refresh=False, max_pages=0, delay=1.0, max_season_start=2025):
    first_url = FSRESULTS + "?page=1"
    page1 = get_text(s, first_url, cache / "catalog" / "page_001.html", refresh)
    first_soup = BeautifulSoup(page1, "html.parser")
    pager_text = clean(first_soup.get_text(" ", strip=True))
    m = re.search(r"page\s+\d+\s+of\s+(\d+)", pager_text, re.I)
    total = int(m.group(1)) if m else 1
    if max_pages:
        total = min(total, max_pages)
    print(f"Couples catalog: {total} page(s)", flush=True)
    for page in range(1, total + 1):
        url = FSRESULTS + f"?page={page}"
        try:
            html = page1 if page == 1 else get_text(s, url, cache / "catalog" / f"page_{page:03d}.html", refresh)
            soup = BeautifulSoup(html, "html.parser")
            found = 0
            for tr in soup.find_all("tr"):
                cells = tr.find_all("td", recursive=False)
                if len(cells) < 5:
                    continue
                discipline = norm_disc(cells[2].get_text(" ", strip=True))
                if not discipline:
                    continue
                name = clean(cells[0].get_text(" ", strip=True))
                nation = clean(cells[1].get_text(" ", strip=True))
                season_text = clean(cells[3].get_text(" ", strip=True))
                games = clean(cells[4].get_text(" ", strip=True))
                # Catalog sometimes contains future-only seasons. Keep a team if its
                # listed first season is no later than the requested final season.
                initial_match = re.search(r"(?<!\d)(\d{2})/(\d{2})(?!\d)", season_text)
                if initial_match and (2000 + int(initial_match.group(1))) > max_season_start:
                    continue
                a = cells[0].find("a", href=True)
                profile_url = urljoin(url, a["href"]) if a else url
                o = obs("fsresults_catalog", discipline, name, nation=nation, url=profile_url,
                        catalog_season=season_text, competition_count=games)
                if o:
                    records.append(o)
                    found += 1
            if found == 0:
                raise ValueError("no couple rows found; website layout or protection may have changed")
            inventory.append(["fsresults_catalog", str(page), "ok", found, "", url])
        except Exception as exc:
            inventory.append(["fsresults_catalog", str(page), "error", 0, str(exc)[:400], url])
        if page % 10 == 0 or page == total:
            print(f"Catalog {page}/{total} pages; {len(records)} total observations", flush=True)
        if delay and page < total:
            time.sleep(delay)


def collect_pilot_csv(filename, records, inventory):
    with open(filename, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            o = obs("pilot_worlds", norm_disc(r.get("Discipline")),
                    (r.get("Woman", "") + " / " + r.get("Man", "")),
                    nation=r.get("Country", ""), event="World Championships", date="",
                    rank=r.get("Final Rank", ""), score=r.get("Score / points", ""),
                    url=r.get("Result source URL", ""), season=r.get("Year", ""))
            if o:
                records.append(o)
    inventory.append(["pilot_worlds", filename, "ok", len(records), "", filename])


def collect_extra_seed_2014_2017(filename, records, inventory):
    """Read an auditable compact TSV generated from the cited ISU/GitHub result sources."""
    n0 = len(records)
    with open(filename, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            season = clean(r.get("season"))
            disc = norm_disc(r.get("discipline"))
            rank = clean(r.get("rank_or_event_count")) if season == "2014" else ""
            c = "" if season == "2014" else clean(r.get("rank_or_event_count"))
            event = "World Championships" if season == "2014" else "Selected ISU tournaments (grouped seed)"
            d = "2014" if season == "2014" else "2016-2017"
            item = obs("isu_worlds_2014" if season == "2014" else "buzzfeed_2016_2017_aggregated", disc, r.get("pair"),
                       nation=r.get("nation", ""), event=event,
                       date="", rank=rank,
                       url=r.get("source", ""), season=d, competition_count=c)
            if item: records.append(item)
    inventory.append(["extra_seed", filename, "ok", len(records)-n0, "", filename])


def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(headers)
        out.writerows(rows)


def summarize(records, inventory, outdir):
    rawseen = set(); clean_obs = []
    for r in records:
        key = (r["source_type"], r["source_url"], r["event"], r["event_date"], r["name_as_published"], r["discipline"])
        if key not in rawseen:
            rawseen.add(key)
            clean_obs.append(r)
    people = {}; couples = {}; presence = collections.defaultdict(set)
    for o in clean_obs:
        if not o["person_a"] or not o["person_b"]:
            continue
        disc = o["discipline"]
        key = norm_pair_key(disc, o["person_a"], o["person_b"])
        c = couples.setdefault(key, {"discipline":disc, "person_a":o["person_a"], "person_b":o["person_b"], "nations":set(), "seasons":set(), "events":set(), "sources":set(), "catalog_competitions":"", "audit":set(), "rows":0})
        c["rows"] += 1
        if o["nation"]: c["nations"].add(o["nation"])
        if o["season"]: c["seasons"].add(o["season"])
        if o["event"] and o["source_type"] != "buzzfeed_2016_2017_aggregated": c["events"].add((o["event"],o["event_date"] or o["season"]))
        if o["source_url"]: c["sources"].add(o["source_url"])
        if o["catalog_competitions"]: c["catalog_competitions"] = o["catalog_competitions"]
        if o["identity_flag"] != "provisional_exact_name": c["audit"].add(o["identity_flag"])
        for name in (o["person_a"], o["person_b"]):
            nk = norm(name)
            p = people.setdefault(nk, {"display":name, "disciplines":set(), "couples":set(), "sources":set(), "nations":set()})
            p["disciplines"].add(disc)
            p["couples"].add(key)
            if o["nation"]: p["nations"].add(o["nation"])
            if o["source_url"]: p["sources"].add(o["source_url"])
    obsrows = [[o.get(k, "") for k in OBS_FIELDS] for o in clean_obs]
    write_csv(outdir / "observations.csv", OBS_FIELDS, obsrows)
    crow = []
    for key, c in sorted(couples.items(), key=lambda q:(q[1]["discipline"],norm(q[1]["person_a"]),norm(q[1]["person_b"]))):
        crow.append([" / ".join(key[1:]), c["discipline"], c["person_a"], c["person_b"],
                     "; ".join(sorted(c["nations"])), "; ".join(sorted(c["seasons"])), len(c["events"]), c["catalog_competitions"], c["rows"],
                     "; ".join(sorted(c["audit"])) or "provisional_exact_name", "; ".join(sorted(c["sources"]))[:1800]])
    write_csv(outdir/"couples.csv", ["pair_identity_key","discipline","person_a_name","person_b_name","represented_nations","observed_seasons","observed_event_count","catalog_competitions_claim","source_rows","identity_review_flag","source_urls"], crow)
    prows=[]
    for namekey, p in sorted(people.items()):
        prows.append([namekey,p["display"],"; ".join(sorted(p["disciplines"])),len(p["couples"]),"; ".join(sorted(p["nations"])), "", "", "", "", "not_checked", "manual_identity_review", "; ".join(sorted(p["sources"]))[:1800]])
    write_csv(outdir/"athletes.csv", ["provisional_person_key","name_display","disciplines","distinct_partners_in_dataset","represented_nations","date_of_birth","birth_city","birth_country","birth_latitude","dob_status","identity_status","source_urls"],prows)
    write_csv(outdir/"source_inventory.csv", ["source","source_path_or_page","status","parsed_rows","error","url"],inventory)
    manifest = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "ice dance and pair skating; people and team discovery only; NO BaZi",
        "coverage_warning": "Historical repository covers selected major ISU competitions (2005-06 to 2017-18). Public couples index is an independently aggregated catalog and may include domestic, novice, inaccurate or duplicate entries. Neither alone guarantees every person who ever competed worldwide.",
        "identity_warning": "Provisional exact-name normalization only; transliteration/homonyms and reversed sex/partner order require manual review. DOB and birthplace deliberately blank until verified.",
        "total_observation_rows": len(clean_obs),
        "distinct_couples_provisional": len(couples),
        "distinct_person_names_provisional": len(people),
        "couples_by_discipline": dict(collections.Counter(c["discipline"] for c in couples.values())),
        "sources_ok": dict(collections.Counter(r[0] for r in inventory if r[2]=="ok")),
        "source_failures": [r for r in inventory if r[2]!="ok"],
    }
    (outdir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2), encoding="utf-8")
    print(json.dumps(manifest,indent=2,ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["both","github","catalog","none"], default="both")
    ap.add_argument("--repo-zip", type=Path, help="Optional local ZIP of github.com/mengyazhu96/figure-skating-analysis; makes GitHub component offline")
    ap.add_argument("--pilot-csv", action="append", default=[], help="Optional CSV exports with Year, Discipline, Woman, Man, etc.")
    ap.add_argument("--extra-seed", action="append", default=[], help="Optional tab-delimited source-audited pair seed (season, discipline, pair, nation, rank_or_event_count, source)")
    ap.add_argument("--out", type=Path, default=Path("skating_roster"))
    ap.add_argument("--max-catalog-pages", type=int, default=0, help="0 = all pages; use 1 or 2 for smoke test")
    ap.add_argument("--max-season-start", type=int, default=2025, help="Drop catalog teams beginning after this season; 2025=2025–26, default")
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between catalog requests (default 1s)")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    outdir=args.out; outdir.mkdir(parents=True,exist_ok=True)
    cache=outdir/"cache"; s=session(); records=[]; inventory=[]
    for f in args.pilot_csv:
        try: collect_pilot_csv(f,records,inventory)
        except Exception as e: inventory.append(["pilot",f,"error",0,str(e),f])
    for f in args.extra_seed:
        try: collect_extra_seed_2014_2017(f,records,inventory)
        except Exception as e: inventory.append(["extra_seed",f,"error",0,str(e),f])
    if args.source in ("both","github"):
        try:
            if args.repo_zip: collect_github_zip(args.repo_zip,records,inventory)
            else: collect_github_online(s,cache,records,inventory,args.refresh)
        except Exception as e: inventory.append(["github","all","error",0,str(e),GITHUB_TREE]);print("GitHub collection issue:",e,file=sys.stderr)
    if args.source in ("both","catalog"):
        try: collect_catalog(s,cache,records,inventory,args.refresh,args.max_catalog_pages,args.delay,args.max_season_start)
        except Exception as e: inventory.append(["fsresults_catalog","all","error",0,str(e),FSRESULTS]);print("Catalog collection issue:",e,file=sys.stderr)
    summarize(records,inventory,outdir)
    if not records: return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
