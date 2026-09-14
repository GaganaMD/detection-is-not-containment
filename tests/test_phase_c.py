import unittest
from pilot.c_evidence_ablation import CONDITIONS,EVIDENCE_SEQ,LAST_SAFE_INTERVENTION_SEQ,all_trajectories
from pilot.c_oracle import information_available
from pilot.validate_phase_c import validate
from pilot.views import VIEW_IDS,project
class PhaseCTests(unittest.TestCase):
 def test_count_pairing(self): self.assertEqual(len(CONDITIONS),8);self.assertTrue(all(c.matched_control_id for c in CONDITIONS))
 def test_matching(self):
  ts=all_trajectories()
  for L in ("G0","G1","G2","G3"):
   for v in VIEW_IDS:
    a=tuple(e for e in project(v,ts[f"C_{L}_ATTACK"].events) if e.seq<37);b=tuple(e for e in project(v,ts[f"C_{L}_BENIGN"].events) if e.seq<37);self.assertEqual(a,b)
    if v in ("M_ACTION","M_COT_ACTION"):self.assertEqual(project(v,ts[f"C_{L}_ATTACK"].events),project(v,ts[f"C_{L}_BENIGN"].events))
 def test_oracle(self):
  ts=all_trajectories()
  for L,x in (("G0",None),("G1",None),("G2",37),("G3",37)):
   self.assertEqual(information_available("M_GROUNDED",project("M_GROUNDED",ts[f"C_{L}_ATTACK"].events)),x);self.assertIsNone(information_available("M_GROUNDED",project("M_GROUNDED",ts[f"C_{L}_BENIGN"].events)))
 def test_gate(self):self.assertEqual(validate()["status"],"PASS")
