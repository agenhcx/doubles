# ISU modern profile-side alias consolidation v4 — source-reviewed QA

## Why this follows cross-era v3

The 2026-10-18 source-backed historical-modern v3 audit resolves 7
known ambiguous candidate graph components: six modern name-ID aliases
and one historic cross-partner identity. It is a conservative
candidate-graph preview, NOT a frozen study sample.

A broader offline scan of the original 1,584 modern season-ranking
rows reveals **12 separate cases** where the SAME ISU biography
profile ID, SAME member side, and different season rows have distinct
provisional person-name IDs. Four were already source-reviewed as part
of cross-era v3 (SORENSEN/SOERENSEN, Maxim/Maksym NIKITIN,
SOUQUET/SOUQUET-BASIEGE, CAIN/CAIN-GRIBBLE). Two other v3 modern
aliases (Alexa KNIERIM and Aleksandr KOROVIN) involve distinct
official couple biographies, so they did not trigger this test.

Eight further modern-side aliases were found and verified against
the corresponding official ISU biographies and published dates.

| Earlier season name | ISU canonical published name | Official DOB | Official profile |
|---|---|---|---|
| Alexandra NAZAROVA | Oleksandra NAZAROVA | 1996-11-30 | isufs00012757 |
| Maria GOLUBTSOVA | Mariia HOLUBTSOVA | 2000-12-20 | isufs00014925 |
| Kirill BELOBROV | Kyryl BIELOBROV | 2000-11-29 | isufs00014925 |
| Jennifer URBAN | Jennifer JANSE VAN RENSBURG | 1993-05-09 | isufs00102043 |
| Georgy REVIYA | Giorgi REVIA | 1999-04-03 | isufs00103257 |
| Lou TERREAU | Lou TERREAUX | 2002-04-14 | isufs00103664 |
| Elizaveta ZHUK | Jelizaveta ZUKOVA | 2003-11-02 | isufs00109976 |
| Anastasia GOLUBEVA | Anastasiia GOLUBEVA | 2006-01-03 | isufs00111143 |

The official Jennifer Janse van Rensburg biography explicitly says
she got married in December 2019 and retained Benjamin STEFFAN as
the partner in the same ISU couple profile. The remaining changes are
orthographic/transliteration variants or published surname differences.
DO NOT assume all ISU profile ID equivalence is identity proof in
general; these eight links received explicit source-level review.

Versioned source-only decisions:

    data/adjudications/isu_modern_same_profile_aliases_v1.csv

## Commands (each exactly one line in PowerShell)

From C:\chenxi\bazi_project\doubles:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_cross_era_source_ambiguity_v3.py
    python .\scripts\audit_modern_isu_same_profile_alias_v4.py
    python .\scripts\audit_historic_alias_event_collisions_v1.py --preview .\output\historic_dob\cross_era_identity\ambiguity_source_v3\historical_source_reviewed_pair_preview_v3.csv --out .\output\historic_dob\cross_era_identity\ambiguity_source_v3\event_collision_audit

Prerequisites: historical-v2 reviewed person/pair previews,
historical-v2 source-augmented 190-edge CSV and DOB rescue manifest,
modern season_roster.csv, and the GitHub adjudication tables.
The v4 script additionally requires the completed v3 projected
cross-era manifest and candidate-edge CSV. It refuses stale source
rankings, unreviewed or misassigned profile-side aliases, and any
new profile-side collision not covered by a source-reviewed rule.

## Expected output, pending full local confirmation

Under output/historic_dob/cross_era_identity/modern_profile_v4/:

- modern_profile_alias_source_manifest_v4.json
- modern_same_profile_collision_review_v1.csv
- modern_source_reviewed_person_id_projection_v4.csv
- modern_source_reviewed_pair_preview_v4.csv
- cross_era_modern_alias_source_preview_v4.csv

Static direct calculations with the previously uploaded 1,584-row
ranking CSV and the 14 source-reviewed modern ID mappings yield:

| Measurement | Original | Modern v4 expectation |
|---|---:|---:|
| provisional modern name IDs | 1,050 | 1,036 |
| provisional modern pair-name groups | 622 | 612 |
| source ranking rows | 1,584 | 1,584 |
| cross-era historical-modern candidate edges | 190 raw | 183 v3+v4 grouped leads |

The modern projection preserves all original pair IDs, published
names, seasons and source profiles. It NEVER adds season-ranking
points or interprets ranking rows as event participation.

The historical v3 alias projection still requires a separate
event-collision rerun. Even with these modern name-ID resolutions,
cross-profile aliases or same-name homonyms may exist. All counts
remain QA previews, not verified independent natural-person totals,
and are not a basis to freeze a BaZi cohort or design outcome tests.

## Files to share back

- ambiguity_source_v3/cross_era_source_reviewed_identity_manifest_v1.json
- ambiguity_source_v3/event_collision_audit/historic_alias_event_collision_manifest_v1.json
- modern_profile_v4/modern_profile_alias_source_manifest_v4.json
- modern_profile_v4/modern_same_profile_collision_review_v1.csv

Also share the actual historical-v2
shared_partner_identity/initial_only_v2/historic_initial_only_v2_manifest.json
if not yet supplied, as the prior attached
historic_shared_partner_alias_manifest_v1(3).json still represented
the old 878-slot stage.
