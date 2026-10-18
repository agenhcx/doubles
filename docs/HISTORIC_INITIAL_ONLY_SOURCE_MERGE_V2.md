# Source-approved historic initial-only aliases: reversible identity v2

Date: 2026-10-18. This is a **quality-control preview**, NOT a new
frozen study cohort, independent-person census or prediction result.

## Why a second historical identity pass was required

The earlier v3 audit accepted 33 same-partner/same-official-DOB alias
edges and projected 878 historical audited person slots and 520
distinct partner groups from the 553 original pair IDs. An independent
offline candidate search found another 12 abbreviated personal names
in six pairs. These were not covered by v3 because BOTH partners
changed provisional name IDs in the original event record.

All 12 candidate edges passed the local full-pair, name-initial,
role/discipline and exact official-DOB checks. We then source-reviewed
the six pair identities against the original ISU results (short
published names) AND the original ISU couple biographies (full names
and date-of-birth metadata).

- ISU 2014 Sochi ice dance official results:
  https://results.isu.org/results/owg2014/CAT004RS.HTM
- ISU 2014 Sochi pairs official results:
  https://results.isu.org/results/owg2014/CAT003RS.HTM
- ISU 2009 Four Continents pairs official results:
  https://www.isuresults.com/results/fc2009/CAT003RS.HTM

Person- and source-specific evidence is frozen as an append-only v1
adjudication source ledger:

    data/adjudications/isu_historic_initial_only_pair_merges_v1.csv

The ledger holds six pair rows and 12 person alias sides. Each has
the original short and long person IDs, original pair IDs, DOBs,
ISU official couple biography ID and URL, ISU event result URL,
source-observed full names, and a specific reviewer explanation.

**Spelling caveat:** ISU officially spells the 2009 Taipei male
skater Darryll **SULINDRO-YANG**, while the historic v4
provisional name omits 'I' in **SULNDRO-YANG**. Preserve historic
published variants and identity lineage, do not silently correct
original event names.

## Run (from C:\chenxi\bazi_project\doubles)

Use each command as a single PowerShell line:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_historic_initial_only_source_merges_v2.py
    python .\scripts\audit_historic_alias_event_collisions_v1.py --preview .\output\historic_dob\shared_partner_identity\initial_only_v2\historic_reviewed_pair_groups_preview_v2.csv --out .\output\historic_dob\shared_partner_identity\initial_only_v2\event_collision_audit
    python .\scripts\audit_historic_modern_cross_era_v1.py --historic-people .\output\historic_dob\shared_partner_identity\initial_only_v2\historic_reviewed_person_id_preview_v2.csv --historic-pairs .\output\historic_dob\shared_partner_identity\initial_only_v2\historic_reviewed_pair_groups_preview_v2.csv --out .\output\historic_dob\cross_era_identity\historical_v2

The last cross-era pass uses the same original modern ranking and
Biography source files. It does not overwrite the prior cross-era v1
manifest or the 8-date supplemental preview (which was scoped to
v1 candidate edges). The eight prior missing-DOB historic IDs were
cross-checked against the 12 newly reviewed initial-only source IDs;
none is changed by the v2 mergers. After running the cross-era v2
audit, reapply the SAME source-reviewed 8-DOB ledger to the new
v2 candidate preview, preserving the previous original outputs:

    python .\scripts\audit_cross_era_bio_rescues_v1.py --review .\output\historic_dob\cross_era_identity\historical_v2\historic_modern_identity_review_v1.csv --manifest .\output\historic_dob\cross_era_identity\historical_v2\historic_modern_cross_era_manifest_v1.json --out .\output\historic_dob\cross_era_identity\historical_v2\official_bio_rescue

This should still rescue eight source-specific edges if the exact
same season rankings and Biography files are used; verify the
new source-augmented manifest rather than assuming it succeeded.

## Outputs and expected structural counts

Main output folder:

    output/historic_dob/shared_partner_identity/initial_only_v2/

- historic_initial_only_v2_manifest.json — old/new counts, input SHA256,
  review status and limitations.
- historic_initial_only_source_adjudication_v2.csv — all 12 approved
  source-backed ID edges with full provenance.
- historic_reviewed_person_id_preview_v2.csv — new reversibly projected
  866 historical identity slots (expected, requires local confirmation).
- historic_reviewed_pair_groups_preview_v2.csv — new 514 projected pair
  groups (expected) preserving all 553 original pair IDs.
- event_collision_audit/historic_alias_event_collision_manifest_v1.json
  and .../historic_alias_event_collision_review_v1.csv — rerun
  original pair-event deduplication checks using the v2 map.

The original data and v3 history are retained unchanged. No event
counts or original ranking points are added by this transformation.
Source-review URLs may reference the same ISU dataset used for DOB
coverage and therefore do not represent independent replication.

The prior 195 historic-modern candidate edges may shrink, because
five previous "two historic IDs -> one modern ID" ambiguities are
now represented by one reviewed historic ID each. Whether this
resolves those five components must be checked in the rerun's new
historic_modern_cross_era_manifest_v1.json.

## Return results for next stage

Upload these four files:

1. output/historic_dob/shared_partner_identity/initial_only_v2/historic_initial_only_v2_manifest.json
2. output/historic_dob/shared_partner_identity/initial_only_v2/event_collision_audit/historic_alias_event_collision_manifest_v1.json
3. output/historic_dob/cross_era_identity/historical_v2/historic_modern_cross_era_manifest_v1.json
4. output/historic_dob/cross_era_identity/historical_v2/historic_modern_identity_review_v1.csv

Any nonempty event-collision review CSV, DOB conflict CSV or
exception traceback should be retained for adjudication.

No BaZi, predictions, outcome-driven selection or final cohort
freeze at this stage.
