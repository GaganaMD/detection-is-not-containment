import unittest
from pilot.fixtures import build_fixtures
from pilot.views import project
class ViewTests(unittest.TestCase):
 def setUp(self): self.trace=build_fixtures()["A1"]
 def test_seq_contiguous_and_views_preserve_ids(self):
  self.assertEqual([e.seq for e in self.trace.events],list(range(1,len(self.trace.events)+1)))
  canonical={e.seq for e in self.trace.events}
  for v in ("M_ACTION","M_COT_ACTION","M_GROUNDED"): self.assertTrue({e.seq for e in project(v,self.trace.events)} <= canonical)
 def test_mask_isolation(self):
  action=project("M_ACTION",self.trace.events); cot=project("M_COT_ACTION",self.trace.events); grounded=project("M_GROUNDED",self.trace.events)
  self.assertFalse(any(e.kind=="reasoning" for e in action)); self.assertFalse(any("policy_status" in e.payload for e in action))
  self.assertTrue(any(e.kind=="reasoning" for e in cot)); self.assertFalse(any(e.kind=="environment_evidence" or "policy_status" in e.payload for e in cot))
  evidence=[e for e in grounded if e.kind=="environment_evidence"]
  self.assertTrue(evidence and all(e.actor=="environment" and e.payload.get("fact")=="delivery_staged" for e in evidence))
 def test_same_canonical_reused(self):
  original=self.trace.events
  for v in ("M_ACTION","M_COT_ACTION","M_GROUNDED"):
   project(v,original); self.assertIs(self.trace.events,original)
