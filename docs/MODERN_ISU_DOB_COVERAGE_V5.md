# Modern ISU official-DOB coverage v5 — source audit, not a final roster

Date: 2026-10-18. The prior local runs confirmed a conservative
identity projection:

| Unit | Source | Reviewed preview |
|---|---:|---:|
| Historical audited person slots | 911 | 865 |
| Historical distinct pair groups | 553 | 514 |
| Modern standardized name IDs | 1,050 | 1,036 |
| Modern pair-name groups | 622 | 612 |
| Historical-modern candidate edges | 190 | 183 |

All 1,584 season ranking records and 553 historic original pair IDs
remain in their respective source files. These numbers are **not a
census of independently verified people**.

The modern-profile-v4 audit closed 12 same-ISU-profile-side duplicate-ID
groups using six earlier and eight additional manually source-reviewed
alias edges. Closing this specific queue does NOT prove that every modern
skater has an official DOB, nor that cross-profile partner changes are
fully linked.

## Additional cross-discipline exception

Exactly one original modern name ID appears in both Ice Dance and Pair
Skating: Alex LAPSKY, ID person_91c889ad86ae8.

Two public official ISU biographies substantiate that he is one athlete:

- https://results.isu.org/bios/isufs00111279.htm
  (Sophia BUSHELL / Alex LAPSKY, Ice Dance; DOB 09.03.2003)
- https://www.isuresults.com/bios/isufs00119902.htm
  (Zarah WOOD / Alex LAPSKY, Pair Skating; DOB 09.03.2003;
  explicitly identifies Sophia BUSHELL as former partner)

This confirmation is recorded independently in:

    data/adjudications/isu_modern_cross_discipline_skater_v1.csv

Name-hash identity across disciplines is never automatically treated
as proof in general. Other future cross-discipline collisions must be
held for source-specific review.

## v5 audit inputs

- output/master/season_roster.csv — original 1,584 modern ranking rows.
- output/bios/birth_candidates.csv — full local ISU biography extraction;
  use the existing local file rather than the older 100-row pilot upload.
- data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv —
  six official modern alias relations, one historic relation.
- data/adjudications/isu_modern_same_profile_aliases_v1.csv —
  eight additional official modern profile-side alias relations.
- data/adjudications/isu_cross_era_modern_bio_dob_rescues_v1.csv —
  eight manually curated missing-modern-date source links.
- data/adjudications/isu_modern_cross_discipline_skater_v1.csv —
  Alex LAPSKY dual-discipline evidence.
- output/historic_dob/cross_era_identity/modern_profile_v4/
  modern_profile_alias_source_manifest_v4.json — current source roster
  SHA256 and reviewed modern canonical name-ID count.

The script only promotes a biography DOB when it has an official
profile matching the exact original roster member ID and profile side.
Eight explicitly source-reviewed name-variant DOB rescue rows are kept
separately, with origin labels and URLs. Multiple inconsistent dates
remain on HOLD; none is silently selected. Missing DOB does not mean
the skater has no public birth record.

## Commands (each is one PowerShell line)

From C:\chenxi\bazi_project\doubles:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_modern_source_dob_coverage_v5.py
    python .\scripts\audit_historic_alias_event_collisions_v1.py --preview .\output\historic_dob\cross_era_identity\ambiguity_source_v3\historical_source_reviewed_pair_preview_v3.csv --out .\output\historic_dob\cross_era_identity\ambiguity_source_v3\event_collision_audit

The fourth command repeats the historical event-collision QA under the
final currently reviewed historic 865/514 identity preview. The
2026-10-18 uploads did NOT include that latest event-collision
manifest; an older v1 collision result is not a substitute.

## Output files

The v5 DOB audit writes under output/historic_dob/modern_dob_coverage_v5/:

- modern_dob_coverage_manifest_v5.json
- modern_canonical_dob_coverage_v5.csv
- modern_dob_missing_and_conflicts_v5.csv
- modern_biography_source_rejections_v5.csv
- modern_biography_profile_side_gaps_v5.csv

Send the v5 DOB manifest and missing/conflict queue, plus latest v3
historical event collision manifest. Send the biography-source
rejections CSV if any unexpected invalid or conflicting rows appear.

The next source-review work should be based on **actual modern DOB
missing and conflict counts**, not assumed from the 183 cross-era
edges. All novel sources remain explicit manual adjudication leads.
Ranking points, event scores, compatibility predictions, BaZi features,
null models and performance-based cohort selection are out of scope.
