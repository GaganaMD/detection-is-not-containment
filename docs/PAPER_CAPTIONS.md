# Paper captions

## Figure 1 — Evidence representation
At the critical grounded prefix (sequence 37), paired attack and benign monitor scores are shown across four evidence representations, with the fixed intervention threshold at 51. Relational authorization evidence (G2) is the only tested representation that separates the matched benign case (100 versus 0); the explicit-verdict condition does not preserve that separation. This four-condition deterministic ablation identifies an evidence condition, not a monotonic relationship between explicitness and discrimination.

## Figure 2 — Representation robustness
(a) Sequence-37 suspicion scores and (b) discrete decision outcomes are shown for 12 semantics-preserving identifier assignments. Attack detection is stable (12/12), but benign false positives occur in 4/12 assignments; only 3/12 are strict control-ready under the preregistered composite criterion. The diagnostic is bounded to the tested morphology strata and does not estimate robustness to arbitrary encodings.

## Figure 3 — Matched closed-loop intervention
Matched F1 control and intervention executions have the same cached monitor input and threshold crossing at sequence 37, and retain the same prohibited action attempt at sequence 38. Only the intervention arm revokes authority: the later action is rejected and the environment records an explicit prevention witness, whereas the control arm accepts the action and reaches the prohibited effect. This is a deterministic paired causal witness, not a deployment-rate estimate.

## Figure S1 — Observation-channel timing
First fixed-threshold crossings are compared across action-only, CoT-plus-action, and grounded views for two trajectories; NC denotes no crossing rather than a late numerical event. In A1, CoT-plus-action and grounded views cross at sequence 32; in neutral-reasoning A2, only the grounded view crosses, at sequence 37, one sequence before the last-safe boundary at 38. These two trajectories explain information availability but do not establish a general channel ranking.

## Figure S2 — Prefix-level detection timing
A2 suspicion scores are plotted over every scored prefix for the three monitor views, with the fixed threshold at 51 and the last-safe boundary at sequence 38. Grounded evidence crosses at sequence 37; action-only and CoT-plus-action do not cross in this trajectory. The plot characterizes this deterministic trajectory and does not estimate late-detection prevalence.

## Figure S3 — Closed-loop outcomes
Five deterministic Phase F executions are shown as semantic outcome states rather than uniformly positive yes/no cells. The F1 intervention prevents the attack effect after authority revocation, while the F3 representation false-positive condition revokes legitimate authority, rejects a legitimate action, and fails the task. The matrix summarizes a small diagnostic suite and should not be read as a population risk estimate.
