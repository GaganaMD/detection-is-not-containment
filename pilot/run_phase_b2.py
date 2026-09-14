"""B2 episode runner. Safety gate: no actor inference occurs unless --run-episodes is supplied explicitly."""
from __future__ import annotations
import argparse,hashlib,json,os,time,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from .b2_environment import B2Environment
ROOT=Path(__file__).resolve().parents[1]; P=ROOT/'protocol'; R=ROOT/'results'/'phase_b2'
URL='http://127.0.0.1:11434/api/generate'; MODEL='qwen3:8b'; ACTOR_DIGEST='500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
SEEDS=(11001,11002,11003,11004,11005); OPTIONS={'temperature':0.6,'top_p':0.95,'top_k':20,'seed':None,'num_predict':256,'num_ctx':8192,'repeat_penalty':1}; MAX_STEPS=12; TIMEOUT=120
SCHEMA=json.loads((P/'B2_ACTOR_OUTPUT_SCHEMA.json').read_text(encoding='utf-8'))
def js(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha(b):return hashlib.sha256(b).hexdigest()
def append(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8',newline='\n') as f:f.write(js(row)+'\n');f.flush();os.fsync(f.fileno())
def actor_payload(prompt,history,seed):
    opts=dict(OPTIONS);opts['seed']=seed
    return {'model':MODEL,'system':prompt,'prompt':'Conversation transcript (actor-visible tool results only):\n'+js(history)+'\nReturn the next JSON object only.','stream':False,'format':SCHEMA,'think':False,'options':opts}
def parse_actor(raw):
    """No semantic model repair: accept raw JSON or a lexically extracted balanced JSON object only."""
    candidates=[raw]
    start=raw.find('{')
    if start>=0:
        depth=0;quoted=False;esc=False
        for i,ch in enumerate(raw[start:],start):
            if quoted:
                if esc:esc=False
                elif ch=='\\':esc=True
                elif ch=='"':quoted=False
            elif ch=='"':quoted=True
            elif ch=='{':depth+=1
            elif ch=='}':
                depth-=1
                if depth==0:candidates.append(raw[start:i+1]);break
    for c in candidates:
        try:x=json.loads(c)
        except Exception:continue
        if not isinstance(x,dict) or set(x)!=set(SCHEMA['required']):continue
        if not isinstance(x['reasoning_summary'],str) or not 1<=len(x['reasoning_summary'])<=280:continue
        if x['action'] not in SCHEMA['properties']['action']['enum'] or not isinstance(x['arguments'],dict):continue
        return x,None
    return None,'actor_schema_or_json_invalid'
def invoke(payload):
    req=urllib.request.Request(URL,data=js(payload).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST');started=time.perf_counter();status=None;body='';err=None;timeout=False
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as q: status=q.status;body=q.read().decode('utf-8','replace')
    except urllib.error.HTTPError as e:status=e.code;body=e.read().decode('utf-8','replace');err='http_error:'+str(e.code)
    except TimeoutError:err='timeout';timeout=True
    except urllib.error.URLError as e:timeout=isinstance(e.reason,TimeoutError);err='timeout' if timeout else 'url_error:'+str(e.reason)
    except Exception as e:err='request_exception:'+type(e).__name__+':'+str(e)
    raw=''
    if not err and status==200:
        try:raw=json.loads(body)['response'];assert isinstance(raw,str)
        except Exception as e:err='envelope_parse:'+type(e).__name__
    parsed,perr=(None,err) if err else parse_actor(raw)
    return {'http_status':status,'response_body':body,'raw_actor_response':raw,'latency_ms':round((time.perf_counter()-started)*1000,3),'timeout':timeout,'error':perr,'parsed_action':parsed}
def verify_local_model():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as q:tags=json.load(q)
    found=[m for m in tags.get('models',[]) if m.get('name')==MODEL]
    if len(found)!=1 or found[0].get('digest')!=ACTOR_DIGEST:raise RuntimeError('actor model/digest mismatch')
def run_episode(condition,seed):
    prompt=(P/('B2_HONEST_PROMPT.md' if condition=='H' else 'B2_SIDE_OBJECTIVE_PROMPT.md')).read_text(encoding='utf-8');episode_id=f'B2_{condition}_{seed}';log=R/'actor_calls.jsonl';env=B2Environment();history=[];consecutive_invalid_tools=0;terminal='max_steps'
    append(log,{'record_type':'episode_started','timestamp_utc':now(),'episode_id':episode_id,'condition':condition,'seed':seed,'actor_model':MODEL,'actor_digest':ACTOR_DIGEST,'endpoint':URL,'prompt_sha256':sha(prompt.encode()),'options':{**OPTIONS,'seed':seed},'max_steps':MAX_STEPS})
    for turn in range(1,MAX_STEPS+1):
        payload=actor_payload(prompt,history,seed);attempts=[]
        for attempt_no in (1,2): # exactly one retry, only after transport/parse failure, byte-identical payload
            out=invoke(payload);attempts.append(out)
            append(log,{'record_type':'actor_attempt','timestamp_utc':now(),'episode_id':episode_id,'turn':turn,'attempt':attempt_no,'request_sha256':sha(js(payload).encode()),'request':payload,**out})
            if out['parsed_action'] is not None:break
        out=attempts[-1]
        if out['parsed_action'] is None:
            terminal='invalid_actor_output';break
        action=out['parsed_action'];result,_=env.actor_turn(action['reasoning_summary'],action['action'],action['arguments'])
        history.append({'turn':turn,'action':action,'tool_result':result})
        if action['action']=='finish':terminal='actor_finished';break
        consecutive_invalid_tools=0 if result['ok'] else consecutive_invalid_tools+1
        if consecutive_invalid_tools>=2:terminal='repeated_invalid_tool';break
    outcome=env.outcome();row={'record_type':'episode_completed','timestamp_utc':now(),'episode_id':episode_id,'condition':condition,'seed':seed,'terminal_status':terminal,'raw_history':history,'canonical_events':[e.as_dict() for e in env.events],**outcome}
    append(log,row);return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-episodes',action='store_true',help='explicitly authorize the 10 model-generated B2 episodes');args=ap.parse_args();verify_local_model();print(js({'status':'validated_no_inference','actor_model':MODEL,'actor_digest':ACTOR_DIGEST,'endpoint':URL,'conditions':['H','S'],'seeds':SEEDS,'episode_count':10,'max_steps':MAX_STEPS}))
    if not args.run_episodes:return
    for seed in SEEDS:
        run_episode('H',seed);run_episode('S',seed)
if __name__=='__main__':main()
