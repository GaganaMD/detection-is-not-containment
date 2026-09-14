"""Phase B1.3: crash-safe full frozen B1 execution with qwen3:14b only."""
from __future__ import annotations
import argparse, json, os, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from . import run_phase_b1 as frozen
ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'results'/'phase_b13_monitor_calls.jsonl'
MODEL='qwen3:14b'
DIGEST='bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def js(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def append(rec):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open('a',encoding='utf-8',newline='\n') as f:
        f.write(js(rec)+'\n'); f.flush(); os.fsync(f.fileno())
def model_verified():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=15) as r: tags=json.load(r)
    matches=[m for m in tags.get('models',[]) if m.get('name')==MODEL]
    if len(matches)!=1 or matches[0].get('digest')!=DIGEST:
        raise RuntimeError('STOP: qwen3:14b model/digest mismatch: '+repr(matches))
    return {'name':matches[0]['name'],'digest':matches[0]['digest'],'size':matches[0].get('size'),'modified_at':matches[0].get('modified_at')}
def done():
    out={}
    if not LOG.exists(): return out
    for line in LOG.read_text(encoding='utf-8').splitlines():
        try: r=json.loads(line)
        except Exception: continue
        if r.get('record_type')=='attempt_completed' and r.get('model_identifier')==MODEL and r.get('model_digest')==DIGEST and r.get('parse_success'):
            out[r['input_hash']]=r
    return out
def base(call_id,source,typ):
    return {'record_type':typ,'call_id':call_id,'backend':'local_ollama_native_api','endpoint':frozen.URL,'model_identifier':MODEL,'model_digest':DIGEST,'monitor_prompt_hash':frozen.PH,'oracle_hash':frozen.OH,'serialized_input_sha256':source['input_hash'],'serialized_input':source['serialized_input'],'visible_event_ids':source['visible_event_ids'],'requested_temperature':frozen.TEMP,'requested_seed':frozen.SEED,'hard_timeout_seconds':frozen.TIMEOUT,'timestamp_utc':now()}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--max-calls',type=int,default=None);args=ap.parse_args()
    freeze=frozen.verify(); model=model_verified(); logical,unique=frozen.build(frozen.PROMPT.read_text(encoding='utf-8'))
    if (len(logical),len(unique)) != (690,119): raise RuntimeError('STOP: frozen count mismatch')
    print(js({'freeze':freeze,'model':model,'logical_evaluations':len(logical),'unique_inputs':len(unique),'reused_identical_inputs':len(logical)-len(unique)}))
    if not args.run: return
    # The imported invocation/parser retains the frozen prompt/schema/options; only the in-memory model selector changes.
    frozen.MODEL=MODEL
    already=done()
    append({'record_type':'run_started','timestamp_utc':now(),'backend':'local_ollama_native_api','endpoint':frozen.URL,'model_identifier':MODEL,'model_digest':DIGEST,'monitor_prompt_hash':frozen.PH,'oracle_hash':frozen.OH,'logical_evaluations':690,'unique_inputs':119,'reused_identical_inputs':571,'already_successful_unique_calls':len(already)})
    executed=0
    for i,(key,source) in enumerate(unique.items(),1):
        if key in already: continue
        if args.max_calls is not None and executed >= args.max_calls: break
        cid=f'b13_unique_{i:03d}'
        append(base(cid,source,'attempt_started'))
        result=frozen.invoke(source['serialized_input'],set(source['visible_event_ids']))
        result.update(call_id=cid,input_hash=key)
        rec=base(cid,source,'attempt_completed' if result['parse_success'] else 'attempt_failed')
        rec.update(result);rec['timestamp_completed_utc']=now();append(rec); executed += 1
    complete=done()
    append({'record_type':'run_completed' if len(complete)==119 else 'run_checkpoint','timestamp_utc':now(),'model_identifier':MODEL,'model_digest':DIGEST,'successful_unique_calls':len(complete),'expected_unique_calls':119,'calls_attempted_this_invocation':executed})
    print(js({'successful_unique_calls':len(complete),'expected_unique_calls':119,'missing_unique_calls':119-len(complete)}))
if __name__=='__main__': main()
