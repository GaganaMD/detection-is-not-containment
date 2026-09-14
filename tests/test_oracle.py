import unittest
from pilot.fixtures import build_fixtures
from pilot.information_oracle import information_available
from pilot.views import project
class OracleTests(unittest.TestCase):
 def test_expected_availability_and_no_route_shortcut(self):
  f=build_fixtures()
  for a,expected in (("A1", {"M_ACTION":38,"M_COT_ACTION":32,"M_GROUNDED":32}), ("A2", {"M_ACTION":38,"M_COT_ACTION":38,"M_GROUNDED":37})):
   for view,seq in expected.items():
    projected=project(view,f[a].events); control=project(view,f["H1"].events)
    self.assertEqual(information_available(view,[e for e in projected if e.seq<=seq],[e for e in control if e.seq<=seq]),seq)
 def test_oracle_only_accepts_projected_events(self):
  import inspect
  from pilot import information_oracle
  signature=inspect.signature(information_oracle.information_available)
  self.assertEqual(list(signature.parameters), ["view_id", "prefix", "matched_control"])
  self.assertNotIn("Trajectory", str(signature))
