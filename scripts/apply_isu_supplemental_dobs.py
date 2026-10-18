#!/usr/bin/env python3
"""Non-destructive application of source-audited ISU supplemental birthdates.

Use after audit_isu_identities.py. Never overwrite canonical people or raw
biography records; output a separate augmented people table and audit log.
No network, birthdate inference, geocoding, performance filtering, or BaZi.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import digest, norm, read_csv, valid_date, write_csv

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "data" / "adjudications" / "isu_supplemental_dobs_v1.csv"
ISU_HOSTS = frozenset((
    "results.isu.org", "www.isuresults.com",
    "isu-skating.com", "www.isu-skating.com",
))
FEDERATION_HOSTS = frozenset((
    "ffkm.ru", "www.ffkm.ru", "fsrussia.ru", "www.fsrussia.ru",
))
EVIDENCE_FIELDS = (
    "canonical_person_id", "roster_name", "date_of_birth",
    "official_observed_name", "evidence_status", "source_url",
    "identity_basis", "evidence_note",
)
ADDITIONAL_FIELDS = (
    "supplemental_source_url", "supplemental_observed_name",
    "supplemental_evidence_status", "supplemental_identity_basis",
)
AUDIT_FIELDS = (
    "canonical_person_id", "roster_name", "official_observed_name",
    "source_url", "evidence_status", "identity_basis",
    "source_dob", "before_dob", "after_dob", "application_status",
)


def _check_roster_name(wanted, observed_names):
    names = [v.strip() for v in (observed_names or "").split(";") if v.strip()]
    return bool(wanted) and norm(wanted) in {norm(v) for v in names}


def apply_supplemental_dobs(
    people_path="output/identity/identity_canonical_people.csv",
    evidence_path=EVIDENCE,
    out_dir="output/identity/supplemental",
):
    people_path = Path(people_path)
    evidence_path = Path(evidence_path)
    out = Path(out_dir)
    target_people = out / "identity_canonical_people_supplemented.csv"
    target_audit = out / "supplemental_dob_audit.csv"

    if people_path.resolve() == target_people.resolve():
        raise ValueError("Cannot overwrite the original canonical people file")
    if people_path.resolve() == target_audit.resolve():
        raise ValueError("Cannot overwrite original people with audit log")
    if evidence_path.resolve() in {target_people.resolve(), target_audit.resolve()}:
        raise ValueError("Cannot overwrite evidence CSV")

    people = read_csv(people_path)
    evidence = read_csv(evidence_path)
    if not people:
        raise ValueError("Canonical people file is empty")
    if not evidence:
        raise ValueError("No supplemental evidence rows supplied")
    needed = ("canonical_person_id", "roster_names", "date_of_birth", "dob_status")
    if set(needed) - people[0].keys():
        raise ValueError("Canonical people file is missing required columns")
    if set(EVIDENCE_FIELDS) - evidence[0].keys():
        raise ValueError("Supplemental evidence missing required columns")

    indexed = {}
    prepared = []
    for entry in people:
        person_id = entry["canonical_person_id"]
        if not person_id or person_id in indexed:
            raise ValueError("Blank or duplicate person ID in canonical people")
        if entry["dob_status"] not in {"consistent", "no_verified_bio", "dob_conflict"}:
            raise ValueError("Unknown original DOB status for " + person_id)
        if (entry["dob_status"] == "consistent") != bool(entry["date_of_birth"]):
            raise ValueError("Original DOB status inconsistent for " + person_id)
        if entry["date_of_birth"] and not valid_date(entry["date_of_birth"]):
            raise ValueError("Invalid original DOB for " + person_id)
        enriched = dict(entry)
        enriched.update({k: "" for k in ADDITIONAL_FIELDS})
        prepared.append(enriched)
        indexed[person_id] = enriched

    statuses = Counter()
    seen = set()
    decisions = []
    for e in evidence:
        person_id = e["canonical_person_id"]
        if not person_id or person_id in seen:
            raise ValueError("Blank or duplicate source evidence ID")
        seen.add(person_id)
        if person_id not in indexed:
            raise ValueError("Supplemental evidence refers to an unknown canonical ID: " + person_id)
        person = indexed[person_id]
        if not _check_roster_name(e["roster_name"], person["roster_names"]):
            raise ValueError("Evidence identity/name mismatch: " + person_id)
        if not e["source_url"].startswith("https://"):
            raise ValueError("Evidence URL must be HTTPS: " + person_id)
        if not e["official_observed_name"] or not e["identity_basis"]:
            raise ValueError("Missing evidence identity context: " + person_id)

        initial = person["date_of_birth"]
        source_date = e["date_of_birth"]
        source_status = e["evidence_status"]
        if source_status == "pending_primary_source":
            if source_date:
                raise ValueError("Pending source must not provide accepted DOB: " + person_id)
            action = "held_pending_primary"
        elif source_status in {"official_isu_checked", "official_federation_checked"}:
            parsed_url = urlsplit(e["source_url"])
            host = parsed_url.hostname
            if source_status == "official_isu_checked" and host not in ISU_HOSTS:
                raise ValueError("Approved birthdate URL not on ISU domain: " + person_id)
            if source_status == "official_federation_checked":
                if host not in FEDERATION_HOSTS:
                    raise ValueError("Birthdate URL not on approved skating federation domain: " + person_id)
                if not parsed_url.path.lower().endswith(".pdf"):
                    raise ValueError("Federation DOB evidence must be an official PDF: " + person_id)
            if not valid_date(source_date):
                raise ValueError("Official evidence has invalid DOB: " + person_id)
            if person["dob_status"] == "dob_conflict":
                raise ValueError("Existing DOB conflict requires separate adjudication: " + person_id)
            if person["dob_status"] == "consistent":
                if initial != source_date:
                    raise ValueError("Supplemental DOB contradicts existing DOB: " + person_id)
                action = "already_present"
            else:
                person["date_of_birth"] = source_date
                person["dob_status"] = "consistent"
                action = "accepted_official_source"
            person["supplemental_source_url"] = e["source_url"]
            person["supplemental_observed_name"] = e["official_observed_name"]
            person["supplemental_evidence_status"] = source_status
            person["supplemental_identity_basis"] = e["identity_basis"]
        else:
            raise ValueError("Unrecognized supplemental evidence status: " + person_id)

        statuses[action] += 1
        decisions.append({
            "canonical_person_id": person_id,
            "roster_name": e["roster_name"],
            "official_observed_name": e["official_observed_name"],
            "source_url": e["source_url"],
            "evidence_status": source_status,
            "identity_basis": e["identity_basis"],
            "source_dob": source_date,
            "before_dob": initial,
            "after_dob": person["date_of_birth"],
            "application_status": action,
        })

    result = {
        "scope": "ISU-ranked skating identity DOB supplements; no master mutation or BaZi",
        "canonical_people": len(prepared),
        "evidence_rows": len(evidence),
        "new_official_dobs_accepted": statuses["accepted_official_source"],
        "official_dobs_already_present": statuses["already_present"],
        "pending_primary_verification": statuses["held_pending_primary"],
        "people_with_consistent_dob_after": sum(
            p["dob_status"] == "consistent" for p in prepared
        ),
        "people_without_consistent_dob_after": sum(
            p["dob_status"] != "consistent" for p in prepared
        ),
        "people_with_dob_conflicts_after": sum(
            p["dob_status"] == "dob_conflict" for p in prepared
        ),
        "input_sha256": {
            str(people_path): digest(people_path),
            str(evidence_path): digest(evidence_path),
        },
        "output_files": [
            "identity_canonical_people_supplemented.csv", "supplemental_dob_audit.csv"
        ],
        "limitations": [
            "Official ISU biographies and federation source PDFs curated manually; source contents are not rechecked by this offline script",
            "Non-official or unverified sources, if provided, remain excluded",
            "The evidence source URL and name are kept on each supplemented record",
            "The original canonical people CSV and raw biographies are not overwritten",
            "DOB consistency and pair coverage require running the follow-up coverage report",
        ]
    }
    out.mkdir(parents=True, exist_ok=True)
    write_csv(target_people, list(prepared[0]), prepared)
    write_csv(target_audit, AUDIT_FIELDS, decisions)
    (out / "supplemental_dob_manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--people", default="output/identity/identity_canonical_people.csv")
    p.add_argument("--evidence", default=str(EVIDENCE))
    p.add_argument("--out", default="output/identity/supplemental")
    args = p.parse_args()
    apply_supplemental_dobs(args.people, args.evidence, args.out)


if __name__ == "__main__":
    main()
