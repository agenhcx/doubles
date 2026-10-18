# Historical ISU couple-bio DOB extraction: local pilot

The October 2026 official biography index audit found 477 of 553 historically
observed couples (86.3%) with exact two-name matches to official pair profiles.
The other 65 one-name links and 11 unmatched pairs remain in the identity
review queue; do not drop them or assume missing DOB.

## Pilot (only local network usage)

After fetching the latest code, run:

    python .\scripts\collect_historic_isu_biographies.py --limit 20 --proxy http://127.0.0.1:10808

Inputs are the local official-index queue from the index crosslink step and
the small v2 official historical DOB seed in Git. The script reuses the
already populated cache/isu_bios/ directory and only fetches uncached files.
The first 20 profiles deliberately alternate between lower and higher official
profile IDs to test both legacy and modern page formats. Repeating the command
reuses cached HTML. The complete profile set uses --limit 0, **but should not
be used until the pilot shows the exact-name/date parser is reliable**.

Outputs (all local, ignored by Git) under output/historic_dob/biographies/:

- historic_isu_bio_manifest.json: number attempted, full vs partial parsing,
  cache hits, conflicts, parser modes and input SHA-256 hashes.
- historic_isu_bio_inventory.csv: each official biography's fetch/parse state.
- historic_isu_bio_candidates.csv: one row per expected named skater on each
  inspected source profile, including missing DOBs and explicit source URLs.
- historic_isu_bio_review.csv: unresolved dates or conflicts with a
  previously reviewed primary-source DOB; no silent deletion.
- historic_isu_person_dob_candidates.csv: source grouping by historic person
  ID, with a candidate date only when all observed source dates agree and
  do not contradict the manually reviewed seed.

The biographical parser deliberately requires both the exact historical
full name and a full day-level DOB attached to the Date of birth label.
It supports both:

    Date of birth: 04.10.1985 Dan ZHANG
    Alexander SHAKALOV 26.03.1982 Date of birth:

The latter layout occurs on older ISU records (isufs00007164).
DOBs from competition score tables, notes, or another skater are NOT
accepted without this explicit binding. Some old pages have unexpected
layouts; these are review cases, **not 1 January defaults or guessed DOBs**.

Accepted official sources still require an identity audit before adding
data to a consolidated historical DOB table. A person with different dates
on multiple official pair profiles is reported as conflicted, not silently
assigned either date. Original hist v4 and modern rankings are unmodified.
No astrological feature computation or partner-pool significance test
is performed here.
## Name-order reversal discovered in the 20-profile pilot

The first 20 historical biographies all downloaded, with 38 of 40 DOB
slots automatically bound. The only incomplete profile was the former
Italian ice-dance pair isufs00000472. Its historic ranking stores
FUSAR POLI Barbara / MARGAGLIO Maurizio but the official biography
prints Barbara FUSAR POLI (06.02.1972) and Maurizio MARGAGLIO
(16.11.1974). The first uses the forward DOB label layout, while
the second uses the historical reverse layout.

The parser now accepts only the original full token sequence or a
conservative surname-first/given-first token rotation **immediately
adjacent to a full date and explicit Date of birth label**. It does not
use unconstrained fuzzy matching. Such recovered rows are marked
dob_bound_to_rotated_name_review and kept in historic_isu_bio_review.csv,
even when the raw date field is populated. This lets an auditor accept
the source after inspecting its official page and pair identity.

Run the same 20-person sample with --offline before increasing the
collection size. The expected 40/40 DOB extraction does not imply
40 identity-reviewed records; the two rotated-name rows remain in
the review queue for audit.
