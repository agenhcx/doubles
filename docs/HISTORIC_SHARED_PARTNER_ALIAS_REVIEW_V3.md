# Historic ISU identity reconciliation: 33 source-reviewed partner aliases (v3)

Date: 2026-10-18. This is an **identity audit**, not a frozen BaZi
or partner-compatibility sample, and not a census of all ISU entrants.

## Locally verified starting point

The v2 local run found 33 same-original-partner plus same-official-DOB
identity candidate edges. Eight already had source-reviewed reversible
adjudications. Those eight merge edges projected the historical roster
from 911 audited provisional person slots to 903 and the original 553
pair IDs to 545 distinct pair groups. The follow-up offline source
matrix retained 25 additional candidates involving 50 distinct
provisional IDs, of which 24 had an existing manually curated DOB
reference in the priority/legacy tables, while one did not.

All 25 candidates were subsequently inspected against source-specific
ISU biography pages and exact original partner history; the official
birthdays were consistent with the reported candidate DOB. In addition
to typography-only and missing-given-name variants, several entries
have explicit ISU historical cross-references:

- Aljona/Aliona SAVCHENKO: isufs00035319 shows Bruno MASSOT and
  DOB 1984-01-19; its historical footnote uses Aliona with Robin
  SZOLKOWY, matching the older biography isufs00007498.
- Lesia VOLODENKOVA/VALADZENKAVA: isufs00009828 and the ISU
  2010 European Championships media guide both give 1991-05-01,
  nation BLR and partner Vitali VAKUNOV.
- Maylin HAUSCH/WENDE: isufs00011814 shows Maylin WENDE
  1988-09-22 and carries the previous official hausch-wende web
  contact, with Daniel WENDE as the same partner.
- Kristjan/Kristian RAND: isufs00011454 explicitly lists
  Grethe GRÜNBERG as his earlier partner while isufs00003711
  prints Kristian with the same 1987-06-12 DOB.
- Joti/Panagiotis POLIZOAKIS: isufs00035158 prints Joti with
  Kavita LORENZ; the earlier ISU singles biography isufs00011824
  prints Panagiotis with the identical 1995-06-09 DOB and birthplace.
- Natalja ZABIJAKO / Natalia ZABIIAKO: old Estonian pair biography
  isufs00012937 prints Natalja, 1994-08-15 and Tallinn birthplace.
  Russian biography isufs00035212 prints Natalia, the identical
  DOB/birthplace, and its former-partner note explicitly identifies
  Natalja ZABIJAKO / Alexandr ZABOEV from the earlier era.
- Sasha PALOMÄKI appears in isufs00010767 with Oksana KLIMOVA,
  1991-09-04; the historical replacement-character spelling
  and unaccented PALOMAKI are the same pair/person and date.
- Katie/Kathryn ORSCHER, John BALDWIN/BALDWIN Jr., Jean-Luc
  BAKER/Jea-Luc BAKER, and Harley WINDSOR/one-word WINDSOR all
  match official same-partner duo biographies and complete DOBs.

The v3 source audit file is:

    data/adjudications/isu_historic_shared_partner_id_merges_v3.csv

It **preserves all 8 v2 mappings** and appends 25 further
source-reviewed distinct ID pairs (33 total). Each row records the
canonical/alternative *historic ID*, full day-level DOB, discipline,
same partner, two original pair IDs, ISU profile ID and member side,
the primary ISU couple biography URI, the additional contextual ISU URI,
and the review rationale. The additional URL sometimes points to the
**same ISU biography via its alternate official host**, rather than
providing an independent second DOB measurement; it should not be
misrepresented as independent replication.

Both source-backed dates and partner ties are cross-checked before a
rule can be applied. Name similarity and DOB coincidence alone never
trigger a merge. In particular the Arina USHAKOVA homonym split
remains intact.

## Projected counts, pending latest local run

Applying all 33 reviewed aliases non-destructively to the v4 original
historical pair data yields the structural expectation:

| Unit | Original audit | Identity v3 preview |
|---|---:|---:|
| Audited person slots | 911 | 878 |
| Original pair IDs | 553 | 553 (preserved) |
| Distinct projected historic couple combinations | not yet canonical | 520 |
| Pair groups containing 2+ original pair IDs | — | 32 |
| Number of original pair IDs inside those multi-ID groups | — | 65 |

There are 33 extra pair IDs that collapse into those 32 structural
couple groups. **These counts are not event counts.** A pair's
separate historic-event entries must be deduplicated on source event,
year/season and participant identity before summing rank/score metrics.
Even 878 should not be called the final number of independent natural
people until non-shared-partner aliases and cross-era links are reviewed.

## Local workflow

After pulling the latest GitHub changes:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python .\scripts\audit_historic_shared_partner_aliases.py

The script still produces four files under
output/historic_dob/shared_partner_identity/:

- historic_shared_partner_alias_manifest_v1.json (source hashes,
  source-reviewed merge count, projected person/pair group sizes);
- historic_shared_partner_same_dob_candidates_v1.csv (all 33
  shared-partner identity edges and reviewer status);
- historic_reviewed_person_id_preview_v1.csv (unchanged history
  ID lineage, with only explicit reversible aliases applied);
- historic_reviewed_pair_groups_preview_v1.csv (all source pair IDs
  grouped by projected person members; **no event-count addition**).

No v4 original, 2018–2026 ranking, earlier v1/v2 evidence or birthday
source record is overwritten. The previous generic evidence queue
will have no pending same-partner edges after the v3 audit if the
33 rules match all locally observed candidates. A zero queue does not
prove that no other alias exists (e.g. both partners' IDs changing or
two different partner eras).

Remaining phases before the BaZi research model: cross-era 2004–2026
identity graph QA and event-level duplicate detection, then lock the
sampling and null-model plan without inspecting any BaZi outcomes.
