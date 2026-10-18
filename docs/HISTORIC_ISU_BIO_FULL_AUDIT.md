# Historical ISU biography audit: full 477-profile pass

## Source outputs (user's local collector, 2026-10-17)

- 477 of 477 official pair biographies downloaded and cached (77 cache hits).
- 950 of 954 athlete positions had an exact DOB-label binding.
- 814 unique *provisional historic athlete IDs* appeared in these sources.
- Ten review rows: four rotated given/family-name order, two hyphen/space
  variants, two unfilled official birthdate fields, two contradictory
  birthdates attached to **one erroneous provisional identity**.
- The parent historical v4 dataset still has 910 provisional athlete IDs.
  Counts of unique people are not frozen.

### Corrections and evidence

* Antonio SOUZA-KORDEIRU (1993-03-21) and Simon PROULX-SENECAL
  (1991-12-06) are printed as SOUZA KORDEIRU / PROULX SENECAL without
  hyphens in official profiles isufs00101795 and isufs00054773. The
  parser now recognizes identical tokens separated by hyphen OR space,
  labels them punctuation_variant_review and does not silently promote
  those dates into a final cohort.
* The 2006 PRK pairs profile isufs00009336 genuinely has empty DOB
  fields for both skaters. PHYO Yong Myong's DOB (1989-11-26) is shown
  independently on official ISU singles biography isufs00009337
  and later ice-dance biography isufs00104674.
* JONG Yong Hyok's DOB (1988-01-03) is listed by Olympedia in athlete
  profile 109744, but his ISU pair biography has no DOB: classify this
  as an independently corroborated identity and a **secondary DOB lead**,
  not an ISU-official DOB. The source tiers are recorded separately in
  data/adjudications/isu_historic_external_dob_leads_v1.csv.
* The apparent Arina USHAKOVA cross-profile date conflict is actually
  two different athletes wrongly collapsed by the historical name-only
  ID. Pair skater Arina USHAKOVA (1989-12-18, ISU isufs00008744,
  partner Sergei KAREV) and ice dancer Arina USHAKOVA (2002-06-27,
  ISU isufs00101140, partner Maxim NEKRASOV) are different persons.

The two profile/side-specific homonym identity adjudications are stored
in data/adjudications/isu_historic_homonym_splits_v1.csv. No existing
historical person ID is destroyed, and no other name is automatically
split because of a different date.

## Local steps

Run the collector offline against all 477 cached pair profiles:

    python .\scripts\collect_historic_isu_biographies.py --limit 0 --offline

Then run the independent, non-destructive identity audit:

    python .\scripts\audit_historic_identity_collisions.py

It checks the official reviewed split rules against source DOB, member side,
original pair ID and discipline, and produces under output/historic_dob/identity/:

- historic_identity_manifest.json: profile slots and source/audited IDs;
- historic_source_identity_links.csv: one row per profile/person slot with
  original and reviewed identity;
- historic_audited_people.csv: one row per provisional *audit identity*
  including DOB only if all source dates agree and name parsing is strict;
- historic_identity_review.csv: punctuation/name-order, missing DOB,
  identity mismatch or remaining conflicts.

Expected pending local confirmation: 952/954 DOB fields parsed after the
hyphen fix, 476/477 full-pair DOBs, and 815 audited provisional people
instead of the prior 814 merged IDs. The official blank pair may still
require alternate-source supplementation. These are NOT verified run
results until the user executes the local pipeline.

The historical data use selected ISU events, not a census of every skater.
Incomplete or ambiguous source records remain in the audit; no BaZi,
partner compatibility statistic or zero model is computed.
