# ISU ranked-pair cohort QA (candidate, not frozen)

Use the 2018–19 to 2025–26 ISU season-ranking data as a bounded cohort.
In the latest DOB coverage audit, 1,038 canonical athletes have a usable DOB,
612 distinct ranked pairs have both DOBs, and 1,584 pair-season-level ranking
rows have both DOBs. These are audit totals, not general-population estimates.

The cohort has **two different observational units**:

- isu_ranked_pairs_candidate_v1.csv: one observation per canonical pair
  (not per competition or season). This is the pair-level structural candidate.
- isu_ranked_pair_seasons_candidate_v1.csv: one observation per
  pair-season-level ranking appearance. This file retains rank and ranking
  points within a season. Do not use its row count as independent pairs.

**Do not treat distinct pairs as independent athletes:** one skater can partner
with multiple others, even if all pairs are unique. The script emits
isu_multi_partner_athletes_v1.csv and reports how many people and pairs share
members. Any later null model must account for repeated athletes and season,
country, age, and discipline participation structure before hypotheses are
locked.

Run from the project directory after the supplemented identity and DOB steps:

    python .\scripts\build_isu_ranked_cohort.py

The outputs are all under ignored output/cohort/ (do not commit those tables).
The small isu_ranked_cohort_candidate_manifest_v1.json records exact input
and output SHA-256 digests for reproducibility, and the row counts for both
observational units.

The generator exits nonzero if any DOB is missing or conflicted, a person
reference is missing, a pair changes identities across seasons, a pair is
duplicated in the same season/level, or ranking evidence URLs are absent. It
does not request external data or overwrite existing datasets.

**Important before data freeze:** separately audit missing historical entrants
(from 2004–2018 event results and unranked junior/national events), residual
cross-profile name variants, and the pair-selection/null model. DOB completeness
inside rankings cannot establish coverage of all entrants. We have not computed
BaZi or tested an outcome association in this candidate cohort.
