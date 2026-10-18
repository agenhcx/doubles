# Completing historic ISU name-variant DOB sources

The current 2004–2018 selected-event historical pair study has 910 original
provisional athlete IDs. Exactly 815 audited person IDs occur in the 477
official source-matched pairs (814 original IDs + one source-proven Arina
USHAKOVA homonym split). Of those, 813 have consistent DOBs and two
have a blank DOB on the old PRK pair biography. Six profile/side name
variants have been source-reviewed separately.

## Current batch: all 76 directory-unmatched pairs

An offline index review of 2,007 public ISU couples found 138 candidate
links spanning 70/76 historical pairs. Of 76 unmatched historic pairs,
six had no matching directory candidate because of abbreviated historical
names or expanded published surnames.

Seven historical pairs now have an explicit source-reviewed primary DOB
evidence record:

data/adjudications/isu_historic_manual_pair_dobs_v1.csv

Six were the **zero-directory-candidate** pairs:

- Alexandra NAZAROVA / Maxim NIKITIN:
  Oleksandra NAZAROVA (1996-11-30) / Maksym NIKITIN (1994-10-05),
  https://www.isuresults.com/bios/isufs00012757.htm
- Pilar MAEKAWA / Leonardo MAEKAWA:
  Pilar MAEKAWA MORENO (1994-08-23) / Leonardo MAEKAWA MORENO (1992-08-04),
  https://www.isuresults.com/bios/isufs00013688.htm
- TOBIAS I / STAGNIUNAS D:
  Isabella TOBIAS (1991-08-23) / Deividas STAGNIUNAS (1985-04-28),
  https://www.isuresults.com/bios/isufs00012896.htm
- SINITSINA V / ZHIGANSHIN R:
  Victoria SINITSINA (1995-04-29) / Ruslan ZHIGANSHIN (1992-09-25),
  https://www.isuresults.com/bios/isufs00011268.htm
- SUNYOTO-YANG A / SULNDRO-YANG D:
  Amanda SUNYOTO-YANG (1992-07-08) / Darryll SULINDRO-YANG (1987-10-26),
  https://www.isuresults.com/bios/isufs00009756.htm
- DELLA MONICA N / GUARISE M:
  Nicole DELLA MONICA (1989-06-03) / Matteo GUARISE (1988-09-15),
  https://www.isuresults.com/bios/isufs00034093.htm

The seventh is a **false directory top-1 candidate**:

- Emilia SIMONEN / Matthew PENASSE does NOT equal
  Katherine BOBAK / Matthew PENASSE (ISU isufs00012160).
  The former duo is verified by the ISU athlete profile
  https://isu-skating.com/en/figure-skating/skaters/pairs/emilia-simonen-matthew-penasse/
  with Emilia DOB 1996-01-12. Her partner Matthew PENASSE (1988-09-07)
  is separately verified at
  https://isu-skating.com/figure-skating/skaters/matthew-penasse/.

All seven manual pairs retain the original historic pair ID and both historic
person IDs, the exact official names, separately documented source DOBs and
official URLs, discipline, and an identity-evidence rationale. The 2018 onward
ranking tables and the historic master are unchanged.

## Reusing ISU biography pages for 69 remaining pairs

The source collection tool
scripts/collect_historic_alias_isu_bios.py
takes the top-ranked directory candidate for each as-yet-unreviewed pair,
deduplicates repeated ISU profile IDs, reuses cached biography HTML and
parses DOBs against the **names published on each official page** rather than
the historical spellings. Most historical-to-official links are not yet
verified and MUST remain in the manual-review queue.

After pulling the latest code, run a 20-profile test:

    python .\scripts\collect_historic_alias_isu_bios.py --limit 20 --proxy http://127.0.0.1:10808

If parsing is sound, run all remaining candidate profiles:

    python .\scripts\collect_historic_alias_isu_bios.py --limit 0 --proxy http://127.0.0.1:10808

Default sources are the local index alias candidates and earlier reviewed
historical DOB audit. It separately validates the seven reviewed manual
source pairs against the unchanged historic v4 roster, then skips them
(including the false Emilia/Katherine source) when downloading.

Files created under output/historic_dob/alias_biographies/:

- historic_alias_bio_manifest.json: per-profile DOB extraction and
  cross-check totals, with input SHA256;
- historic_alias_bio_inventory.csv: one row per official source profile;
- historic_alias_dob_leads.csv: raw official DOB/date-bound name source
  mapped to a *candidate* historical side, with the link explicitly unverified;
- historic_alias_bio_review.csv: name differences, source parsing issues,
  and any conflict with an already-audited historical DOB.

The reported "official_profile_person_slots" counts the 2 skaters per
distinct downloaded official profile, while "source_lead_rows" can be
higher if multiple historical pair names point to one profile. One actual
athlete may appear on multiple official couple pages too, so do not
interpret either as independent people.

Do not automatically apply dates from a shared-partner index lead to
the other historic member. The name of the partner alone is not enough
to establish identity. No statistics, BaZi, or partner null models here.

The separate historical PRK PHYO/JONG pair remains in primary-versus-
secondary DOB adjudication: PHYO has an independent ISU singles DOB;
JONG has an Olympedia DOB but no confirmed ISU exact DOB.
