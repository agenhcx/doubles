# Historic ISU partner source-identity reconciliation (October 2026)

## Latest DOB evidence (not statistical results)

The completed offline original-name fallback processed 138 historical
member-link rows from 69 ambiguous pair entries corresponding to 67 unique
official biographies:

- 22 source rows initially did not yield a full DOB using newer ISU INDEX
  names.
- 20 historical-name/profile-header fallback rows recovered exact day-level
  DOBs, representing 17 distinct *original historical provisional IDs*.
  Three original IDs recur for multiple skating partners and have agreeing
  recovered DOBs.
- 113/134 official profile-person slots had a date from the original
  directory-name pass; 20 more unique slots were recovered, resulting in
  **133/134** official slots with a source-labelled date.
- 2 historical candidate member rows remain blank. They are not two missing
  official biography DOBs: one official profile-side now has a DOB by its
  longer printed name while the shorter historic-name link remains
  unverified.

All 20 recovered rows are **source leads**, not automatically approved
cross-era identities. Index-name drift includes married surnames, national
transliteration, misspellings and shortened given names.

## Two source-reviewed missing-member identity exceptions

The independent CSV
data/adjudications/isu_historic_alias_exceptions_v1.csv has exactly
two explicitly reviewed historic pair/profile/side mappings:

1. Alexa SCIMECA (historic pair with Chris KNIERIM,
   pair_70e339c014666, person_d0805bb1ec9d5) corresponds to
   official Alexa SCIMECA KNIERIM on isufs00034201 (1991-06-10).
   The 2015 ISU World Championships pairing lists
   "Alexa SCIMECA / Chris KNIERIM" and the later ISU biography
   confirms the partnership began in 2012 and a 2016 marriage.
   Primary sources:
   https://results.isu.org/events/cat00008337.htm
   https://results.isu.org/bios/isufs00034201.htm
2. Katharina MÜLLER (historic pair with Tim DIECK,
   pair_8013c0fe4bd91, person_ca029607a077f) corresponds to
   printed Katharina ABERT on old isufs00034671 (1995-09-12).
   Independent contemporary official ISU athlete biography lists
   Katharina MUELLER / Tim DIECK with the identical DOB and
   partnership history. Primary sources:
   https://results.isu.org/bios/isufs00034671.htm
   https://isu-skating.com/en/figure-skating/skaters/pairs/katharina-mueller-tim-dieck/

These source reviews are distinct from the newer 2018–2026
isu_bio_name_links_v1.csv adjudication for the same Katharina. The
historical ID is explicitly validated separately.

## Locally calculate 76-pair identity QA

Run after pulling GitHub changes:

    python .\scripts\audit_historic_alias_pair_identity.py

Inputs (all available locally):

- output/historic_dob/alias_fallback/historic_alias_source_name_fallback_leads.csv
- data/historic/v4/couples_v4.csv
- data/adjudications/isu_historic_manual_pair_dobs_v1.csv (7 historic pairs)
- data/adjudications/isu_historic_alias_exceptions_v1.csv (2 individual sides)

The audit deliberately separates:

- Official biography printed-name evidence: both original historic
  names (or source-labelled historic fallback names) unambiguously match
  their respective official DOB-labelled skater sides.
- Explicit source-reviewed exceptional identities (two, above), each
  supported by an independently matching same-partner official source.
- Seven manually source-reviewed pairs, including the 2012-era Emilia
  SIMONEN / Matthew PENASSE rather than the falsely suggested Katherine
  BOBAK / Matthew PENASSE biography.
- The remaining **partner-only, similarity-only, renamed or abbreviated
  directory candidates**, which stay unresolved and are not assigned a DOB.

Expected pair status distribution before local confirmation:

| Type | Expected pairs |
|---|---:|
| Dual source-attested names | 19 |
| Independently reviewed exceptional pair link | 2 |
| Previously source-reviewed pair | 7 |
| Directory identity still uncertain | 48 |
| **Total** | **76** |

The generator also surfaces official profile+side collisions where two
historical provisional person IDs refer to the SAME original ISU skater
position, without merging them. Observed candidates:

- isufs00034201 side 1: Alexa SCIMECA versus Alexa SCIMECA KNIERIM.
- isufs00010027 side 2: Feder SOKOLOV versus Fedor SOKOLOV.

The latter official biography identifies Fedor SOKOLOV (1984-12-14),
partner Ekaterina SOKOLOVA (1990-08-29), and states the pair had skated
together since 2003. These are **identity duplicate leads**, not yet
a destructive master merge.

Output under output/historic_dob/alias_pair_identity/:

- historic_alias_pair_identity_manifest.json (small totals, provenance);
- historic_alias_pair_source_audit.csv (all 76 pair decisions);
- historic_alias_correlated_dob_leads.csv (one labelled date per source
  member on a complete source-linked pair; may repeat original IDs);
- historic_alias_unresolved_pair_review.csv (48 or more remaining pairs);
- historic_alias_profile_side_collisions.csv (possible duplicate IDs).

No original athlete, couple, ranking, biography or DOB seed is overwritten.
The 2004–2018 v4 source is selected historical events, not all
international or national competition entries. The count 910 is
provisional IDs, NOT certified unique people: Arina USHAKOVA required a
split; further surname variants may require evidence-based merging.
No BaZi, pair compatibility tests, or null distributions are computed.
