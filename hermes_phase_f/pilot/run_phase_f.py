"""Phase F execution runner. Uses frozen Phase E cached decisions; never performs model inference."""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,os,tempfile,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from hermes_phase_f.pilot.phase_f_control import run_all
OUT=ROOT/'results/phase_f_controller_executions.jsonl';STATE=ROOT/'results/phase_f_run_state.json';FM=ROOT/'protocol/F_FREEZE_MANIFEST.json'
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name,suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf8',newline='\n') as f:f.write(canon(obj)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def check_freeze():
 m=json.loads(FM.read_text());z=dict(m);h=z.pop('manifest_sha256');assert hashlib.sha256(canon(z).encode()).hexdigest()==h
 for rel,d in m['artifacts'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==d,rel
def append(obj):
 with OUT.open('a',encoding='utf8',newline='\n') as f:f.write(canon(obj)+'\n');f.flush();os.fsync(f.fileno())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');a=ap.parse_args();check_freeze()
 if not a.execute:
  print(canon({'status':'DRY_RUN_NO_EXECUTION_NO_INFERENCE','planned_conditions':5,'model_calls':0}));return
 if OUT.exists():raise RuntimeError('STOP: Phase F output already exists; no overwrite/replay permitted')
 atomic(STATE,{'status':'running','model_calls':0,'completed':0})
 for i,x in enumerate(run_all(),1):
  append({'record_type':'controller_execution_completed','execution':x});atomic(STATE,{'status':'running','model_calls':0,'completed':i})
 atomic(STATE,{'status':'complete','model_calls':0,'completed':5});print(canon({'status':'complete','model_calls':0,'completed':5}))
if __name__=='__main__':main()
