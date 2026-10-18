# 2004–2018 historical ISU DOB coverage: consolidated audit v1

This is a **data-collection audit**, not a statistical sample freeze.
Do NOT apply BaZi, partner compatibility scores, selection based on
significance, or a randomized null model in this phase.

## Why we need this audit now

The selected historic ISU event dataset has 910 original provisional skater IDs
and 553 provisional pair IDs. ISU official biography index lookup yielded:

- 477 couples with exact two-name index match. Their biography sources
  created 815 provisional audited identities after **one confirmed two-person
  homonym split** (Arina USHAKOVA). The latest approved name-variant audit
  reports 813 official DOB candidates, two blank legacy DOB fields.
- 76 historical pairs did not exactly match index names; 28 pairs have source
  correlated names or separately reviewed official biographies and 48 are
  still identity candidates.
- 56 official DOB source records from the 28 linked pairs involve only 52
  different original historic IDs (some skaters have multiple partners).
- Two other pairs map multiple original provisional person IDs to the
  *same* published ISU couple profile side: Alexa SCIMECA / Alexa
  SCIMECA KNIERIM and Feder/Fedor SOKOLOV. These are NOT silently merged.

We must find the actual *union* of IDs with source-backed DOBs instead of
adding 813 + 52 as if they were disjoint.

## Local execution

After pulling the repository, run:

    python .\scripts\audit_historic_dob_coverage.py

Required preexisting local files:
- output/historic_dob/identity/historic_audited_people.csv
- output/historic_dob/alias_pair_identity/historic_alias_correlated_dob_leads.csv
- output/historic_dob/alias_pair_identity/historic_alias_unresolved_pair_review.csv
- output/historic_dob/alias_pair_identity/historic_alias_profile_side_collisions.csv
- output/historic_dob/historic_identity_dob_candidates.csv (prior 2018+
  same-couple surname/identity lead audit)

All other inputs are versioned in the repository:
- data/historic/v4/athletes_v4.csv (910 tentative original IDs)
- data/historic/v4/couples_v4.csv (553 pairs)
- data/adjudications/isu_historic_primary_dob_seed_v2.csv (35 manually checked)
- data/adjudications/isu_historic_external_dob_leads_v1.csv (PHYO official
  singles biography, JONG Olympedia secondary DOB lead)

The script requires all inputs to exist; a missing file is an error,
**not** automatically an empty source. No network is accessed. Input
SHA-256s are retained in the output manifest; masters are never modified.

## Strict and expanded DOB tiers

1. **Official source-linked candidate:** DOB bound to the officially
   published person's historical profile, an explicitly reviewed
   official identity alias/partner, or an independently inspected ISU
   seed biography. We require dates to agree across sources.
2. **Ranked same-pair-only candidate:** DOB carried from a verified
   2018+ ISU person in a unique exact-name same-partner cross-era
   match. It is **not promoted** into the primary tier without
   separate historical identity confirmation.
3. **Secondary-only candidate:** JONG Yong Hyok's DOB at Olympedia is
   tracked separately; it remains a lead, not an ISU official DOB.
4. **No DOB evidence:** source person ID still needs official DOB work.
5. **Source conflict:** any contradictory primary/cross-era DOB is
   held with both values for manual review, never silently resolved.

The script reports both original historic provisional IDs and audit identity
**slots**. With the one confirmed Arina homonym split there should be
911 slots before any separately reviewed alias merges; this is not a
certified independent-person count. Name changes like Feder/Fedor are still
two original IDs until corroborating profile-based merge adjudications
are explicitly approved. One skater can have multiple pair results, and
pairs with repeated members are not independent statistical observations.

## Local output files

Under output/historic_dob/coverage/:
- historic_dob_coverage_manifest_v1.json: source overlap and pair completeness;
- historic_dob_coverage_people_v1.csv: every provisional audit identity,
  source tiers, DOB candidates, review status, official URLs;
- historic_dob_missing_priority_v1.csv: missing primary DOBs ordered by
  number of identified historical partners;
- historic_dob_coverage_pairs_v1.csv: all 553 pairs, with strict/expanded
  DOB coverage and provisional identity lineage;
- historic_dob_source_conflicts_v1.csv: all conflicting source dates;
- historic_unresolved_pair_dob_v1.csv: 48 unresolved identity pairs,
  including DOB completeness despite the unverified pair linkage;
- historic_candidate_duplicate_ids_v1.csv: two same-profile-side
  duplicate-ID candidates, not automatically merged.

All outputs are local and ignored by Git; upload only the small manifest,
missing-priority list (or its first section), and conflicts/review data to
continue. Never publish a proposed pair-null before DOB collection closes.
