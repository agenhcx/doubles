# Historical surname-plus-initial identity audit v1 (no automatic merges)

During the 2026-10-18 historic/modern comparison, six historic
provisional IDs matched modern official DOBs despite a different old
name string. Inspection of the original historic v4 pair roster exposed
a specific upstream cause: some competition files published the
skater's surname followed by only the first letter of the given name.

A **static inspection** of the 553 historic v4 pair records found 12
such provisional skater IDs in six pairs:

| Abbreviated historic pair | Candidate full historic pair |
| --- | --- |
| SINITSINA V / ZHIGANSHIN R | Victoria SINITSINA / Ruslan ZHIGANSHIN |
| TOBIAS I / STAGNIUNAS D | Isabella TOBIAS / Deividas STAGNIUNAS |
| MOORE-TOWERS K / MOSCOVITCH D | Kirsten MOORE-TOWERS / Dylan MOSCOVITCH |
| DELLA MONICA N / GUARISE M | Nicole DELLA MONICA / Matteo GUARISE |
| DAVIDOVICH A / KRASNOPOLSKI E | Andrea DAVIDOVICH / Evgeni KRASNOPOLSKI |
| SUNYOTO-YANG A / SULNDRO-YANG D | Amanda SUNYOTO-YANG / Darryll SULNDRO-YANG |

The first five short-name rows came from the 2014 Sochi Winter Olympics
source and the sixth from a 2008–09 source. Importantly, the ISU
official Olympic result pages themselves sometimes print these
abbreviations. Primary result pages and older official athlete bios
provide substantial pair chronology evidence for the first five:

- https://results.isu.org/results/owg2014/CAT004RS.HTM
- https://results.isu.org/results/owg2014/CAT003RS.HTM
- https://results.isu.org/bios/isufs00011268.htm (Sinitsina/Zhiganshin)
- https://results.isu.org/bios/isufs00012896.htm (Tobias/Stagniunas)
- https://www.isuresults.com/bios/isufs00012356.htm (Moore-Towers/Moscovitch)
- https://results.isu.org/bios/isufs00034501.htm (Davidovich/Krasnopolski)

The initial shared-partner alias audit could not find these duplicates
because BOTH members of the old published pair had new provisional
IDs. A fixed partner ID was therefore not available as an anchor.

## Run this conservative discovery stage

From C:\chenxi\bazi_project\doubles after pulling and tests:

    git -c http.proxy=http://127.0.0.1:10808 pull --ff-only
    python -m unittest discover -s tests -v
    python .\scripts\audit_historic_initial_only_aliases_v1.py

Expected artifacts under output/historic_dob/initial_only_alias_audit/:

- historic_initial_only_alias_manifest_v1.json
- historic_initial_only_person_candidate_links_v1.csv
- historic_initial_only_pair_candidate_groups_v1.csv

The offline script proposes a link ONLY if surname+given initial,
member side, discipline, BOTH members of the same prospective full pair
and historical official day-level birth dates agree. It neither
auto-merges nor modifies the 878/520 v3 reviewed historical preview.
An official source-specific adjudication step is still required.
If all 12 identity links are eventually accepted, the historical
identity count could drop by up to 12, but DO NOT treat that expectation
as a finalized person count. Event-count collision analysis must also
be rerun after any future source-approved identity changes.

This is quality control only. No BaZi or predictive hypotheses are
generated from the sample.
