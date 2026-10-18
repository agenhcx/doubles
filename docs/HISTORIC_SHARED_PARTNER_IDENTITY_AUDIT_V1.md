# Post-DOB identity QA: shared partner + same official birthdate

## Scope and boundaries

The latest 2004–2018 historical v4 audit has successfully reached
**911 / 911 audited identity slots with official DOB source candidates**
and **553 / 553 historical pairs with both members' DOBs**. The original
v4 source contains 910 *provisional name-based* IDs, including an Arina
USHAKOVA false same-name merge that has been **split into two distinct
people** (born 1989 and 2002).

DOB completeness is **not** the same as verified unique-person or
unique-couple identity counts. Do not freeze an analysis set or calculate
BaZi / compatibility / null-model outcomes at this phase.

## Why further historic alias detection is necessary

The ISU official profile-side collision audit surfaced Alexa SCIMECA
vs Alexa SCIMECA KNIERIM, and Feder vs Fedor SOKOLOV. However, the
historic roster also records other same-identity spellings in **separate
names and separate partner-pair IDs**, even when both were sourced from
official ISU records:

- Yuko KAWAGUCHI / Yuko KAVAGUTI: the ISU biography
  https://www.isuresults.com/bios/isufs00009880.htm explicitly states
  the spelling was changed. Both historic IDs are paired with
  Alexander SMIRNOV and share DOB 1981-11-20.
- Ekaterina SOSINOVA / Ekaterina SOKOLOVA: the ISU
  https://www.isuresults.com/bios/isufs00010027.htm gives DOB
  1990-08-29 under SOKOLOVA and documents her marriage to Fedor.
  The separate 2008 official ISU event results
  https://results.isu.org/results/ec2008/SEG005.HTM list
  SOSINOVA / Fedor SOKOLOV, same actual pair.
- Alexa SCIMECA / Alexa SCIMECA KNIERIM: the same Chris KNIERIM,
  official birthdate 1991-06-10, and the 2016 marriage appear in
  https://www.isuresults.com/bios/isufs00034201.htm .
- Feder SOKOLOV / Fedor SOKOLOV: the official date is
  1984-12-14 on ISU profile isufs00010027, side 2.

The four **source-reviewed** reversible alias mappings are stored
as data/adjudications/isu_historic_shared_partner_id_merges_v1.csv.
Canonical ID selection is a stable bookkeeping choice, not evidence
that one spelling was the original person's preferred name. The
original identities and event/pair records remain unchanged.

## Full-dataset candidate scan

Run from the doubles repository root:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python .\scripts\audit_historic_shared_partner_aliases.py

The offline script uses the already-generated
output/historic_dob/coverage/historic_dob_coverage_people_v1.csv,
the original data/historic/v4/couples_v4.csv, and the reviewed v1
identity-mapping rules.

It finds every distinct pair of original athlete IDs that:
1. Occur in the same skating discipline and athlete role;
2. Have **the same original historical partner ID**; and
3. Have matching, exact, official-linked day-level DOBs.

It creates **review candidates**, not automatic merges. A matching DOB
is not by itself proof of identity; different skaters can share a birth
date and the same historic partner across different years. A score for
name resemblance is only used to prioritize manual review, never to
accept an identity. The Arina USHAKOVA homonym split remains intact.

## Non-destructive outputs

Under output/historic_dob/shared_partner_identity/:

- historic_shared_partner_alias_manifest_v1.json — unique candidate
  alias edges, counts of source-reviewed rules, original and preview
  person/pair units, hashes of all inputs.
- historic_shared_partner_same_dob_candidates_v1.csv — original member
  IDs, names, shared partner, exact DOB, original pair IDs, review-only
  name-similarity score, and explicit source-review status.
- historic_reviewed_person_id_preview_v1.csv — person lineage after
  the **four reviewed merges only**, retaining all old IDs.
- historic_reviewed_pair_groups_preview_v1.csv — a projection that
  groups source pair IDs that would become the same canonical pairing.

**CRITICAL:** multiple historic pair IDs may contain independently
identified competition events, and others may duplicate the SAME
competition. The projection DOES NOT sum, collapse or replace event
counts or pair seasons. It preserves the old pair IDs and flags that
an event-level deduplication is required before performance analysis.

The identity audit output is not the final cohort. Some true same-person
aliases will not be detected by shared-partner criteria, including
partners whose own provisional IDs are also split, or aliases not
sharing any identical recorded teammate ID. Additional source reviews
and a cross-era historic+2018+ identity reconciliation remain necessary.

No original source files or previous DOB manifests are overwritten.
No astrological fields, date permutations, significance tests or
performance-selected samples are generated.
