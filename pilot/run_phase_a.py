"""Run Phase A locally: APPARATUS MONITOR — NOT AN AI MONITOR RESULT."""
from __future__ import annotations
import csv
from pathlib import Path
from .fixtures import build_fixtures
from .metrics import evaluate
from .views import VIEW_IDS

def main() -> None:
    root = Path(__file__).resolve().parents[1]; results = root / "results"; results.mkdir(exist_ok=True)
    fixtures = build_fixtures(); rows=[]; prefix_rows=[]
    for trace in fixtures.values():
        control = fixtures[trace.matched_control_id]
        for view in VIEW_IDS:
            row, prefixes = evaluate(trace, control, view); rows.append(row.csv_dict()); prefix_rows.extend(prefixes)
    with (results / "phase_a_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (results / "phase_a_prefix_scores.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f, fieldnames=list(prefix_rows[0])); writer.writeheader(); writer.writerows(prefix_rows)
    print(f"wrote {len(rows)} result rows and {len(prefix_rows)} prefix-score rows")
if __name__ == "__main__": main()
