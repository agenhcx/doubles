# Historic ISU DOB-source closeout candidate — 2026-10-18

## Baseline full-coverage audit (local run, v2)

The user's latest offline cumulative manifest confirms:

| Unit/status | v2 observed |
|---|---:|
| Original historical v4 person IDs | 910 |
| Source-audited identity slots (one reviewed homonym split) | 911 |
| Slots with source-linked official day-level DOB | 910 |
| Only secondary DOB, not yet official | 1 |
| Source DOB conflicts | 0 |
| Historical pairs with both official DOBs | 552 / 553 |
| Unresolved pair-to-ISU-profile identity links | 48 |
| Possible duplicate original IDs pointing to same ISU profile side | 2 |

These totals are conditional on the selected 2004–2018 event-source dataset,
NOT all international entrants, all participants or a final set of unique
people. The unresolved 48 pairs already have both athletes' DOBs from other
official records; their remaining problem is source-matched pair identity,
not unobserved dates.

## Last official DOB: Yong Hyok JONG (1988-01-03)

The formerly missing athlete, original historic ID
person_121570cb3d68f, is "JONG Yong Hyok", a 2005–2006 historical
Pair Skating teammate of PHYO Yong Myong (pair_20c64960fd0e4).

The older official ISU Olympic-season pairing biography,
https://www.isuresults.com/bios/isufs00009336.htm,
lists *Yong Myong PHYO / Yong Hyko JONG*, but leaves both DOB fields
blank. Crucially, the same ISU source documents Jong's previous pairing
with *Mi Hyang SUNG*, including a 2005 Karl Schäfer Memorial appearance
and a temporary partnership switch for the 2006 Olympics because
Mi Hyang was not age eligible.

A **different official ISU pair biography**,
https://www.isuresults.com/bios/isufs00007318.htm,
lists *Mi Hyang SUNG / Yong Hyok JONG* and explicitly gives

    Date of birth: 03.01.1988 Yong Hyok JONG

It also names the previous partner Paek Mi Hyang and lists 2005 Karl
Schäfer Memorial and 2009 Nebelhorn appearances. This direct ISU DOB
is independently consistent with the preexisting secondary
Olympedia record https://www.olympedia.org/athletes/109744.

## Source versioning and safeguards

The append-only primary-source evidence file
data/adjudications/isu_historic_priority_dob_sources_v3.csv
retains all 50 v2 source reviews and adds one source record for Jong,
for **51 distinct historical provisional IDs**. His source
corroboration URL is the *earlier official PHYO/JONG biography*,
not another independently recorded DOB.

The existing secondary-only lead in
data/adjudications/isu_historic_external_dob_leads_v1.csv
is preserved unchanged. The consolidated auditor uses the new official
record to promote Jong to the official-source tier, while retaining
both official source links and the Olympedia URI as audit provenance.
Only the explicit person and pair ID associated with the two
official profiles can be promoted.

The validation now accepts a corroborating official ISU pair biography
URL only when it has an exact /bios/isufsNNNNNNNN.htm path on a trusted
ISU domain. Untrusted domains, non-HTTPS sources, malformed profile
paths, query parameters and userinfo are rejected. The corroborating
page establishes the identity transition, not the actual DOB.

## Expected local verification (not yet run)

From the user's latest v2 manifest, v3 should yield:

- **911 / 911 audited identity slots with official DOB evidence**;
- **553 / 553 selected historical pairs with both official DOBs**;
- **0 unresolved missing official DOBs** and **0 date conflicts**;
- *48 unresolved pair identity links*, plus *two profile-side duplicate-ID
  candidates*, unchanged from v2.

These are projections until the user runs the new audit locally.
Even when reached, the dataset is **DOB-source-complete**, not
identity-frozen, and should not enter any BaZi or partner-null analysis.
Further work should address reversible name aliases, sampled-event
completeness, and later prospective/preregistered study selection.

From the repository root, run:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python .\scripts\audit_historic_dob_coverage.py

Upload the small manifest, missing-priority and source-conflicts outputs
from output/historic_dob/coverage/ to confirm official DOB closeout.
