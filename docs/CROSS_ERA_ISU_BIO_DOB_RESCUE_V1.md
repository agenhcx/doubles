# Cross-era ISU Biography DOB rescue v1 — audit-not-merge

## What was observed

The 2026-10-18 cross-era manifest contains 878 historic provisional
identity slots and 1,584 modern Season's World Ranking rows. It returns
195 candidate identity edges involving 189 historic slots and 189
modern discipline slots. Of the 195 edges, 187 had modern ISU biography
day-level DOB evidence agreeing with historic audited DOBs and 8 had
a missing modern date. Zero modern DOB conflicts were reported.

The 8 missing modern dates were caused by ISU-published name variants
or a modern roster without a biography URL. They are not proof that
these people lack a publicly available birthday. We searched official
ISU profile pages and curated a versioned 8-row source ledger at:

    data/adjudications/isu_cross_era_modern_bio_dob_rescues_v1.csv

The ledger records exact audited old/modern IDs, roster member and
partner names, which of the two profile members holds the DOB, ISO date,
printed official name, an ISU primary URL, an optional contextual ISU URL,
and a reviewer note. Several contextual pages identify old partnerships
but are not independent birthdate measurements.

Specific cases:
- Jennifer URBAN: modern duo profile uses Jennifer JANSE VAN RENSBURG,
  gives 1993-05-09 and lists Sevan LERCHE as a previous partner. The
  official ISU historic index links Jennifer URBAN to both Sevan LERCHE
  and Benjamin STEFFAN.
- Alexandra NAZAROVA / Maxim NIKITIN: the present ISU pair bio uses
  Oleksandra / Maksym and gives dates 1996-11-30 / 1994-10-05.
- Nikolaj SORENSEN: official couple bio prints SOERENSEN, 1989-02-18.
- Alla LOBODA: 2018-19 pair with Anton SHIBNEV has an official ISU
  profile, 1998-12-10, despite a blank ranking profile_url.
- Pierre SOUQUET: official duo profile prints SOUQUET-BASIEGE and lists
  earlier partner Lorenza ALESSANDRINI; DOB 1994-07-18.
- Alexander KOROVIN: EFIMOVA pair biography prints Aleksandr KOROVIN,
  1994-02-15.
- Ashley CAIN: LEDUC pair biography prints CAIN-GRIBBLE, 1995-07-22,
  plus the former Joshua REAGAN partnership.

## How to run

From C:\chenxi\bazi_project\doubles, after pulling the main branch:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_cross_era_bio_rescues_v1.py

The audit takes the **existing** cross-era v1 review, v1 manifest and
exact same modern season_roster.csv, checks the cached SHA256 lineage and
all 8 curated source-to-roster mappings, and writes a separate preview:

    output/historic_dob/cross_era_identity/official_bio_rescue/historic_modern_identity_source_augmented_v1.csv
    output/historic_dob/cross_era_identity/official_bio_rescue/historic_modern_curated_bio_rescue_audit_v1.csv
    output/historic_dob/cross_era_identity/official_bio_rescue/historic_modern_bio_rescue_manifest_v1.json

Expected if the original 2026-10-18 inputs are unchanged: 8
source-reviewed date rescues, 0 missing DOBs among the **195 candidate
edges**, and unchanged 24 ambiguous candidate edges. 195 candidate
edges are not 195 verified people, and 0 missing *cross-era candidate*
DOBs does NOT imply all 1,050 modern provisional name IDs have DOBs.

## What this does not establish

- The script performs OFFLINE lineage checks; it does not re-download
  or independently inspect official website content at execution.
- Source-backed birth dates often come from the same ISU records
  already used for historical coverage; agreement is not independent
  replication.
- 12 multi-edge identity components (24 candidate edges) remain
  unresolved as independent-person counts. Do not collapse them by
  birthdate coincidence or name similarity alone.
- Original historic person and pair IDs, season-ranking rows,
  official source candidate files and all masters remain untouched.
- This is data QA, not cohort selection and not astrological analysis.
