#!/usr/bin/env python3
"""Audit official 2018 Milan event entries against existing historic/modern IDs.

A source-preserving crosswalk, never an automatic identity merge. Inputs are
previously verified official entry/result CSV plus the local reviewed historical
and modern identity preview. No event-count aggregation or BaZi calculation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path('output/frame/isu_wc2018_pilot_v1')
EVENT_ROWS = BASE / 'official_entry_result_link_review_v1.csv'
EVENT_MANIFEST = BASE / 'official_wc2018_entry_result_manifest_v1.json'
PAGE_INVENTORY = BASE / 'official_source_page_inventory_v1.csv'
ORIGINAL = Path('data/historic/v4/couples_v4.csv')
HIST_PAIRS = Path('output/historic_dob/cross_era_identity/ambiguity_source_v3/historical_source_reviewed_pair_preview_v3.csv')
HIST_PEOPLE = Path('output/historic_dob/cross_era_identity/ambiguity_source_v3/historical_source_reviewed_person_preview_v3.csv')
EVENT_INDEX = Path('data/historic/v4/event_inventory_v4.csv')
MODERN = Path('output/master/season_roster.csv')
MODERN_PEOPLE = Path('output/historic_dob/cross_era_identity/modern_profile_v4/modern_source_reviewed_person_id_projection_v4.csv')
OUT = Path('output/frame/isu_wc2018_identity_bridge_v1')
EVENT = 'wc2018'
SEASON = '2017-2018'
EXPECTED = {'Ice Dance': (31, 20, 11), 'Pair Skating': (28, 16, 12)}
PROFILE = re.compile(r'^/bios/(isufs[0-9]+)\.htm$', re.I)
LINK_FIELDS = ('event_id','discipline','entry_ordinal','name_as_published',
               'person_a_as_published','person_b_as_published','nation_as_published',
               'isu_profile_id','isu_profile_url','entry_source_url','entry_source_sha256',
               'result_source_url','final_placement','result_status',
               'result_points_as_published','result_points_interpretation',
               'result_profile_id','result_nation_as_published','entry_result_link_status')
HIST_FIELDS = ('pair_id','discipline','person_a_id','person_b_id','person_a_name','person_b_name')
PREVIEW_FIELDS = ('discipline','projected_person_a_id','projected_person_b_id','original_pair_ids')
PERSON_FIELDS = ('projected_person_id','date_of_birth')
MODERN_FIELDS = ('discipline','pair_id','person_a_id','person_b_id','person_a_name',
                 'person_b_name','profile_url','season')
MODERN_CANON_FIELDS = ('discipline','original_modern_person_id','canonical_modern_person_id')
OUTPUT_FIELDS = [
    'event_id','discipline','entry_ordinal','name_as_published','nation_as_published',
    'isu_profile_id','entry_source_url','result_source_url','result_status',
    'final_placement','result_points_as_published','result_points_interpretation',
    'historic_original_pair_ids','historic_projected_a_id','historic_projected_b_id',
    'historic_a_dob','historic_b_dob','historic_a_individual_leads',
    'historic_b_individual_leads','historic_pair_link_status',
    'modern_pair_ids','modern_name_matched_pair_ids','modern_profile_matched_pair_ids',
    'modern_canonical_a_ids','modern_canonical_b_ids','modern_link_status',
    'event_extension_status','identity_decision',
]
EXT_FIELDS = [
    'event_id','discipline','name_as_published','person_a_as_published',
    'person_b_as_published','nation_as_published','isu_profile_id',
    'entry_source_url','result_source_url','final_placement','result_status',
    'points_as_published','points_interpretation','historic_pair_link_status',
    'historic_original_pair_ids','historical_identity_merge_action',
    'event_observation_status',
]


def read(path, columns):
    with Path(path).open('r',newline='',encoding='utf-8-sig') as f:
        table=csv.DictReader(f)
        missing=set(columns)-set(table.fieldnames or [])
        if missing:raise ValueError(f'{path}: missing columns {sorted(missing)}')
        return list(table)


def write(path,rows,columns):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(s):return {x.strip() for x in (s or '').split(';') if x.strip()}


def joined(items):return '; '.join(sorted({x for x in items if x}))


def norm_name(s):
    x=unicodedata.normalize('NFKD',(s or '').casefold())
    x=''.join(c for c in x if not unicodedata.combining(c))
    return ' '.join(sorted(re.findall(r'[a-z0-9]+',x)))


def profile_id(url):
    u=urlsplit(url or '')
    if u.scheme not in {'http','https'} or u.hostname not in {'results.isu.org','www.isuresults.com'} or u.username or u.password or u.port is not None or u.query or u.fragment:
        return ''
    m=PROFILE.fullmatch(u.path)
    return m.group(1).lower() if m else ''


def valid_date(s):
    try:return bool(s and date.fromisoformat(s).isoformat()==s)
    except (ValueError,TypeError):return False


def audit(event_rows=EVENT_ROWS,event_manifest=EVENT_MANIFEST,inventory=PAGE_INVENTORY,
          original=ORIGINAL,historic_pairs=HIST_PAIRS,historic_people=HIST_PEOPLE,
          historic_event_index=EVENT_INDEX,modern=MODERN,modern_people=MODERN_PEOPLE,out=OUT):
    paths=(event_rows,event_manifest,inventory,original,historic_pairs,
           historic_people,historic_event_index,modern,modern_people)
    with Path(event_manifest).open(encoding='utf-8') as f:meta=json.load(f)
    if (meta.get('source_status')!='SOURCE_PAGES_VALIDATED' or
        meta.get('pages_validated')!=4 or meta.get('official_entry_records')!=59 or
        meta.get('official_result_records')!=59 or
        meta.get('joined_entry_result_records')!=59 or
        meta.get('results_without_entry')!=0 or
        meta.get('entry_result_link_status_counts')!={'PROFILE_MATCH_BOTH_OFFICIAL_PAGES':59}):
        raise ValueError('2018 official source pilot is incomplete or its manifest changed')
    if sha(inventory)!=meta.get('page_inventory_sha256'):
        raise ValueError('Official source page inventory SHA disagrees with validated manifest')
    pages=read(inventory,('discipline','page_kind','requested_url','raw_sha256','rows_parsed','expected_rows','status'))
    expected_pages={}
    for d,(count,_,_) in EXPECTED.items():
        for k in ('entry','result'):expected_pages[(d,k)]=count
    seen={}
    for p in pages:
        key=(p['discipline'],p['page_kind'])
        if key in seen or key not in expected_pages or p['status']!='VALIDATED' or not re.fullmatch('[a-f0-9]{64}',p['raw_sha256']):
            raise ValueError('Duplicate, failed or unexpected ISU official source page')
        if int(p['rows_parsed'])!=expected_pages[key] or int(p['expected_rows'])!=expected_pages[key]:
            raise ValueError('Official source page counts inconsistent with fixed 2018 frame')
        seen[key]=p
    if len(seen)!=4:raise ValueError('Not all four official entry/result pages verified')

    observed=read(event_rows,LINK_FIELDS)
    old_pairs=read(original,HIST_FIELDS)
    canon_pairs=read(historic_pairs,PREVIEW_FIELDS)
    people=read(historic_people,PERSON_FIELDS)
    old_events=read(historic_event_index,('event_id',))
    modern_rows=read(modern,MODERN_FIELDS)
    modern_ident=read(modern_people,MODERN_CANON_FIELDS)
    if (len(observed)!=59 or len(old_pairs)!=553 or len(canon_pairs)!=514 or
        len(people)!=865 or len(modern_rows)!=1584):
        raise ValueError('Historical/modern roster source counts differ from last reviewed QA phase')
    if any(e['event_id'].startswith(SEASON+'|'+EVENT+'|') for e in old_events):
        raise ValueError('2018 Worlds already present in historic event inventory: would duplicate event')

    old_by_id={}
    norm_old=defaultdict(list)
    per_side=defaultdict(set)
    for x in old_pairs:
        pid=x['pair_id'];d=x['discipline']
        if not pid or pid in old_by_id:raise ValueError('Repeated/blank old historic pair')
        old_by_id[pid]=x
        norm_old[(d,norm_name(x['person_a_name']),norm_name(x['person_b_name']))].append(pid)
        per_side[(d,'a',norm_name(x['person_a_name']))].add(x['person_a_id'])
        per_side[(d,'b',norm_name(x['person_b_name']))].add(x['person_b_id'])
    pair_canonical={}
    for g in canon_pairs:
        ids=fields(g['original_pair_ids'])
        if not ids or not g['projected_person_a_id'] or not g['projected_person_b_id']:
            raise ValueError('Empty reviewed historical identity lineage')
        for pid in ids:
            if pid in pair_canonical or pid not in old_by_id:
                raise ValueError('Original pair ID not uniquely represented in reviewed historical projection')
            pair_canonical[pid]=g
    if set(pair_canonical)!=set(old_by_id):
        raise ValueError('Review projection does not preserve all original historic pair IDs')
    historic_dobs={}
    for x in people:
        id_=x['projected_person_id']
        if not id_ or id_ in historic_dobs or not valid_date(x['date_of_birth']):
            raise ValueError('Invalid historical source-reviewed date or repeated identity')
        historic_dobs[id_]=x['date_of_birth']
    for g in canon_pairs:
        if g['projected_person_a_id'] not in historic_dobs or g['projected_person_b_id'] not in historic_dobs:
            raise ValueError('Historical preview references missing reviewed person ID')

    modern_idmap={}
    for r in modern_ident:
        key=(r['discipline'],r['original_modern_person_id'])
        canon=r['canonical_modern_person_id']
        if not all((key[0],key[1],canon)) or key in modern_idmap:
            raise ValueError('Duplicate/blank modern person ID projection')
        modern_idmap[key]=canon
    modern_by_name=defaultdict(list)
    modern_by_profile=defaultdict(list)
    for m in modern_rows:
        d=m['discipline'];a=m['person_a_id'];b=m['person_b_id']
        if not all((d,a,b)) or a==b:
            raise ValueError('Malformed modern roster identity')
        if (d,a) not in modern_idmap or (d,b) not in modern_idmap:
            raise ValueError('Modern person ID projection does not cover all ranked skaters')
        modern_by_name[(d,norm_name(m['person_a_name']),norm_name(m['person_b_name']))].append(m)
        p=profile_id(m['profile_url'])
        if p:modern_by_profile[(d,p)].append(m)

    outputs=[];extensions=[];bydisc=Counter();historic_statuses=Counter();modern_statuses=Counter();result_statuses=Counter()
    seen_event_profiles=set();seen_ordinals=set();seen_placements=set();novel_pairs=[]
    for r in observed:
        d=r['discipline'];pid=r['isu_profile_id'].lower();event=SEASON+'|'+EVENT+'|'+d
        if d not in EXPECTED or r['event_id']!=event or (d,pid) in seen_event_profiles:
            raise ValueError('Unrecognized/repeated 2018 event or official profile ID')
        seen_event_profiles.add((d,pid))
        if (not profile_id(r['isu_profile_url'])==pid
            or r['result_profile_id'].lower()!=pid or r['entry_result_link_status']!='PROFILE_MATCH_BOTH_OFFICIAL_PAGES'
            or r['nation_as_published']!=r.get('result_nation_as_published',r['nation_as_published'])):
            raise ValueError('Unapproved original ISU entry-result identity association')
        if (r['entry_source_sha256']!=seen[(d,'entry')]['raw_sha256'] or
                r['entry_source_url']!=seen[(d,'entry')]['requested_url'] or
                r['result_source_url']!=seen[(d,'result')]['requested_url']):
            raise ValueError('Official entry/result URL or source hash differs from validated pages')
        if r['result_status'] not in {'FINAL_COMPLETE','FINAL_NOT_REACHED'}:
            raise ValueError('Unrecognized official result status')
        if (r['result_status']=='FINAL_COMPLETE') != (r['result_points_interpretation']=='TOTAL_SCORE'):
            raise ValueError('An FNR short-program score would be treated as full total score')
        if not re.fullmatch(r'[0-9]{1,3}[,.][0-9]{2}',r['result_points_as_published']):
            raise ValueError('Missing/malformed official published result points')
        if not r['entry_ordinal'].isdigit() or not r['final_placement'].isdigit():
            raise ValueError('Malformed official entry/result ordinal')
        entry_key=(d,int(r['entry_ordinal']));result_key=(d,int(r['final_placement']))
        if entry_key in seen_ordinals or result_key in seen_placements:
            raise ValueError('Repeated official entry ordinal or final placement')
        seen_ordinals.add(entry_key);seen_placements.add(result_key)
        bydisc[d]+=1;result_statuses[(d,r['result_status'])]+=1
        pairkey=(d,norm_name(r['person_a_as_published']),norm_name(r['person_b_as_published']))
        historic_hits=norm_old.get(pairkey,[])
        if len(historic_hits)>1:
            raise ValueError('Multiple historic original pairs share identical published names; manual hold required')
        if historic_hits:
            old_id=historic_hits[0];group=pair_canonical[old_id]
            ha=group['projected_person_a_id'];hb=group['projected_person_b_id']
            hs='EXACT_NAME_PAIR_TO_REVIEWED_HISTORIC_PAIR'
        else:
            old_id='';ha='';hb='';hs='NO_EXACT_HISTORIC_PAIR_NEW_COMBINATION_REVIEW'
        individual_a=per_side.get((d,'a',norm_name(r['person_a_as_published'])),set())
        individual_b=per_side.get((d,'b',norm_name(r['person_b_as_published'])),set())
        modern_name_hits=modern_by_name.get(pairkey,[])
        modern_profile_hits=modern_by_profile.get((d,pid),[])
        exact_modern_prof=[x for x in modern_profile_hits if (d,norm_name(x['person_a_name']),norm_name(x['person_b_name']))==pairkey]
        modern_union=modern_name_hits+modern_profile_hits
        ca={modern_idmap[(d,x['person_a_id'])] for x in modern_union}
        cb={modern_idmap[(d,x['person_b_id'])] for x in modern_union}
        if exact_modern_prof:
            ms='SAME_OFFICIAL_PROFILE_AND_BOTH_NAMES_MODERN_ROSTER'
        elif modern_profile_hits:
            ms='SAME_PROFILE_DIFFERENT_MODERN_PUBLISHED_NAMES_REVIEW'
        elif modern_name_hits:
            ms='SAME_BOTH_NAMES_DIFFERENT_OR_MISSING_MODERN_PROFILE_REVIEW'
        else:
            ms='NOT_IN_MODERN_SEASON_RANKING_DO_NOT_INFER_ABSENCE'
        o={
            'event_id':event,'discipline':d,'entry_ordinal':r['entry_ordinal'],
            'name_as_published':r['name_as_published'],'nation_as_published':r['nation_as_published'],
            'isu_profile_id':pid,'entry_source_url':r['entry_source_url'],
            'result_source_url':r['result_source_url'],'result_status':r['result_status'],
            'final_placement':r['final_placement'],'result_points_as_published':r['result_points_as_published'],
            'result_points_interpretation':r['result_points_interpretation'],
            'historic_original_pair_ids':old_id,'historic_projected_a_id':ha,'historic_projected_b_id':hb,
            'historic_a_dob':historic_dobs.get(ha,''),'historic_b_dob':historic_dobs.get(hb,''),
            'historic_a_individual_leads':joined(individual_a),'historic_b_individual_leads':joined(individual_b),
            'historic_pair_link_status':hs,
            'modern_pair_ids':joined(x['pair_id'] for x in modern_union),
            'modern_name_matched_pair_ids':joined(x['pair_id'] for x in modern_name_hits),
            'modern_profile_matched_pair_ids':joined(x['pair_id'] for x in modern_profile_hits),
            'modern_canonical_a_ids':joined(ca),'modern_canonical_b_ids':joined(cb),
            'modern_link_status':ms,'event_extension_status':'NEW_EVENT_CELL_NOT_IN_ORIGINAL_HISTORIC_V4',
            'identity_decision':'REVIEWED_SOURCE_LINK_CANDIDATE_NO_AUTO_MERGE',
        }
        outputs.append(o);historic_statuses[hs]+=1;modern_statuses[ms]+=1
        extension={
            'event_id':event,'discipline':d,'name_as_published':r['name_as_published'],
            'person_a_as_published':r['person_a_as_published'],
            'person_b_as_published':r['person_b_as_published'],
            'nation_as_published':r['nation_as_published'],'isu_profile_id':pid,
            'entry_source_url':r['entry_source_url'],'result_source_url':r['result_source_url'],
            'final_placement':r['final_placement'],'result_status':r['result_status'],
            'points_as_published':r['result_points_as_published'],
            'points_interpretation':r['result_points_interpretation'],
            'historic_pair_link_status':hs,'historic_original_pair_ids':old_id,
            'historical_identity_merge_action':'NONE_SOURCE_CROSSWALK_PREVIEW_ONLY',
            'event_observation_status':'OFFICIAL_ENTRY_AND_RESULT_NEW_EVENT_CELL_NOT_MERGED',
        }
        extensions.append(extension)
        if not historic_hits:novel_pairs.append(o)
    for d,(expected_n,finals,fnr) in EXPECTED.items():
        if bydisc[d]!=expected_n or result_statuses[(d,'FINAL_COMPLETE')]!=finals or result_statuses[(d,'FINAL_NOT_REACHED')]!=fnr:
            raise ValueError('2018 entry frame changed or results/FNR split is inconsistent')
    if len(outputs)!=59:raise ValueError('2018 source crosswalk lost rows')
    for d,(count,_,_) in EXPECTED.items():
        if sorted(i for x,i in seen_ordinals if x==d)!=list(range(1,count+1)) or sorted(i for x,i in seen_placements if x==d)!=list(range(1,count+1)):
            raise ValueError('Official page ordinal or placement gap')
    out=Path(out)
    write(out/'official_wc2018_historical_modern_pair_bridge_v1.csv',outputs,OUTPUT_FIELDS)
    write(out/'official_wc2018_new_event_observations_preview_v1.csv',extensions,EXT_FIELDS)
    write(out/'official_wc2018_nonmatching_historical_pairs_review_v1.csv',novel_pairs,OUTPUT_FIELDS)
    summary={
        'stage':'wc2018_identity_event_extension_crosswalk_preview_not_frozen',
        'official_entry_result_records':len(outputs),
        'original_historic_pair_ids':len(old_pairs),
        'source_reviewed_historic_pair_groups':len(canon_pairs),
        'source_reviewed_historic_person_slots':len(people),
        'historic_exact_two_name_pair_matches':historic_statuses['EXACT_NAME_PAIR_TO_REVIEWED_HISTORIC_PAIR'],
        'historic_new_pair_combination_review':len(novel_pairs),
        'modern_source_pair_link_status_counts':dict(sorted(modern_statuses.items())),
        'historic_pair_link_status_counts':dict(sorted(historic_statuses.items())),
        'new_official_event_observations_preview':len(extensions),
        'original_event_observations_mutated':0,
        'official_2018_result_status_counts':{'|'.join(k):v for k,v in sorted(result_statuses.items())},
        'input_sha256':{str(p):sha(p) for p in paths},
        'limitations':[
            'This is an OFFLINE source crosswalk, not a person-identity approval or final research cohort',
            'Same normalized complete pair names and matching official profile identify candidates, not proof of natural-person identity',
            'Unmatched modern rankings do not show that the athlete was absent from competition',
            'All 59 new rows are for a missing official event cell, not necessarily 59 new historical couples',
            'FNR published points are short-segment results, not final total competition scores',
            'No original source event, historic identity preview, modern ranking, DOB file or score is overwritten',
            'No astrology, performance-based sample selection, significance test or holdout leakage',
        ],
    }
    (out/'official_wc2018_identity_bridge_manifest_v1.json').write_text(
        json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key,default in [('event-rows',EVENT_ROWS),('event-manifest',EVENT_MANIFEST),
                        ('inventory',PAGE_INVENTORY),('original',ORIGINAL),
                        ('historic-pairs',HIST_PAIRS),('historic-people',HIST_PEOPLE),
                        ('historic-event-index',EVENT_INDEX),('modern',MODERN),
                        ('modern-people',MODERN_PEOPLE),('out',OUT)]:
        p.add_argument('--'+key,type=Path,default=default)
    a=vars(p.parse_args())
    audit(**{k.replace('-','_'):v for k,v in a.items()})


if __name__=='__main__':main()
