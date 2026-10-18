# Modern 28-gap official-DOB source review v6 (2026-10-18)

This is an explicit **source-augmented DOB preview**, not a frozen scientific
cohort or a claim that 1,036 identifiers are independently verified people.

## Baseline

The locally uploaded modern v5 audit found:

- 1,584 season-ranking observations
- 1,050 raw provisional modern skater name IDs
- 14 reviewed name-ID aliases; 1,036 canonical modern name-ID slots
- 1,008 original source-linked DOB slots (97.2973%)
- 28 missing official DOB slots, zero source-date conflicts
- 23 missing the ranking's biography link, five nonexact Biography
  name/ID matches; there was a sixth rejected biography side (Korovin)
  which already had acceptable independent modern ISU date evidence.

The 28 source gaps have been manually researched without editing original
season rankings or source Biography files. Each is keyed to the v5
canonical name ID, original roster name/partner/member side, official
printed name, ISO date, original source URL, optional contextual source URL,
source-tier classification and reviewer note in:

    data/adjudications/isu_modern_dob_official_missing_rescues_v6.csv

**27 source rows are ISU biographies** (same-pair, prior-partner,
prior single-skater, official published variant or direct old profile).
One person, Daniil RAGIMOV, has a distinct official national federation
source tier.

## Source caveats, preserved rather than concealed

- **Daniil RAGIMOV**: the Russian figure skating federation's signed
  2015–16 national squad PDF lists Рагимов Даниил Алексеевич,
  22.05.1998, Samara squad affiliation. Its 2017–18
  official competition protocol lists Anastasia SHAKUN/Daniil RAGIMOV
  in the same Samara region/training context; ISU separately lists the
  Shakun/Ragimov couple. This is labeled
  NATIONAL_FEDERATION_ROSTER_PLUS_COMPETITION, NOT an ISU DOB biography
  nor an independent replication.
    https://fsrussia.ru/files/docs/RUteam1516.pdf
    https://fsrussia.ru/files/docs/competitons/1718/1etap1718_protocol_revised.pdf
- **Katharina MUELLER**: official ISU page
  katharina-mueller-tim-dieck/ gives 12.09.1995, with Tim DIECK.
  The other ISU profile currently displays Katharina ABERT for the same
  exact Tim DIECK team/profile, with legacy Mueller/Dieck contacts and
  biographical text. No legal name-change reason was inferred.
- **Liubov EFIMENKO**: earlier ISU singles bio provides DOB 20.06.1999;
  official later partner page URL identifies Liubov Efimenko/Dmitry
  Epstein though the current page name display is Liubov AHO.
  These are preserved as linked historical published labels.
- **Anastasiia SAMMEL** and **Danylo YEFREMENKO**: each historical ISU
  Biography lists a **different former partner**. Their 2021–22 ranking
  shows them together; do not pretend the historical biography itself
  lists the new ranking pair.
- Where two ISU hosts point to the same original profile, this is one
  source, not independent DOB replication.
- **Karina AKAPOVA** appears as AKOPOVA in ISU historical profiles.

## Offline v6 workflow

From C:\chenxi\bazi_project\doubles, run one PowerShell line at a time:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\audit_modern_official_dob_rescue_v6.py

The script requires the previously generated v5 manifest, canonical DOB
coverage CSV, missing/conflict CSV and original modern season roster.
It checks the modern ranking SHA against v5, exact existing v5 missing
IDs, original roster member and partner relationships, date format,
source URI host/path and explicit curator notes. It refuses changes
to known DOBs or gaps not in the reviewed v5 missing queue.

It does NOT re-fetch primary evidence URLs while running offline,
and it does NOT overwrite the modern v5 outputs or an original master.

Expected new folder: output/historic_dob/modern_dob_rescue_v6/

- modern_official_dob_rescue_manifest_v6.json
- modern_official_dob_rescue_adjudication_v6.csv (28 sources; official
  source tier and offline-check status, including federation)
- modern_canonical_dob_source_augmented_v6.csv (1,036 original canonical
  name IDs, newly attached DOB sources and explicit provenance)

If the user's source files are unchanged and all 28 adjudications pass,
v6 PREVIEW projects 1,036/1,036 dated name-ID slots, with zero missing
DOBs and zero held DOB-date conflicts. **This is source-coverage
completeness for a defined 1,584 ranking-row dataset, NOT a census
of worldwide event entrants or of natural persons.** The historical
2004–18 cohort has distinct sampling limitations.

## Next separate audit

The historical latest v3 projected pair preview (865 person slots /
514 pair groups) must still be checked for event collision after
the cross-partner Antonino/Antonio review, rather than assuming an old
3,237-event audit covers new identity mappings:

    python .\scripts\audit_historic_alias_event_collisions_v1.py --preview .\output\historic_dob\cross_era_identity\ambiguity_source_v3\historical_source_reviewed_pair_preview_v3.csv --out .\output\historic_dob\cross_era_identity\ambiguity_source_v3\event_collision_audit

Return the two local manifests (v6 DOB, v3 event collision), and any
unexpected test failure or source-review exception. Only after this
should we decide the next event-start-list coverage and sampling
plan. Never use career scores, BaZi features or performance signals
to approve identities.
