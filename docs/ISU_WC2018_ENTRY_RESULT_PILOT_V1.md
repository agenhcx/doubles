# ISU 2018 Milan World Championships: event-first entry/result collection pilot

Date: 2026-10-18. This is a source-preserving acquisition and identity-QA
pilot. It does **not** modify any historical v4 event or athlete master,
and does **not** calculate BaZi, select a sample based on results, or
claim a complete international skating-entrant universe.

## Prerequisite audit

The locally supplied competition-frame v1 manifest passed these
source/frame checks:

- Historical results: 15 seasons, 135 tournament instances,
  270 discipline-event cells, 3,237 original pair-event records.
- 266/270 historical event cells have only third-party links in the
  current index. This does not prove they are inaccurate, but means
  independent official-result provenance remains to be audited.
- Modern collection: 1,584 ISU **Season's World Ranking** rows,
  not individual event starts or results.
- 2018 Milan Worlds was absent from the historic v4 event inventory
  in both Ice Dance and Pair Skating.

Four primary official Swiss Timing ISU pages were checked:

| Discipline | Official entries | Final results | Published entries | Completed free segment | Did not reach final segment |
|---|---|---|---:|---:|---:|
| Ice Dance | https://results.isu.org/results/season1718/wc2018/CAT004EN.HTM | https://results.isu.org/results/season1718/wc2018/CAT004RS.HTM | 31 | 20 | 11 |
| Pair Skating | https://results.isu.org/results/season1718/wc2018/CAT003EN.HTM | https://results.isu.org/results/season1718/wc2018/CAT003RS.HTM | 28 | 16 | 12 |

The **59 event entries** are not assumed to be 59 globally new pairs.
In these particular published results, 59 corresponding placements are
shown (36 completed the free segment, 23 were Final Not Reached). The
ISU's FNR display gives short-program/dance scores, **not** total scores.
The entry sheets and result sheets must therefore be retained as
different data objects. Entries do not generically guarantee a start.

## Local collection

From C:\chenxi\bazi_project\doubles, run each PowerShell command on
its own line:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\collect_isu_wc2018_entries_v1.py --proxy http://127.0.0.1:10808

If direct access works, omit --proxy. The four raw official HTML pages
are preserved in cache/isu_wc2018_official/ (cache excluded from Git).
To **replay without network** once the pages have been downloaded:

    python .\scripts\collect_isu_wc2018_entries_v1.py --offline

For an intentional fresh download, use --refresh together with the
proxy or direct connection; --offline and --refresh cannot be combined.

## Validation rules

The collector requires the exact two official gap source entries in
data/frame/isu_verified_entry_gaps_v1.csv and checks approved URLs.
Each official page must contain one unambiguous name/profile link per
entry/result row, one ordinal/placement, an attributable country code,
and the expected row count.

Rank/entry numbers must have no gaps or duplicates. The result page must
also contain the independently verified final/FNR split (20/11 for
Ice Dance, 16/12 for Pairs). Incomplete HTML, network failures, encoding
issues, structural changes and unexpected record counts are recorded
as failures, **never silently treated as zero participants**.

Entry/result records are linked first on ISU biography ID within each
discipline and then compared with published names and nations.
Unmatched profile IDs, name differences (e.g. historical UTF-8/Latin-1
issues), and nation mismatches remain visible in a review status.
Name-only fallback is explicitly held, not treated as proof of identity.

## Outputs

Under output/frame/isu_wc2018_pilot_v1/:

- official_wc2018_entry_result_manifest_v1.json
- official_source_page_inventory_v1.csv (four page statuses, URLs,
  cache paths, and HTML SHA256 values)
- official_event_entries_v1.csv (59 expected entry records; no result
  assumptions, original names/profile URLs/nations preserved)
- official_event_results_v1.csv (59 expected result rows; final vs FNR
  scores are separate, not added)
- official_entry_result_link_review_v1.csv (59 expected candidate
  pair-level entry/result correspondences and hold flags)
- official_result_without_entry_review_v1.csv (should be empty for
  this four-page pilot)

The main source-status field is SOURCE_PAGES_VALIDATED only when all
four page parses pass. It is not equivalent to every row being
independently person-identity-confirmed; inspect
entry_result_link_status_counts as well. Original historical roster,
DOB source ledgers, modern season-ranking rows, results and scores
remain untouched.

## Next stage after the first real run

Compare new official entrants against reviewed 865 historical person
slots and 514 historical pair groups, without equating name similarity
or the same date alone with identity. Use source-reviewed links to
identify which new entries actually extend the existing event/roster
records. Add 2018 Milan results as separate event observations only
after review of any name, nation or profile exceptions.

Next, build an explicitly defined target event universe for a bounded
season/family (e.g., all senior World Championships and GP Series
in 2017–18), and an official event entry/results inventory before
claiming completeness percentages. Keep the 2020–21 pandemic ranking
disruption as an exceptional stratum and do not mix junior and senior
rankings into a single performance outcome.

## Return files

Please upload:
1. output/frame/isu_wc2018_pilot_v1/official_wc2018_entry_result_manifest_v1.json
2. output/frame/isu_wc2018_pilot_v1/official_source_page_inventory_v1.csv
3. output/frame/isu_wc2018_pilot_v1/official_entry_result_link_review_v1.csv

If any official page fails, the source-page inventory plus the cached
HTML file (if available) can diagnose the exact parser difference.
Do not rerun broad historical crawling unless the four-page pilot
identifies a broader issue.
