"""Read-only checks for the public research release; never performs model inference."""
from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLE_HASH = "83141b61abf6c95ad2afa6bddea72e74ca59f79aae32f41fd04cf3d17e37b93d"
PROMPT_HASH = "d6bbb910488951d4daad76f80d140c88ba134b1b6984df2b9ecfba8d2b4b7b4a"

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    oracle = (ROOT / "docs" / "ORACLE_FREEZE_A5.md").read_bytes()
    marker = b"## Integrity hash"
    if marker not in oracle:
        raise SystemExit("FAIL: oracle integrity marker is absent")
    oracle_body = oracle.split(marker, 1)[0]
    prompt = (ROOT / "docs" / "PHASE_B1_MONITOR_PROMPT.txt").read_bytes()
    required = [
        "results/phase_b13_monitor_calls.jsonl",
        "results/phase_b13_score_curves.csv",
        "results/phase_e_monitor_calls.jsonl",
        "results/phase_f_controller_executions.jsonl",
        "figures/main/fig1_evidence_representation.png",
        "figures/main/fig2_representation_robustness.png",
        "figures/main/fig3_closed_loop_intervention.png",
        "figures/supporting/figS1_observation_channel_timing.png",
        "figures/supporting/figS2_prefix_detection_timing.png",
        "figures/supporting/figS3_closed_loop_outcomes.png",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    if missing:
        raise SystemExit("FAIL: missing released artifacts: " + ", ".join(missing))
    actual_oracle = sha256(oracle_body)
    actual_prompt = sha256(prompt)
    if actual_oracle != ORACLE_HASH:
        raise SystemExit(f"FAIL: oracle hash {actual_oracle}")
    if actual_prompt != PROMPT_HASH:
        raise SystemExit(f"FAIL: prompt hash {actual_prompt}")
    print("PASS: release structure present")
    print("PASS: oracle hash", actual_oracle)
    print("PASS: monitor prompt hash", actual_prompt)
    print("PASS: no inference was run")

if __name__ == "__main__":
    main()
