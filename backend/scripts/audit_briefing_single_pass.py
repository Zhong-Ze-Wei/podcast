"""Replay recorded outputs and measure payloads. No database or model calls."""
import json
import os
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.services.briefing_lab_service import parse_model_json
from app.services.episode_analysis_service import validate_episode_analysis, EpisodeAnalysisService
from app.services.briefing_modes_service import mode_template, MODE_INDEX

OUT = ROOT/'docs/ai/data/experiments/2026-10-03-single-pass'
OUT.mkdir(parents=True,exist_ok=True)
rows=[json.loads(x) for x in (ROOT/'docs/ai/data/2026-09/sources.jsonl').read_text(encoding='utf-8').splitlines()]
source=next(s for s in rows if s['id']=='ep6abbd73b347d7753e4916e7f')
baseline=ROOT/'docs/ai/data/experiments/2026-10-02-shared-analysis-qa/live-results/episode-analysis'
attempts=json.loads(next((baseline/'attempts').glob('*.json')).read_text(encoding='utf-8'))['attempts']
reading=json.loads(next(baseline.glob('*.json')).read_text(encoding='utf-8'))
first=parse_model_json(attempts[0]['content'])
repaired=deepcopy(first)
bad_quote=repaired['points'][5]['quote']
original_quote=bad_quote.replace('Uh, except','Uh except',1)
assert original_quote in source['full_text']
repaired['points'][5]['quote']=original_quote
repaired_result=validate_episode_analysis(repaired,source)
audits=[]
for index, attempt in enumerate(attempts,1):
    data=parse_model_json(attempt['content'])
    base_point=None
    for point in data['points']:
        try:
            validate_episode_analysis({'takeaway':data['takeaway'],'points':[point],'quotes':[],'concepts':[],'resources':[]},source)
        except (ValueError, KeyError, TypeError):
            continue
        base_point=point
        break
    assert base_point is not None
    failed=[]; valid={}
    for kind in ['points','quotes','concepts','resources']:
        valid[kind]=0
        for item_index,item in enumerate(data[kind],1):
            single={'takeaway':data['takeaway'],'points':[base_point],'quotes':[],'concepts':[],'resources':[]}
            single[kind]=[item]
            try:
                validate_episode_analysis(single,source)
                valid[kind]+=1
            except (ValueError, KeyError, TypeError) as error:
                failed.append({'kind':kind,'index':item_index,'title':item.get('title',''),'reason':str(error),'quote':item.get('quote','')})
    audits.append({'attempt':index,'usage':attempt['usage'],'seconds':attempt['elapsed_seconds'],
                   'generated':{kind:len(data[kind]) for kind in valid},'valid':valid,'failed':failed})

fields=('id','source_id','kind','title','text','quote','translation','context','speaker','original_term','original_title','resource_kind','relation')
current={'sources':[{'id':source['id'],'title':source['title'],'feed':source.get('feed','')}],
         'single_readings':[EpisodeAnalysisService.compact(reading)],
         'evidence_candidates':[{k:c.get(k,'') for k in fields} for c in EpisodeAnalysisService.cards(reading)]}
compact={'source_id':source['id'],'title':source['title'],'summary':reading['takeaway'],
         'topics':[{'id':f'T{i}','title':p['title'],'text':p['meaning'],'boundary':p['boundary']} for i,p in enumerate(reading['points'],1)],
         'quotes':[{'id':f'Q{i}','text':q['translation'] or q['quote'],'brief':q['brief']} for i,q in enumerate(reading['quotes'],1)],
         'concepts':[{'id':f'C{i}','title':c['title'],'text':c['text']} for i,c in enumerate(reading['concepts'],1)],
         'resources':[{'id':f'R{i}','title':c['title'],'text':c['text'],'relation':c['relation']} for i,c in enumerate(reading['resources'],1)]}
size=lambda value:len(json.dumps(value,ensure_ascii=False,separators=(',',':')))
old=[]; hits=0; inputs=0
for s in rows:
    path=ROOT/'docs/ai/data/experiments/2026-10-01-perspectives/responses'/f"{s['id']}.1.json"
    response=json.loads(path.read_text(encoding='utf-8'))
    usage=response['usage']; hits+=usage.get('prompt_cache_hit_tokens',0); inputs+=usage['prompt_tokens']
    if s['id'] in [source['id'],'ep6abbd6d4347d7753e4916e6d']:
        old.append({'source_id':s['id'],'title':s['title'],'characters':len(s['full_text']),
                    'usage':usage,'seconds':response.get('elapsed_seconds'),'finish_reason':response['choices'][0]['finish_reason']})
result={'date':'2026-10-03','new_api_calls':0,'source_id':source['id'],'source_characters':len(source['full_text']),
        'mode_prompt_prefix':{'common_system_prefix_chars':len(os.path.commonprefix([mode_template(mode) for mode in MODE_INDEX])),
                              'material_after_divergent_system':True,'full_material_reuse_guaranteed':False},
        'punctuation_repair_replay':{'difference':'Model added one comma: Uh, except versus original Uh except',
            'action':'Replace this evidence with the exact original passage, leave every other field unchanged',
            'full_existing_validator_passed':True,'retained_items':sum(len(repaired_result[k]) for k in ['points','quotes','concepts','resources']),
            'avoided_retry_tokens':attempts[1]['usage']['total'],'avoided_retry_seconds':attempts[1]['elapsed_seconds'],
            'scope':'One known sample, not a generic fuzzy-match implementation'},
        'validation_replay':audits,'payload_size_comparison':{'current_chars':size(current),'compact_chars':size(compact),
            'reduction':1-size(compact)/size(current),'same_saved_analysis':True,
            'tradeoff':'Aggregation reads Chinese summaries/translations and IDs. Original passages remain stored for display and targeted retrieval; semantic equivalence is not established.'},
        'archived_single_pass':old,'archived_first_attempt_cache':{'hits':hits,'input':inputs,'ratio':hits/inputs},
        'new_experiment_status':'blocked: Docker Desktop failed to start; configured model stored in MongoDB could not be loaded. No new generation request reached the model.'}
(OUT/'offline-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'compact-input-example.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
