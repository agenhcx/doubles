# Doubles competition-frame audit v1 — events are not rankings

2026-10-18. This is an evidence-based **sampling frame audit**, not a
preregistered final cohort and not a BaZi calculation.

## Verified starting point

The user's most recent local v6 manifest confirms 1,036/1,036 modern
reviewed name-ID slots have source-linked DOB evidence, with zero
unresolved date conflicts (27 new ISU-source records, one national
federation-source record). The latest historical-v3 pair/event collision
manifest confirms 3,237 original pair-event rows and zero collisions
under the 865-person/514-couple reversible identity preview.

These successful QA checks do **not** establish coverage of all ISU event
entrants.

The historic v4 event inventory contains 135 known tournament instances,
270 discipline-specific competition events and 3,237 pair-event records
from **selected** adult events across 2003-04 through 2017-18.

The present series families (across the entire historical file) are:
- 78 Grand Prix Series tournaments, 13 Grand Prix Finals;
- 14 World Championships, 13 European Championships,
  13 Four Continents Championships;
- 4 Olympic Winter Games figure-skating tournaments.

The first two historical seasons, 2003-04 and 2004-05, contain only the
World Championships. A careful event-code parser must treat
`gpfraYYYY` as Grand Prix **France**, not Grand Prix Final (`gpfYYZZ`).

### Verified historical gap: World Championships Milan 2018

The existing historic v4 inventory lists 2017-18 Olympic Winter Games
but **does not list the 2018 World Championships** in either discipline.

ISU primary official entries:
- Ice Dance, 31 published pairs:
  https://results.isu.org/results/season1718/wc2018/CAT004EN.HTM
- Pair Skating, 28 published pairs:
  https://results.isu.org/results/season1718/wc2018/CAT003EN.HTM
- Event index:
  https://results.isu.org/results/season1718/wc2018/index.htm

These **59 event entries are currently unrepresented**, not necessarily
59 previously unseen natural pairs, nor 59 skaters, nor 59 graded results.
Official start/entry, withdrawal and result status must remain distinct.
The gap is recorded as a versioned *source observation* at
`data/frame/isu_verified_entry_gaps_v1.csv`. This file changes no
existing event or identity rows.

### Modern rank-only sample and the 2020-21 issue

Modern input is 1,584 **ISU Season's World Ranking** rows for
2018-19 to 2025-26 (senior rows every season; independent junior pages
only 2023-24 onward in this specific collection). There are 1,309
senior and 275 junior ranking rows; these are not event start lists.
The historic data have no corresponding broad junior event frame.

2020-21 has 20 ranked Ice Dance pairs and 20 ranked Pair Skating pairs;
that small list reflects severe COVID disruptions and altered points
eligibility, not evidence of a proportionate decline in active athletes.
See original ISU ranking pages under
https://results.isu.org/ws/wr2020-21/ and ISU's 2020 council notice
https://isu-d8g8b4b7ece7aphs.a03.azurefd.net/isuproduction/uploads/images/decisionsoftheisucouncil/Decisions_of_the_Council_10.12.20.pdf

The current official calendar also lists championship, senior GP,
Junior GP and Challenger events missing from the *rankings-only*
activity proxy:
https://isu-skating.com/en/figure-skating/events/?season=2025%2F2026

## Reproducible offline audit

From `C:\chenxi\bazi_project\doubles`, use each as one PowerShell command:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\audit_competition_frame_v1.py

Required source inputs:
- `data/historic/v4/event_inventory_v4.csv`
- `data/historic/v4/season_coverage_v4.csv`
- `output/master/season_roster.csv`
- `output/historic_dob/cross_era_identity/ambiguity_source_v3/event_collision_audit/historic_alias_event_collision_manifest_v1.json`
- `output/historic_dob/modern_dob_rescue_v6/modern_official_dob_rescue_manifest_v6.json`
- `data/frame/isu_verified_entry_gaps_v1.csv`

Expected outputs under `output/competition_frame_audit_v1/`:
- `competition_frame_audit_manifest_v1.json`
- `historical_selected_event_frame_v1.csv`
- `historical_event_family_inventory_v1.csv`
- `modern_rankings_source_frame_v1.csv`
- `official_event_gap_review_v1.csv`

The code was compiled locally and six offline synthetic regression
tests passed before commit. Actual full dataset output still requires
execution on the user's local repository and review of its manifest.

## Next *separate* acquisition experiment

1. First ingest the two verified 2018 Milan Worlds **official entries**
   into an immutable, original-name and source-URL record table.
2. Fetch the corresponding Results pages, separately recording actual
   ranked, final-not-reached, withdrawn and entry-only states. Never
   assume ranking points measure one specific event.
3. Link to reviewed identities via reversible mappings; hold unresolved
   aliases. Do not merge or mutate the 3,237-row original v4 file.
4. Before claiming any quantitative coverage %, enumerate an **official
   target event universe** for a declared season, event class and
   discipline, with a source inventory of actual event pages.
5. Prefer event-first, all entrants (including non-scoring/unranked)
   to a ranking-score-threshold cohort. Explicitly stratify year,
   discipline, senior/junior and competition family. Treat 2020-21 as
   a structural pandemic exception.
6. Preregister scientific hypotheses only after the selection
   mechanism and holdout framework are locked, without inspecting
   BaZi features or outcome-dependent sample inclusion.

**Return** `competition_frame_audit_manifest_v1.json` and
`official_event_gap_review_v1.csv` for review; a full 2018 Milan
entry-ingestion pilot can then be built from the audited fixed source
frame.

This project phase must not compute astrological compatibility,
statistical significance, career score-based selection or new hypotheses.
