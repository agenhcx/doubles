#!/usr/bin/env python3
"""Evidence-only queue for unreviewed historic same-partner/same-DOB aliases.

Use AFTER audit_historic_shared_partner_aliases.py. Never auto-merge
person IDs based on name similarity, DOB or a shared partner.
No network, performance filtering, BaZi, or master mutations.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from audit_isu_identities import read_csv, digest, write_csv, valid_date

ROOT = Path(__file__).resolve().parent.parent
FIELDS = [
    "discipline", "audit_person_a_id", "audit_person_b_id", "historic_name_a",
    "historic_name_b", "shared_dob", "shared_partner_ids",
    "shared_partner_names", "historic_pair_ids_a", "historic_pair_ids_b",
    "primary_curated_source_a", "primary_curated_source_b",
    "primary_curated_observed_name_a", "primary_curated_observed_name_b",
    "other_existing_official_urls_a", "other_existing_official_urls_b",
    "source_support_tier", "review_status", "review_note"
]
OFFICIAL = {"results.isu.org", "www.isuresults.com",
            "isu-skating.com", "www.isu-skating.com"}


def require(rows, cols, label):
    if not rows or set(cols) - set(rows[0]):
        raise ValueError(label + " empty or missing required columns")


def semi(value):
    return {x.strip() for x in (value or "").split(";") if x.strip()}


def official(url):
    u = urlsplit(url)
    return (u.scheme in {"http", "https"} and u.hostname in OFFICIAL
            and u.username is None and u.password is None and u.port is None
            and not u.query and not u.fragment)


def make_queue(
    candidates_path="output/historic_dob/shared_partner_identity/historic_shared_partner_same_dob_candidates_v1.csv",
    people_path="output/historic_dob/coverage/historic_dob_coverage_people_v1.csv",
    couples_path="data/historic/v4/couples_v4.csv",
    priority_path="data/adjudications/isu_historic_priority_dob_sources_v3.csv",
    seed_path="data/adjudications/isu_historic_primary_dob_seed_v2.csv",
    out_dir="output/historic_dob/shared_partner_identity/source_review",
):
    paths = list(map(Path, (
        candidates_path, people_path, couples_path, priority_path, seed_path
    )))
    candidates, people, couples, priority, seed = [
        read_csv(x) for x in paths
    ]
    require(candidates, (
        "discipline", "audit_person_a_id", "audit_person_b_id",
        "historic_person_a_id", "historic_person_b_id",
        "historic_name_a", "historic_name_b", "shared_dob",
        "shared_partner_ids", "shared_partner_names",
        "historic_pair_ids_a", "historic_pair_ids_b",
        "identity_review_status"
    ), "Candidate aliases")
    require(people, (
        "audit_person_id", "original_historic_person_id",
        "date_of_birth_primary_candidate", "dob_coverage_status", "source_urls"
    ), "Audited DOB people")
    require(couples, ("pair_id", "person_a_id", "person_b_id",
                      "discipline"), "Historic pairs")
    require(priority, ("historic_person_id", "date_of_birth", "source_url",
                       "official_observed_name"), "Reviewed ISU priority")
    require(seed, ("historic_person_id", "date_of_birth", "source_url",
                   "source_observed_name"), "Reviewed ISU seed")

    persons = {}
    for p in people:
        if not p["audit_person_id"] or p["audit_person_id"] in persons:
            raise ValueError("Duplicate or empty audited identity")
        persons[p["audit_person_id"]] = p
    pairs = {}
    for p in couples:
        if not p["pair_id"] or p["pair_id"] in pairs:
            raise ValueError("Duplicate/blank historic pair")
        pairs[p["pair_id"]] = p

    sources = defaultdict(list)
    for source_type, rows, printed in (
        ("v3", priority, "official_observed_name"),
        ("legacy", seed, "source_observed_name")
    ):
        for p in rows:
            if not valid_date(p["date_of_birth"]) or not official(p["source_url"]):
                raise ValueError("Curated DOB source is malformed")
            sources[p["historic_person_id"]].append(
                (source_type, p["date_of_birth"], p["source_url"], p[printed])
            )

    pending = []
    approved = 0
    seen = set()
    for r in candidates:
        status = r["identity_review_status"]
        if status == "source_reviewed_reversible_merge":
            approved += 1
            continue
        if status != "candidate_same_partner_same_dob_not_merged":
            raise ValueError("Unknown candidate review state")
        aa, bb = r["audit_person_a_id"], r["audit_person_b_id"]
        key = (r["discipline"], *sorted((aa, bb)))
        if aa == bb or key in seen:
            raise ValueError("Duplicate or self-alias candidate")
        seen.add(key)
        if not valid_date(r["shared_dob"]):
            raise ValueError("Invalid candidate DOB")
        shared = semi(r["shared_partner_ids"])
        if not shared:
            raise ValueError("Shared partner reference absent")
        support = {}
        for side, aid in (("a", aa), ("b", bb)):
            p = persons.get(aid)
            if (p is None or p["original_historic_person_id"] !=
                    r["historic_person_" + side + "_id"] or
                    p["dob_coverage_status"] != "official_source_linked" or
                    p["date_of_birth_primary_candidate"] != r["shared_dob"]):
                raise ValueError("Alias candidate lacks matching official DOB and ID")
            referenced = semi(r["historic_pair_ids_" + side])
            if not referenced:
                raise ValueError("Missing original pair evidence")
            shared_verified = False
            for pair_id in referenced:
                pair = pairs.get(pair_id)
                if not pair or pair["discipline"] != r["discipline"]:
                    raise ValueError("Invalid pair/discipline in candidate")
                aid_original = r["historic_person_" + side + "_id"]
                if pair["person_a_id"] == aid_original:
                    other = pair["person_b_id"]
                elif pair["person_b_id"] == aid_original:
                    other = pair["person_a_id"]
                else:
                    raise ValueError("Candidate person not a pair member")
                if other in shared:
                    shared_verified = True
            if not shared_verified:
                raise ValueError("Pair does not share claimed original partner")
            matches = [x for x in sources.get(
                p["original_historic_person_id"], []
            ) if x[1] == r["shared_dob"]]
            urls = sorted(u for u in semi(p["source_urls"]) if official(u))
            support[side] = (matches, urls)

        type_a = bool(support["a"][0])
        type_b = bool(support["b"][0])
        tier = (
            "both_ids_have_curated_sources" if type_a and type_b else
            "one_id_has_curated_source" if type_a or type_b else
            "no_separate_curated_source_yet"
        )
        def cited(side, element):
            return "; ".join(sorted({x[element] for x in support[side][0]}))
        pending.append({
            "discipline": r["discipline"],
            "audit_person_a_id": aa, "audit_person_b_id": bb,
            "historic_name_a": r["historic_name_a"],
            "historic_name_b": r["historic_name_b"],
            "shared_dob": r["shared_dob"],
            "shared_partner_ids": r["shared_partner_ids"],
            "shared_partner_names": r["shared_partner_names"],
            "historic_pair_ids_a": r["historic_pair_ids_a"],
            "historic_pair_ids_b": r["historic_pair_ids_b"],
            "primary_curated_source_a": cited("a", 2),
            "primary_curated_source_b": cited("b", 2),
            "primary_curated_observed_name_a": cited("a", 3),
            "primary_curated_observed_name_b": cited("b", 3),
            "other_existing_official_urls_a": "; ".join(support["a"][1]),
            "other_existing_official_urls_b": "; ".join(support["b"][1]),
            "source_support_tier": tier,
            "review_status": "NOT_APPROVED_REQUIRES_IDENTITY_SOURCE_REVIEW",
            "review_note": (
                "Same DOB/partner is only a candidate. Confirm printed ISU "
                "name variants and actual pair chronology before merging."
            ),
        })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pending.sort(key=lambda r: (
        r["source_support_tier"] == "no_separate_curated_source_yet",
        r["source_support_tier"] == "one_id_has_curated_source",
        r["historic_name_a"]
    ))
    write_csv(out / "historic_pending_alias_official_evidence_v1.csv",
              FIELDS, pending)
    tiers = Counter(r["source_support_tier"] for r in pending)
    summary = {
        "status": "SOURCE_EVIDENCE_QUEUE_NO_AUTO_MERGES",
        "already_reviewed_alias_groups": approved,
        "remaining_alias_groups": len(pending),
        "curated_source_tiers": dict(sorted(tiers.items())),
        "unreviewed_distinct_audit_ids": len({
            x for r in pending
            for x in (r["audit_person_a_id"], r["audit_person_b_id"])
        }),
        "input_sha256": {str(p): digest(p) for p in paths},
        "limitations": [
            "Previously validated DOB source URLs are audit leads, not fresh page fetches",
            "All unresolved aliases remain distinct until source-specific adjudication",
            "No original person IDs, events, results or DOB sources are rewritten",
            "No astrological features, outcome selection or null model computed",
        ],
    }
    (out / "historic_pending_alias_source_manifest_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", default="output/historic_dob/shared_partner_identity/historic_shared_partner_same_dob_candidates_v1.csv")
    p.add_argument("--people", default="output/historic_dob/coverage/historic_dob_coverage_people_v1.csv")
    p.add_argument("--pairs", default="data/historic/v4/couples_v4.csv")
    p.add_argument("--priority", default="data/adjudications/isu_historic_priority_dob_sources_v3.csv")
    p.add_argument("--seed", default="data/adjudications/isu_historic_primary_dob_seed_v2.csv")
    p.add_argument("--out", default="output/historic_dob/shared_partner_identity/source_review")
    a = p.parse_args()
    make_queue(a.candidates, a.people, a.pairs, a.priority, a.seed, a.out)


if __name__ == "__main__":
    main()
