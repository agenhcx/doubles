#!/usr/bin/env python3
"""Merge audited 2004–2018 ISU results with 2018–2026 ISU season rosters.

Only roster identity discovery; NO BaZi and NO fabricated birth dates.
Historical pair-event counts remain unchanged: season rankings are NOT events.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime as dt
import json
from pathlib import Path
from audit_v4 import norm, person_id, pair_id


def load_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def join(existing, new):
    a=[v.strip() for v in (existing or "").split(";") if v.strip()]
    a.extend([v.strip() for v in new if v and v.strip()])
    return "; ".join(sorted(set(a)))


def merge(historic_dir, ranking_csv, output_dir):
    oldc=load_csv(historic_dir/"couples_v4.csv")
    olda=load_csv(historic_dir/"athletes_v4.csv")
    ranks=load_csv(ranking_csv)
    historic_lookup={(r["discipline"],norm(r["person_a_name"]),norm(r["person_b_name"])):r for r in oldc}
    old_people={r["person_id"]:r for r in olda}
    pairs={k:dict(v) for k,v in historic_lookup.items()}
    people={r["person_id"]:dict(r) for r in olda}
    season_rows=[];issues=[]; seen=set()
    per_pair=collections.defaultdict(list)
    added_names=collections.defaultdict(set)
    raw_ids_seen=collections.defaultdict(set)

    for i,r in enumerate(ranks, 2):
        disc=r["discipline"].strip()
        if disc not in ("Ice Dance", "Pair Skating"):
            issues.append({"row":i,"issue":"invalid_discipline","details":disc});continue
        name1,name2=(r.get("person_a") or "").strip(),(r.get("person_b") or "").strip()
        if not name1 or not name2 or norm(name1)==norm(name2):
            issues.append({"row":i,"issue":"invalid_pair_members","details":f"{name1} / {name2}"});continue
        key=(disc,norm(name1),norm(name2))
        rev=(disc,norm(name2),norm(name1))
        if rev in pairs and key not in pairs:
            issues.append({"row":i,"issue":"reversed_member_order","details":f"{name1} / {name2} | {disc}"})
            # do not change historic identities without checking sex/order
            continue
        if key not in pairs:
            pid=pair_id(key)
            pairs[key]={"pair_id":pid,"discipline":disc,
                       "person_a_id":person_id(key[1]),"person_b_id":person_id(key[2]),
                       "person_a_name":name1,"person_b_name":name2,
                       "represented_nations":"","identified_event_count":"0",
                       "events_with_numeric_rank":"0","events_with_numeric_score":"0",
                       "events_listed_withdrawn":"0","distinct_seasons_with_identified_events":"0",
                       "first_season":"","last_season":"","observed_seasons":"",
                       "source_types":"","evidence_only_aggregated_source":"YES",
                       "identity_status":"provisional_isu_ranking",
                       "name_variants_a":name1,"name_variants_b":name2,
                       "count_interpretation":"ISU season ranking only; independent event count unknown"}
        team=pairs[key]
        yr=r.get("season") or ""
        lev=r.get("level") or ""
        uniq=(key,yr,lev)
        if uniq in seen:
            # Duplicate source row is not a second independent result.
            issues.append({"row":i,"issue":"duplicate_ranking_row","details":f"{team['pair_id']} {yr} {lev}"})
            continue
        seen.add(uniq)
        team["represented_nations"]=join(team.get("represented_nations"),[r.get("nation","")])
        team["source_types"]=join(team.get("source_types"),["isu_season_ranking"])
        added_names[team["pair_id"]+"|A"].add(name1)
        added_names[team["pair_id"]+"|B"].add(name2)
        for name,which in [(name1,"A"),(name2,"B")]:
            k=norm(name); pid=person_id(k)
            if pid not in people:
                people[pid]={"person_id":pid,"name_display":name,"name_variants":name,
                    "disciplines":disc,"different_partners_provisional":"",
                    "distinct_identified_competitions":"0",
                    "represented_nations":"","role_A_or_B":which,
                    "date_of_birth":"","birth_city":"","birth_country":"","birth_latitude":"",
                    "dob_status":"not_checked","identity_review_flags":"provisional_isu_ranking"}
            person=people[pid]
            person["disciplines"]=join(person.get("disciplines"),[disc])
            person["represented_nations"]=join(person.get("represented_nations"),[r.get("nation","")])
            person["role_A_or_B"]=join(person.get("role_A_or_B"),[which])
            raw_ids_seen[pid].add(name)
        rankvalue=r.get("rank") or ""
        pointsvalue=r.get("points") or ""
        rec={"pair_id":team["pair_id"],"discipline":disc,"season":yr,"level":lev,
             "person_a_id":team["person_a_id"],"person_b_id":team["person_b_id"],
             "person_a_name":name1,"person_b_name":name2,"nation":r.get("nation", ""),
             "rank":rankvalue,"ranking_points":pointsvalue,
             "source_url":r.get("source_url", ""),"profile_url":r.get("profile_url", ""),
             "source_type":"isu_season_ranking",
             "interpretation":"rank/points are season-specific; NOT event scores"}
        season_rows.append(rec)
        per_pair[team["pair_id"]].append(rec)

    for k,t in pairs.items():
        rs=per_pair.get(t["pair_id"],[])
        srt=sorted({x["season"] for x in rs})
        t["isu_ranking_seasons"]="; ".join(srt)
        t["isu_ranking_season_count"]=str(len(srt))
        t["isu_ranking_rows"]=str(len(rs))
        t["isu_best_rank_in_own_season"]=(str(min(int(x["rank"]) for x in rs if x["rank"].isdigit())) if any(x["rank"].isdigit() for x in rs) else "")
        t["isu_junior_or_senior"]="; ".join(sorted({x["level"] for x in rs}))
        a,b=added_names.get(t["pair_id"]+"|A",set()),added_names.get(t["pair_id"]+"|B",set())
        t["name_variants_a"]=join(t.get("name_variants_a",""),a)
        t["name_variants_b"]=join(t.get("name_variants_b",""),b)

    for pid,p in people.items():
        p["name_variants"]=join(p.get("name_variants",""),raw_ids_seen.get(pid,set()))
        if len(raw_ids_seen.get(pid,set()))>1:
            issues.append({"row":"","issue":"multiple_published_spellings_auto_token_matched","details":p["name_display"]+" :: "+" | ".join(sorted(raw_ids_seen[pid]))})
        p["isu_ranking_seasons"]= "; ".join(sorted({r["season"] for r in season_rows if pid in (r["person_a_id"],r["person_b_id"])}))
    out=Path(output_dir)
    hist_fields=list(oldc[0]); per_fields=list(olda[0]);
    team_fields=hist_fields+["isu_ranking_seasons","isu_ranking_season_count","isu_ranking_rows","isu_best_rank_in_own_season","isu_junior_or_senior"]
    people_fields=per_fields+["isu_ranking_seasons"]
    roster_fields=["pair_id","discipline","season","level","person_a_id","person_b_id","person_a_name","person_b_name","nation","rank","ranking_points","source_url","profile_url","source_type","interpretation"]
    save_csv(out/"couples_master.csv",sorted(pairs.values(),key=lambda r:(r["discipline"],r["pair_id"])),team_fields)
    save_csv(out/"athletes_master.csv",sorted(people.values(),key=lambda r:r["person_id"]),people_fields)
    save_csv(out/"season_roster.csv",sorted(season_rows,key=lambda r:(r["season"],r["discipline"],r["level"],int(r["rank"]) if r["rank"].isdigit() else 9999)),roster_fields)
    save_csv(out/"identity_review.csv",issues,["row","issue","details"])
    summary={"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":"Ice dance + pair skating master roster; NO BaZi",
        "historic_unique_couples":len(oldc),"historic_unique_athletes":len(olda),
        "isu_ranking_rows_imported":len(season_rows),"unique_couples_including_rankings":len(pairs),
        "unique_athletes_including_rankings":len(people),
        "new_couples_vs_v4":len(pairs)-len(oldc),"new_athletes_vs_v4":len(people)-len(olda),
        "review_flags":len(issues),
        "warnings":["Identity provisional, with accents and surname order normalized conservatively",
                    "Season rankings are not individual competition results",
                    "The dataset does not cover every novice/national/ISU entrant",
                    "No DOB or birth location is inferred; no BaZi calculated"]}
    (out/"manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historic",type=Path,default=Path("data/historic/v4"))
    p.add_argument("--ranking",type=Path,default=Path("output/isu/isu_season_roster.csv"))
    p.add_argument("--out",type=Path,default=Path("output/master"))
    a=p.parse_args()
    if not a.ranking.exists():
        p.error(f"Ranking CSV does not exist: {a.ranking}; run collect_isu_seasons.py first")
    result=merge(a.historic,a.ranking,a.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
