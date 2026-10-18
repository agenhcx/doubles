#!/usr/bin/env python3
"""Offline audit: recover historic ISU DOB leads missed by newer INDEX names.

Problem: a current ISU directory may call a skater 'Kristin FRASER-LUKANIN'
but her corresponding *historical* official biography still prints
'Kristin FRASER', immediately after the date-of-birth label.

This does not establish all historical-name identity links. Recovered dates
are kept in a separate reviewer-only evidence field, never written into
the canonical DOB or the original, index-name-based 'published_dob' column.
All profile caches and inputs are read-only. No network or BaZi.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from audit_isu_identities import digest, read_csv, valid_date, write_csv
from collect_historic_isu_biographies import fold, parse_member

OFFICIAL_HOSTS = {"www.isuresults.com", "results.isu.org"}
OUT_FIELDS = [
    "historic_pair_id", "discipline", "historic_person_id",
    "side_on_profile", "historical_name", "published_name",
    "original_published_dob", "original_parse_status", "profile_id",
    "source_url", "prior_audited_dob", "original_identity_status",
    "historical_name_dob_candidate", "historical_name_observed_in_bio",
    "historical_name_parse_status", "historical_name_parse_method",
    "date_comparison_to_prior", "candidate_review_status",
]
REVIEW_FIELDS = OUT_FIELDS
VALID_SIDES = {"1", "2"}


def validate_leads(rows):
    if not rows:
        raise ValueError("No historic alias DOB leads")
    required = {
        "historic_pair_id", "discipline", "historic_person_id",
        "side_on_profile", "historical_name", "published_name",
        "published_dob", "profile_id", "source_url", "parse_status",
        "prior_audited_dob", "historical_identity_link_status",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError("Alias DOB leads missing fields: " + repr(sorted(missing)))

    keys = set()
    grouped = defaultdict(dict)
    for row in rows:
        profile = row["profile_id"]
        side = row["side_on_profile"]
        pair_id = row["historic_pair_id"]
        if not pair_id or not profile.startswith("isufs") or not profile[5:].isdigit():
            raise ValueError("Unrecognized ISU profile or blank pair")
        if side not in VALID_SIDES:
            raise ValueError("Unexpected profile member side")
        key = (pair_id, profile, side)
        if key in keys:
            raise ValueError("Repeated candidate pair/profile/person-side")
        keys.add(key)
        url = urlsplit(row["source_url"])
        # Legacy ISU index pages supplied http:// links, even though
        # the domain/profile path are official. This is an OFFLINE source
        # audit: accepting their recorded URI does not fetch over HTTP.
        # Retain the exact input URL as provenance, do not silently rewrite.
        # Reject all other domains, URL schemes, userinfo, custom ports,
        # unrelated paths, and query/fragment redirections.
        if (url.scheme not in {"http", "https"}
                or url.hostname not in OFFICIAL_HOSTS
                or url.username is not None or url.password is not None
                or url.port is not None
                or url.path.lower() != f"/bios/{profile.lower()}.htm"
                or url.query or url.fragment):
            raise ValueError("Unapproved ISU source link")
        if row["published_dob"] and not valid_date(row["published_dob"]):
            raise ValueError("Invalid original official DOB")
        if row["prior_audited_dob"] and not valid_date(row["prior_audited_dob"]):
            raise ValueError("Invalid prior identity DOB")
        if row["historical_identity_link_status"] != "not_verified_directory_candidate_only":
            raise ValueError("Do not use this recovery tool with approved or mutated aliases")
        grouped[(pair_id, profile)][side] = row
    for pair_profile, sides in grouped.items():
        if set(sides) != VALID_SIDES:
            raise ValueError("Incomplete source pair-side rows: " + repr(pair_profile))
        if sides["1"]["historic_person_id"] == sides["2"]["historic_person_id"]:
            raise ValueError("Both source members have one historic person ID")
        if (sides["1"]["source_url"] != sides["2"]["source_url"]
                or sides["1"]["discipline"] != sides["2"]["discipline"]):
            raise ValueError("Inconsistent official source URL or discipline")
    return grouped



def eligible_historic_full_name(name):
    """Only attempt fallback with an actual full name, not a bare surname or initials.

    Source-name-only rows (such as WINDSOR or MARINARO) are legitimate
    historical observations, but cannot prove an individual's identity.
    A full-name check applies ONLY to the fallback; source DOBs parsed
    from the official published names are preserved as-is.
    """
    tokens = re.findall(r"[a-z0-9]+", fold(name).casefold())
    return len(tokens) >= 2 and all(len(part) >= 2 for part in tokens)


def full_name_ends_at_profile_field(html, observation):
    """Reject a short historic name that is a PREFIX of a longer source name.

    Example: 'Alexa SCIMECA' is a prefix of the official profile name
    'Alexa SCIMECA KNIERIM', so the DOB is NOT source-bound to that
    shorter historical name without a separate identity review.

    This guard is only applied to the new fallback, not the original,
    previously audited primary DOB records.
    """
    if not observation or not observation["date_of_birth"]:
        return False
    method = observation["parse_method"]
    if "name_date_label_legacy" in method:
        # Reversed layout requires the complete name immediately before
        # the date and date-of-birth label, already enforced by parser.
        return True
    if "label_date_name" not in method:
        return False
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    flat = fold(soup.get_text(" ", strip=True))[:3500]
    shown_name = fold(observation["observed_name"])
    year, month, day = map(int, observation["date_of_birth"].split("-"))
    normalized_date = f"{year:04d}-{month:02d}-{day:02d}"
    expr = re.compile(
        r"\bDate\s+of\s+birth\s*:\s*"
        r"(?P<date>[0-3]?\d\.[01]?\d\.(?:18|19|20)\d{2})\s+"
        + re.escape(shown_name) + r"(?!\w)",
        re.I,
    )
    # The immediately following token should be the team code, a known
    # field heading, or the next person's 'Date of birth' heading.
    # A longer surname (like KNIERIM) or more given-name material
    # is NOT a complete match.
    end_marker = re.compile(
        r"^(?:[A-Z]{3}\b|Place\s+of\s+birth\s*:|Date\s+of\s+birth\s*:"
        r"|Height\s*:|Home\s+town\s*:|Former\s+Partners\s*:)",
        re.I,
    )
    import datetime as dt
    for m in expr.finditer(flat):
        try:
            parsed = dt.datetime.strptime(m.group("date"), "%d.%m.%Y").date()
        except ValueError:
            continue
        if parsed.isoformat() != normalized_date:
            continue
        tail = flat[m.end():].lstrip()
        if not tail or end_marker.match(tail):
            return True
    return False


def audit(
    leads_path="output/historic_dob/alias_biographies/historic_alias_dob_leads.csv",
    cache_dir="cache/isu_bios",
    out_dir="output/historic_dob/alias_fallback",
):
    leads_path = Path(leads_path)
    cache = Path(cache_dir)
    data = read_csv(leads_path)
    pairs = validate_leads(data)
    source_profiles = sorted({p for _, p in pairs})
    documents = {}
    unavailable = {}
    for profile in source_profiles:
        filepath = cache / (profile.lower() + ".html")
        if not filepath.is_file():
            unavailable[profile] = "cached_html_missing"
            continue
        try:
            documents[profile] = filepath.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as e:
            unavailable[profile] = type(e).__name__

    output_rows = []
    # Cache flattened biography headers by profile, not by historic
    # couple. One official profile may have multiple candidate links.
    flattened_headers = {}
    for (pair_id, profile), sides in sorted(pairs.items()):
        for side in ("1", "2"):
            original = sides[side]
            prior, original_dob = (original["prior_audited_dob"],
                                   original["published_dob"])
            recovered = ""
            source_name = ""
            parse_status = "not_needed"
            parse_method = ""
            if not original_dob:
                if profile not in documents:
                    parse_status = "cached_html_missing"
                elif not eligible_historic_full_name(original["historical_name"]):
                    # A one-word historical surname or name with initials
                    # cannot prove DOB ownership. Do not crash or match it.
                    parse_status = "historic_name_incomplete_review_only"
                else:
                    if profile not in flattened_headers:
                        soup = BeautifulSoup(documents[profile], "html.parser")
                        for tag in soup(["script", "style"]):
                            tag.decompose()
                        flattened_headers[profile] = fold(
                            soup.get_text(" ", strip=True)
                        )[:3500]
                    observed = parse_member(
                        flattened_headers[profile], original["historical_name"]
                    )
                    recovered = observed["date_of_birth"]
                    source_name = observed["observed_name"] if recovered else ""
                    parse_status = observed["parse_status"]
                    parse_method = observed["parse_method"]
                    if recovered and not full_name_ends_at_profile_field(
                        documents[profile], observed
                    ):
                        recovered = ""
                        source_name = ""
                        parse_status = "source_name_prefix_or_header_boundary_ambiguous"
                        parse_method = ""

            if original_dob:
                review_state = "original_official_dob_unaltered"
                comparison = (
                    "agrees_with_prior" if prior and original_dob == prior
                    else "conflicts_with_prior" if prior else "prior_unknown"
                )
            elif recovered:
                comparison = (
                    "agrees_with_prior" if prior and recovered == prior
                    else "conflicts_with_prior" if prior else "prior_unknown"
                )
                review_state = (
                    "fallback_conflicts_with_prior_hold"
                    if comparison == "conflicts_with_prior"
                    else "historic_name_labelled_dob_needs_identity_review"
                )
            else:
                comparison = "no_recovered_date"
                review_state = "not_recovered_needs_official_source"
            output_rows.append({
                "historic_pair_id": pair_id, "discipline": original["discipline"],
                "historic_person_id": original["historic_person_id"],
                "side_on_profile": side,
                "historical_name": original["historical_name"],
                "published_name": original["published_name"],
                "original_published_dob": original_dob,
                "original_parse_status": original["parse_status"],
                "profile_id": profile, "source_url": original["source_url"],
                "prior_audited_dob": prior,
                "original_identity_status": original["historical_identity_link_status"],
                "historical_name_dob_candidate": recovered,
                "historical_name_observed_in_bio": source_name,
                "historical_name_parse_status": parse_status,
                "historical_name_parse_method": parse_method,
                "date_comparison_to_prior": comparison,
                "candidate_review_status": review_state,
            })

    # Each unique official profile/side counts once, even if multiple
    # historical IDs happen to point to the same profile/side.
    by_slot = defaultdict(lambda: {"direct": set(), "fallback": set()})
    for row in output_rows:
        k = (row["profile_id"], row["side_on_profile"])
        for field, group in [
            ("original_published_dob", "direct"),
            ("historical_name_dob_candidate", "fallback"),
        ]:
            if row[field]:
                by_slot[k][group].add(row[field])
    conflicting_slots = sorted(
        f"{k[0]}:{k[1]}" for k, v in by_slot.items()
        if len(v["direct"] | v["fallback"]) > 1
    )
    if conflicting_slots:
        # Do not reject the traceable output; surface contradictory page
        # bindings explicitly and block using it as a certified DOB table.
        for row in output_rows:
            if f'{row["profile_id"]}:{row["side_on_profile"]}' in conflicting_slots:
                row["candidate_review_status"] = "conflicting_same_source_side_hold"

    before = sum(bool(v["direct"]) for v in by_slot.values())
    recovered_slots = sum(not v["direct"] and len(v["fallback"]) == 1
                          for v in by_slot.values())
    review = [r for r in output_rows if
              r["candidate_review_status"] not in {"original_official_dob_unaltered"}]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "historic_alias_source_name_fallback_leads.csv",
              OUT_FIELDS, output_rows)
    write_csv(out / "historic_alias_source_name_fallback_review.csv",
              REVIEW_FIELDS, review)
    report = {
        "stage": "official_biography_original_name_fallback_evidence_only",
        "source_lead_rows": len(data),
        "historical_pairs": len(pairs),
        "unique_official_profiles": len(source_profiles),
        "profiles_without_cached_html": len(unavailable),
        "missing_cache_profile_ids": sorted(unavailable),
        "original_rows_without_published_dob": sum(not r["published_dob"] for r in data),
        "original_official_profile_slots_with_dob": before,
        "historical_name_fallback_rows_with_dob": sum(bool(r["historical_name_dob_candidate"])
                                                      for r in output_rows),
        "new_unique_official_slots_recovered": recovered_slots,
        "unique_official_profile_slots_with_a_labelled_dob": (
            before + recovered_slots
        ),
        "remaining_unique_profile_slots_without_labelled_dob": (
            2 * len(source_profiles) - before - recovered_slots
        ),
        "historical_name_fallback_rows_still_missing": sum(
            not r["original_published_dob"] and not r["historical_name_dob_candidate"]
            for r in output_rows
        ),
        "historical_person_ids_appearing_in_leads": len({
            row["historic_person_id"] for row in data
        }),
        "source_slot_date_disagreements": conflicting_slots,
        "review_rows": len(review),
        "review_status_counts": dict(sorted(Counter(
            r["candidate_review_status"] for r in review
        ).items())),
        "inputs_sha256": {
            str(leads_path): digest(leads_path),
        },
        "restrictions": [
            "All new dates are source-labelled candidates, NOT accepted historic person DOBs",
            "The pairing/identity across index names and historic names remains unverified",
            "Every original published DOB and all master records remain untouched",
            "Incomplete historical names and initials are not parsed as full-name evidence",
            "No missing/ambiguous date or identity is guessed",
            "Profile/person-side duplicates are excluded from unique slot counts",
            "No BaZi, no partner null model and no statistical selection",
        ],
    }
    (out / "historic_alias_source_name_fallback_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--leads", default="output/historic_dob/alias_biographies/historic_alias_dob_leads.csv")
    p.add_argument("--cache", default="cache/isu_bios")
    p.add_argument("--out", default="output/historic_dob/alias_fallback")
    opts = p.parse_args()
    audit(opts.leads, opts.cache, opts.out)


if __name__ == "__main__":
    main()
