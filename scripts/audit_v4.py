#!/usr/bin/env python3
r"""Reconstruct independent skater, couple and verifiable event records (NO BaZi).

Usage (single-line PowerShell):
python .\ice_dance_pair_event_audit_v4.py --observations .\observations.csv --v3-athletes .\athletes_v3.csv --v3-couples .\couples_v3.csv --out .\skating_roster_v4

Standard-library only. 
"""
import argparse,collections,csv,datetime,hashlib,json,re,unicodedata
from pathlib import Path

DICS=['Ice Dance','Pair Skating']

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(path,rows,fieldnames):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction='ignore');w.writeheader();w.writerows(rows)

def norm(name):
    v=''.join(x for x in unicodedata.normalize('NFKD',(name or '').casefold()) if not unicodedata.combining(x))
    return ' '.join(sorted(re.findall(r'[a-z0-9]+',v)))
def ident(tag,s):return tag+'_'+hashlib.sha1(s.encode('utf-8')).hexdigest()[:13]
def pair_key(r):return (r['discipline'],norm(r['person_a']),norm(r['person_b']))
def pair_id(k):return ident('pair','|'.join(k))
def person_id(n):return ident('person',n)
def season_event(r):
    source=r['source_type'];ss=r['season']
    if source=='buzzfeed_2016_2017_aggregated':return None
    if source=='pilot_worlds':
        year=int(ss)
        return (f'{year-1}-{year}', f'wc{year}')
    if source=='isu_worlds_2014':return ('2013-2014','wc2014')
    return (ss,r['event'])
def score_is_num(v):
    try:return bool(v and float(v)>-999)
    except (ValueError,TypeError):return False

def best_name(names):
    names=set(names);names.discard('')
    if not names:return ''
    def score(s):
        tokens=s.split();first_cap=bool(tokens and tokens[0][:1].isupper() and (not tokens[0].isupper()))
        end_cap=bool(tokens and tokens[-1].isupper())
        return ('�' not in s,first_cap,end_cap,len(s),s)
    return sorted(names,key=score,reverse=True)[0]

