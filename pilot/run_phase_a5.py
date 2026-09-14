"""Run Phase A.5 locally: APPARATUS MONITOR — NOT AN AI MONITOR RESULT."""
from __future__ import annotations
import csv
from pathlib import Path
from .fixtures import build_phase_a5_fixtures, build_phase_a5_counterfactual_pair
from .metrics_a5 import evaluate
from .structural_matching import diagnostics
from .views import VIEW_IDS

def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def _evaluate(fixtures: dict):
    rows=[]; prefix=[]
    for trace in fixtures.values():
        control=fixtures[trace.matched_control_id]
        for view in VIEW_IDS:
            row,prefixes=evaluate(trace,control,view); rows.append(row.csv_dict()); prefix.extend(prefixes)
    return rows,prefix
def main() -> None:
    root=Path(__file__).resolve().parents[1]; results=root/"results"; results.mkdir(exist_ok=True)
    fixtures=build_phase_a5_fixtures(); rows,prefixes=_evaluate(fixtures)
    _write(results/"phase_a5_summary.csv",rows); _write(results/"phase_a5_prefix_scores.csv",prefixes)
    _write(results/"phase_a5_structural_matching.csv",diagnostics(fixtures["B1"],fixtures["A2"]))
    cf_rows,cf_prefixes=_evaluate(build_phase_a5_counterfactual_pair())
    _write(results/"phase_a5_counterfactual_route.csv",cf_rows); _write(results/"phase_a5_counterfactual_prefix_scores.csv",cf_prefixes)
    print(f"wrote {len(rows)} primary rows, {len(prefixes)} primary prefixes, {len(cf_rows)} counterfactual rows")
if __name__=="__main__": main()
