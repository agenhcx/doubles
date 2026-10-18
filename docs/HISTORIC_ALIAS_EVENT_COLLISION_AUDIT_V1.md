# Historical pair-event collision audit v1 (2004–2018)

This follows the identity adjudication in
[HISTORIC_SHARED_PARTNER_ALIAS_REVIEW_V3.md](HISTORIC_SHARED_PARTNER_ALIAS_REVIEW_V3.md).
It is a **non-destructive QA preview**, not an updated scientific cohort.

## Input dependencies

1. The original 553 historic pair IDs and their v4 event records:
   \`data/historic/v4/pair_events_v4.csv\`.
2. The **locally regenerated v3** reviewed pair-group preview:
   \`output/historic_dob/shared_partner_identity/historic_reviewed_pair_groups_preview_v1.csv\`.

First sync the source-reviewed 33 alias rules and generate the pair preview:

\`\`\`powershell
git pull --ff-only
python .\scripts\audit_historic_shared_partner_aliases.py
\`\`\`

The first audit should show 33 source-reviewed alias edges, 0 pending
same-original-partner candidates, 878 audited person identity slots, 520
projected pair groups and 553 preserved original pair IDs. These are
structural expectations; they **must be checked in the local manifest**.

Then check historic event collisions:

\`\`\`powershell
python .\scripts\audit_historic_alias_event_collisions_v1.py
\`\`\`

The script records three files under
\`output/historic_dob/shared_partner_identity/event_collision_audit/\`:

- \`historic_alias_event_collision_manifest_v1.json\`: input hashes,
  source-record counts, projected pair-event count and conflict counts.
- \`historic_alias_event_collision_review_v1.csv\`: only projected
  pair + event combinations where 2+ original pair-event records collide.
- \`historic_pair_event_identity_preview_v1.csv\`: all projected
  pair-event groups, retaining original lineage and observed values.

A shared projected team + original \`event_id\` is a **review candidate**.
The script neither sums ranking points nor averages scores.
Different rank, score, result status, season, event label or an inherited
v4 rank-source conflict puts a collision on explicit HOLD.
Missing rank/status also remains under review. Matching available
values are not a substitute for independent review.

All old pair IDs, event IDs, source URLs, DOB evidence and v4 files remain
unchanged. Season's World Rankings 2018–2026 are not individual event
results and are never added into the historical event count.

## Next phase

After reviewing and resolving event collisions, audit cross-era
historical athlete identities versus the 2018–2026 season roster,
including partner/name changes and missing profiles. Do **not** interpret
the 878 historical identity slots as a final unique-person count.
No BaZi features or null-model analyses are computed at this stage.
