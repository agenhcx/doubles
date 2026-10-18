# ISU athlete identity and birthdate audit (v1)

The original ISU observations and provisional identifiers are immutable. Reviewed
identity links are scoped to official **couple profile ID + skater side**. No
fuzzy global name matching, BaZi calculation or geographic inference occurs.

## Audited roster

- 1,584 season-ranking rows from 2018–19 through 2025–26.
- 597 linked ISU couple profile IDs.
- 1,050 original name-derived roster IDs.
- 12 reviewed name-ID split mappings, across 10 ISU profiles, are in
  data/adjudications/isu_profile_id_splits_v1.csv.
- Applying these 12 mappings yields 1,038 **provisional canonical roster IDs**.
  This is not a count of all historical athletes and does not prove no other
  spelling-based duplicates exist.
- Six source-reviewed Biography/roster name mismatches are recorded in
  data/adjudications/isu_bio_name_links_v1.csv, without creating new person IDs.
- Min CHOE, formerly an unmatched seventh row, was repaired by the parser
  update for biographies without a Place of birth field.
- 31 ranking records have no ISU profile URL; at least 24 provisional athlete
  IDs lack any linked profile URL in the ranked seasons.

ISU biographies expressly document the 2019 marriage-related variants Ashley
CAIN / CAIN-GRIBBLE and Jennifer URBAN / JANSE VAN RENSBURG. For the Ukrainian
transliteration changes, the official couple profile ID, member side and
partner relationship permit conservative identity linking. The small source
tables preserve both names, old/new identifiers, official URLs, and evidence
notes. Source-correlated does not mean the original master has been edited.

## Run the identity audit locally

After locally collecting all 597 biographies, run the following single
PowerShell command from C:\chenxi\bazi_project\doubles:

    python .\scripts\audit_isu_identities.py --roster .\output\master\season_roster.csv --births .\output\bios\birth_candidates.csv

Local files written to output/identity/ (excluded from Git):

| File | Description |
| --- | --- |
| identity_audit_manifest.json | Totals, SHA-256 input hashes and limitations |
| identity_birth_links.csv | Profile-side to canonical ID and link status |
| identity_unresolved.csv | Unmatched, ambiguous or invalid DOB links |
| identity_dob_conflicts.csv | Conflicting DOB observations for same canonical person |
| identity_canonical_people.csv | Per-person DOB only when linked official dates agree |
| identity_canonical_season_roster.csv | Enriched **copy**, original plus canonical IDs |

The script never overwrites season_roster.csv, birth_candidates.csv or
athletes_master.csv, never downloads anything, and never treats a ranking
position as an event score.

## Audit invariants

1. Each biography row is linked through its official profile ID and side.
2. Source-reviewed name aliases require exact published-name and DOB checks
   against the local biography data before being assigned.
3. Split aliases must match the exact two roster IDs and their published names
   on that official profile side. Unresolved side ambiguity stays unresolved.
4. Conflicting DOBs from different profiles are reported and the affected
   canonical person's date is left blank.
5. Raw birthplaces (34 missing in the latest 1,194-row collector summary)
   must not be replaced by represented nation or inferred hemisphere.
6. Matching DOB or spelling on *different* profile IDs is not enough to
   automatically merge athlete identities.
7. These outputs are provisional research evidence, not a frozen statistical
   cohort. Finish missingness and identity QA before hypothesis testing.

To continue in chat without uploading the full 1,194-row data, share only
identity_audit_manifest.json plus identity_dob_conflicts.csv and
identity_unresolved.csv if they contain rows.

## Official supplemental DOB sources (October 2026)

After the baseline audit, the 24 people without an ISU Biography hyperlink
were independently traced to official DOB sources. The small reviewed evidence
file data/adjudications/isu_supplemental_dobs_v1.csv stores their canonical
person IDs, complete DOBs, names as printed, official URLs, identity links
and source types:

- 22 DOBs from ISU biographies or ISU individual/pair skater profiles.
- 1 DOB for Anatoliy BELOVODCHENKO (2000-01-31) from the Moscow Figure
  Skating Federation's 2020 championships entry list. It names his partner
  Julia TULTSEVA (2001-06-04) on the adjacent line:
  https://ffkm.ru/images/files/020-21/2020-12-09/Partlist_ChM_2020.pdf
  (printed page 4; PDF page index 3).
- 1 DOB for Daniil RAGIMOV (1998-05-22) from the Russian Figure Skating
  Federation's signed 2015–16 national team roster, alongside previous
  partner Karolina KLIKICH:
  https://fsrussia.ru/files/docs/RUteam1516.pdf
  (printed page 14; PDF page index 13).

These two official federation records supersede earlier secondary leads.
No date from the athlete partner-search site, fan forum, or unofficial
compilation is accepted as the primary source. The official *new ISU pair*
pages for Julia TULTSEVA and Anastasia SHAKUN show one woman's DOB,
not the DOB of her male partner.

**Non-destructive local workflow** (run from the repository root):

    python .\scripts\apply_isu_supplemental_dobs.py

Then recompute pair/season coverage against the supplemented copy:

    python .\scripts\report_isu_dob_coverage.py --people .\output\identity\supplemental\identity_canonical_people_supplemented.csv --out .\output\identity\supplemental

Output under output/identity/supplemental/ is local-only, and the original
canonical people CSV remains unchanged. Review supplemental_dob_manifest.json
and dob_coverage_manifest.json before concluding the final coverage.

**Expected, not yet locally verified:** 24 supplemental DOB additions,
1,038/1,038 canonical ranked athletes with DOB, and 612/612 ranked canonical
pairs with both DOBs. The complete DOB coverage, even if achieved, does
not mean the ranking corpus covers all ISU entrants, domestic skaters,
or historical figure skaters. Independent DOB source confirmation and
identity QA are still sampling prerequisites.
