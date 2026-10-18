#!/usr/bin/env python3
"""Non-destructive event collision audit after historic identity v3 review.

Group historic v4 pair-event records by reviewed projected team and original
event_id. Preserve original IDs and conflicting values. No master rewrites,
season-rank additions, birthdate inference, or astrological calculations.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

PREVIEW = Path("output/historic_dob/shared_partner_identity/historic_reviewed_pair_groups_preview_v1.csv")
EVENTS = Path("data/historic/v4/pair_events_v4.csv")
OUT = Path("output/historic_dob/shared_partner_identity/event_collision_audit")
FIELDS = [
    "discipline", "projected_person_a_id", "projected_person_b_id",
    "event_id", "season", "event", "original_pair_ids",
    "original_pair_event_ids", "original_event_record_count",
    "original_pair_id_count", "rank_values", "score_values",
    "result_status_values", "source_urls", "review_status",
]


def read(path, required):
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing required columns {sorted(missing)}")
        return list(reader)


def write(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sep(values):
    return "; ".join(sorted(set(v for v in values if v)))


def ids(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(preview_path=PREVIEW, event_path=EVENTS, out_dir=OUT):
    preview = read(preview_path, (
        "discipline", "projected_person_a_id", "projected_person_b_id",
        "original_pair_ids", "original_pair_rows"))
    events = read(event_path, (
        "pair_id", "pair_event_id", "discipline", "event_id", "season",
        "event", "rank", "score_as_reported", "result_status", "source_urls"))
    if not preview or not events:
        raise ValueError("Projected teams and original pair-events must both be nonempty")

    mapped = {}
    for p in preview:
        key = (p["discipline"], p["projected_person_a_id"], p["projected_person_b_id"])
        raw = ids(p["original_pair_ids"])
        if not all(key) or not raw or len(raw) != len(set(raw)):
            raise ValueError("Blank team fields or duplicate original pair ID within group")
        if str(len(raw)) != p["original_pair_rows"]:
            raise ValueError("Projected original_pair_rows disagrees with ID lineage")
        for original in raw:
            if original in mapped:
                raise ValueError("Original pair ID mapped to multiple teams: " + original)
            mapped[original] = key

    grouped = defaultdict(list)
    seen_event_ids = set()
    for r in events:
        pid, event, original_id = r["pair_id"], r["event_id"], r["pair_event_id"]
        if pid not in mapped or not event or not original_id:
            raise ValueError("Unmapped pair ID or missing stable event ID: " + repr((pid, event, original_id)))
        team = mapped[pid]
        if r["discipline"] != team[0]:
            raise ValueError("Discipline mismatch for original pair: " + pid)
        if original_id in seen_event_ids:
            raise ValueError("Repeated original pair_event_id: " + original_id)
        seen_event_ids.add(original_id)
        grouped[(*team, event)].append(r)

    rows = []
    for key, values in sorted(grouped.items()):
        discs = {r["discipline"] for r in values}
        seasons = {r["season"] for r in values}
        event_names = {r["event"] for r in values}
        ranks = {r["rank"].strip() for r in values if r["rank"].strip()}
        scores = {r["score_as_reported"].strip() for r in values if r["score_as_reported"].strip()}
        statuses = {r["result_status"].strip() for r in values if r["result_status"].strip()}
        incomplete = any(not r["rank"].strip() or not r["result_status"].strip() for r in values)
        conflict = (
            len(discs) > 1 or len(seasons) > 1 or len(event_names) > 1 or
            len(ranks) > 1 or len(scores) > 1 or len(statuses) > 1 or
            any(r.get("rank_source_conflict", "").strip() not in ("", "none") for r in values)
        )
        if len(values) == 1:
            status = "SINGLE_ORIGINAL_EVENT"
        elif conflict:
            status = "MULTIPLE_ORIGINAL_EVENTS_FIELD_CONFLICT_HOLD"
        elif incomplete:
            status = "MULTIPLE_ORIGINAL_EVENTS_INCOMPLETE_HOLD"
        else:
            status = "MULTIPLE_ORIGINAL_EVENTS_VALUES_AGREE_REVIEW"
        rows.append({
            "discipline": key[0],
            "projected_person_a_id": key[1],
            "projected_person_b_id": key[2],
            "event_id": key[3],
            "season": sep(seasons),
            "event": sep(event_names),
            "original_pair_ids": sep(r["pair_id"] for r in values),
            "original_pair_event_ids": sep(r["pair_event_id"] for r in values),
            "original_event_record_count": len(values),
            "original_pair_id_count": len({r["pair_id"] for r in values}),
            "rank_values": sep(ranks),
            "score_values": sep(scores),
            "result_status_values": sep(statuses),
            "source_urls": sep(u for r in values for u in ids(r["source_urls"])),
            "review_status": status,
        })

    collisions = [r for r in rows if int(r["original_event_record_count"]) > 1]
    out = Path(out_dir)
    write(out / "historic_pair_event_identity_preview_v1.csv", rows, FIELDS)
    write(out / "historic_alias_event_collision_review_v1.csv", collisions, FIELDS)
    tally = Counter(r["review_status"] for r in rows)
    summary = {
        "stage": "historic_identity_v3_event_collision_audit_not_frozen",
        "original_historic_pair_ids_mapped": len(mapped),
        "original_pair_event_records": len(events),
        "projected_distinct_pair_event_groups": len(rows),
        "event_collision_groups": len(collisions),
        "extra_source_pair_event_records_in_collision_groups": len(events) - len(rows),
        "field_conflict_groups": tally["MULTIPLE_ORIGINAL_EVENTS_FIELD_CONFLICT_HOLD"],
        "incomplete_collision_groups": tally["MULTIPLE_ORIGINAL_EVENTS_INCOMPLETE_HOLD"],
        "value_agree_collision_groups": tally["MULTIPLE_ORIGINAL_EVENTS_VALUES_AGREE_REVIEW"],
        "status_counts": dict(sorted(tally.items())),
        "inputs_sha256": {str(preview_path): sha(preview_path), str(event_path): sha(event_path)},
        "limitations": [
            "Projected teams are source-reviewed alias identities, not a frozen cohort",
            "Matching event_id is a candidate for deduplication, not approval of conflicts",
            "Original pair/event IDs, rank, score, season, source URLs and files stay unchanged",
            "Season rankings are not events and are never added here",
            "Aliases involving two entirely changed partner IDs can remain undiscovered",
            "No BaZi, compatibility analysis, significance testing or outcome selection",
        ],
    }
    (out / "historic_alias_event_collision_manifest_v1.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", type=Path, default=PREVIEW)
    p.add_argument("--events", type=Path, default=EVENTS)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    audit(args.preview, args.events, args.out)


if __name__ == "__main__":
    main()
