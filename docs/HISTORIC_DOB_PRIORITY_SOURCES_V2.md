# Historic ISU DOB priority-source expansion, v2

**Data collection only — not an independent-person census or a frozen
statistical cohort.** The previous historical-v4 coverage audit found
860/911 original-plus-proven-homonym audit slots with official DOB
sources, two DOBs linked only by later same-pair rankings, one
Olympedia-only DOB, and 48 without adequate DOB evidence.

This v2 catalog preserves the 43 source-reviewed DOB records of v1 and
adds **seven** new historically scoped records, with original person ID,
pair ID, counterpart's historic name, full date, exact printed official
name, source URL, and source-evidence rationale. An optional additional
column records a separate official result-page citation corroborating
pair identity, *not* a second observed DOB.

The seven additional source identities:

| Historic name | Date of birth | Primary ISU source | Independent partner evidence |
|---|---|---|---|
| Ekaterina SOSINOVA | 1990-08-29 | isufs00010027, printed SOKOLOVA | 2008 European Championships ISU results explicitly name SOSINOVA / Fedor SOKOLOV |
| Feder SOKOLOV | 1984-12-14 | isufs00010027, printed Fedor | 2008 European Championships pairing and original historical Ekaterina pairing |
| DAVIDOVICH A | 1997-03-24 | isufs00034501, printed Andrea DAVIDOVICH | Original historic pairing with Evgeni KRASNOPOLSKI |
| KRASNOPOLSKI E | 1988-10-04 | isufs00034501, printed Evgeni KRASNOPOLSKI | Original historic pairing with Andrea DAVIDOVICH |
| Lesia VALADZENKAVA | 1991-05-01 | 2010 ISU Europeans media guide, published athlete roster | Official 2009 Junior Worlds pairing with Vitali VAKUNOV |
| Ho Jung LEE | 1997-03-15 | isufs00034775, printed Hojung LEE | Richard Kang In KAM in the same ISU biography |
| Elizabeta MAKAROVA | 1994-06-17 | ISU Elizaveta MAKAROVA / Leri KENCHADZE athlete pair page | Historic pairing with Leri KENCHADZE |

The full primary-media-guide PDF is:
https://www.isuresults.com/events/EC10_MediaGuide.pdf

The independent partner/orthography event source for SOSINOVA/Fedor is:
https://results.isu.org/results/ec2008/SEG005.HTM

The older ISU biography may use SOKOLOVA where the official competition
results say SOSINOVA. The source-specific pairing is corroborated; the
separate v4 provisional IDs **Feder** and **Fedor** are not automatically
merged. The archival ISU first-skater page for MAKAROVA displays her
DOB, not an inferred date for her partner.

## One remaining historical identity DOB without official primary corroboration

JONG Yong Hyok, historic pair partner PHYO Yong Myong, has DOB
1988-01-03 in the independent Olympedia source
https://www.olympedia.org/athletes/109744
but both date cells are blank in legacy ISU duo isufs00009336. PHYO
has independent official ISU singles DOB evidence and is covered.
JONG remains *secondary-only*, never promoted as an official DOB.

## Strict audit and expected metrics

The source-integrating script now defaults to the v2 catalog:

    python .\scripts\audit_historic_dob_coverage.py

It accepts only ISU official biography or skater URLs plus the *exact*
whitelisted historical media-guide PDF path, with separately validated
secondary ISU event URLs for pairing chronology. Generic PDFs from
other sites, wrong partner names, unrelated profile URLs, source date
disagreements, or duplicate historic person IDs are rejected or held.

The expected next **local** coverage audit, if all seven new DOBs
confirm as source-compatible, is **910/911 official primary DOB
candidates** (99.89%), with just **one secondary-only DOB slot**.
The audited identity count remains 911 until further reversible alias
merges, and the number of pairs with two official DOBs must be read
from the local manifest rather than inferred from this projection.

The archived user files, historic pair IDs, raw biography cache,
and earlier v1 reviewed records remain unchanged. Do not compute
BaZi or partner/calendar null models during DOB collection.
