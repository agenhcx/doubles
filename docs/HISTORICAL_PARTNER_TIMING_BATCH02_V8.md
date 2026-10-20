# Historical partnership timing: second source-review batch (v8)

Reviewed 2026-10-20. This is an additive evidence ledger, not an executable migration, a final timeline, or a statistical sample.

## Scope and continuity

The retained historical baseline remains 501 event-backed pair keys, 1,315 pair-season rows and 3,296 selected pair-event observations. No original registry, DOB, score, pair-season row or previous source table is rewritten.

This pass continues the previous discipline-specific ordering by focal registry person ID and chronological different-partner observation comparison. There are three comparison rows per discipline, involving **five distinct focal people**: Aritz Maestu contributes two Pairs comparisons.

The container runtime failed during this turn. Consequently the prior v7 ZIP could not be opened or its exact queue hashes revalidated. Continuity was reconstructed manually using exact person IDs in the original uploaded historical_pair_seasons_v6.csv. The earlier six pilot cases are not repeated here. Original v7 contrast IDs are not invented; the new ledger provides explicit person, pair and observed-season keys instead.

## Results

| Case | Focal person | Observed old partner -> observed new partner | Last old / first new selected season | Explicit new formation time |
|---|---|---|---|---|
| V8_D04 | Justyna Plutowska | Peter Gerber -> Jeremie Flemin | 2013-14 / 2017-18 | May 2016; ISU pair biography |
| V8_D05 | Paul Poirier | Vanessa Crone -> Piper Gilles | 2010-11 / 2012-13 | July 2011; Canadian Olympic Committee |
| V8_D06 | Kristjan / Kristian Rand | Grethe Gruenberg -> Caitlin Mallory | 2006-07 / 2008-09 | Summer 2008; ISU pair biography |
| V8_P04 | Nathan Bartholomay | Felicia Zhang -> Deanna Stellato | 2013-14 / 2017-18 | July 2016; U.S. Figure Skating |
| V8_P05 | Aritz Maestu | Veronica Grigorieva -> Marcelina Lech | 2013-14 / 2015-16 | Not established in reviewed primary sources |
| V8_P06 | Aritz Maestu | Marcelina Lech -> Laura Barquero | 2015-16 / 2017-18 | Not established in reviewed primary sources |

The formation fields have three month-level statements and one year-plus-season-word statement. No exact formation day is supplied or invented. The two cases without explicit timing remain missing; they were not replaced with easier cases.

## Important new structural finding: an intervening partner

The U.S. Figure Skating roster and retrospective athlete interview identify **Gretchen Donlan** between Bartholomay's partnerships with Zhang and Stellato. The federation profile gives Donlan/Bartholomay as 2014-16, while the interview explicitly places their split in **March 2016**. Formation with Stellato is stated as **July 2016**.

Primary sources:

- https://usfigureskating.org/sports/figure-skating/roster/-nbsp--deanna-stellato-and-nathan-bartholomay/57
- https://usfigureskating.org/news/2018/11/15/figure-skating-nathan-bartholomay-found-the-right-girl-in-deanna-stellato.aspx

Therefore the selected-observation endpoints Zhang -> Stellato must **not** be encoded as one direct partnership switch. Donlan is a source-confirmed intervening partner not present in this focal person's selected pair-season sequence. This pass did not determine whether a Donlan/Bartholomay pair already exists among the registry-only rows. It creates neither a new person ID nor a new pair/event record.

The same interview says Zhang retired in July in a narrative about the aftermath of Sochi 2014. The ledger distinguishes the explicitly stated month from the year resolved from context and labels this as **retirement**, not an exact dated split. The March 2016 date applies to Donlan/Bartholomay, not Zhang/Bartholomay. No duration is calculated by subtracting these partial dates.

## Earlier observation is not formation

For Lech/Maestu, the Spanish federation's 2014 national championship result lists the pair. Its event index gives an overall event window of **19-21 December 2014**:

- https://www.rfedh.es/wp-content/uploads/resultados-patinaje/CEsp_2014/CAT027RS.HTM
- https://www.rfedh.es/wp-content/uploads/resultados-patinaje/CEsp_2014/index.htm

This is earlier paired competition evidence than their first selected-history season (2015-16). It is not a formation statement. The result page's 22 December update date is not treated as a competition or formation date. The exact pair-specific competition day was not established in this pass. National competitions are outside the selected historical frame and this row is not appended to it.

For Barquero/Maestu, the inspected ISU biography and federation competition news confirm the partnership but do not explicitly establish its formation date. An Olympics.com search-index lead mentions 2017, but the full page returned HTTP 502. That snippet was not promoted to an accepted formation time. Similarly a secondary lead to a Crone/Poirier end announcement was not accepted because the cited original announcement was not retrieved.

## Files and verification boundary

Structured source ledger:

`data/adjudications/historical_partner_timing_batch02_v8.json`

It contains the six comparison keys, source URLs and locations, short evidence excerpts, precision-specific time fields, explicit missing-data statuses, intervening-partner flag and provenance limitations. Sources are retrospective official biographies/interviews unless otherwise labeled. Webpage update dates and review date are separated from the historical event time.

This turn performed exact-ID file reads and primary-web-text review. **No code tests were executed, no original HTML snapshots were saved, no local ZIP was generated, and no full historical hash replay was performed.** The source CSV hash quoted in the ledger is from the prior manifest, not an independent checksum computed this turn. GitHub's file creation is persistence of a manual ledger, not validation of an executable pipeline.

No installation or script run is required. An ordinary fast-forward pull retrieves the new ledger and this note:

```powershell
git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
```

## Next source tasks

Keep all 165 observed different-partner comparisons and all 1,793 adjacent-observation comparisons in the earlier work tables. This pass does not rewrite that queue or manufacture a new cumulative validation manifest. Continue the fixed-order source review while separately retaining these follow-ups: exact formation evidence for the two Maestu cases, original prior-partnership end announcements, and the registry-only status of Donlan/Bartholomay. Do not search for performance or BaZi effects before the observation mechanism and final analysis plan are defined.
