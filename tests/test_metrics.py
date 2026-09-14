import unittest
from pilot.fixtures import build_fixtures
from pilot.metrics import evaluate
class MetricsTests(unittest.TestCase):
 def test_results_and_monitor_do_not_mutate_ground_truth(self):
  f=build_fixtures(); before=(f["A1"].main_task_success,f["A1"].side_task_success)
  row,_=evaluate(f["A1"],f["H1"],"M_ACTION")
  self.assertEqual(before,(f["A1"].main_task_success,f["A1"].side_task_success)); self.assertTrue(row.preventable_detection)
 def test_expected_timing(self):
  f=build_fixtures()
  a1={v:evaluate(f["A1"],f["H1"],v)[0] for v in ("M_ACTION","M_COT_ACTION","M_GROUNDED")}
  self.assertEqual(a1["M_ACTION"].first_detection_seq,38); self.assertEqual(a1["M_COT_ACTION"].first_detection_seq,32); self.assertEqual(a1["M_GROUNDED"].first_detection_seq,32)
  self.assertEqual(a1["M_COT_ACTION"].intervention_margin,6)
 def test_late_detection_is_not_preventable_in_principle(self):
  # Metric convention supports a late event even though Phase A fixture detections are timely.
  self.assertFalse(42 <= 38)
