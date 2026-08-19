# Script Inventory

The `scripts/` directory contains repository tooling, not a second public API.
Run a script only from a source checkout and follow its owning document. A
filename being present here does not make the operation safe for production or
promise command-line compatibility across releases.

## Routine Repository Gates

| Script | Role |
| --- | --- |
| `check.sh` | Main local source, test, typing, formatting, documentation, and web gate |
| `check-correctness.sh` | Extended correctness and methodological evidence gate |
| `check-wheel.sh` | Fresh wheel/sdist and installed-distribution smoke gate |
| `wheel_smoke.py` | Installed-package interface and bundled-resource checks |
| `model_build_smoke.py` | Installed model-building smoke check |
| `case_study_wheel_smoke.py` | Installed fictional case-study interface smoke check |

Use [CONTRIBUTING.md](../CONTRIBUTING.md) for the normal development sequence.

## Evidence and Contract Builders

These regenerate reviewed, deterministic repository evidence or compatibility
contracts. Their corresponding tests normally provide a `--check`-style drift
gate.

- `audit_small_area_control_coverage.py`
- `build_external_canadian_comparison.py`
- `build_field_eligibility_inventory.py`
- `build_methodology_evidence.py`
- `build_multiscale_validation_evidence.py`
- `build_public_interface.py`
- `build_release_evidence.py`
- `prepare_pumf_metadata.py`

Do not hand-edit generated artifacts to make a check pass. Review the source,
generator, artifact diff, and methodological implications together.

## Model and Archive Publication

- `build_all_model_packages.py` builds the reviewed model catalogue locally.
- `build_corrected_model_assets.py` creates non-overwriting rights-metadata
  correction candidates.
- `build_zenodo_depositions.py` constructs bound Zenodo metadata and execution
  manifests.
- `deposit_zenodo_records.py` is the fail-closed archive executor.

These scripts can prepare or perform externally visible publication work.
Follow [RELEASING.md](../RELEASING.md) and the applicable ADR exactly. A dry run,
reviewed manifest, authenticated preflight, and required production gates do
not imply authorization to publish.

## Geography and Bounded Operations

- `build_geodata_release.mjs`, `simplify_boundaries.mjs`,
  `simplify_all_boundaries.mjs`, and `simplify_csd_partitions.mjs` prepare
  display-boundary artifacts.
- `prove_quebec_da_2021.py` and `finalize_quebec_da_2021.py` support the bounded
  Québec DA evidence workflow.
- `reset_nonconverged_national_batches.py` is a narrow recovery tool for
  restartable national execution state, not a general reset command.

Use the [small-area execution reference](../docs/small-area-reference.md) and
the prepared-geodata section of [RELEASING.md](../RELEASING.md).

## Benchmarks

- `benchmarks.py` contains the maintained local IPF and small-area probes.
- `benchmark_national_candidate_pools.py` measures the bounded national
  candidate-pool path.

Benchmarks are machine-dependent developer evidence, not runtime guarantees.
The contributor guide records the supported commands and interpretation.

## Maintenance Rule

When adding a script, classify it here, link its owning procedure, state
whether it can write external state, and add a test appropriate to its risk.
Prefer a package module or maintained CLI command when users are expected to
depend on the behavior.
