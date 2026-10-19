# 2017-18 senior core: official entry/result tables v1

This follows the verified 11-index, 22-discipline-cell inventory. It is not
a new identity merge, an expanded scientific cohort, or a complete world
competition census. The original data and WC2018 extension stay unchanged.

## Confirmed input, not a participant denominator

The uploaded core1718 source inventory reports 11 index pages verified,
zero failed, 44 discovered Entry/Result URLs, 20 locally present legacy
cells and two WC2018 overlay cells. The selected frame contains 291 local
pair-event records. Its all-entrant coverage fraction is deliberately null.
The uploaded inventory bytes match the SHA256 in its manifest.

The 291 selected-frame records are NOT the complete 3,296-row historical
union and are NOT an imposed target for the new official tables. The new
collector must report whatever source rows it actually parses. Equal row
counts would not, by themselves, demonstrate equal identities or scores.

## New collector

    scripts/collect_core1718_entry_results_v1.py

It reads the exact URLs from the hashed inventory; it does not generate
CAT or data filenames. It downloads the 44 referenced tables and stores
immutable per-URL HTML snapshots with effective URL, UTC retrieval time
and SHA256 sidecars. Redirects must stay within the same official event.

The parser locates the Name/Nation/position/Points headers. It supports
slash-separated names and explicit HTML line breaks. Unsplit published
names stay in the record with empty member fields and a review flag;
there is no inferred name boundary or new person ID.

The official pages inspected through the browser show two important
format differences:

- NHK Trophy uses Entry and Final Results tables with line-break names,
  and puts Points AFTER SP/FS or SD/FD:
  https://www.isuresults.com/results/season1718/gpjpn2017/data0400.htm
  https://www.isuresults.com/results/season1718/gpjpn2017/data0390.htm
- The Olympic pairs Entry sheet includes abbreviated names and the
  source nation label OAR. It must not be silently recoded as RUS:
  https://results.isu.org/results/season1718/owg2018/CAT003EN.HTM

Nation labels are preserved from the nation column and image metadata,
not inferred geography. Conflicting printed/flag labels are held. Thus
BUL and OAR no longer depend on an incomplete hand-built country list.

## Three separate outputs of the comparison process

1. Official source rows: Entry and Result rows remain different objects,
   with raw cell strings, original names, source hashes, explicit statuses,
   published points, and separate total/short-segment score fields.
2. Entry-to-result leads: same-profile matches are checked against both
   names and nation. Name-only, different-name, entry-only and result-only
   cases remain review cases. A missing results page is NOT evidence that
   every entered pair withdrew.
3. Official-to-local leads: exact normalized full-pair names are compared
   with the unchanged legacy or WC2018 overlay record for that same event.
   Rank/point differences are retained, never repaired automatically.
   An unmatched abbreviation is not declared a newly discovered person.

Final Not Reached source rows retain short-segment points, not totals.
WD/DNS/DQ rows are retained; any displayed points on those rows are left
unclassified rather than guessed to be totals or short-program scores.
Unknown statuses remain flagged. Numerical agreement does not reclassify
the meaning of a legacy score or independently verify a person's identity.

The source page may be a final snapshot rather than the first entry list.
Early replacements/withdrawals missing from that snapshot cannot be
reconstructed from these four columns or inferred from count equality.

## Testing performed before delivery

33 new synthetic/offline tests were executed successfully in Python
3.13.5. Python 3.10 syntax parsing also passed; the Python 3.10 interpreter
itself was not available in this environment. Tests cover header order,
line-break names, source nation codes, FNR, WD/DNS/DQ, unknown states,
entry-only/result-only relationships, source comparison differences,
44-page offline integration, cache corruption, stale inputs, redirect
restrictions and refusal to overwrite an output folder.

These fixtures are synthetic HTML, NOT archived copies of the real 44
source pages. Browser text was inspected for several official formats,
but the execution environment could not download the raw ISU HTML.
The new parser still requires a first real run on the user's machine.
The complete repository test suite has not been rerun here.

## Commands: one line per PowerShell command

From C:\chenxi\bazi_project\doubles:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\collect_core1718_entry_results_v1.py --proxy http://127.0.0.1:10808

This first run fetches 44 table pages, not the 11 index pages already
fetched by the prior stage. It uses its own new table cache; even WC2018
is parsed as a separate comparison snapshot, not added to the union again.

Default output:

    output/frame/isu_core1718_entry_results_v1/

Default cache:

    cache/isu_core1718_entry_results_v1/

Existing outputs are not overwritten. After a completed download, replay
from cache into a new output directory:

    python .\scripts\collect_core1718_entry_results_v1.py --offline --out .\output\frame\isu_core1718_entry_results_v1_replay

If an online run was incomplete, repeat the online command with a new
--out directory; existing valid cache snapshots are reused and missing
pages are fetched. For a deliberately new remote snapshot, specify BOTH
a new --cache and a new --out directory. Do not delete or edit source
hash metadata to silence errors.

## Output files and interpretation

- core1718_entry_result_manifest_v1.json: page outcomes, actual entry and
  result row counts, status summaries, local difference counts and hashes.
- core1718_table_page_inventory_v1.csv: one row per attempted source page;
  written after each attempt, with errors and raw HTML hashes.
- core1718_official_table_records_v1.csv: all parsed source records;
  raw cells and uncertain fields are retained for inspection.
- core1718_entry_result_links_v1.csv: one-to-one source-page links or holds.
- core1718_local_result_comparison_v1.csv: exact-name comparison leads,
  unmatched local/official rows and published rank/point differences.
- core1718_cell_counts_v1.csv: 22 cell-level counts and comparison states;
  unknown source counts are blank, not zero.

ALL_44_TABLES_PARSED means the selected tables parsed without row flags;
it does not mean zero identity discrepancies. Inspect the comparison
counts as well. PARSED_WITH_ROW_REVIEW retains uncertain source rows.
INCOMPLETE means a page failed or was not attempted. The command exits
nonzero for incomplete collection or cell-level comparison errors.

Upload the manifest, cell-count CSV and local-result comparison CSV.
If any page fails, include the page inventory. Do not merge these new
source records into the historical union based on parsing success alone.
No astrology, outcome-based eligibility changes or cohort freeze occur.
