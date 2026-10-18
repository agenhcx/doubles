#!/usr/bin/env python3
"""Gather Wikidata P569 birthdate LEADS for historical ISU skaters.

All output is unverified evidence for human corroboration. No Wikidata date
is used to update original athletes, officially verified DOBs, or cohorts.

Run only on your computer; caches are reusable and excluded from Git:
python .\scripts\collect_historic_wikidata_leads.py --limit 20 --proxy http://127.0.0.1:10808
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from audit_historic_dob_gap import safe_name
from audit_isu_identities import read_csv, write_csv
from collect_isu_seasons import configure_session

API = "https://www.wikidata.org/w/api.php"
FIELDS = [
    "historic_person_id", "historic_name", "historic_partner_names",
    "historic_match_status", "query_name", "wikidata_qid",
    "wikidata_label", "wikidata_description", "wikidata_url",
    "wikidata_birthdates_day_precision", "date_conflict_in_item",
    "figure_skater_occupation_or_sport", "source_status",
    "evidence_status"
]


def best_query(row):
    candidates = [row.get("historic_name", "")]
    candidates += row.get("historic_name_variants", "").split(" | ")
    names = [s.strip() for s in candidates if safe_name(s)]
    if not names:
        return ""
    # Prefer the original historical display name; aliases are fallback only.
    return names[0]


def cache_search_path(cache, query):
    key = hashlib.sha1(query.casefold().encode("utf-8")).hexdigest()[:20]
    return Path(cache) / "search" / (key + ".json")


def entity_cache_path(cache, qid):
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Invalid Wikidata item ID")
    return Path(cache) / "entities" / (qid + ".json")


def get_json(session, params, path, *, offline, refresh, timeout, delay):
    path = Path(path)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise FileNotFoundError(str(path))
    response = session.get(API, params=params, timeout=(5, timeout))
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError("Wikidata API: " + str(data["error"])[:250])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if delay > 0:
        time.sleep(delay)
    return data


def birthdates_with_day_precision(entity):
    dates = set()
    for claim in entity.get("claims", {}).get("P569", []):
        if claim.get("rank") == "deprecated":
            continue
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if not isinstance(value, dict) or value.get("precision", 0) < 11:
            continue
        m = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})T", value.get("time", ""))
        if not m:
            continue
        year, month, day = map(int, m.groups())
        try:
            from datetime import date
            date(year, month, day)
        except ValueError:
            continue
        if 1850 <= year <= 2100:
            dates.add(f"{year:04d}-{month:02d}-{day:02d}")
    return sorted(dates)


def is_skater_entity(entity):
    claims = entity.get("claims", {})
    wanted = {("P106", "Q13219587"), ("P641", "Q38108")}
    for prop, qid in wanted:
        for claim in claims.get(prop, []):
            if claim.get("rank") == "deprecated":
                continue
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(value, dict) and value.get("id") == qid:
                return True
    return False


def entity_lead(person, query, search_result, item):
    qid = search_result["id"]
    dates = birthdates_with_day_precision(item)
    return {
        "historic_person_id": person["historic_person_id"],
        "historic_name": person["historic_name"],
        "historic_partner_names": person.get("historic_partner_names", ""),
        "historic_match_status": person.get("match_status", ""),
        "query_name": query,
        "wikidata_qid": qid,
        "wikidata_label": search_result.get("label", ""),
        "wikidata_description": search_result.get("description", ""),
        "wikidata_url": "https://www.wikidata.org/wiki/" + qid,
        "wikidata_birthdates_day_precision": "; ".join(dates),
        "date_conflict_in_item": "YES" if len(dates) > 1 else "NO",
        "figure_skater_occupation_or_sport": "YES" if is_skater_entity(item) else "UNKNOWN",
        "source_status": "candidate_item_details_loaded",
        "evidence_status": "wikidata_unverified_needs_official_corroboration",
    }


def run(
    queue_path="output/historic_dob/historic_dob_followup_queue.csv",
    cache_dir="cache/historic_wikidata", out_dir="output/historic_dob/wikidata",
    *, limit=20, offline=False, refresh=False, proxy=None, no_env_proxy=False,
    timeout=20, delay=0.75
):
    queue = read_csv(queue_path)
    if not queue:
        raise ValueError("Empty historical gap queue")
    # Actual DOB gaps first; exact-name but non-overlapping partnerships last.
    pri = {
        "unmatched_full_name": 0, "partner_alias_suggestion": 1,
        "ambiguous_full_name": 2, "exact_name_only": 3,
        "abbreviated_or_incomplete_name": 4,
    }
    queue.sort(key=lambda r: (
        pri.get(r.get("match_status", ""), 5),
        -(int(r.get("identified_competitions", "0") or "0")
          if str(r.get("identified_competitions", "")).isdigit() else 0),
        r["historic_person_id"]
    ))
    tasks = [(r, best_query(r)) for r in queue]
    tasks = [(r, q) for r, q in tasks if q]
    if limit:
        tasks = tasks[:limit]
    session = configure_session(proxy, no_env_proxy)
    session.headers["User-Agent"] = (
        "PublicFigureDoublesStudy/0.1 (https://github.com/agenhcx/doubles; "
        "research-only historic athlete birthdate candidate index)"
    )
    # No guessed dates: search and entity records are stored in a local cache.
    searches, errors = [], []
    for person, query in tasks:
        try:
            params = {
                "action": "wbsearchentities", "format": "json",
                "search": query, "language": "en", "uselang": "en",
                "type": "item", "limit": 5,
            }
            data = get_json(session, params, cache_search_path(cache_dir, query),
                            offline=offline, refresh=refresh,
                            timeout=timeout, delay=delay)
            hits = [h for h in data.get("search", [])
                    if re.fullmatch(r"Q[1-9]\d*", h.get("id", ""))]
            searches.append((person, query, hits))
        except (requests.RequestException, OSError, ValueError) as e:
            errors.append({
                "historic_person_id": person["historic_person_id"],
                "query_name": query,
                "stage": "search",
                "error": type(e).__name__ + ": " + str(e)[:200],
            })
            # Offline cache misses are expected; network errors must not
            # trigger many repetitive requests to a blocked endpoint.
            if not offline:
                break

    qids = sorted({h["id"] for _, _, hits in searches for h in hits},
                  key=lambda x: int(x[1:]))
    loaded_entities = {}
    # Batch Wikibase requests (max 25 IDs here) and cache each item separately.
    missing = [qid for qid in qids
               if refresh or not entity_cache_path(cache_dir, qid).exists()]
    if missing and not offline and not errors:
        for i in range(0, len(missing), 25):
            chunk = missing[i:i + 25]
            try:
                data = get_json(
                    session,
                    {"action": "wbgetentities", "format": "json",
                     "ids": "|".join(chunk), "props": "claims|labels|descriptions",
                     "languages": "en"},
                    Path(cache_dir) / "batches" /
                    (hashlib.sha1("|".join(chunk).encode()).hexdigest()[:20] + ".json"),
                    offline=False, refresh=refresh, timeout=timeout, delay=delay,
                )
                for qid in chunk:
                    item = data.get("entities", {}).get(qid)
                    if not isinstance(item, dict) or "missing" in item:
                        continue
                    p = entity_cache_path(cache_dir, qid)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            except (requests.RequestException, OSError, ValueError) as e:
                errors.append({
                    "historic_person_id": "",
                    "query_name": "|".join(chunk),
                    "stage": "entity_batch",
                    "error": type(e).__name__ + ": " + str(e)[:200],
                })
                break

    for qid in qids:
        path = entity_cache_path(cache_dir, qid)
        if path.exists():
            try:
                loaded_entities[qid] = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as e:
                errors.append({
                    "historic_person_id": "", "query_name": qid,
                    "stage": "read_cache",
                    "error": type(e).__name__ + ": " + str(e)[:200],
                })

    leads = []
    no_search_hits = 0
    for person, query, hits in searches:
        if not hits:
            no_search_hits += 1
        for result in hits:
            qid = result["id"]
            if qid in loaded_entities:
                leads.append(entity_lead(person, query, result, loaded_entities[qid]))
            else:
                leads.append({
                    "historic_person_id": person["historic_person_id"],
                    "historic_name": person["historic_name"],
                    "historic_partner_names": person.get("historic_partner_names", ""),
                    "historic_match_status": person.get("match_status", ""),
                    "query_name": query, "wikidata_qid": qid,
                    "wikidata_label": result.get("label", ""),
                    "wikidata_description": result.get("description", ""),
                    "wikidata_url": "https://www.wikidata.org/wiki/" + qid,
                    "wikidata_birthdates_day_precision": "",
                    "date_conflict_in_item": "",
                    "figure_skater_occupation_or_sport": "UNKNOWN",
                    "source_status": "entity_details_missing",
                    "evidence_status": "wikidata_unverified_needs_official_corroboration",
                })
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_wikidata_dob_leads.csv", FIELDS, leads)
    if errors:
        write_csv(out / "wikidata_fetch_errors.csv",
                  ["historic_person_id", "query_name", "stage", "error"], errors)
    else:
        write_csv(out / "wikidata_fetch_errors.csv",
                  ["historic_person_id", "query_name", "stage", "error"], [])
    manifest = {
        "stage": "secondary_source_leads_only_no_accepted_dobs",
        "queue_people": len(queue),
        "searches_selected": len(tasks),
        "searches_ok": len(searches),
        "search_errors": len(errors),
        "no_wikidata_results": no_search_hits,
        "candidate_item_rows": len(leads),
        "items_with_day_precision_dob": sum(bool(r["wikidata_birthdates_day_precision"])
                                             for r in leads),
        "items_with_figure_skater_signal": sum(
            r["figure_skater_occupation_or_sport"] == "YES" for r in leads
        ),
        "offline": offline, "refresh": refresh,
        "limitations": [
            "Wikidata candidates are secondary leads only, never a source-verified DOB",
            "Human identity adjudication and a primary official DOB source are still required",
            "A same-name entity can describe a different individual",
            "P569 precision under day-level is excluded; do not infer Jan 1",
            "A Wikidata entity may have contradictory dates; all are reported",
            "Batch failures or cache misses are explicit and never interpreted as no athlete",
        ],
    }
    (out / "historic_wikidata_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", default="output/historic_dob/historic_dob_followup_queue.csv")
    p.add_argument("--cache", default="cache/historic_wikidata")
    p.add_argument("--out", default="output/historic_dob/wikidata")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy", action="store_true")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--delay", type=float, default=0.75)
    opts = p.parse_args()
    if opts.limit < 0:
        p.error("--limit must be nonnegative")
    run(opts.queue, opts.cache, opts.out, limit=opts.limit, offline=opts.offline,
        refresh=opts.refresh, proxy=opts.proxy, no_env_proxy=opts.no_env_proxy,
        timeout=opts.timeout, delay=opts.delay)


if __name__ == "__main__":
    main()
