# Cross-era 7-identity source review: reversible graph v3 (2026-10-18)

## Evidence and state

The latest user's historical-v2 DOB-rescued cross-era CSV contains
190 candidate edges, all with agreeing historical/current day-level
ISU DOB evidence, and 14 ambiguous candidate edges. These are 7
two-edge graph components: six HISTORIC→two MODERN-name-ID relations,
and one two-HISTORIC→one MODERN-ID relation.

The two similarly named uploaded historic/modern v1 manifests still
reported prior 878 people/520 pairs and 195 candidate edges; **do not**
treat them as the historical-v2 manifests. The historical-v2 source
augmented file and its own rescue manifest explicitly identify 190
candidate edges and 14 ambiguous edges.

All seven source relationships have now been reviewed against official
ISU athlete/couple biographies and old partner records:

| Scope | Official canonical name | Earlier/alternate name | Exact DOB |
|---|---|---|---|
| modern | Nikolaj SOERENSEN | Nikolaj SORENSEN | 1989-02-18 |
| modern | Maksym NIKITIN | Maxim NIKITIN | 1994-10-05 |
| modern | Pierre SOUQUET-BASIEGE | Pierre SOUQUET | 1994-07-18 |
| modern | Aleksandr KOROVIN | Alexander KOROVIN | 1994-02-15 |
| modern | Ashley CAIN-GRIBBLE | Ashley CAIN | 1995-07-22 |
| modern | Alexa KNIERIM | Alexa SCIMECA KNIERIM | 1991-06-10 |
| historic | Antonio SOUZA-KORDEIRU | Antonino SOUZA-KORDYERU | 1993-03-21 |

The seven original old/modern IDs, primary source URI, second official
context URI, DOB and adjudication rationale are recorded in:

    data/adjudications/isu_cross_era_ambiguity_identity_links_v1.csv

Important specific source evidence:

- ISU bio isufs00014665 has Fournier Beaudry / Nikolaj SOERENSEN,
  with the historical SORENSEN ranking alias referring to the same
  ISU profile ID and partner.
- ISU bio isufs00012757 has Nazarova / Maksym NIKITIN, same
  profile and older Maxim/Nazarova ranking era.
- ISU bio isufs00106270 explicitly annotates prior
  Alessandrini / Pierre SOUQUET, while current name reads SOUQUET-BASIEGE.
- ISU bio isufs00113788 names former partner Alisa EFIMOVA and
  same DOB/birthplace as isufs00035425, confirming KOROVIN.
- ISU bio isufs00101521 records CAIN-GRIBBLE, DOB and 2019 marriage;
  older isufs00012260 uses Ashley CAIN with identical DOB.
- ISU bio isufs00110201 records Alexa KNIERIM and names Chris KNIERIM
  as former partner; the earlier bio isufs00034201 names Alexa
  SCIMECA KNIERIM with identical DOB and birthplace.
- ISU bio isufs00101795 records Antonio SOUZA KORDEIRU's old partner
  Arina CHERNIAVSKAIA; official ISU 2014 Cup of China results list
  Arina with Antonino SOUZA-KORDYERU.

These are SOURCE-REVIEWED alias edges, not seven separately
replicated birthdates. Some official URLs point to the same ISU
record or to historical records linked by prior partnerships.

## Usage

From the doubles repository root in PowerShell, run each as one line:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_cross_era_source_ambiguity_v3.py
    python .\scripts\audit_historic_alias_event_collisions_v1.py --preview .\output\historic_dob\cross_era_identity\ambiguity_source_v3\historical_source_reviewed_pair_preview_v3.csv --out .\output\historic_dob\cross_era_identity\ambiguity_source_v3\event_collision_audit

The v3 script requires:

- historical-v2 reviewed person/pair preview in
  output/historic_dob/shared_partner_identity/initial_only_v2/
- full modern season roster in output/master/season_roster.csv
- historical-v2 cross-era source-augmented 190-edge CSV and matching
  rescue manifest in
  output/historic_dob/cross_era_identity/historical_v2/official_bio_rescue/
- the 7-rule versioned adjudication ledger.

It verifies the original manifest's modern-roster hash; all 14 input
ambiguous edges must be accounted for by exactly the seven reviewed
rules. Stale rosters, DOB disagreements, mismatched official name
sides, unauthorized merges and extra ambiguities fail closed.

## Outputs

Under output/historic_dob/cross_era_identity/ambiguity_source_v3/:

- cross_era_source_reviewed_identity_manifest_v1.json
- source_reviewed_cross_era_canonical_candidates_v1.csv
- historical_source_reviewed_person_preview_v3.csv
- historical_source_reviewed_pair_preview_v3.csv
- modern_source_reviewed_pair_preview_v1.csv
- source_reviewed_alias_rules_applied_v1.csv
- event_collision_audit/ (after the second command)

Before running, a structural simulation on the *uploaded* 190 candidate
edges plus 1,584 modern ranking rows projects:

| Unit | Prior | Preview after seven source alias relations |
|---|---:|---:|
| Cross-era candidate edges | 190 | 183 |
| Known ambiguous candidate edges | 14 | 0 unreviewed in this **specific queue** |
| Modern provisional name IDs | 1,050 | 1,044 |
| Modern distinct pair-name combinations | 622 | 619 |
| Historic reviewed slots | 866 expected after historical v2 | 865 expected |

These are expected STRUCTURAL preview numbers, not independent-person
population counts, and must be checked against the full local inputs.
The script preserves all 190 raw candidate rows via their original
historic/modern ID lineage. The historic event collision audit must be
rerun after the single new cross-partner historical alias.

**Neither ISU ranking rows nor event-level performance values are
summed or used for identity proposals. No BaZi, null model,
statistical hypotheses, sample selection or cohort freeze.**

## Return files

Please supply these after local runs:

1. ambiguity_source_v3/cross_era_source_reviewed_identity_manifest_v1.json
2. ambiguity_source_v3/event_collision_audit/historic_alias_event_collision_manifest_v1.json
3. ambiguity_source_v3/source_reviewed_cross_era_canonical_candidates_v1.csv
4. initial_only_v2/historic_initial_only_v2_manifest.json (the actual
   historical-v2 confirmation, not historic_shared_partner_alias_manifest_v1.json).

If collision review is nonempty, return it too.
