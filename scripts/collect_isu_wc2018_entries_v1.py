#!/usr/bin/env python3
"""Fetch and audit 2018 Milan ISU World Championships pairs/dance entry & result pages.

Official event-first SOURCE observations only. Results and entries are never
merged into historic v4, and season rankings are not treated as event starts.
Uses cached raw HTML for reproducible offline replay. No BaZi or cohort freeze.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
GAPS = ROOT / "data/frame/isu_verified_entry_gaps_v1.csv"
CACHE = ROOT / "cache/isu_wc2018_official"
OUTPUT = ROOT / "output/frame/isu_wc2018_pilot_v1"
EVENT_CODE = "wc2018"
SEASON = "2017-2018"
ALLOWED = {"results.isu.org", "www.isuresults.com"}
COUNTRIES = frozenset("ARM AUS AUT AZE BEL BLR BRA CAN CHN CRO CZE DEN ESP EST FIN FRA GBR GEO GER GRE HKG HUN INA IND IRL ISL ISR ITA JPN KAZ KOR LAT LTU MEX NED NOR NZL POL PRK ROU RUS SUI SVK SWE TPE TUR UKR USA UZB".split())
GAP_FIELDS = ["season", "event_code", "discipline", "official_entry_url", "official_published_entry_pairs"]
ENTRY_FIELDS = [
    "event_id", "discipline", "entry_ordinal", "name_as_published",
    "person_a_as_published", "person_b_as_published", "nation_as_published",
    "isu_profile_id", "isu_profile_url", "entry_source_url", "entry_source_sha256",
    "entry_data_status",
]
RESULT_FIELDS = [
    "event_id", "discipline", "final_placement", "name_as_published",
    "person_a_as_published", "person_b_as_published", "nation_as_published",
    "isu_profile_id", "isu_profile_url", "result_status", "points_as_published",
    "points_interpretation", "total_points_if_final", "short_segment_points_if_fnr",
    "result_source_url", "result_source_sha256",
]
JOIN_FIELDS = ENTRY_FIELDS + [
    "result_source_url", "final_placement", "result_status", "result_name_as_published",
    "result_nation_as_published", "result_points_as_published",
    "result_points_interpretation", "result_profile_id", "entry_result_link_status",
]
PAGE_FIELDS = [
    "discipline", "page_kind", "requested_url", "cache_path", "cached",
    "raw_sha256", "rows_parsed", "expected_rows", "status", "error",
]


class UntrustedPage(ValueError):
    """Parsing or source identity problem: do not publish misleading counts."""


def read_csv(path: Path, keys):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not set(keys).issubset(reader.fieldnames or []):
            raise ValueError("Source manifest missing required columns: " + str(sorted(set(keys) - set(reader.fieldnames or []))))
        return list(reader)


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def norm_name(name):
    import unicodedata
    x = unicodedata.normalize("NFKD", clean(name).casefold())
    x = "".join(c for c in x if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", x))


def split_pair(text):
    value = clean(text)
    if value.count("/") != 1:
        raise UntrustedPage("ISU pair text did not contain exactly one name delimiter: " + repr(value))
    a, b = [clean(v) for v in value.split("/", 1)]
    if not a or not b or len(a.split()) < 2 or len(b.split()) < 2 or len(a) > 100 or len(b) > 100:
        raise UntrustedPage("Malformed ISU two-member name: " + repr(value))
    return a, b


def source_url(url: str, *, kind: str) -> bool:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED or p.username or p.password or p.port is not None or p.query or p.fragment:
        return False
    suffix = "EN" if kind == "entry" else "RS"
    return bool(re.fullmatch(rf"/results/season1718/wc2018/CAT00[34]{suffix}\.HTM", p.path, re.I))


def profile_href(raw_href, source_uri):
    uri = urljoin(source_uri, raw_href)
    p = urlsplit(uri)
    if p.scheme not in ("http", "https") or p.hostname not in ALLOWED or p.username or p.password or p.port is not None or p.query or p.fragment:
        raise UntrustedPage("Unapproved ISU biography link: " + uri)
    m = re.fullmatch(r"/bios/(isufs[0-9]+)\.htm", p.path, re.I)
    if not m:
        raise UntrustedPage("Unexpected ISU athlete profile path: " + uri)
    return m.group(1).lower(), uri


def decode_html(raw):
    # Legacy Swiss Timing pages can be Latin-1 or Windows-1252; prefer the
    # declared metadata, then a lossless UTF-8 decode, then Windows-1252.
    head = raw[:8192]
    match = re.search(rb"charset\s*=\s*['\"]?([a-zA-Z0-9_\-]+)", head, re.I)
    choices = [match.group(1).decode("ascii") if match else "", "utf-8", "cp1252", "latin-1"]
    tried = set()
    for enc in choices:
        if not enc or enc.lower() in tried:
            continue
        tried.add(enc.lower())
        try:
            return raw.decode(enc, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    raise UntrustedPage("Could not decode source HTML without loss")


def page_identity(html, discipline, kind):
    soup = BeautifulSoup(html, "html.parser")
    top = clean(soup.get_text(" ", strip=True)[:1500]).casefold()
    if discipline == "Pair Skating" and not re.search(r"\bpairs\b", top):
        raise UntrustedPage("Downloaded page does not identify the Pairs discipline")
    if discipline == "Ice Dance" and "ice dance" not in top:
        raise UntrustedPage("Downloaded page does not identify the Ice Dance discipline")
    if kind == "entry" and "entries" not in top:
        raise UntrustedPage("Downloaded page is not an ISU entry list")
    if kind == "result" and "result" not in top:
        raise UntrustedPage("Downloaded page is not an ISU final result list")
    return soup


def extract_profile_row(tr, src_url):
    links = []
    for a in tr.select("a[href]"):
        if a.find_parent("tr") is not tr:
            continue
        href = a.get("href", "")
        if re.search(r"/bios/isufs[0-9]+\.htm(?:$|[?#])", href, re.I):
            links.append(a)
    if not links:
        return None
    if len(links) != 1:
        raise UntrustedPage("Expected exactly one skater-pair profile link per table row")
    a = links[0]
    full_name = clean(a.get_text(" ", strip=True))
    person_a, person_b = split_pair(full_name)
    prof_id, prof_url = profile_href(a["href"], src_url)
    cells = tr.find_all("td", recursive=False)
    if not cells:
        raise UntrustedPage("ISU athlete row has no direct cells")
    name_cell_idx = next((i for i, cell in enumerate(cells) if a in cell.descendants), -1)
    if name_cell_idx < 0:
        raise UntrustedPage("Could not locate profile name within table row")
    before = [clean(cell.get_text(" ", strip=True)) for cell in cells[:name_cell_idx]]
    # The first numeric column is the entry number or final placement.
    nums = [int(x.rstrip(".")) for x in before if re.fullmatch(r"\d{1,3}\.?", x)]
    if len(nums) != 1:
        raise UntrustedPage("Expected one row number before athlete name: " + repr(before))
    number = nums[0]
    nation = ""
    for cell in cells[name_cell_idx + 1:]:
        t = clean(cell.get_text(" ", strip=True))
        if t in COUNTRIES:
            nation = t
            break
        for img in cell.select("img"):
            for candidate in (img.get("alt", ""), img.get("title", "")):
                if clean(candidate) in COUNTRIES:
                    nation = clean(candidate)
                    break
            if nation:
                break
            src = img.get("src", "")
            stem = src.rsplit("/", 1)[-1].split(".")[0].upper()
            if stem in COUNTRIES:
                nation = stem
                break
        if nation:
            break
    if not nation:
        raise UntrustedPage("Unrecognized or missing nation for " + full_name)
    return {
        "number": number, "name": full_name, "person_a": person_a,
        "person_b": person_b, "nation": nation, "profile_id": prof_id,
        "profile_url": prof_url,
        "cell_strings": [clean(c.get_text(" ", strip=True)) for c in cells],
        "name_cell_idx": name_cell_idx,
    }


def parse_list(html, *, discipline, kind, source_uri, raw_sha):
    if kind not in ("entry", "result") or not source_url(source_uri, kind=kind):
        raise UntrustedPage("Unapproved fixed pilot source URL")
    soup = page_identity(html, discipline, kind)
    data = []
    seen_prof = set()
    seen_names = set()
    section = "final_complete"
    for node in soup.find_all(["tr", "h2", "h3", "caption"]):
        if kind == "result" and "final not reached" in clean(node.get_text(" ", strip=True)).lower():
            if not node.select("a[href*='/bios/']"):
                section = "final_not_reached"
                continue
        if node.name != "tr":
            continue
        item = extract_profile_row(node, source_uri)
        if not item:
            continue
        if item["profile_id"] in seen_prof:
            raise UntrustedPage("Duplicated official athlete profile in source page: " + item["profile_id"])
        seen_prof.add(item["profile_id"])
        normalized = norm_name(item["name"])
        if normalized in seen_names:
            raise UntrustedPage("Duplicated published couple name in page")
        seen_names.add(normalized)
        event_id = SEASON + "|" + EVENT_CODE + "|" + discipline
        if kind == "entry":
            data.append({
                "event_id": event_id, "discipline": discipline,
                "entry_ordinal": item["number"], "name_as_published": item["name"],
                "person_a_as_published": item["person_a"],
                "person_b_as_published": item["person_b"],
                "nation_as_published": item["nation"],
                "isu_profile_id": item["profile_id"], "isu_profile_url": item["profile_url"],
                "entry_source_url": source_uri, "entry_source_sha256": raw_sha,
                "entry_data_status": "OFFICIAL_ENTRIES_NOT_INFERRED_START",
            })
        else:
            cell_values = item["cell_strings"][item["name_cell_idx"] + 1:]
            scores = [score for value in cell_values
                      for score in re.findall(r"(?<!\d)\d{1,3}[.,]\d{2}(?!\d)", value)]
            if len(scores) != 1:
                raise UntrustedPage("Expected one score cell, not zero/multiple: " + item["name"] + " " + repr(cell_values))
            score = scores[0]
            final = section == "final_complete"
            data.append({
                "event_id": event_id, "discipline": discipline,
                "final_placement": item["number"],
                "name_as_published": item["name"],
                "person_a_as_published": item["person_a"],
                "person_b_as_published": item["person_b"],
                "nation_as_published": item["nation"],
                "isu_profile_id": item["profile_id"], "isu_profile_url": item["profile_url"],
                "result_status": "FINAL_COMPLETE" if final else "FINAL_NOT_REACHED",
                "points_as_published": score,
                "points_interpretation": "TOTAL_SCORE" if final else "SHORT_SEGMENT_ONLY_NOT_TOTAL",
                "total_points_if_final": score.replace(",", ".") if final else "",
                "short_segment_points_if_fnr": score.replace(",", ".") if not final else "",
                "result_source_url": source_uri, "result_source_sha256": raw_sha,
            })
    return data


def check_expected(records, *, n, kind, disc):
    if len(records) != n:
        raise UntrustedPage(f"{disc} {kind} count mismatch: {len(records)} != official {n}")
    numbers = [int(r["entry_ordinal"] if kind == "entry" else r["final_placement"]) for r in records]
    if sorted(numbers) != list(range(1, n + 1)):
        raise UntrustedPage(f"{disc} {kind} rank / entry ordinal gap or duplication")
    if kind == "result":
        # Verified by the original 2018 ISU final result tables.
        finals, fnr = {"Ice Dance": (20, 11), "Pair Skating": (16, 12)}[disc]
        counts = Counter(r["result_status"] for r in records)
        if counts["FINAL_COMPLETE"] != finals or counts["FINAL_NOT_REACHED"] != fnr:
            raise UntrustedPage(f"{disc} result segment-status mismatch {counts}; expected {finals}/{fnr}")


def link_entries_results(entries, results):
    by_profile = {}
    for r in results:
        key = (r["discipline"], r["isu_profile_id"])
        if key in by_profile:
            raise UntrustedPage("Multiple results under one discipline/profile ID")
        by_profile[key] = r
    output = []
    used = set()
    for entry in sorted(entries, key=lambda x: (x["discipline"], int(x["entry_ordinal"]))):
        match = by_profile.get((entry["discipline"], entry["isu_profile_id"]))
        same_name = False
        if not match:
            names = [r for r in results if r["discipline"] == entry["discipline"] and
                     norm_name(r["name_as_published"]) == norm_name(entry["name_as_published"])]
            if len(names) > 1:
                raise UntrustedPage("Ambiguous same-name result without matching biography ID")
            if len(names) == 1:
                match = names[0]
                same_name = True
        rec = dict(entry)
        rec.update({
            "result_source_url": match["result_source_url"] if match else "",
            "final_placement": match["final_placement"] if match else "",
            "result_status": match["result_status"] if match else "ENTRY_ONLY_NO_RESULT_EVIDENCE",
            "result_name_as_published": match["name_as_published"] if match else "",
            "result_nation_as_published": match["nation_as_published"] if match else "",
            "result_points_as_published": match["points_as_published"] if match else "",
            "result_points_interpretation": match["points_interpretation"] if match else "",
            "result_profile_id": match["isu_profile_id"] if match else "",
            "entry_result_link_status": (
                "ENTRY_ONLY_NO_RESULT_EVIDENCE" if not match else
                "NAME_ONLY_PROFILE_MISMATCH_HOLD" if same_name else
                "PROFILE_MATCH_NATION_CONFLICT_HOLD" if match["nation_as_published"] != entry["nation_as_published"] else
                "PROFILE_MATCH_PUBLISHED_NAME_DIFF_REVIEW" if norm_name(match["name_as_published"]) != norm_name(entry["name_as_published"]) else
                "PROFILE_MATCH_BOTH_OFFICIAL_PAGES"
            ),
        })
        if match:
            used.add((match["discipline"], match["isu_profile_id"]))
        output.append(rec)
    result_only = [r for r in results if (r["discipline"], r["isu_profile_id"]) not in used]
    return output, result_only


def verify_gap_manifest(gap_rows):
    if len(gap_rows) != 2:
        raise ValueError("Expected exactly two verified 2018 Worlds disciplines")
    pairmap = {x["discipline"]: x for x in gap_rows}
    if set(pairmap) != {"Ice Dance", "Pair Skating"}:
        raise ValueError("Unexpected gap discipline")
    rows = []
    for disc in ("Ice Dance", "Pair Skating"):
        r = pairmap[disc]
        n = int(r["official_published_entry_pairs"])
        if (r["season"] != SEASON or r["event_code"] != EVENT_CODE or
                n != {"Ice Dance": 31, "Pair Skating": 28}[disc] or
                not source_url(r["official_entry_url"], kind="entry") or
                not r["official_entry_url"].upper().endswith(("CAT004EN.HTM" if disc == "Ice Dance" else "CAT003EN.HTM"))):
            raise ValueError("Wrong 2018 official entry source or expected count: " + disc)
        result_url = r["official_entry_url"][:-6] + "RS.HTM"
        if not source_url(result_url, kind="result"):
            raise ValueError("Derived official result source URL is invalid")
        rows.append((disc, n, r["official_entry_url"], result_url))
    return rows


def download_page(session, url, cache_path, *, offline=False, refresh=False, timeout=25):
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes(), True
    if offline:
        raise FileNotFoundError("Official HTML not cached: " + str(cache_path))
    response = session.get(url, timeout=(6, timeout))
    response.raise_for_status()
    raw = response.content
    if len(raw) < 500:
        raise UntrustedPage("Official page unexpectedly short")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(raw)
    return raw, False


def run(*, gaps_path=GAPS, cache_dir=CACHE, output_dir=OUTPUT,
        offline=False, refresh=False, proxy=None, no_env_proxy=False, timeout=25):
    if offline and refresh:
        raise ValueError("--offline cannot be combined with --refresh")
    session = requests.Session()
    session.headers["User-Agent"] = "DoublesResearchDataset/0.2 (public ISU event tables)"
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("--proxy must be an HTTP(S) proxy URL")
        session.trust_env = False
        session.proxies.update({"http": proxy, "https": proxy})
    elif no_env_proxy:
        session.trust_env = False
    gap_rows = read_csv(gaps_path, GAP_FIELDS)
    sources = verify_gap_manifest(gap_rows)
    inventory, all_entries, all_results, failures = [], [], [], []
    for disc, number, entry_uri, result_uri in sources:
        for kind, uri in (("entry", entry_uri), ("result", result_uri)):
            name = f"wc2018_{'dance' if disc == 'Ice Dance' else 'pairs'}_{kind}.html"
            target = Path(cache_dir) / name
            item = {"discipline": disc, "page_kind": kind, "requested_url": uri,
                    "cache_path": str(target), "cached": "", "raw_sha256": "",
                    "rows_parsed": 0, "expected_rows": number,
                    "status": "ERROR_NOT_ACCEPTED", "error": ""}
            try:
                raw, cached = download_page(session, uri, target, offline=offline, refresh=refresh, timeout=timeout)
                item["cached"] = "YES" if cached else "NO"
                item["raw_sha256"] = digest(raw)
                parsed = parse_list(decode_html(raw), discipline=disc, kind=kind,
                                    source_uri=uri, raw_sha=item["raw_sha256"])
                item["rows_parsed"] = len(parsed)
                check_expected(parsed, n=number, kind=kind, disc=disc)
                if kind == "entry":
                    all_entries.extend(parsed)
                else:
                    all_results.extend(parsed)
                item["status"] = "VALIDATED"
            except (requests.RequestException, ValueError, OSError) as exc:
                item["error"] = type(exc).__name__ + ": " + str(exc)[:300]
                failures.append(item.copy())
            inventory.append(item)
            print(f"[{item['status']}] {disc} {kind}: {item['rows_parsed']}/{number} {item['error']}", flush=True)
    joined, result_only = link_entries_results(all_entries, all_results)
    out = Path(output_dir)
    write_csv(out / "official_source_page_inventory_v1.csv", inventory, PAGE_FIELDS)
    write_csv(out / "official_event_entries_v1.csv", all_entries, ENTRY_FIELDS)
    write_csv(out / "official_event_results_v1.csv", all_results, RESULT_FIELDS)
    write_csv(out / "official_entry_result_link_review_v1.csv", joined, JOIN_FIELDS)
    write_csv(out / "official_result_without_entry_review_v1.csv", result_only, RESULT_FIELDS)
    status_counts = Counter(x["entry_result_link_status"] for x in joined)
    section_counts = Counter((x["discipline"], x["result_status"]) for x in all_results)
    complete = not failures and len(all_entries) == 59 and len(all_results) == 59
    manifest = {
        "stage": "official_isu_wc2018_entry_result_source_pilot_not_frozen",
        "source_status": "SOURCE_PAGES_VALIDATED" if complete else "SOURCE_PAGES_INCOMPLETE_DO_NOT_USE_AS_COHORT",
        "season": SEASON, "event_code": EVENT_CODE,
        "pages_attempted": len(inventory), "pages_validated": len(inventory) - len(failures),
        "page_failures": len(failures),
        "official_entry_records": len(all_entries),
        "official_result_records": len(all_results),
        "joined_entry_result_records": len(joined),
        "results_without_entry": len(result_only),
        "entry_result_link_status_counts": dict(sorted(status_counts.items())),
        "result_category_counts": {f"{d}|{state}": n for (d, state), n in sorted(section_counts.items())},
        "page_inventory_sha256": digest((out / "official_source_page_inventory_v1.csv").read_bytes()),
        "gap_source_sha256": digest(Path(gaps_path).read_bytes()),
        "limitations": [
            "Official entries are a published entry list, not automatically actual starting participants",
            "Final not reached results contain short-segment points, not total championship scores",
            "Name/profile disagreements and entrants without results remain visible for human source review",
            "No original historic pairs/events, modern rankings, DOB candidate masters or identity graph are mutated",
            "No BaZi, significance, career-performance cohort selection, or independent-person inference",
        ],
    }
    (out / "official_wc2018_entry_result_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gaps", type=Path, default=GAPS)
    p.add_argument("--cache", type=Path, default=CACHE)
    p.add_argument("--out", type=Path, default=OUTPUT)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--timeout", type=int, default=25)
    a = p.parse_args()
    summary = run(gaps_path=a.gaps, cache_dir=a.cache, output_dir=a.out,
                  offline=a.offline, refresh=a.refresh, proxy=a.proxy,
                  no_env_proxy=a.no_env_proxy, timeout=a.timeout)
    raise SystemExit(0 if summary["source_status"] == "SOURCE_PAGES_VALIDATED" else 2)


if __name__ == "__main__":
    main()
