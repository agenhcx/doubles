# Historical ISU selected-events DOB follow-up: 43 reviewed primary sources

The 2004–2018 historic cohort audit reported:
- 910 original provisional IDs / 911 audit identity slots, including an
  independently confirmed same-name Arina USHAKOVA homonym split.
- 860 identity slots with reviewed official DOB evidence.
- 2 additional exact-name/same-partner ranking-only DOB leads.
- 1 Olympedia DOB lead without an official ISU source, and 48 without
  acceptable primary DOBs.
- 510/553 historical pairs with both official DOB candidates.
- 0 source DOB conflicts in the earlier processed data.

## New high-priority official DOB records

data/adjudications/isu_historic_priority_dob_sources_v1.csv stores **43**
distinct missing original historical IDs. For each athlete, it includes:

- Their exact original historic name and provisional person ID.
- Full ISU source name, **day-precision date of birth**, and unmodified
  HTTPS ISU biography link.
- Original historic pair ID and exact recorded partner name.
- Source-evidence category (same officially documented couple, or
  named official athlete profile with separately corroborated historical
  partnership context).
- Explanatory review notes, with original orthographic deviations retained.

This table is an append-only, source-scoped DOB *evidence* layer, NOT a
replacement of the historic v4 master or a claim of full unique-person
identity closure.

Examples of the main source corrections:

- Guillame GFELLER is Guillaume GFELLER (1985-04-27) in ISU
  isufs00011071, explicitly partnered with Andrea CHONG.
- Alexandra and Roman ZARETSKI appear as ZARETSKY on their old
  isufs00005493 couple biography.
- Darja BEKLEMISCSEVA / Mark MAGYAR directly corresponds to historic
  Daria BEKLEMISHEVA / Mark MAGYAR (1997-06-27) in their ISU profile.
- John BALDWIN Jr. (1973-10-18) with Rena INOUE, and Danny O'SHEA
  (1991-02-13) with Tarah KAYNE, have their complete dates on original
  ISU two-person biographies.
- The exact Katelyn GOOD (1990-11-08) / Nikolaj SOERENSEN (1989-02-18)
  historical duo is linked in isufs00012142.
- Amanda SUNYOTO-YANG and Darryll SULINDRO-YANG are siblings:
  1992-07-08 and 1987-10-26 on isufs00009756.
- Alisa EFIMOVA / Aleksandr KOROVIN's ISU biography isufs00035425
  confirms 1999-06-08 / 1994-02-15, respectively, independently of the
  newer 2018+ ranking DOB match.

The priority CSV preserves the original misspellings/short names,
including Jea-Luc BAKER, MARINARO, WINDSOR, and corrupted non-ASCII
names. Their official identity is linked via the separately recorded
historic pair/partner and an original ISU source; **do not use broad
fuzzy matching on unrelated people**.

## Do not fill identities still requiring investigation

The following original provisional skater IDs were intentionally **not
promoted** in this v1 official-primary table:

- Ekaterina SOSINOVA (name resembles Ekaterina SOKOLOVA but historical
  partner context is not yet sufficiently resolved);
- Feder SOKOLOV (possible duplicate of a different provisional Fedor
  SOKOLOV ID; ISU has Fedor 1984-12-14, but the profile-side duplication
  needs an explicit reversible identity merge);
- Ho Jung LEE;
- Lesia VALADZENKAVA;
- Elizabeta MAKAROVA;
- initial-only DAVIDOVICH A and KRASNOPOLSKI E;
- JONG Yong Hyok, whose 1988-01-03 date is an Olympedia lead, not an
  ISU officially printed DOB in the old pair profile.

These eight remain open until the right person and source can be
adjudicated, or must be reported as missing in the final study.
No selection can depend on later BaZi statistics.

## A noteworthy discrepancy in ISU editorial material

Deanna STELLATO-DUDEK's several named official skater and couple
biographies, including her original USA partnership with Nathan
BARTHOLOMAY, print **1983-06-22**, as does the ISU 2024 Worlds
Facts & Figures PDF. An ISU 2026 Olympics news/Facts & Figures article
instead says "June 6, 1983". This conflicting editorial claim should
be disclosed in source QA; the 2024 official event document and
athlete-registration-like skater profiles strongly support June 22.
We have not overwritten, inferred, or used the article date as a DOB
observation in the biographical source audit. Revisit any material
contradictions during publication verification.

## Recompute locally

Once GitHub changes are merged, run:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python .\scripts\audit_historic_dob_coverage.py

The CLI now includes the new versioned official priority source file.
Prior library calls without the new optional priority parameter are
unchanged; main reads all ten sources and writes to the same *separate*
audit output directory.

New checks on every reviewed row:

1. Full date of birth, HTTPS official ISU hostname and biography path.
2. Exact source historic person ID and v4 displayed name.
3. Exact original historic pair ID, original partner name, discipline
   and that the athlete is actually a member of this pair.
4. Approved evidence status/category and nonblank source identity context.
5. Duplicate priority person IDs are rejected, and any disagreement
   with older official or same-pair ranked dates is held as a conflict.
6. Original v4, previous official seed tables and earlier audit views
   are never modified.

If all 43 new primary DOB records have compatible identities/dates,
the **predicted** audit result is 903/911 official DOB-covered slots,
with eight source gaps still open. This is a prediction, NOT a
completed local run. The actual number of complete pairs should be
read from the new local manifest, not guessed from source-row totals.

The original historical source universe remains the previously covered
selected ISU competitions, not all entrants. No BaZi, partner
compatibility test, calendar or athlete-pool null model is computed.
