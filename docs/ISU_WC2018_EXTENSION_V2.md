# WC2018 event-local source extension v2

This is a reversible registry/event preview, not a final research cohort.

## Uploaded evidence

The user's WC2018 identity-bridge manifest reports 59 official entries/results,
56 exact two-name historic pair candidates and three unmatched pair combinations.
The historical source preview has 865 person slots and 514 pair groups, preserving
553 original pair IDs. The latest historical collision audit has 3,237 pair-event
rows with no duplicate canonical event keys.

The three unmatched rows do NOT mean three newly formed real-world partnerships.
They are unmatched to the selected historical registry by exact published names.

## Source-specific decisions (reviewed 2026-10-19)

| Event pair | Local decision | Registry effect |
| --- | --- | --- |
| Allison REED / Saulius AMBRULEVICIUS | Both are existing historic members; add this combination to the event-local extension | +1 pair, no new person |
| Olivia SMART / Adrian DIAZ | Existing historical pair uses Adria DIAZ; use the exact old pair and member IDs after checking both DOBs | No new pair or person |
| Elizaveta KASHITSYNA / Mark MAGYAR | Reuse Mark's historic ID; add a source-scoped Elizaveta slot and their combination, provided no exact historical name or ID already exists | +1 pair, +1 source-scoped person |

Reviewed primary sources:

- https://results.isu.org/bios/isufs00103181.htm gives Allison 1994-06-08,
  Saulius 1992-06-10 and their previous partner histories. It says this
  partnership began in spring 2017; the registry extension does not claim 2018
  was their actual partnership start.
- https://results.isu.org/bios/isufs00101308.htm gives Olivia 1997-04-01 and
  Adrian 1990-09-17. The versioned historical DOB source table already records
  historical Adria DIAZ against official Adrian DIAZ. The extension requires
  pair_da01b03835770 and its exact old member IDs, not general fuzzy matching.
- https://results.isu.org/bios/isufs00105349.htm gives Elizaveta 2001-06-15,
  Saratov RUS, and Mark 1990-04-28. Elizaveta's new identifier is scoped to
  this official profile/member side; wider cross-dataset alias QA remains open.

The versioned decisions are in:

    data/adjudications/isu_wc2018_pair_extension_rules_v2.csv

Each existing member's DOB must match the locally reviewed historical registry.
Reusing the same ISU biography does not supply an independent DOB replication.
The offline script checks the ledger, source lineage and structural constraints;
it does not download or independently re-review web pages.

## Separate modern-name warning

The one SAME_PROFILE_DIFFERENT_MODERN_PUBLISHED_NAMES_REVIEW case is
Deanna STELLATO / Nathan BARTHOLOMAY. The modern roster says Deanna
STELLATO-DUDEK with the same profile isufs00102206 and Nathan. Current official
https://results.isu.org/bios/isufs00102206.htm shows Deanna 1983-06-22 and Nathan
1989-05-18. This explains the published-name warning, but this v2 extension does
not change the modern identity map or automatically promote global cross-era
identity decisions. The 22 event pairs absent from the later season rankings
remain evidence of no ranking match, not evidence of nonparticipation.

## Run from repository root (one PowerShell command per line)

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\audit_wc2018_extension_v2.py

No new packages or network requests are needed for the audit itself. Existing
v1 bridge outputs, official pilot link table, historical people/pair previews,
original pair-event table and latest collision manifest must remain available
at their established repository paths. The script verifies their prior SHA256
lineage and compares every new event observation against the validated official
entry/result link row.

## Outputs

New directory:

    output/frame/isu_wc2018_extension_v2/

- wc2018_extension_manifest_v2.json: counts, limitations, input/output SHA256s.
- wc2018_resolved_event_overlay_v2.csv: 59 new observations with member links,
  rule IDs and separate total-score / short-segment-only columns.
- wc2018_new_person_slots_v2.csv: the one new event-source-scoped person record.
- wc2018_new_pair_combinations_v2.csv: the two new registry combinations.
- historical_plus_wc2018_event_index_v2.csv: a combined source-row index,
  preserving original record IDs and hashes instead of rewriting legacy scores.

Expected with the currently reviewed full local inputs:

| Measure | Before | v2 preview |
| --- | ---: | ---: |
| Historical person slots | 865 | 866 |
| Historical pair groups | 514 | 516 |
| Pair-event observations in union index | 3,237 | 3,296 |
| WC2018 rows linked to already represented pair groups | 56 exact-name candidates | 57 after one reviewed name variant |
| New registry pair combinations | 0 | 2 |

These expected full-data counts require a local run. Fourteen synthetic tests
were actually executed before publishing. They exercise valid 59-row projection,
DOB/name mismatches, hostile URLs, repeated append, FNR score separation, source
hash changes, input preservation and deterministic replay.

56 inherited exact-name pair links keep their candidate status. Only the three
explicit exception decisions receive event-local source-reviewed treatment.
A 3,296-row index is not a claim that all 3,296 scores are comparable, that all
historic links are independently confirmed, or that every entrant is covered.
The 23 WC2018 Final Not Reached rows keep short-segment scores separate; no
whole-event total is fabricated. Existing legacy score semantics are untouched.

## No overwrite / replay

The audit refuses an already existing output directory. For an intentional
replay without replacing earlier results, use a fresh destination:

    python .\scripts\audit_wc2018_extension_v2.py --out .\output\frame\isu_wc2018_extension_v2_replay

It also refuses to append if WC2018 already appears under the normalized old
pair-event keys. This avoids duplication if historical source files later change.

## Return

Send wc2018_extension_manifest_v2.json and wc2018_new_pair_combinations_v2.csv
from the new output directory. An unexpected validation error should be reviewed
rather than bypassed. No astrology, performance-based sample inclusion,
significance tests, null models or cohort freeze are part of this stage.
