# Historic ISU DOB follow-up after 477 official biographies

The local full-pool audit on 2026-10-17 reports 477/477 successfully cached
pair biographies, 952/954 explicitly labelled DOBs, 814 original historic
person IDs present, and 815 reviewed IDs after separating the two distinct
Arina USHAKOVA athletes. The separate identity audit reports:
807 identities with consistent directly parsed date evidence, six with
source-specific name variants still requiring approval, two with no DOB
on the old pair page, and zero conflicts after the homonym split.

## Six official name-variant adjudications

The file data/adjudications/isu_historic_name_variants_v1.csv includes six
source-reviewed entries, keyed by historic ID, ISU profile ID and person side.
Every entry also records the historical name, name printed on the original
ISU source, exact date, parser status and official biography URL.

- FUSAR POLI Barbara, 1972-02-06, isufs00000472, side 1.
- MARGAGLIO Maurizio, 1974-11-16, isufs00000472, side 2.
- McLAUGHLIN Keauna, 1992-09-25, isufs00009743, side 1.
- WANG Jiayue, 1988-04-14, isufs00011901, side 1.
- Antonio SOUZA-KORDEIRU, 1993-03-21, isufs00101795, side 2.
- Simon PROULX-SENECAL, 1991-12-06, isufs00054773, side 2.

All six were inspected against official ISU couple biographies (same
partner, role, exact day-level DOB). Their sources are the original official
pages, not an inferred year of birth or a similarity-only identity match.

The historical identity audit now approves ONLY those specific profile/side
observations when the original name, parsed official name, parse status and
DOB ALL match the adjudication table. Altering one of these fields leaves
the row unresolved. Its output records the approval flag and official URL.
The input collector/masters remain untouched.

Run locally after a normal Git pull:

    python .\scripts\audit_historic_identity_collisions.py

Expected but not locally re-run as part of this Git commit: the original
six name variants become source-approved, leaving only the two source rows
with missing DOB in the old PRK pair profile. The resulting historical
audited-person count remains 815; the DOB-consistent candidate count would
be 813, subject to local verification.

## Two old PRK pair skaters

PHYO Yong Myong has DOB 1989-11-26 on official ISU singles biography
https://results.isu.org/bios/isufs00009337.htm; the older 2006 pair
biography isufs00009336 omits the DOB for BOTH skaters.

JONG Yong Hyok has DOB 1988-01-03 on independent Olympedia record
https://www.olympedia.org/athletes/109744. This is a secondary-source
lead, NOT an ISU-profile verified date, and must remain flagged as
not primary-tier verified unless an official corroborating record appears.
No assumption of either birthday based on pair/season is acceptable.

## Remaining 76 historical pairs

The first official ISU directory audit had 477 exact-name pair matches,
65 one-partner-indexed pairs and 11 entirely unmatched pair names.
Run the *offline* directory lead generator:

    python .\scripts\audit_historic_isu_unmatched_pairs.py

It reads the previously downloaded ~2,007-line ISU directory CSV and the
553-row pair comparison CSV. It ranks up to five leads per as-yet-unmatched
historical pair based on an exact named partner or relatively similar pair
names within the same skating discipline.

Outputs under output/historic_dob/isu_index/alias_review/ are:
- historic_pair_alias_review_manifest.json (small summary);
- historic_pair_alias_review_candidates.csv (proposed links with BOTH
  name fields and URLs, all marked not_verified_candidate_only);
- historic_unmatched_pair_inventory.csv (each of the 76 pairs, including
  those with zero suggested official profiles).

Candidate identity links MUST be verified from official pair biographies,
partnership chronology, and any differing DOBs before the identity table
is amended. The resemblance score is a review-priority hint, not
statistical evidence, and cannot auto-fill birthdates.

No BaZi, partner scoring, calendar null, or athlete-pool null is computed.
Birthdate collection and identity QA remain separate from analysis design.
