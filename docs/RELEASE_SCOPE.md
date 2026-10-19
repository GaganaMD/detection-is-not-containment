# Public release scope

This is a curated, public, reproducibility-oriented snapshot of the completed Phase A/A.5, B1.3, C, D, E, and F workstreams. The minimal frozen B2/B2-R protocol lineage required by the Phase C manifest is included only for byte-level Phase C validation; it is not presented as an executed result.

Included:
- deterministic apparatus, frozen oracle, views, metrics, model-monitor runner, counterfactual and invariance code;
- completed B1.3/C/D/E raw local-call JSONL plus reconstructed CSV/summary evidence;
- Phase F's deterministic cached-decision controller and its completed replay records;
- frozen conditions/manifests, result reports, and publication figures.
- the report's forensics and checklist-protocol pipeline (`forensics/`, `claims/`, and the non-frozen files in `protocol/`): code, outputs, and source manifests, but not the third-party page snapshots.

Intentionally excluded:
- unfinished B2/B2-R execution artifacts, partial caches, run state, and results;
- failed historical B1 harness attempts that are superseded by the completed direct-native run;
- local environments, credentials, model files, and transient build/test outputs.

The included raw model records from the monitoring experiment are synthetic research data; the forensics and protocol outputs are derived from public web sources. This repository does not contain secrets, hosted API credentials, or model weights. Source files and published data are released under MIT; third-party model weights remain subject to their own licenses.
