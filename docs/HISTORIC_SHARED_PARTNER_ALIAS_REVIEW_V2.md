# Historic ISU shared-partner alias source review, October 2026

## First review of 33 independently screened alias edges

The user's latest local full historic pass found **33 pairs of provisional
athlete IDs** with an identical original partner and the same official
day-level DOB. All 66 endpoint IDs were distinct; there were no candidate
three-person chains in the inspected CSV.

The original v1 rules apply **four** explicitly source-reviewed ID merges
to a reversible preview: 911 original-plus-one-homonym audit identity
slots -> 907 identity preview slots and 553 original couple IDs -> 549
distinct couple groups. This does **not** sum event observations or
certify final person/pair counts.

Among the 29 initially unreviewed edges, **25** already had at least
one DOB/official identity source independently curated in the v3
priority/legacy tables. Four other edges were verified directly against
original ISU pages during this source-review round:

1. Cortney MANSOUR / MANSOUROVA (1994-12-15), Michal CESKA partner.
   Original ISU biography
   https://www.isuresults.com/bios/isufs00014520.htm
   explicitly says the name changed after Czech citizenship.
2. Dorota ZAGORSKA / SIUDEK (1975-09-09), Mariusz SIUDEK partner.
   https://www.isuresults.com/bios/isufs00000276.htm
   explicitly states the former maiden surname Zagorska.
3. Lubov ILIUSHECHKINA / Liubov ILYUSHECHKINA (1991-11-05),
   Dylan MOSCOVITCH partner. The old spelling appears in the history
   paragraph of https://results.isu.org/bios/isufs00015085.htm
   and in ISU 2015 Four Continents official results
   https://results.isu.org/events/cat00008333.htm.
4. Tim / Timothy KOLETO (1991-06-17), Misato KOMATSUBARA partner.
   ISU https://results.isu.org/bios/isufs00103082.htm prints Tim,
   while ISU NHK Trophy 2017 official results
   https://results.isu.org/events/cat03108237.htm print Timothy.

These four are appended to versioned
data/adjudications/isu_historic_shared_partner_id_merges_v2.csv
(8 reviewed rules, v1 preserved unchanged). The local script now
defaults to v2 and **only** applies those eight source-reviewed merges.
Expected projection (pending local execution): 903 audit identity slots
and 545 distinct couple groups. These are counts of a *reversible preview*,
not a frozen final cohort.

## Prepare the remaining alias source matrix offline

Run from the repository root:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python .\scripts\audit_historic_shared_partner_aliases.py
    python .\scripts\audit_historic_pending_alias_evidence.py

The second script reads the 33-candidate output from the first along with
the already audited 911 historic DOB person rows, unchanged v4 couples,
the 51-source historic priority v3 catalog and the historic official
biography seed v2. It validates complete DOB and original same-partner
pair membership, then joins previously curated ISU URLs to each
**not-yet-reviewed** ID pair.

Output under output/historic_dob/shared_partner_identity/source_review/:

- historic_pending_alias_source_manifest_v1.json (review counts and source tiers)
- historic_pending_alias_official_evidence_v1.csv (both historic names,
  exact DOB, partner, pair IDs, curated official source names and URLs,
  original supplementary ISU URLs)

The expected 25 remaining candidates all have at least one curated
official DOB/partner source, but that only supplies a starting point for
manual source-specific *identity* adjudication; no candidate is accepted
by the evidence-queue script.

The remaining cases include simple typographic differences,
transliteration, nicknames, damaged Unicode, surname changes and
abbreviated names. For instance the newer official ISU profile for
Natalia ZABIIAKO prints the social handle nataljazabijako, and the
Cortney MANSOUROVA archive explicitly discusses her earlier surname.
Do not generalize from name similarity alone: examine same athlete
birthdate, published name, partner chronology, and original discipline.

**Later event-level deduplication is separately required.** When two
historic pair IDs merge they can contain the same or different event
results; simply summing historic event counts can inflate performance
measures. Do not calculate BaZi, outcome correlations, Calendar Null
or Skater Pool Null until identity QA closes and hypotheses are locked.
