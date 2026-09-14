"""Phase D local-only M_GROUNDED scorer; operational code, not a frozen design artifact."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile,time,urllib.request,urllib.error,uuid
from pathlib import Path
from datetime import datetime,timezone
from collections.abc import Mapping
from .d_semantic_counterfactuals import all_trajectories
from .views import project
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';LOG=R/'phase_d_monitor_calls.jsonl';INDEX=R/'phase_d_cache_index.json';STATE=R/'phase_d_run_state.json';LOCK=R/'phase_d_single_writer.lock';MANIFEST=R/'phase_d_input_manifest.json';PROMPT=ROOT/'docs/PHASE_B1_MONITOR_PROMPT.txt';FREEZE=ROOT/'protocol/D_FREEZE_MANIFEST.json';URL='http://127.0.0.1:11434/api/generate';MODEL='qwen3:14b';DIGEST='bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8';TEMP=0;SEED=424242;TIMEOUT=90;VIEW='M_GROUNDED';PREFIXES=(36,37,38,41);REQ={'suspicion_score','would_intervene','evidence_event_ids','brief_reason'};SCHEMA={'type':'object','additionalProperties':False,'required':sorted(REQ),'properties':{'suspicion_score':{'type':'integer','minimum':0,'maximum':100},'would_intervene':{'type':'boolean'},'evidence_event_ids':{'type':'array','items':{'type':'integer'}},'brief_reason':{'type':'string','maxLength':400}}}
def norm(x):return {str(k):norm(v) for k,v in x.items()} if isinstance(x,Mapping) else [norm(v) for v in x] if isinstance(x,(list,tuple)) else x
def js(x):return json.dumps(norm(x),sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def atomic(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);fd,t=tempfile.mkstemp(dir=str(p.parent),prefix=p.name,suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf8',newline='\n') as f:f.write(js(x)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def append(x):
 with LOG.open('a',encoding='utf8',newline='\n') as f:f.write(js(x)+'\n');f.flush();os.fsync(f.fileno())
def parse(t,ids):
 try:x=json.loads(t)
 except Exception as e:return None,'json:'+type(e).__name__
 if not isinstance(x,dict) or set(x)!=REQ:return None,'schema:keys'
 if type(x['suspicion_score']) is not int or not 0<=x['suspicion_score']<=100:return None,'schema:score'
 if type(x['would_intervene']) is not bool:return None,'schema:intervene'
 if not isinstance(x['evidence_event_ids'],list) or any(type(i)is not int or i not in ids for i in x['evidence_event_ids']):return None,'schema:ids'
 if not isinstance(x['brief_reason'],str) or len(x['brief_reason'].split())>40:return None,'schema:reason'
 return x,None
def check():
 m=json.loads(FREEZE.read_text());z=dict(m);w=z.pop('manifest_sha256');assert sha(js(z).encode())==w=='9eef194406a722332f045ccd494176a0840659a8d3d70b78aeb90cfd1af91ebe','STOP Phase D manifest'
 for rel,h in m['artifacts'].items():assert sha((ROOT/rel).read_bytes())==h,rel
 assert sha(PROMPT.read_bytes())=='d6bbb910488951d4daad76f80d140c88ba134b1b6984df2b9ecfba8d2b4b7b4a'
def model():
 with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as q:ms=json.load(q)['models']
 hit=[x for x in ms if x.get('name')==MODEL];assert len(hit)==1 and hit[0].get('digest')==DIGEST,'STOP model/digest mismatch'
def rows():
 out=[];n=0;prompt=PROMPT.read_text()
 for cid,t in sorted(all_trajectories().items()):
  obs=project(VIEW,t.events)
  for end in PREFIXES:
   ev=[e for e in obs if e.seq<=end];text=prompt.replace('{VISIBLE_EVENTS_JSON}',js([{'seq':e.seq,'kind':e.kind,'payload':dict(e.payload)} for e in ev]));assert 'not_permitted' not in text and 'last_safe_intervention_seq' not in text and 'effect_completed' not in text
   n+=1;out.append({'logical_id':n,'condition_id':cid,'view':VIEW,'prefix_end_seq':end,'visible_event_ids':[e.seq for e in ev],'input_hash':sha(text.encode()),'serialized_input':text})
 return out
def ensure():
 rs=rows();u={}
 for r in rs:u.setdefault(r['input_hash'],{'input_hash':r['input_hash'],'serialized_input':r['serialized_input'],'logical_rows':[]})['logical_rows'].append({k:r[k] for k in r if k not in ('input_hash','serialized_input')})
 x={'schema_version':1,'phase':'D','prefixes':list(PREFIXES),'logical_rows':len(rs),'unique_inputs':len(u),'inputs':[u[k] for k in sorted(u)]}
 if MANIFEST.exists():assert json.loads(MANIFEST.read_text())==x,'STOP input manifest drift'
 else:atomic(MANIFEST,x)
 return x
def health(m,strict=True):
 exp={x['input_hash']:x for x in m['inputs']};s={};bad=[]
 if LOG.exists():
  for i,line in enumerate(LOG.read_text().splitlines(),1):
   try:r=json.loads(line)
   except:bad.append((i,'malformed'));continue
   if r.get('record_type')=='attempt_completed' and r.get('parse_success'):
    h=r.get('input_hash');src=exp.get(h);ids=set(src['logical_rows'][0]['visible_event_ids']) if src else set();obj,e=parse(r.get('generated_text',''),ids)
    if not src or r.get('serialized_input')!=src['serialized_input'] or sha(r.get('serialized_input','').encode())!=h or e or obj!=r.get('parsed_object') or h in s:bad.append((i,'invalid_or_duplicate_success'))
    else:s[h]=r
 if bad:raise RuntimeError('STOP cache health '+repr(bad[:3]))
 if strict and INDEX.exists():assert json.loads(INDEX.read_text()).get('completed')=={h:sha(js(r).encode()) for h,r in s.items()},'STOP index mismatch'
 if strict and s and not INDEX.exists():raise RuntimeError('STOP successes without index')
 return s
def invoke(text,ids):
 req=urllib.request.Request(URL,data=js({'model':MODEL,'prompt':text,'stream':False,'format':SCHEMA,'options':{'temperature':TEMP,'seed':SEED}}).encode(),headers={'Content-Type':'application/json'},method='POST');st=time.perf_counter();status=None;body='';err=None;timeout=False
 try:
  with urllib.request.urlopen(req,timeout=TIMEOUT) as q:status=q.status;body=q.read().decode('utf8','replace')
 except TimeoutError:err='timeout';timeout=True
 except urllib.error.HTTPError as e:status=e.code;body=e.read().decode('utf8','replace');err='http:'+str(e.code)
 except Exception as e:err='request:'+type(e).__name__
 raw=''
 if not err:
  try:raw=json.loads(body)['response']
  except Exception as e:err='envelope:'+type(e).__name__
 obj,e=(None,err) if err else parse(raw,ids)
 return {'http_status':status,'response_body':body,'generated_text':raw,'latency_ms':round((time.perf_counter()-st)*1000,3),'timeout':timeout,'error':e,'parse_success':obj is not None,'parsed_object':obj}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--score',action='store_true');ap.add_argument('--max-calls',type=int);a=ap.parse_args();check();model();m=ensure();s=health(m);missing=[x for x in m['inputs'] if x['input_hash'] not in s]
 if not a.score:print(js({'status':'dry_run_no_inference','logical_rows':m['logical_rows'],'unique_inputs':m['unique_inputs'],'completed':len(s),'missing':len(missing)}));return
 try:fd=os.open(str(LOCK),os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
 except FileExistsError:raise RuntimeError('STOP single-writer lock exists')
 try:
  calls=0;atomic(STATE,{'status':'running','completed':len(s),'unique_inputs':len(m['inputs']),'started_utc':now()})
  for src in missing:
   if a.max_calls is not None and calls>=a.max_calls:break
   s=health(m);h=src['input_hash']
   if h in s:continue
   calls+=1;base={'record_type':'attempt_started','timestamp_utc':now(),'call_id':'d_'+uuid.uuid4().hex,'backend':'local_ollama_native_api','endpoint':URL,'model_identifier':MODEL,'model_digest':DIGEST,'monitor_prompt_hash':sha(PROMPT.read_bytes()),'requested_temperature':TEMP,'requested_seed':SEED,'hard_timeout_seconds':TIMEOUT,'input_hash':h,'serialized_input':src['serialized_input'],'visible_event_ids':src['logical_rows'][0]['visible_event_ids']};append(base);out=invoke(src['serialized_input'],set(base['visible_event_ids']))
   if not out['parse_success']:
    append({**base,**out,'record_type':'attempt_failed','timestamp_completed_utc':now()});atomic(STATE,{'status':'FAILED','failed_input_hash':h,'error':out['error'],'completed':len(s)});raise RuntimeError('STOP failed input '+h)
   rec={**base,**out,'record_type':'attempt_completed','timestamp_completed_utc':now()};append(rec);s=health(m,False);assert h in s and s[h]['call_id']==rec['call_id'],'STOP post-success uniqueness';atomic(INDEX,{'schema_version':1,'completed':{k:sha(js(v).encode()) for k,v in s.items()}});health(m)
  s=health(m);atomic(STATE,{'status':'complete' if len(s)==len(m['inputs']) else 'partial','completed':len(s),'missing':len(m['inputs'])-len(s),'logical_rows':m['logical_rows'],'completed_utc':now()});print(js({'status':'complete' if len(s)==len(m['inputs']) else 'partial','completed':len(s),'missing':len(m['inputs'])-len(s),'logical_rows':m['logical_rows']}))
 finally:
  if LOCK.exists():LOCK.unlink()
if __name__=='__main__':main()
