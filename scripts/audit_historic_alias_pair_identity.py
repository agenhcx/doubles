#!/usr/bin/env python3
"""Non-destructive identity QA for the 76 non-exact historic ISU pair links.

Inputs: 69 ranked directory alias candidates plus 7 manually reviewed
historical pairs. Distinguish names actually attested on older official
biography headers from unverified directory similarity/partner-only leads.
No BaZi, DOB imputation, or edits to historic/master records.

python .\scripts\audit_historic_alias_pair_identity.py
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, norm, read_csv, valid_date, write_csv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCEPTIONS = ROOT / "data/adjudications/isu_historic_alias_exceptions_v1.csv"
DEFAULT_MANUAL = ROOT / "data/adjudications/isu_historic_manual_pair_dobs_v1.csv"
OFFICIAL_BIO_HOSTS = {"results.isu.org", "www.isuresults.com"}
OFFICIAL_WEB_HOSTS = OFFICIAL_BIO_HOSTS | {"isu-skating.com", "www.isu-skating.com"}
PAIR_FIELDS = [
    "historic_pair_id", "discipline", "profile_id",
    "historic_person_a_id", "historic_person_b_id",
    "historic_person_a_name", "historic_person_b_name",
    "published_name_a", "published_name_b",
    "person_a_dob_evidence", "person_b_dob_evidence",
    "person_a_link_basis", "person_b_link_basis", "pair_identity_status",
    "official_profile_url", "review_reason",
]
PEOPLE_FIELDS = [
    "historic_person_id", "historic_pair_id", "discipline", "profile_id",
    "profile_side", "historical_name", "official_name", "date_of_birth_candidate",
    "identity_evidence_status", "dob_evidence_type", "source_url",
    "reviewed_exception_source_url",
]
COLLISION_FIELDS = [
    "profile_id", "side_on_profile", "historic_person_ids",
    "historic_names", "historic_pair_ids", "official_index_names",
    "candidate_dates", "status",
]


def require(rows, fields, label):
    if not rows:
        raise ValueError(label + " has no source records")
    missing = set(fields) - set(rows[0])
    if missing:
        raise ValueError(label + " lacks columns: " + repr(sorted(missing)))


def official_bio_url(url, profile):
    p = urlsplit(url)
    return (p.scheme in {"https", "http"}
            and p.hostname in OFFICIAL_BIO_HOSTS
            and p.username is None and p.password is None
            and p.port is None and not p.query and not p.fragment
            and p.path.lower() == f"/bios/{profile.lower()}.htm")


def reviewed_exceptions(path):
    rows = read_csv(path)
    require(rows, (
        "historic_pair_id", "historic_person_id", "side_on_profile",
        "discipline", "historical_name", "index_name", "official_bio_name",
        "date_of_birth", "source_profile_id", "source_bio_url",
        "independent_official_url", "other_partner_historical_name",
        "evidence_status", "adjudication_reason"
    ), "Reviewed exceptions")
    result = {}
    for r in rows:
        key = (r["historic_pair_id"], r["source_profile_id"].lower(),
               r["side_on_profile"])
        if key in result or key[2] not in {"1", "2"}:
            raise ValueError("Duplicate or invalid reviewed profile/side exception")
        if r["evidence_status"] != "source_corroborated":
            raise ValueError("Exception lacks independent official source corroboration")
        if not valid_date(r["date_of_birth"]):
            raise ValueError("Reviewed exception has invalid DOB")
        if not official_bio_url(r["source_bio_url"], key[1]):
            raise ValueError("Reviewed exception not linked to expected ISU biography")
        independent = urlsplit(r["independent_official_url"])
        if (independent.scheme != "https" or independent.hostname not in OFFICIAL_WEB_HOSTS
                or independent.username is not None or independent.password is not None
                or independent.port is not None):
            raise ValueError("Exception corroboration source is not an official ISU website")
        if not r["adjudication_reason"].strip():
            raise ValueError("Exception evidence rationale is missing")
        result[key] = r
    return result


def historic_pairs(path):
    index = {}
    rows = read_csv(path)
    require(rows, (
        "pair_id", "discipline", "person_a_id", "person_b_id",
        "person_a_name", "person_b_name"
    ), "Historical roster")
    for r in rows:
        if not r["pair_id"] or r["pair_id"] in index:
            raise ValueError("Duplicated historical pair identifier")
        index[r["pair_id"]] = r
    return index


def read_and_validate_alias_rows(path, historic):
    data = read_csv(path)
    require(data, (
        "historic_pair_id", "discipline", "historic_person_id", "side_on_profile",
        "historical_name", "published_name", "profile_id", "source_url",
        "original_published_dob", "historical_name_dob_candidate",
        "historical_name_parse_status", "historical_name_observed_in_bio",
        "candidate_review_status", "original_identity_status"
    ), "Source-name fallback")
    pairs = defaultdict(dict)
    slots = defaultdict(list)
    for r in data:
        pid, side, pair_id = r["profile_id"].lower(), r["side_on_profile"], r["historic_pair_id"]
        if not pair_id or pair_id not in historic:
            raise ValueError("Source candidate references unknown historic pair ID")
        if side not in {"1", "2"} or not pid.startswith("isufs") or not pid[5:].isdigit():
            raise ValueError("Invalid ISU profile/side")
        if not official_bio_url(r["source_url"], pid):
            raise ValueError("Source candidate URL does not match official ISU profile")
        old = historic[pair_id]
        expected_id = old["person_a_id"] if side == "1" else old["person_b_id"]
        expected_name = old["person_a_name"] if side == "1" else old["person_b_name"]
        if (r["historic_person_id"] != expected_id
                or r["historical_name"] != expected_name
                or r["discipline"] != old["discipline"]):
            raise ValueError("Source candidate mismatches historical pair identity")
        if side in pairs[(pair_id, pid)]:
            raise ValueError("Duplicate historic pair official source-side observation")
        pairs[(pair_id, pid)][side] = r
        for field in ("original_published_dob", "historical_name_dob_candidate"):
            if r[field] and not valid_date(r[field]):
                raise ValueError("Source observation has invalid complete DOB")
        slots[(pid, side)].append(r)
    pair_lookup = defaultdict(list)
    for (pair_id, pid), members in pairs.items():
        if set(members) != {"1", "2"}:
            raise ValueError("One historical pair lacks both profile-side records")
        if members["1"]["source_url"] != members["2"]["source_url"]:
            raise ValueError("Source pair has inconsistent official biography URL")
        pair_lookup[pair_id].append((pid, members))
    if any(len(profiles) != 1 for profiles in pair_lookup.values()):
        raise ValueError("One historic alias candidate maps to multiple top profiles")
    return pair_lookup, slots


def side_evidence(row, exception=None):
    """Return evidence label and DOB; never trust partner-only index match."""
    hist, published = row["historical_name"], row["published_name"]
    date = row["original_published_dob"]
    fallback = row["historical_name_dob_candidate"]
    if date and norm(hist) == norm(published):
        return "index_name_exact_official_dob", date, row["source_url"], ""
    if (fallback and row["historical_name_parse_status"] ==
            "dob_explicitly_bound_to_expected_name" and
            norm(row["historical_name_observed_in_bio"]) == norm(hist) and
            row["candidate_review_status"] ==
            "historic_name_labelled_dob_needs_identity_review"):
        return "historic_full_name_on_official_bio", fallback, row["source_url"], ""
    if exception:
        return ("independently_reviewed_official_alias",
                exception["date_of_birth"], exception["source_bio_url"],
                exception["independent_official_url"])
    return "identity_link_unresolved", "", row["source_url"], ""


def build(
    fallback_path="output/historic_dob/alias_fallback/historic_alias_source_name_fallback_leads.csv",
    historic_path="data/historic/v4/couples_v4.csv",
    manual_path=DEFAULT_MANUAL,
    exception_path=DEFAULT_EXCEPTIONS,
    out_dir="output/historic_dob/alias_pair_identity",
):
    inputs = list(map(Path, (fallback_path, historic_path, manual_path, exception_path)))
    historic = historic_pairs(inputs[1])
    pair_links, slots = read_and_validate_alias_rows(inputs[0], historic)
    exceptions = reviewed_exceptions(inputs[3])
    manually_reviewed = read_csv(inputs[2])
    require(manually_reviewed, (
        "historic_pair_id", "historic_person_a_id", "historic_person_b_id",
        "historic_person_a_name", "historic_person_b_name", "discipline",
        "official_person_a_name", "official_person_b_name",
        "official_person_a_dob", "official_person_b_dob",
        "official_person_a_source_url", "official_person_b_source_url",
        "provenance_status"
    ), "Seven reviewed historic pair sources")
    manual_pairs = {}
    for m in manually_reviewed:
        pair_id = m["historic_pair_id"]
        if pair_id in manual_pairs or pair_id not in historic:
            raise ValueError("Duplicate or non-historic manually reviewed pair")
        old = historic[pair_id]
        for side in ("a", "b"):
            if (m[f"historic_person_{side}_id"] != old[f"person_{side}_id"]
                    or m[f"historic_person_{side}_name"] != old[f"person_{side}_name"]):
                raise ValueError("Manual official pair contradicts historical IDs")
            if not valid_date(m[f"official_person_{side}_dob"]):
                raise ValueError("Manual official pair DOB invalid")
            u = urlsplit(m[f"official_person_{side}_source_url"])
            if u.scheme != "https" or u.hostname not in OFFICIAL_WEB_HOSTS:
                raise ValueError("Manually reviewed pair source not official")
        if m["discipline"] != old["discipline"] or not m["provenance_status"].startswith("reviewed_"):
            raise ValueError("Unsupported manual pair identity review status")
        manual_pairs[pair_id] = m

    # Manually reviewed rows supersede directory candidate hypotheses.
    ignored_manual_candidates = set(pair_links) & set(manual_pairs)
    decisions, persons, used_exceptions = [], [], set()
    for pair_id, entries in sorted(pair_links.items()):
        if pair_id in manual_pairs:
            continue
        profile, members = entries[0]
        details = []
        for side, opposite in (("1", "2"), ("2", "1")):
            row = members[side]
            ekey = (pair_id, profile, side)
            exc = exceptions.get(ekey)
            if exc:
                other = members[opposite]
                if (exc["historic_person_id"] != row["historic_person_id"] or
                        exc["discipline"] != row["discipline"] or
                        exc["historical_name"] != row["historical_name"] or
                        exc["index_name"] != row["published_name"] or
                        exc["other_partner_historical_name"] != other["historical_name"]):
                    raise ValueError("Official exception mismatches historical pair evidence")
                # The other historical skater has to be unambiguously named
                # on the official profile to anchor the exception.
                other_basis, _, _, _ = side_evidence(other)
                if other_basis == "identity_link_unresolved":
                    raise ValueError("Exception lacks source-matched opposite partner")
                used_exceptions.add(ekey)
            basis, dob, source, corroborate = side_evidence(row, exc)
            details.append((side, row, basis, dob, source, corroborate))
        success = all(x[2] != "identity_link_unresolved" for x in details)
        approved_exception = any(x[2] == "independently_reviewed_official_alias"
                                 for x in details)
        state = ("source_reviewed_alias_exception_pair" if success and approved_exception else
                 "dual_names_source_attested_pair" if success else
                 "unverified_directory_identity_candidate")
        gap = "; ".join(f"{row['historical_name']} => {row['published_name']}"
                        for _, row, basis, _, _, _ in details
                        if basis == "identity_link_unresolved")
        decisions.append({
            "historic_pair_id": pair_id, "discipline": members["1"]["discipline"],
            "profile_id": profile,
            "historic_person_a_id": members["1"]["historic_person_id"],
            "historic_person_b_id": members["2"]["historic_person_id"],
            "historic_person_a_name": members["1"]["historical_name"],
            "historic_person_b_name": members["2"]["historical_name"],
            "published_name_a": members["1"]["published_name"],
            "published_name_b": members["2"]["published_name"],
            "person_a_dob_evidence": details[0][3],
            "person_b_dob_evidence": details[1][3],
            "person_a_link_basis": details[0][2],
            "person_b_link_basis": details[1][2],
            "pair_identity_status": state,
            "official_profile_url": members["1"]["source_url"],
            "review_reason": gap,
        })
        if success:
            for side, row, basis, dob, source, corroborate in details:
                persons.append({
                    "historic_person_id": row["historic_person_id"],
                    "historic_pair_id": pair_id, "discipline": row["discipline"],
                    "profile_id": profile, "profile_side": side,
                    "historical_name": row["historical_name"],
                    "official_name": (exceptions[(pair_id, profile, side)]
                                      ["official_bio_name"]
                                      if (pair_id, profile, side) in exceptions
                                      else (row["historical_name_observed_in_bio"]
                                            if basis == "historic_full_name_on_official_bio"
                                            else row["published_name"])),
                    "date_of_birth_candidate": dob,
                    "identity_evidence_status": state,
                    "dob_evidence_type": basis,
                    "source_url": source,
                    "reviewed_exception_source_url": corroborate,
                })
    if set(exceptions) != used_exceptions:
        raise ValueError("Some reviewed ISU alias exceptions were not observed/validated")

    for pair_id, m in sorted(manual_pairs.items()):
        old = historic[pair_id]
        decisions.append({
            "historic_pair_id": pair_id, "discipline": m["discipline"],
            "profile_id": m.get("official_profile_id", ""),
            "historic_person_a_id": old["person_a_id"],
            "historic_person_b_id": old["person_b_id"],
            "historic_person_a_name": old["person_a_name"],
            "historic_person_b_name": old["person_b_name"],
            "published_name_a": m["official_person_a_name"],
            "published_name_b": m["official_person_b_name"],
            "person_a_dob_evidence": m["official_person_a_dob"],
            "person_b_dob_evidence": m["official_person_b_dob"],
            "person_a_link_basis": "manually_reviewed_pair",
            "person_b_link_basis": "manually_reviewed_pair",
            "pair_identity_status": "manual_official_source_pair",
            "official_profile_url": m["official_person_a_source_url"],
            "review_reason": "",
        })
        for side, number in (("a", "1"), ("b", "2")):
            persons.append({
                "historic_person_id": old[f"person_{side}_id"],
                "historic_pair_id": pair_id, "discipline": old["discipline"],
                "profile_id": m.get("official_profile_id", ""),
                "profile_side": number,
                "historical_name": old[f"person_{side}_name"],
                "official_name": m[f"official_person_{side}_name"],
                "date_of_birth_candidate": m[f"official_person_{side}_dob"],
                "identity_evidence_status": "manual_official_source_pair",
                "dob_evidence_type": "manual_source_reviewed",
                "source_url": m[f"official_person_{side}_source_url"],
                "reviewed_exception_source_url": "",
            })
    if len(decisions) != len(pair_links) + len(manual_pairs) - len(ignored_manual_candidates):
        raise ValueError("Pair coverage audit unexpectedly gained/lost pair IDs")

    # Distinct original historic IDs are STILL not equal to unique people.
    # These collisions are visible evidence for later explicit alias merging.
    collisions = []
    for (profile, side), records in sorted(slots.items()):
        ids = sorted({r["historic_person_id"] for r in records})
        if len(ids) < 2:
            continue
        dates = sorted({
            value for r in records
            for value in (r["original_published_dob"], r["historical_name_dob_candidate"])
            if value
        })
        collisions.append({
            "profile_id": profile, "side_on_profile": side,
            "historic_person_ids": "; ".join(ids),
            "historic_names": "; ".join(sorted({r["historical_name"] for r in records})),
            "historic_pair_ids": "; ".join(sorted({r["historic_pair_id"] for r in records})),
            "official_index_names": "; ".join(sorted({r["published_name"] for r in records})),
            "candidate_dates": "; ".join(dates),
            "status": "same_official_profile_side_multiple_provisional_ids_review",
        })

    by_person = defaultdict(set)
    for r in persons:
        by_person[r["historic_person_id"]].add(r["date_of_birth_candidate"])
    conflicting_people = sorted(k for k, v in by_person.items() if len(v) > 1)
    if conflicting_people:
        # Keep the evidence rows, but never describe contradictory persons as
        # consistent accepted DOBs.
        for r in persons:
            if r["historic_person_id"] in conflicting_people:
                r["identity_evidence_status"] = "cross_source_dob_conflict_hold"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    decisions.sort(key=lambda r: r["historic_pair_id"])
    persons.sort(key=lambda r: (r["historic_person_id"], r["historic_pair_id"]))
    write_csv(out / "historic_alias_pair_source_audit.csv", PAIR_FIELDS, decisions)
    write_csv(out / "historic_alias_correlated_dob_leads.csv", PEOPLE_FIELDS, persons)
    write_csv(out / "historic_alias_profile_side_collisions.csv", COLLISION_FIELDS, collisions)
    open_pairs = [x for x in decisions if
                  x["pair_identity_status"] == "unverified_directory_identity_candidate"]
    write_csv(out / "historic_alias_unresolved_pair_review.csv", PAIR_FIELDS, open_pairs)
    statuses = Counter(x["pair_identity_status"] for x in decisions)
    unique_proven = {r["historic_person_id"] for r in persons
                     if r["historic_person_id"] not in conflicting_people}
    manifest = {
        "stage": "source_correlated_historic_alias_pair_candidates_not_a_frozen_roster",
        "pairs_processed": len(decisions),
        "official_name_directory_candidate_pairs": len(pair_links),
        "manually_source_reviewed_pairs": len(manual_pairs),
        "manually_reviewed_directory_pairs_superseded": len(ignored_manual_candidates),
        "source_reviewed_alias_exceptions": len(used_exceptions),
        "pair_status_counts": dict(sorted(statuses.items())),
        "review_pair_rows": len(open_pairs),
        "source_correlated_dob_evidence_rows": len(persons),
        "source_correlated_original_historic_ids": len(unique_proven),
        "historical_ids_with_conflicting_correlated_dates": len(conflicting_people),
        "conflicting_historic_ids": conflicting_people,
        "same_profile_side_multiple_historic_ids": len(collisions),
        "input_sha256": {str(path): digest(path) for path in inputs},
        "limitations": [
            "Dual labelled historic names and a partner anchor provide source-correlated candidates, not a second independent DOB source",
            "Remaining partner-only/name-similarity links do not assign any DOB to the historic athlete",
            "An official profile-side mapped to multiple historic IDs is audited, not automatically merged",
            "Overlapping sources and multi-partner skaters mean the source rows are NOT independent people",
            "Original historic/season files and all birthdate masters stay unchanged",
            "No birthdate filling from a name similarity, birth year or country",
            "No BaZi, compatibility features, or null-model calculation",
        ],
    }
    (out / "historic_alias_pair_identity_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fallback", default="output/historic_dob/alias_fallback/historic_alias_source_name_fallback_leads.csv")
    p.add_argument("--historic", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--manual", default=str(DEFAULT_MANUAL))
    p.add_argument("--exceptions", default=str(DEFAULT_EXCEPTIONS))
    p.add_argument("--out", default="output/historic_dob/alias_pair_identity")
    a = p.parse_args()
    build(a.fallback, a.historic, a.manual, a.exceptions, a.out)


if __name__ == "__main__":
    main()
