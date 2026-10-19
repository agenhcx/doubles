# Bounded 2017-18 official source inventory v1

Date: 2026-10-19. Acquisition and source QA only; not a frozen scientific cohort.

## WC2018 checkpoint confirmed by the user's local outputs

The uploaded wc2018_extension_manifest_v2.json reports 865 -> 866 historical
registry person slots, 514 -> 516 pair groups, and 3,237 legacy source rows
plus 59 WC2018 overlay rows -> 3,296 union-index rows, with no event-key
collisions. The 59 new rows retain 36 total scores and 23 short-segment-only
scores. The added combinations are Reed/Ambrulevicius and Kashitsyna/Magyar;
Smart/Diaz reuses the historical pair through a source-specific name rule.

The separately uploaded wc2018_new_pair_combinations_v2.csv was read and its
actual SHA256 matched the extension manifest:

    09e67ee29574b2a2c4f1130157369289aa06876278e1b0837fba1c1caf8a69ab

The other extension files were not uploaded in this turn. Their reported
counts are grounded in the user's manifest, not a fresh full-data rerun here.
The new inventory script checks all four extension output hashes locally.

Keep the existing qualifications: 56 inherited exact-name links remain
candidates, the new person is an event-scoped source slot, and the 3,296-row
union is a source-row index rather than a harmonized or pooled score dataset.

## Defined acquisition scope, not all events in the season

This batch covers the 2017-18 senior non-team Pairs and Ice Dance categories
in 11 tournaments: six Grand Prix stops, the Grand Prix Final, Europeans,
Four Continents, Olympic individual events, and Worlds. This yields 22
selected event-discipline cells and an expected 44 Entry/Result pointers.
It excludes Junior, Challenger, national events and Olympic team competition
from THIS BATCH, not permanently from the research programme.

The official index pages were inspected via web retrieval on 2026-10-19:

- https://www.isuresults.com/results/season1718/gprus2017/
- https://www.isuresults.com/results/season1718/gpcan2017/
- https://www.isuresults.com/results/season1718/gpchn2017/
- https://www.isuresults.com/results/season1718/gpjpn2017/
- https://www.isuresults.com/results/season1718/gpfra2017/
- https://www.isuresults.com/results/season1718/gpusa2017/
- https://results.isu.org/results/season1718/gpf1718/
- https://results.isu.org/results/season1718/ec2018/
- https://results.isu.org/results/season1718/fc2018/
- https://results.isu.org/results/season1718/owg2018/
- https://results.isu.org/results/season1718/wc2018/

The NHK Trophy and Grand Prix Final use Comnet data0300.htm/data0390.htm
and data0400.htm/data0490.htm-style pages. Do not manufacture CATxxx URLs
from the Milan collector. The GPF index also lists Junior categories;
the Olympic index includes Team categories. Exact category-row labels and
Entry/Result anchor text determine the discovered source pointers.

## What this step actually does

The collector downloads only the 11 INDEX pages, caches original bytes,
records requested/effective URLs, UTC retrieval time and SHA256, and extracts
four actual HTML links per index. It cross-tabulates the 22 selected cells
against the old event inventory and the hash-verified WC2018 overlay.
It DOES NOT fetch or parse the 44 linked entrant/result tables in this step.
Those pointers are explicitly marked
REFERENCED_ONLY_NOT_DOWNLOADED_OR_ROW_AUDITED.

A successful 11/11 index scan therefore means source pointers were found,
not that every entrant or result is already complete or independently checked.
The global/all-entrant coverage fraction remains null. Existing legacy
results are not promoted to officially revalidated results by this operation.
No DOB, identity, score, old CSV or extension output is modified.

## Execution and tests

The new script was compiled and all 17 synthetic offline tests were executed
successfully in the development runtime. Tests cover ordinary and Comnet
links, mixed Junior/Team pages, missing categories, duplicate links, wrong
events, unsafe URLs/redirects, cache tampering, extension-hash changes,
non-overwrite outputs and an 11-index end-to-end offline fixture.

The runtime could not download raw official HTML through its direct Python
network connection. Thus the parser has NOT been executed here on the user's
full source dataset or all actual raw index pages. Actual local execution
remains necessary; do not describe synthetic tests as live-site validation.

From C:\chenxi\bazi_project\doubles, each command is one PowerShell line:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m compileall -q .\scripts .\tests
    python -m unittest discover -s tests -v
    python .\scripts\collect_core1718_source_inventory_v1.py --proxy http://127.0.0.1:10808

Inputs:
- data/historic/v4/event_inventory_v4.csv
- output/frame/isu_wc2018_extension_v2/wc2018_extension_manifest_v2.json
- all four files named in that extension manifest's output_sha256 map

Outputs under output/frame/isu_core1718_source_inventory_v1/:
- core1718_source_inventory_manifest_v1.json
- core1718_event_source_inventory_v1.csv

Expected, pending the local run: 11 verified index pages, 22 selected cells,
44 source pointers, 20 legacy cells and two WC2018 overlay cells. No new
entrant/result rows are ingested. Network/parser failures preserve explicit
hold rows and produce a nonzero exit status, never a false zero-participant
observation. The output directory must be new.

After successful download, replay from immutable cache into a new directory:

    python .\scripts\collect_core1718_source_inventory_v1.py --offline --out .\output\frame\isu_core1718_source_inventory_v1_replay

A new --cache directory requests a fresh independent snapshot; this version
does not silently refresh existing raw-source bytes.

Return the two new output files. The subsequent acquisition step can then
use these exact source pointers to fetch the official Entry/Result tables,
retain WD/FNR/entry-only states, and compare them with existing source rows
without double-appending competitions already present in the union.

No astrology, outcome-driven selection, null modelling, hypothesis changes
or research-cohort freeze is performed by this stage.
