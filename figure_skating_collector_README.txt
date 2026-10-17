ICE DANCE + PAIR SKATING ROSTER COLLECTION (no BaZi)

Scope: any publicly listed ice dance or pair-skating combination; senior/junior/novice not yet harmonized. Sources are event result CSVs in a historical research GitHub archive and an independently aggregated public couples catalog. This is not exhaustive worldwide (no national/all-club guaranteed coverage).

Online collection (Windows PowerShell, one line each):
python -m pip install requests beautifulsoup4
python .\collect_ice_dance_pairs_roster.py --source both --pilot-csv .\ice_dance_pairs_seed_2004_2005.csv --extra-seed .\figure_skating_extra_seed_2014_2016_2017.tsv --out .\skating_roster

If your network blocks GitHub raw data, download this archive using a browser:
https://github.com/mengyazhu96/figure-skating-analysis/archive/refs/heads/master.zip
Then:
python .\collect_ice_dance_pairs_roster.py --source github --repo-zip .\figure-skating-analysis-master.zip --pilot-csv .\ice_dance_pairs_seed_2004_2005.csv --extra-seed .\figure_skating_extra_seed_2014_2016_2017.tsv --out .\skating_roster

For a quick source-site smoke test:
python .\collect_ice_dance_pairs_roster.py --source catalog --max-catalog-pages 2 --out .\skating_roster_test

Outputs:
  athletes.csv        Provisional unique people; DOB, place of birth, latitude intentionally blank.
  couples.csv         Exact-name normalized unique partnerships (order-independent).
  observations.csv    Observed pairs, source, event/season, score and rank when present.
  source_inventory.csv Source URLs and download/parse status; failures are not silently skipped.
  manifest.json       Counts, limitations, failed sources and collection timestamp.

Important limitations:
  - No Bazi computation. DOB/place of birth need independent source verification later.
  - Name variants and transliterations are *not* automatically merged.
  - The public couples catalog includes domestic and unusual/novice/solo records; these are explicitly flagged for audit.
  - Results archive covers a selected 2005-06 through 2017-18 set of major international events, not all junior/regional/ISU events.
  - The public couples catalog can change or restrict access, so the script caches downloaded HTML and CSV files and preserves failures in source_inventory.csv.
  - If one source is blocked, the other source's results are still exported; inspect manifest.json before interpreting counts.

IMPORTANT: The online catalog contains 2026–27 listings. Default max season start 2025 keeps data beginning no later than 2025–26; undated listings remain marked and need review.
Do not treat a historical list from selected major competitions as an exhaustive ISU roster; missing years, junior/regional events and pandemic 2020–21 require explicit coverage audits.
If the catalog appears unavailable or the HTML changes, the script records the error; inspect source_inventory.csv and manifest.json.
