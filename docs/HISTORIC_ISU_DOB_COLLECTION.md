# Historical ISU DOB discovery, 2004–2018

## Scope

The historical v4 seed contains 910 provisional athlete identities and 553
pairs reconstructed from selected historical ISU event results. These are NOT
all international entrants in those years. Current 2018–19 to 2025–26 ranking
data contain 1,038 DOB-complete provisional canonical people and 612 canonical
pairs. The **cross-era intersection is not known until the local audit runs**.

Data collection is independent of the later Calendar Null / Skater Pool Null
design. No BaZi indicators, matching-score optimization, significance tests,
or performance-based athlete exclusion occur in this phase.

## Two-step collection plan (run locally)

1. Reuse names and verified DOBs already in the recent ISU-ranked cohort:

    python .\scripts\audit_historic_dob_gap.py

   Files under output/historic_dob/: historic_dob_gap_manifest.json,
   historic_identity_dob_candidates.csv, historic_same_pair_candidates.csv,
   historic_dob_followup_queue.csv.

   A unique exact name + independently listed matching partner is tagged
   exact_name_same_pair; a unique name without that pair evidence is tagged
   exact_name_only. Neither automatically modifies the master. Historical
   abbreviated names, ambiguous full names and unmatched names remain in the
   review queue. An unchanged partner may suggest a surname/alias candidate,
   but NEVER approves that identity. Existing DOBs are suggestions with
   source links, not newly independent verification.

2. Search public Wikidata for additional **DOB leads only**:

    python .\scripts\collect_historic_wikidata_leads.py --limit 20 --proxy http://127.0.0.1:10808

   This pilot selects the first 20 safe full-name unresolved records, queries
   the documented MediaWiki Action API, caches all search and entity responses,
   and writes output/historic_dob/wikidata/historic_wikidata_manifest.json and
   historic_wikidata_dob_leads.csv. Every Wikidata P569 value must specify
   day precision (11); month/year-precision values are not guessed as Jan 1.
   The output label is always wikidata_unverified_needs_official_corroboration,
   even when the entity reports figure skating as an occupation or sport.

   The script is resumable: successful search/entity responses are cached
   under the ignored cache/historic_wikidata/ directory. --offline replays
   existing cached results; --limit 0 means all names in the follow-up queue.
   Network errors are visible in wikidata_fetch_errors.csv and never treated
   as absent people. Do not conduct a large full run until the 20-person pilot
   establishes API accessibility and useful candidate quality.

## Verification policy

Accept a new historical DOB only after matching the public figure using
independent identity clues (ISU pair partner, discipline, era, nationality,
or a unique profile ID) AND inspecting a trustworthy official biography,
competition start list, federation roster or comparable primary source.
Store the exact source URL, the printed birthdate and any name variants.
Do not fill unknown dates from a bare Wikipedia/Wikidata claim.

Birth location is separate from nationality/represented team. Keep full
audit queues so publication can describe missingness and selection bias.
Any user-facing global count must identify the bounded historical source
coverage; it does not represent all skaters.

## Pool-null prior art (method NOT original)

The statistical idea of testing whether observed paired people differ from
randomly re-matched people drawn from the same pool has extensive precedent:

- "Indirect assortative mating for human disease and longevity", Heredity
  (2019), doi:10.1038/s41437-019-0185-3, permuted partners within groups
  stratified by birth year and birth place, using 10,000 permutations.
  https://www.nature.com/articles/s41437-019-0185-3
- Maslov & Sneppen (2002), Science 296:910–913,
  doi:10.1126/science.1065103, degree-preserving network edge swaps.
  https://pubmed.ncbi.nlm.nih.gov/11988575/
- Neal (2025), Social Networks 80:59–64,
  doi:10.1016/j.socnet.2024.09.001, trade randomization of bipartite networks
  with fixed degree sequences and a practical stopping rule.
  https://www.sciencedirect.com/science/article/pii/S0378873324000583
- Franken, Bekhuis & Tolsma (2025), Research Quarterly for Exercise and
  Sport 96:233–247, doi:10.1080/02701367.2024.2389907, empirical sports
  partnership selection analysis; this is conceptual context, NOT evidence
  that the paper uses the same pool-rewiring null.
  https://pubmed.ncbi.nlm.nih.gov/39213427/

Methodological novelty, if any, must come from the scientifically appropriate
data frame, preregistered dyadic birthdate features, temporal partner-network
constraints, missingness audits, and independent external validation—not from
claiming to invent within-pool random pairing. No nulls are implemented in the
current collection scripts.
