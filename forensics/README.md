# forensics/

Inputs for the claims pipeline in `../claims/` (report section 3.1, appendix A.1).

| Path | Role |
|------|------|
| `sources/manifest.json`, `sources/extra_sources_manifest.json` | URL, slug, fetch time and SHA-256 for each of the 20 public sources |
| `sources/fetch_snapshots.py`, `sources/fetch_extra_sources.py` | Re-fetch the pages into `sources/raw/` (network) |
| `src/check_event_grounding.py` | Quote-matching helper imported by `claims/src/prefilter.py` |

The page snapshots themselves (`sources/raw/`) are not included: they are third-party content. To re-run extraction (`claims/src/extract_claims.py`) or the link prefilter, fetch them first and compare each file's SHA-256 with the manifest; pages that have changed since will not match. Shipped outputs in `../claims/out/` were produced from the original snapshots.

Source ids (`SRC01`..`SRC20`) are assigned in `../claims/data/source_registry.json`. See `../docs/DUAL_USE.md` for what is and is not extracted.
