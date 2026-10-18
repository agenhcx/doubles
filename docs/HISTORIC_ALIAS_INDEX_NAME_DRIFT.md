# Historic ISU alias biography: INDEX name versus archived profile name

## First 67 official candidate profiles (October 2026)

The local source run for the 69 not-yet-approved historical pair aliases
fetched 67 distinct official biographies (0 fetch failures; 42 cache hits).
The initial name-index parser extracted both date-labelled DOBs from 46
profiles and one side from 21 others: 113/134 unique official
profile-person positions. The output has 138 candidate historical-side
rows, of which 116 displayed a parsed published DOB; 42 agreed with a
previously audited historical person's DOB, 0 disagreed, and 22 rows
did not parse a DOB with the CURRENT directory name.

The problem is often a **newer directory name** versus an **older archived
biography's printed name**. These examples were directly inspected:

- ISU isufs00000479: current index "Galit CHAIT MORACCI"; old biography
  "Galit CHAIT" with DOB 1975-01-29.
- ISU isufs00004927: current index "Kristin FRASER-LUKANIN"; old biography
  "Kristin FRASER" with DOB 1980-02-29.
- ISU isufs00003711: index "Kristjan RAND"; older biography
  "Kristian RAND" with DOB 1987-06-12.
- ISU isufs00007498: index "Aljona SAVCHENKO"; old biography
  "Aliona SAVCHENKO" with DOB 1984-01-19.
- ISU isufs00011009: index "Liubov ILYUSHECHKINA"; old biography
  "Lubov ILIUSHECHKINA" with DOB 1991-11-05.
- ISU isufs00034671: old biography says **Katharina ABERT**
  (1995-09-12), while both the historic athlete name
  "Katharina MÜLLER" and newer index "Katharina MUELLER" do not
  appear in its biographical header. This case must NOT be guessed from
  name fallback: a separate, source-adjudicated alias is required.
- ISU isufs00034201: old biography says Alexa SCIMECA KNIERIM
  (1991-06-10) while the newer index says Alexa KNIERIM; the
  historic roster has both "Alexa SCIMECA" and "Alexa SCIMECA KNIERIM"
  as separate provisional IDs. These need later identity deduplication
  and cannot be auto-merged on the same date.

The ISU index itself is not the full set of all historical skaters.
Older and current ISU pages may change after a cache was collected.

## Offline historical-name DOB fallback

Run the new script after the original 67-profile collector:

    python .\scripts\audit_historic_alias_bio_fallback.py

It reads:
- output/historic_dob/alias_biographies/historic_alias_dob_leads.csv
- cache/isu_bios/isufsNNNNNNNN.html (the **already cached** biographies)

For each originally blank DOB, it checks the ORIGINAL historic full
athlete name against the cached official biography header. It requires
an explicit Date of birth label, a valid full date, and the entire
historic name. It uses the same limited punctuation/name-order parser
as the audited original collector. It does not use fuzzy matching.

One extra guard rejects partial historical names that are only prefixes
of the printed ISU name, e.g. "Alexa SCIMECA" is not the whole name
"Alexa SCIMECA KNIERIM". Recovery requires evidence that the official
name field actually ends at that point (or the legacy DOB label directly
follows in reverse-layout pages). A source-dated full name and a short
historical name are not automatically considered the same athlete.

Three outputs under output/historic_dob/alias_fallback/:

- historic_alias_source_name_fallback_manifest.json:
  how many originally missing slots were recovered and what remains.
- historic_alias_source_name_fallback_review.csv:
  the new DOB candidates and the still-unmatched source positions.
- historic_alias_source_name_fallback_leads.csv:
  complete source-side audit with old index name, historic name, actual
  name matched on the profile, DOB, prior comparison and source URL.

**All newly recovered dates are review-only candidates**. The date of a
published official name is not automatically assigned to the old roster
ID: one known false directory hit paired the wrong woman with the right
male partner, so historical pair identity must be corroborated before
any DOB can be promoted. The original 138-row source lead file, the
manually reviewed seven-pair exception table and all master records
remain unchanged.

A profile/side whose old and fallback name bindings produce conflicting
dates is marked for manual inspection. One official profile with many
historical candidate links is still only two official side positions.

We do not calculate any BaZi, compatibility hypothesis or random-pair
null-model statistic during this data-collection stage.

## Archived official HTTP hyperlinks (source-format correction)

The original alias lead CSV produced by the public ISU biography index
contains URLs such as `http://www.isuresults.com/bios/isufs00004927.htm`.
All 138 rows of the initial full alias-source batch use this legacy HTTP
format. The offline fallback previously rejected those source citations
by requiring HTTPS, stopping before checking any cached file.

The URL validation now accepts the recorded HTTP **or** HTTPS scheme
only for exact official ISU hosts and the corresponding
`/bios/<profile_id>.htm` path. Untrusted hosts, URL userinfo, nondefault
ports, arbitrary paths and query/fragment strings are still rejected.
The original source URL is preserved unchanged for reproducibility.
This validation never initiates an HTTP request; all DOB lookups are
from existing local HTML cache.

## Source full names versus incomplete historical names

The first local fallback run revealed two one-word historical names in
the 138-row source-lead CSV: `WINDSOR` (Harley WINDSOR,
1996-10-22) and `MARINARO` (Michael MARINARO, 1992-01-07).
Those two DOBs were already extracted from ISU biographies using the
published full names. The old fallback attempted to reparse both
members unconditionally, raising `ValueError: Expected full athlete name`.

The fallback now processes each partner separately and only reparses
a person whose originally bound published-name DOB is blank. Unknown
historical names consisting of only one word or initials are labelled
`historic_name_incomplete_review_only` rather than crashing the full
batch or inferring a date. Prior ISU dates, original source URLs, profile
IDs, and master records are never changed. The program still requires
exact biographical label/date association and manual identity verification.