def pipeline(obs_path,athletes_v3_path=None,couples_v3_path=None):
    raw=read_csv(obs_path)
    v3p={r['person_id']:r for r in read_csv(athletes_v3_path)} if athletes_v3_path else {}
    v3c={r['pair_id']:r for r in read_csv(couples_v3_path)} if couples_v3_path else {}
    keys=set();pair_source=collections.defaultdict(set);person_source=collections.defaultdict(set)
    pair_nations=collections.defaultdict(set);pair_names=collections.defaultdict(lambda:(set(),set()))
    person_names=collections.defaultdict(set);person_nations=collections.defaultdict(set)
    person_roles=collections.defaultdict(set);person_disc=collections.defaultdict(set);person_partner=collections.defaultdict(set)
    obs_issues=[];cross_event=collections.defaultdict(list);mappings=[]
    agg_only=collections.defaultdict(set);raw_sourcen=collections.Counter()

    for i,r in enumerate(raw,2):
        r=dict(r)
        src=r.get('source_type','');raw_sourcen[src]+=1
        if (r.get('identity_flag')=='bad_slash_split' and not r.get('person_b','').strip()
                and (r.get('name_as_published','') or '').count('/')==1):
            segments=[x.strip() for x in r['name_as_published'].split('/',1)]
            if all(len(re.findall(r'[A-Za-z]+',x))>=2 for x in segments):
                r['person_a'],r['person_b']=segments
                obs_issues.append({'raw_row_number':i,'issue':'repaired_bad_slash_split',
                   'source_type':src,'discipline':r.get('discipline',''),
                   'published_name':r.get('name_as_published',''),'source_url':r.get('source_url','')})
        if not r.get('person_a','').strip() or not r.get('person_b','').strip() or not norm(r.get('person_a')) or not norm(r.get('person_b')):
            obs_issues.append({'raw_row_number':i,'issue':'missing_or_malformed_partner','source_type':src,'discipline':r.get('discipline',''), 'published_name':r.get('name_as_published',''), 'source_url':r.get('source_url','')})
            mappings.append({'raw_row_number':i,'source_type':src,'discipline':r['discipline'],'season_raw':r['season'],'event_raw':r['event'],'normalized_season':'','normalized_event':'','pair_id':'','member_a_id':'','member_b_id':'','event_counted':'NO','reason':'invalid_partner','source_url':r['source_url']})
            continue
        k=pair_key(r);keys.add(k);pid=pair_id(k)
        a,b=k[1:];aid,bid=person_id(a),person_id(b)
        pair_source[k].add(src)
        person_source[a].add(src);person_source[b].add(src)
        if r.get('nation','').strip():
            pair_nations[k].add(r['nation'].strip());person_nations[a].add(r['nation'].strip());person_nations[b].add(r['nation'].strip())
        pair_names[k][0].add(r['person_a']);pair_names[k][1].add(r['person_b'])
        person_names[a].add(r['person_a']);person_names[b].add(r['person_b'])
        person_roles[a].add('A');person_roles[b].add('B')
        person_disc[a].add(k[0]);person_disc[b].add(k[0])
        person_partner[a].add((k[0],b));person_partner[b].add((k[0],a))
        ev=season_event(r)
        if ev:
            cross_event[(k,ev)].append((i,r))
        else:agg_only[k].add(src)
        mappings.append({'raw_row_number':i,'source_type':src,'discipline':k[0],
            'season_raw':r['season'],'event_raw':r['event'],'normalized_season':ev[0] if ev else '',
            'normalized_event':ev[1] if ev else '',
            'pair_id':pid,'member_a_id':aid,'member_b_id':bid,
            'event_counted':'YES' if ev else 'NO','reason':'individual_event' if ev else 'grouped_aggregated_seed',
            'source_url':r['source_url']})
    pnames={n:best_name(v) for n,v in person_names.items()}
    for n in pnames:
        if person_id(n) in v3p:pnames[n]=v3p[person_id(n)]['name_display']
    couple_display={}
    for k in keys:
        pid=pair_id(k)
        old=v3c.get(pid,{})
        couple_display[k]=(old.get('person_a_name') or best_name(pair_names[k][0]),old.get('person_b_name') or best_name(pair_names[k][1]))

    event_rows=[];duplicates=[];pair_events=collections.defaultdict(list);athlete_ev=collections.defaultdict(set)
    event_registry=collections.defaultdict(list)
    for (k,ev),rr in sorted(cross_event.items()):
        season,evt=ev;discipline=k[0]
        rank_variants={r['rank'].strip() for _,r in rr if r['rank'].strip()}
        if len(rank_variants)>1:
            issue='different_ranks'
        else:issue=''
        # A dated non-seed row with rank+score is more informative than an undated seed row.
        ranking={'gh_historic_event':3,'pilot_worlds':2,'isu_worlds_2014':1}
        i,obs=max(rr,key=lambda x:(ranking.get(x[1]['source_type'],0),score_is_num(x[1]['score']),x[1]['rank'].isdigit()))
        rank=obs['rank'].strip();score=obs['score'].strip();pid=pair_id(k)
        sources=sorted({r['source_type'] for _,r in rr});urls=sorted({r['source_url'] for _,r in rr});
        event_uid=season+'|'+evt+'|'+discipline
        if rank.isdigit():status='ranked'
        elif rank.upper() in {'WD','W/D','WITHDRAWN'}:status='withdrawn'
        else:status='unranked_or_unknown'
        names=couple_display[k]
        rec={'pair_event_id':ident('pair_event',pid+'|'+event_uid),'pair_id':pid,
           'discipline':discipline,'person_a_id':person_id(k[1]),'person_b_id':person_id(k[2]),
           'person_a_name':names[0],'person_b_name':names[1],'season':season,
           'event':evt,'event_id':event_uid,'event_date':obs['event_date'],'nation':obs['nation'],
           'rank':rank,'score_as_reported':score,'result_status':status,
           'score_numeric_available':'YES' if score_is_num(score) else 'NO',
           'source_row_count':len(rr),'source_types':'; '.join(sources),'source_urls':'; '.join(urls),
           'rank_source_conflict':issue,'rank_source_values':'; '.join(sorted(rank_variants)),
           'note':'Event-listed includes withdrawals; scores are NOT comparable across rule eras.'}
        event_rows.append(rec);pair_events[k].append(rec);event_registry[event_uid].append(rec)
        athlete_ev[k[1]].add(event_uid);athlete_ev[k[2]].add(event_uid)
        if len(rr)>1:
            duplicates.append({'pair_event_id':rec['pair_event_id'],'pair_id':pid,'discipline':discipline,
              'pair_name':names[0]+' / '+names[1],'season':season,'event':evt,
              'source_rows':len(rr),'rank_variants':' | '.join(sorted(rank_variants)),
              'rank_conflict':issue or 'none','sources':'; '.join(sources),'urls':'; '.join(urls)})
        if issue:
            obs_issues.append({'raw_row_number':i,'issue':'cross_source_rank_conflict','source_type':obs['source_type'],'discipline':discipline,'published_name':obs['name_as_published'],'source_url':obs['source_url']})

    couples=[]
    for k in sorted(keys):
        pid=pair_id(k); e=pair_events.get(k,[]);count_by_type=collections.Counter(x['result_status'] for x in e)
        ses=sorted({x['season'] for x in e});ranked=sum(x['result_status']=='ranked' for x in e)
        if len(e)==0:count_note='aggregated source only; independent events UNKNOWN'
        else:count_note='distinct identified competition events in covered sources; not entire career'
        old=v3c.get(pid,{});a,b=couple_display[k]
        couples.append({'pair_id':pid,'discipline':k[0],'person_a_id':person_id(k[1]),'person_b_id':person_id(k[2]),
           'person_a_name':a,'person_b_name':b,'represented_nations':'; '.join(sorted(pair_nations[k])),
           'identified_event_count':len(e),'events_with_numeric_rank':ranked,
           'events_with_numeric_score':sum(x['score_numeric_available']=='YES' for x in e),
           'events_listed_withdrawn':count_by_type['withdrawn'],
           'distinct_seasons_with_identified_events':len(ses),
           'first_season':ses[0] if ses else '', 'last_season':ses[-1] if ses else '',
           'observed_seasons':'; '.join(ses),'source_types':'; '.join(sorted(pair_source[k])),
           'evidence_only_aggregated_source':'YES' if agg_only.get(k) else 'NO',
           'identity_status':old.get('identity_status','provisional_order_insensitive'),
           'name_variants_a':' | '.join(sorted(pair_names[k][0])),
           'name_variants_b':' | '.join(sorted(pair_names[k][1])),
           'count_interpretation':count_note})
    couple_by_pid={r['pair_id']:r for r in couples}
    partner_entries=[];people=[];switch_audit=[]
    for n in sorted(person_names):
        pid=person_id(n);old=v3p.get(pid,{});partner_ids=sorted(person_partner[n]);nunique=len(partner_ids)
        p_ids=sorted({pair_id((d,n,m)) if (d,n,m) in keys else pair_id((d,m,n)) for d,m in partner_ids})
        # The stored pair-key orientation is normally person_a followed by person_b.
        for d,m in partner_ids:
            k=(d,n,m) if (d,n,m) in keys else (d,m,n)
            partner_entries.append({'person_id':pid,'athlete_name':pnames[n],'discipline':d,
               'partner_person_id':person_id(m),'partner_name':pnames[m],
               'pair_id':pair_id(k),'pair_identified_events':len(pair_events.get(k,[])),
               'pair_first_season':couple_by_pid[pair_id(k)]['first_season'],
               'pair_last_season':couple_by_pid[pair_id(k)]['last_season'],
               'has_mult_partners':'YES' if nunique>=2 else 'NO'})
        flags=set(filter(None,(old.get('identity_review_flags','') or '').split('; ')))
        if len(person_roles[n])>1:flags.add('role_order_conflict')
        if len(person_disc[n])>1:flags.add('multi_discipline')
        if any('�' in name for name in person_names[n]):flags.add('replacement_character')
        if any(len(re.findall('[A-Za-z]+',v))>=2 and any(len(tok)==1 for tok in re.findall('[A-Za-z]+',v)) for v in person_names[n]):flags.add('possible_abbreviated_name')
        people.append({'person_id':pid,'name_display':pnames[n],
            'name_variants':' | '.join(sorted(person_names[n])),
            'disciplines':'; '.join(sorted(person_disc[n])),
            'different_partners_provisional':nunique,
            'distinct_identified_competitions':len(athlete_ev[n]),
            'represented_nations':'; '.join(sorted(person_nations[n])),
            'role_A_or_B':'; '.join(sorted(person_roles[n])),
            'date_of_birth':'','birth_city':'','birth_country':'','birth_latitude':'',
            'dob_status':'not_checked',
            'identity_review_flags':'; '.join(sorted(flags)) if flags else 'provisional_identity'})

    # Record partner-switch eligibility WITHIN the same discipline.
    pl_group=collections.defaultdict(list)
    for entry in partner_entries:
        pl_group[(entry['person_id'],entry['discipline'])].append(entry)
    for (pid,disc),entries in sorted(pl_group.items()):
        if len(entries)<2:continue
        v=sorted((int(x['pair_identified_events']) for x in entries),reverse=True)
        switch_audit.append({'person_id':pid,'athlete_name':entries[0]['athlete_name'],
            'discipline':disc,'different_partners_in_discipline':len(v),
            'partners_with_at_least_1_event':sum(x>=1 for x in v),
            'partners_with_at_least_2_events':sum(x>=2 for x in v),
            'partners_with_at_least_5_events':sum(x>=5 for x in v),
            'largest_partner_event_count':v[0], 'second_largest_partner_event_count':v[1],
            'observed_partner_details':' | '.join(x['partner_name']+' ('+str(x['pair_identified_events'])+' events)' for x in sorted(entries,key=lambda x:int(x['pair_identified_events']),reverse=True)),
            'interpretation':'Provisional identity; partner-count evidence, NOT inferred chronological partner transitions'})

    # All identified competitions: 2004/2005 Worlds, 2005-06 through 2017-18 selected competition results.
    events=[]
    for uid,arr in sorted(event_registry.items()):
        byp={x['pair_id']:x for x in arr}
        season,evt,disc=uid.split('|')
        events.append({'event_id':uid,'season':season,'event':evt,'discipline':disc,
         'different_couples_seen':len(byp),
         'numeric_ranked_couples':sum(x['result_status']=='ranked' for x in byp.values()),
         'withdrawn_listed_couples':sum(x['result_status']=='withdrawn' for x in byp.values()),
         'competition_date':sorted({x['event_date'] for x in byp.values() if x['event_date']})[0] if any(x['event_date'] for x in byp.values()) else '',
         'source_urls':'; '.join(sorted({u for x in byp.values() for u in x['source_urls'].split('; ') if u}))})

    # Data audit: non-audited/source-specific event records are preserved, never inferred from grouped seed.
    season_disc=collections.defaultdict(lambda: {'events':set(),'pairs':set(),'ranked_pairs':set()})
    for x in event_rows:
        k=(x['season'],x['discipline']); season_disc[k]['events'].add(x['event_id']);season_disc[k]['pairs'].add(x['pair_id'])
        if x['result_status']=='ranked':season_disc[k]['ranked_pairs'].add(x['pair_id'])
    season_rows=[]
    for (s,d),g in sorted(season_disc.items()):
        season_rows.append({'season':s,'discipline':d,'different_competitions':len(g['events']),
         'different_couples':len(g['pairs']),'couples_with_numeric_rank':len(g['ranked_pairs']),
         'pair_event_results':sum(x['season']==s and x['discipline']==d for x in event_rows)})

    count=collections.Counter(x['discipline'] for x in couples)
    n_multi=sum(x['different_partners_provisional']>=2 for x in people)
    n_three=sum(x['different_partners_provisional']>=3 for x in people)
    by_d={d:{} for d in DICS}
    for d in DICS:
        pr=[x for x in couples if x['discipline']==d]
        by_d[d]={'pairs':len(pr),'identified_pair_event_rows':sum(x['identified_event_count'] for x in pr),
          'pairs_at_least_1_event':sum(x['identified_event_count']>=1 for x in pr),
          'pairs_at_least_2_events':sum(x['identified_event_count']>=2 for x in pr),
          'pairs_at_least_5_events':sum(x['identified_event_count']>=5 for x in pr),
          'pairs_at_least_10_events':sum(x['identified_event_count']>=10 for x in pr),
          'pairs_at_least_5_ranked_events':sum(x['events_with_numeric_rank']>=5 for x in pr)}
    summary={'scope':'Ice Dance / Pair Skating roster and competition audit; no BaZi',
     'source_observation_rows':len(raw),'source_rows_by_type':dict(raw_sourcen),
     'valid_raw_observations':len(raw)-sum(x['issue']=='missing_or_malformed_partner' for x in obs_issues),
     'repaired_observations':sum(x['issue']=='repaired_bad_slash_split' for x in obs_issues),
     'excluded_malformed_observations':sum(x['issue']=='missing_or_malformed_partner' for x in obs_issues),
     'provisional_unique_athletes':len(people),'provisional_unique_couples':len(couples),
     'athletes_with_2plus_partners_provisional':n_multi,'athletes_with_3plus_partners_provisional':n_three,
     'athlete_discipline_entries_with_2plus_partners':len(switch_audit),
     'athlete_discipline_entries_2partners_each_with_2plus_events':sum(x['partners_with_at_least_2_events']>=2 for x in switch_audit),
     'athlete_discipline_entries_2partners_each_with_5plus_events':sum(x['partners_with_at_least_5_events']>=2 for x in switch_audit),
     'unique_event_ids_including_discipline':len(events),
     'unique_tournament_instances_across_disciplines':len({(x['season'],x['event']) for x in events}),
     'identified_pair_event_records':len(event_rows),
     'cross_source_duplicate_pair_event_groups':len(duplicates),
     'pairs_only_with_aggregate_seed_no_individual_event':sum(x['identified_event_count']==0 for x in couples),
     'by_discipline':by_d,
     'first_covered_season':min(x['season'] for x in events),
     'last_covered_season':max(x['season'] for x in events),
     'coverage_warning':'Only the available major competitions 2004 Worlds, 2005 Worlds, 2005-06 through 2017-18 selected ISU competitions. No broad 2018-19 onward harvest. Not all entrants worldwide.',
     'event_count_definition':'distinct (discipline,season,event) competition entries for a couple; WD included in event count, numeric_rank_count separate; grouped BuzzFeed seed excluded from per-event counts.',
     'identity_warning':'Order-insensitive exact same name tokens only. Similar spellings and distinct homonyms NOT adjudicated. Empty DOB/location by design.',
     'raw_scores_comparability_warning':'Do not pool historical total scores across seasons and scoring regimes without standardization.'}
    return {'summary':summary,'athletes_v4.csv':people,'couples_v4.csv':couples,
     'pair_events_v4.csv':event_rows,'partner_links_v4.csv':partner_entries,'partner_switch_audit_v4.csv':switch_audit,
     'season_coverage_v4.csv':season_rows,'event_inventory_v4.csv':events,
     'duplicate_event_sources_v4.csv':duplicates,'observation_mapping_v4.csv':mappings,
     'review_anomalies_v4.csv':obs_issues}

def main():
    p=argparse.ArgumentParser();p.add_argument('--observations',type=Path,required=True);p.add_argument('--v3-athletes',type=Path);p.add_argument('--v3-couples',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    res=pipeline(a.observations,a.v3_athletes,a.v3_couples)
    for name,rows in res.items():
        if name=='summary':continue
        if rows:write_csv(a.out/name,rows,list(rows[0]))
    (a.out/'summary_v4.json').write_text(json.dumps(res['summary'],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(res['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
