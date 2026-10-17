#!/usr/bin/env python3
r"""Collect ISU Season's World Rankings for Ice Dance / Pair Skating; NO BaZi.

This is a season roster source, NOT a list of every entrant and NOT an event-level score.
The page cache is local and excluded from Git. A missing or unparseable page is
recorded as an error, never reported as an empty successful season.

One-line PowerShell:
 python .\scripts\collect_isu_seasons.py --season-start 2018 --season-end 2025 --out .\output\isu
Offline replay (after at least one download):
 python .\scripts\collect_isu_seasons.py --offline --out .\output\isu
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

SOURCES = (
    ("senior", "Ice Dance", "wrdance.htm"),
    ("senior", "Pair Skating", "wrpairs.htm"),
    ("junior", "Ice Dance", "wrjuniordance.htm"),
    ("junior", "Pair Skating", "wrjuniorpairs.htm"),
)
FIELDS = ["season", "season_start_year", "level", "discipline", "rank", "points", "person_a", "person_b", "nation", "name_as_published", "source_url", "profile_url", "status"]
META_FIELDS = ["season", "level", "discipline", "status", "rows", "url", "cache_file", "error"]
NATION_PATTERN = re.compile(r"^[A-Z]{3}$")
INT_PATTERN = re.compile(r"^\d{1,4}$")
POINT_PATTERN = re.compile(r"^\d{1,5}(?:\.\d+)?$")
BAD_NAMES = {"men", "ladies", "women", "pairs", "ice dance", "season", "world ranking"}
# In 2018-19 some ISU ranking tables put the three-letter country code in
# the same cell as "person A / person B". Do not mistake it for a surname.
# Keep this as an explicit allowlist: never trim an arbitrary capitalized name.
ISU_COUNTRY_CODES = frozenset((
    "ARM AUS AUT AZE BEL BLR BRA CAN CHN CRO CYP CZE DEN ESP EST FIN FRA "
    "GBR GEO GER GRE HKG HUN INA IND IRL ISL ISR ITA JPN KAZ KOR LAT LTU "
    "MAS MEX NED NOR NZL PHI POL PRK ROU RSA RUS SGP SLO SRB SUI SVK "
    "SWE TPE TUR UKR USA UZB"
).split())


class DownloadFailed(RuntimeError):
    """A whole source page failed; networking failures should stop the batch."""
    def __init__(self, message: str, *, network_block: bool = False):
        super().__init__(message)
        self.network_block = network_block


def configure_session(proxy: str | None = None, no_env_proxy: bool = False) -> requests.Session:
    """Explicit --proxy takes priority over HTTPS_PROXY/HTTP_PROXY in the environment.

    Requests merges environment proxies into requests before session proxies,
    so simply calling sess.proxies.update(...) is insufficient when trust_env=True.
    """
    session = requests.Session()
    session.headers["User-Agent"] = (
        "DoublesResearchDataset/0.2 (ISU public historical roster; research only)"
    )
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("--proxy must be an HTTP(S) URL, e.g. http://127.0.0.1:10808")
        session.trust_env = False
        session.proxies.update({"http": proxy, "https": proxy})
    elif no_env_proxy:
        session.trust_env = False
    return session


def clean(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").replace("\xa0", " ")).strip()


def validate_pair_name(name: str):
    """Only exact 'person A / person B' names; no speculative split."""
    if name.count("/") != 1:
        return None
    names = [clean(v) for v in name.split("/", 1)]
    if len(names) != 2:
        return None
    if any(len(n) < 3 or len(n) > 90 or len(n.split()) < 2 or n.casefold() in BAD_NAMES for n in names):
        return None
    if any(re.search(r"(?:\d{4}|http:|https:|\bseason\b)", n, flags=re.I) for n in names):
        return None
    return names


def parse_page(html: str, *, season: str, level: str, discipline: str, url: str):
    """Extract individual ranking rows; retain raw rank, points and provenance.

    All major historical and newer ISU rankings are HTML tables with one
    couple per row. This intentionally requires a numeric rank plus a name.
    """
    soup = BeautifulSoup(html, "html.parser")
    head = clean(soup.get_text(" ", strip=True)[:2500]).lower()
    if "world ranking" not in head and "world standings" not in head:
        raise ValueError("This page does not appear to be an ISU ranking page")
    seen = {}
    for tr in soup.select("tr"):
        td = tr.find_all("td", recursive=False)
        if len(td) < 3:
            continue
        # Some older pages have a nested per-year points table; examine
        # only the top-level cells so a nested row cannot create a couple.
        simple = [clean(c.get_text(" ", strip=True)) for c in td]
        candidates = [(idx, raw) for idx, raw in enumerate(simple)
                      if len(raw) < 200 and validate_pair_name(raw)]
        if not candidates:
            continue
        candidates.sort(key=lambda x: abs(x[0] - 2))
        idx, raw = candidates[0]
        names = validate_pair_name(raw)
        if not names or idx < 1:
            continue
        rank_candidates = [(j, t) for j, t in enumerate(simple[:idx]) if INT_PATTERN.fullmatch(t)]
        if not rank_candidates:
            continue
        try:
            rank = int(rank_candidates[0][1])
        except ValueError:
            continue
        if rank < 1 or rank > 2000:
            continue
        points = ""
        numeric_after_rank = [t for j, t in rank_candidates if j > rank_candidates[0][0]]
        if numeric_after_rank:
            points = numeric_after_rank[0]
        nation = ""
        for v in simple[idx+1:idx+5]:
            if NATION_PATTERN.fullmatch(v):
                nation = v
                break
            # Some ISU generations combine nation with a season subtable.
            cand = re.match(r"^([A-Z]{3})(?:\s+|$)", v)
            if cand:
                nation = cand.group(1)
                break
        if not nation:
            # Some 2018-19 tables embed the nation code in the same TD as
            # the couple name, e.g. "Madison HUBBELL / Zachary DONOHUE USA".
            # Only strip an explicit known ISU three-letter country code.
            suffix = re.fullmatch(r"(.+?)\s+([A-Z]{3})", names[1])
            if suffix and suffix.group(2) in ISU_COUNTRY_CODES:
                candidate_b = suffix.group(1)
                if validate_pair_name(f"{names[0]} / {candidate_b}"):
                    names[1] = candidate_b
                    nation = suffix.group(2)
        anchor = td[idx].find("a", href=True)
        profile = urljoin(url, anchor["href"]) if anchor else ""
        rec = dict(season=season, season_start_year=season[:4], level=level,
                   discipline=discipline, rank=str(rank), points=points,
                   person_a=names[0], person_b=names[1], nation=nation,
                   name_as_published=raw, source_url=url,
                   profile_url=profile, status="parsed_provisional")
        nk = (" ".join(sorted(names[0].casefold().split())), " ".join(sorted(names[1].casefold().split())))
        if nk not in seen or rank < int(seen[nk]["rank"]):
            seen[nk] = rec
    if not seen:
        raise ValueError("No pairs with numeric rank parsed; check HTML layout or access")
    result = sorted(seen.values(), key=lambda r: (int(r["rank"]), r["person_a"], r["person_b"]))
    return result


def download(session, season, basename, cache_dir: Path, *, offline=False, refresh=False, timeout=25):
    cache_path = cache_dir / season / basename
    base = f"/ws/wr{season}/{basename}"
    urls = [f"https://results.isu.org{base}", f"https://www.isuresults.com{base}"]
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8"), urls[0], cache_path
    if offline:
        raise FileNotFoundError(f"No cached HTML for {season}/{basename}")
    failures = []
    network_errors = []
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for url in urls:
        try:
            resp = session.get(url, timeout=(5, timeout))
            resp.raise_for_status()
            html = resp.content.decode(resp.encoding or "utf-8", errors="replace")
            if len(html) < 300:
                raise ValueError("HTML unusually short")
            cache_path.write_text(html, encoding="utf-8")
            return html, url, cache_path
        except Exception as exc:
            failures.append(f"{url}: {type(exc).__name__}: {str(exc)[:160]}")
            network_errors.append(isinstance(exc, (
                requests.exceptions.ProxyError,
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            )))
    raise DownloadFailed(" ; ".join(failures), network_block=all(network_errors))


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    sess = configure_session(args.proxy, args.no_env_proxy)
    if args.proxy:
        parsed = urlsplit(args.proxy)
        print(f"[NETWORK] Explicit {parsed.scheme.upper()} proxy at {parsed.hostname}:{parsed.port}; "
              "ignoring HTTP_PROXY/HTTPS_PROXY environment variables", flush=True)
    elif args.no_env_proxy:
        print("[NETWORK] Direct connection; ignoring environment proxies", flush=True)
    else:
        print("[NETWORK] Using system environment proxy settings, if configured", flush=True)
    rows, inventory = [], []
    use_levels = set(args.level.split(","))
    # Independent Junior World Standings/Season Rankings started only in
    # 2023-24 (ISU Communication 2550, announced 2023-04-06).
    # Before that, junior international results contributed to the overall
    # standings; their standalone wrjunior*.htm pages did not yet exist.
    all_jobs = [(f"{year}-{(year+1)%100:02d}", level, discipline, basename)
                for year in range(args.season_start, args.season_end + 1)
                for level, discipline, basename in SOURCES if level in use_levels]
    not_applicable = [j for j in all_jobs if j[1] == "junior" and int(j[0][:4]) < 2023]
    jobs = [j for j in all_jobs if j not in not_applicable]
    if not_applicable:
        print(f"[INFO] {len(not_applicable)} pre-2023/24 junior ranking pages "
              "not applicable (independent junior rankings began 2023/24)", flush=True)
    for index, (season, level, discipline, basename) in enumerate(jobs):
        url = f"https://results.isu.org/ws/wr{season}/{basename}"
        ent = dict(season=season, level=level, discipline=discipline,
                   status="error", rows=0, url=url,
                   cache_file=str(cache / season / basename), error="")
        blocked = False
        try:
            html, fetched_url, cache_path = download(
                sess, season, basename, cache, offline=args.offline,
                refresh=args.refresh, timeout=args.timeout)
            item = parse_page(html, season=season, level=level,
                              discipline=discipline, url=fetched_url)
            ent.update(status="ok", rows=len(item), url=fetched_url,
                       cache_file=str(cache_path))
            rows.extend(item)
            print(f"[OK] {season} {level:<6} {discipline:<13}: {len(item)} couples", flush=True)
        except Exception as exc:
            ent["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"
            print(f"[FAIL] {season} {level:<6} {discipline:<13}: {ent['error']}",
                  file=sys.stderr, flush=True)
            # Two independent mirrors both failing at the connection layer means
            # there is no reason to try thirty more pages on the same network.
            blocked = isinstance(exc, DownloadFailed) and exc.network_block and not args.offline
        inventory.append(ent)
        if blocked:
            print("[STOP] Both ISU hosts failed to connect. Remaining pages SKIPPED, "
                  "not counted as successful. Check proxy port/settings or use offline cache.",
                  file=sys.stderr, flush=True)
            for remaining_season, remaining_level, remaining_disc, remaining_base in jobs[index + 1:]:
                inventory.append(dict(
                    season=remaining_season, level=remaining_level,
                    discipline=remaining_disc, status="skipped_network",
                    rows=0,
                    url=f"https://results.isu.org/ws/wr{remaining_season}/{remaining_base}",
                    cache_file=str(cache / remaining_season / remaining_base),
                    error="Not attempted; earlier source connection failed"))
        # Preserve success/failure state, even when the network is unavailable.
        write_csv(out / "isu_season_roster.csv", rows, FIELDS)
        write_csv(out / "source_inventory.csv", inventory, META_FIELDS)
        if blocked:
            break
        if args.delay > 0 and not args.offline:
            time.sleep(args.delay)
    failures = sum(1 for x in inventory if x["status"] != "ok")
    summary = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "scope": "ISU Season's World Rankings, Ice Dance and Pair Skating, senior/junior; no BaZi",
               "season_start": args.season_start, "season_end": args.season_end,
               "levels_requested": sorted(use_levels), "source_pages_requested": len(jobs),
               "source_pages_not_applicable": len(not_applicable),
               "not_applicable_pages": [{"season": j[0], "level": j[1],
                   "discipline": j[2], "reason": "Independent junior rankings did not exist before 2023-24"}
                   for j in not_applicable],
               "source_pages_attempted": sum(x["status"] != "skipped_network" for x in inventory),
               "source_pages_skipped": sum(x["status"] == "skipped_network" for x in inventory),
               "source_pages_ok": sum(x["status"] == "ok" for x in inventory),
               "source_pages_failed": failures,
               "season_roster_rows": len(rows),
               "all_sources_complete": failures == 0,
               "data_limitations": [
                 "Rankings exclude teams without qualifying season ranking points and are not full ISU start lists",
                 "A season ranking row is not an individual competition result and must not inflate pair event counts",
                 "Rankings, nation, names and profiles require identity QA; no DOB or place-of-birth implied",
                 "In-progress seasons should not be compared directly with completed seasons",
                 "Independent junior World Standings and Season Rankings began in 2023-24; "
                 "pre-2023/24 junior entries are unavailable as standalone season rankings"],
               "source_failures": [x for x in inventory if x["status"] != "ok"]}
    (out / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["source_pages_requested", "source_pages_ok", "source_pages_failed", "season_roster_rows"]}, ensure_ascii=False))
    return 0 if failures == 0 else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--season-start", type=int, default=2018)
    p.add_argument("--season-end", type=int, default=2025)
    p.add_argument("--level", default="senior,junior", help="senior,junior or senior or junior")
    p.add_argument("--out", default="output/isu")
    p.add_argument("--cache", default="cache/isu")
    p.add_argument("--offline", action="store_true", help="Parse existing cached HTML only")
    p.add_argument("--refresh", action="store_true", help="Redownload pages even when cached")
    p.add_argument("--proxy", help="Explicit proxy URL; overrides HTTP_PROXY/HTTPS_PROXY, e.g. http://127.0.0.1:10808")
    p.add_argument("--no-env-proxy", action="store_true", help="Direct connection if --proxy omitted; with --proxy already implied")
    p.add_argument("--timeout", type=int, default=25)
    p.add_argument("--delay", type=float, default=.3)
    args = p.parse_args()
    if args.season_start < 1990 or args.season_end < args.season_start or args.season_end > 2030:
        p.error("Invalid season range")
    if not set(args.level.split(",")).issubset({"senior", "junior"}):
        p.error("--level must be senior, junior, or senior,junior")
    return run(args)

if __name__ == "__main__":
    raise SystemExit(main())
