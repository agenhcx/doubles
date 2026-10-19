# Milan 2018 official event → historical/modern identity crosswalk v1

Date: 2026-10-18. This is an **offline source audit**, not an approved ID
merge or a frozen statistical sample. It does not modify original v4
events, modern season rankings or audited birth-date records.

## Source result: four official pages now all validated

The user-supplied official WC2018 pilot manifest and its four-page
inventory report:

| Discipline | Official entrants / result rows | Free segment completed | Final not reached |
| --- | ---: | ---: | ---: |
| Ice Dance | 31 | 20 | 11 |
| Pair Skating | 28 | 16 | 12 |
| **Total** | **59** | **36** | **23** |

All 59 entries match one result row by the same ISU biography profile
ID, published name and nation. Both entry and result source URLs,
published score interpretation and original page hashes are preserved.
The 23 Final Not Reached points are **short-segment-only**, not
competition total points.

Input:
`output/frame/isu_wc2018_pilot_v1/official_entry_result_link_review_v1.csv`.
The 2018 World Championship event cells are absent from the historical
v4 inventory; therefore all 59 are **new event observations**, not 59
new names/people/couples.

## Preliminary name-only overlaps

Using the 59 verified original event entries and the 553 raw historic
v4 pairs, a direct, order-insensitive-normalized **two-member
published-name** comparison found:

- 56 exact historical-pair name matches;
- 3 complete pairs not present in the old historic pair source:
  - Allison REED / Saulius AMBRULEVICIUS: both people appear with other
    historical partners;
  - Olivia SMART / Adrian DIAZ: the old source has Olivia SMART and
    historical **Adria DIAZ**; the full new pair-name match is not
    approved without a separate official alias adjudication;
  - Elizaveta KASHITSYNA / Mark MAGYAR: Mark appears in older historical
    partnerships; Elizaveta is not matched in the old historic pair table.
- Modern 2018–26 Season's World Ranking source-name overlap was 36
  exact two-member published-name pairs; a separate 37th pair has
  an ISU profile ID match without exactly matching both published
  names. **A ranking page is not a competition start list.**

These are preliminary name-based comparisons, not an assertion that 56
historical person identities are independently attested. A new pair
observation still needs original profile/source-level comparison and
reviewed historical ID lineage.

The current ISU official profile
https://results.isu.org/bios/isufs00101308.htm confirms Adrian DIAZ,
DOB 1990-09-17, partnered with Olivia SMART. An older historic skater
may appear as Adria DIAZ: retain both names and review DOB/partner
history before merging the provisional IDs.

The ISU Kashitsyna/Magyar profile
https://isu-skating.com/en/figure-skating/skaters/pairs/elizaveta-kashitsyna-mark-magyar/
reports Elizaveta's DOB as 2001-06-15; this is **a birthdate source
lead**, not automatic promotion into any historic person master.

## Local audit

Requirements (from earlier successful steps):
- official WC2018 entry/result pilot manifest, full 59-row joined CSV,
  four-page source inventory under
  `output/frame/isu_wc2018_pilot_v1/`;
- `data/historic/v4/couples_v4.csv` (553 original pairs) and
  `data/historic/v4/event_inventory_v4.csv`;
- `output/historic_dob/cross_era_identity/ambiguity_source_v3/`
  historical person/pair previews (865 slots / 514 pair groups);
- `output/master/season_roster.csv` (1,584 rows);
- `output/historic_dob/cross_era_identity/modern_profile_v4/`
  reviewed modern-person-ID projection.

Run from `C:\chenxi\bazi_project\doubles`, each command on its own
single PowerShell line:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\audit_wc2018_identity_bridge_v1.py

No network fetch is required: all source inputs are the existing
local files. Seven synthetic-data regression tests (built at full
59/553/514/865/1,584 record sizes) passed before the GitHub update;
the complete real-data audit still requires local execution.

## Outputs

Generated separately at `output/frame/isu_wc2018_identity_bridge_v1/`:

- `official_wc2018_identity_bridge_manifest_v1.json`:
  exact historical/modern source overlap counts, audit statuses, SHA256
  provenance and unmet identity constraints;
- `official_wc2018_historical_modern_pair_bridge_v1.csv`:
  all 59 official pair entries/results, old pair-ID and canonical
  historian-person candidate links, modern rankings/profile source
  leads, and whether each needs an identity review;
- `official_wc2018_nonmatching_historical_pairs_review_v1.csv`:
  only new pair-combination candidates;
- `official_wc2018_new_event_observations_preview_v1.csv`:
  all 59 independent event observations, retaining original official
  names, profile IDs, result status, interpretation, rank, score
  and separate source URLs.

The code refuses to merge if 2018 Worlds already exists in the historic
event inventory, if old pair IDs are not preserved, if an official
source page hash changes, if a source result status loses the FNR-score
semantics, or if multiple modern canonical IDs conflict. No new
event pair score is added to the historical master.

## Next

After the local crosswalk run, adjudicate only new pair combinations
and any profile-ID/published-name disagreements. Then design an
immutable event extension with unique (`event_id`,`isu_profile_id`)
source keys before calculating a hypothetical new historical
event-observation count. Lock the event sampling frame without looking
at career performance, BaZi features, or compatibility outcomes.

**Return** the bridge manifest and the nonmatching historical pair
review CSV. If a modern ID conflict appears, return those rows too.
