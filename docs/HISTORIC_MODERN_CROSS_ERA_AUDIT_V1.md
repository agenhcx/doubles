# Cross-era ISU athlete identity audit v1 (historic 2004–2018 vs season rankings 2018–2026)

This is a **non-destructive evidence index**, not a merged natural-person
roster, not a frozen study cohort and not a basis for BaZi testing.

The reviewed historical baseline is 911 audit identity slots, 33 explicit
source-reviewed reversible aliases, 878 projected person slots, 553
original pair IDs and 520 projected historic pair groups. The historical
event collision audit found 0 repeated projected pair-event keys among
3,237 original event records. All original source events remain unchanged.

## Prior uploaded modern data, for planning only

An October 17 uploaded season-roster export contained 1,584 season-ranking
rows, 1,050 provisional skater name IDs and 622 provisional pair IDs.
Against the historic v4 source pair names and the 33-reviewed-alias map,
181 skater name IDs occurred in both eras; 68 complete name-normalized
pairs occurred in both eras. Only 81 of those 181 name-ID overlaps had
modern official DOB candidates in the uploaded 100-row Biography pilot.
These numbers are **preliminary name-ID matches**, not 181 independently
confirmed people. The local pipeline below recomputes from current files.

## Inputs

Required, from prior steps:

- output/historic_dob/shared_partner_identity/historic_reviewed_person_id_preview_v1.csv
- output/historic_dob/shared_partner_identity/historic_reviewed_pair_groups_preview_v1.csv
- output/master/season_roster.csv

Optional, but highly valuable:

- output/bios/birth_candidates.csv — official ISU biography dates from
  collect_isu_biographies.py. Only valid exact-name-match source rows,
  including roster-confirmed trailing-country-field repairs, are used
  for a modern DOB check. When the file is absent, the audit runs and
  records missing modern DOB evidence. It does not substitute a birthday.

Run from repository root (single-line PowerShell commands):

    git pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_historic_shared_partner_aliases.py
    python .\scripts\audit_historic_modern_cross_era_v1.py

If Git requires the user's local HTTP proxy instead, replace the pull
command with:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only

## Outputs

Under output/historic_dob/cross_era_identity/:

- historic_modern_cross_era_manifest_v1.json: status counts and SHA256s
  of inputs, so old and fresh roster runs cannot be silently confused.
- historic_modern_identity_review_v1.csv: every candidate link, paired
  evidence, names, modern ISU DOB evidence and explicit conflict holds.
- historic_modern_pair_bridges_v1.csv: complete pair combinations seen
  in both periods under provisional name ID matching.
- historic_modern_bio_conflicts_v1.csv: multiple different accepted
  modern biography dates for a provisional modern person ID.
- historic_modern_unlinked_historic_v1.csv: historic reviewed skaters
  without a cross-era lead; this is **not proof of nonparticipation**.

## Evidence policy

1. Identical person IDs in these datasets are hashes of standardized
   names. They do not prove real-world identity and trigger no merger.
2. ISU biography matching dates are cross-checked against historic
   reviewed dates. Conflicting dates, multiple modern dates, and
   one-to-many links remain explicitly held.
3. Exact historic/modern pair matches supply a useful partner anchor but
   are still provisional. Same DOB + similar name can create additional
   review leads; no DOB-only matches are accepted.
4. A second URL for an identical ISU biography is not independent
   corroboration.
5. A modern season ranking is not an event participation roster. Event
   ranks and points never contribute to candidate generation.
6. Original identity IDs, birthdays, partner IDs, event scores and the
   master files are not overwritten.

Human QA should prioritize DOB conflicts, one-to-many links, and
cross-era skaters with both members of a pair matched. Additional modern
Biography downloads can be performed later locally using the already
provided biography collector, with conservative source review.
No BaZi features or null-model calculations belong to this phase.
