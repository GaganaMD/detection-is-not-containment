"""Phase D no-inference validation gate."""
import hashlib,json
from pathlib import Path
from .d_semantic_counterfactuals import CONDITIONS,all_trajectories
from .views import project
ROOT=Path(__file__).resolve().parents[1]
def norm(x):return {str(k):norm(v) for k,v in x.items()} if hasattr(x,'items') else [norm(v) for v in x] if isinstance(x,(list,tuple)) else x
def vis(events,end=None):return [{'seq':e.seq,'kind':e.kind,'actor':e.actor,'payload':norm(e.payload),'parents':list(e.parent_seq_ids)} for e in events if end is None or e.seq<=end]
def mh(m):
 z=dict(m);z.pop('manifest_sha256',None);return hashlib.sha256(json.dumps(z,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate():
 ts=all_trajectories(); cs={x.condition_id:x for x in CONDITIONS}; proto=json.loads((ROOT/'protocol/D_CONDITIONS.json').read_text()); assert {x['condition_id'] for x in proto['conditions']}==set(cs) and all(tuple(next(x for x in proto['conditions'] if x['condition_id']==c.condition_id)['authorized_routes'])==c.authorized_routes for c in CONDITIONS); bad=('not_permitted','approved','attack','benign','condition_id','authorization','last_safe_intervention_seq','prohibited_effect','side_objective')
 out={'status':'PASS','inference_calls':0,'condition_count':len(cs),'checks':{}}
 for c in CONDITIONS:
  t=ts[c.condition_id]; assert len(t.events)==41 and t.events[-1].seq==41
  for view in ('M_ACTION','M_COT_ACTION','M_GROUNDED'):
   x=vis(project(view,t.events),38)
   assert all(e['kind']!='effect' and not any(q in json.dumps(e['payload'],sort_keys=True).lower() for q in bad) for e in x)
 for fam in ('D0','D1','D2','D4','D5'):
  a=cs[fam+'_ATTACK'];b=cs[fam+'_BENIGN'];ta=ts[a.condition_id];tb=ts[b.condition_id]
  assert a.target_route==b.target_route and a.authorization=='not_permitted' and b.authorization=='approved'
  assert vis(project('M_ACTION',ta.events))==vis(project('M_ACTION',tb.events))
  assert vis(project('M_COT_ACTION',ta.events))==vis(project('M_COT_ACTION',tb.events))
  assert vis(project('M_GROUNDED',ta.events),36)==vis(project('M_GROUNDED',tb.events),36)
  assert ta.last_safe_intervention_seq==38 and tb.last_safe_intervention_seq is None
  ea=ta.events[36].payload; eb=tb.events[36].payload
  assert ea['route_id'] not in ea['authorized_routes'] and eb['route_id'] in eb['authorized_routes']
  if fam in ('D4','D5'): assert len(ea['authorized_routes'])==len(eb['authorized_routes'])
 d3a,d3b=ts['D3_BENIGN_AB'],ts['D3_BENIGN_BA'];assert vis(project('M_ACTION',d3a.events))==vis(project('M_ACTION',d3b.events));assert vis(project('M_COT_ACTION',d3a.events))==vis(project('M_COT_ACTION',d3b.events));assert vis(project('M_GROUNDED',d3a.events),36)==vis(project('M_GROUNDED',d3b.events),36);assert set(d3a.events[36].payload['authorized_routes'])==set(d3b.events[36].payload['authorized_routes']) and d3a.events[36].payload['route_id'] in d3a.events[36].payload['authorized_routes'] and d3b.events[36].payload['route_id'] in d3b.events[36].payload['authorized_routes']
 m=json.loads((ROOT/'protocol/D_FREEZE_MANIFEST.json').read_text());assert mh(m)==m['manifest_sha256']
 for rel,h in m['artifacts'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==h,rel
 out['checks']={k:'PASS' for k in ('paired_pre_evidence_byte_identity','action_projection_pair_identity','cot_action_projection_pair_identity','grounded_only_divergence_seq_37','D4_equal_cardinality','D5_equal_cardinality','D4_D5_target_constant_within_pair','D4_D5_membership_only_relation','D3_benign_set_order_invariance','no_explicit_policy_verdict','no_visible_condition_labels','no_safe_or_effect_labels','safe_boundary_fixed','effect_environment_only','frozen_manifest','no_inference')};return out
def main():
 r=validate();(ROOT/'protocol/D_VALIDATION_REPORT.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
