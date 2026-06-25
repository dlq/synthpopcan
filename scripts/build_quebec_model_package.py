"""Build and exercise the packaged Quebec 2016 linked model.

This is a maintainer workflow script. It uses SynthPopCan's Python library
modules directly so the release process is reproducible outside the CLI.
Source microdata and generated CSVs stay under ``data/private``. The final
reviewed package is copied into ``data/private/model-release-assets`` for
maintainer upload as a GitHub Release asset.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

from synthpopcan.cli_tree import (
    apply_target_profile,
    filter_training_sample_by_geography,
    geography_filter_manifest,
    model_manifest,
    read_model_release_manifest,
    read_source_provenance,
    release_blocking_issues,
    train_tree_sample,
    tree_training_sample_from_export,
    write_tree_generation_manifest,
)
from synthpopcan.microdata import (
    export_training_rows,
    read_statcan_2016_hierarchical_seed_sample,
    resolve_tree_column_block_pair,
)
from synthpopcan.tree import (
    audit_tree_model,
    generate_linked_population_to_csv,
    read_tree_model,
    write_tree_model,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data/raw/statscan/2016-census/PUMF Census 2016"
    / "pumf-98M0002-E-2016-hierarchical"
    / "pumf-98M0002-E-2016-hierarchical_F1.csv"
)
WORK_DIR = ROOT / "data/private/benchmarks/tree-release-2016-pr24-all-fields"
PACKAGE_ID = "quebec-2016-all-fields"
PACKAGE_PATH = (
    ROOT / "data/private/model-release-assets/quebec-2016-all-fields-package.json"
)
HOUSEHOLDS = 3_750_000


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Quebec 2016 all-fields linked model package."
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Also generate the large 3.75M-household synthetic CSV outputs.",
    )
    args = parser.parse_args()

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    package = build_package()
    PACKAGE_PATH.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {PACKAGE_PATH.relative_to(ROOT)}")

    if args.generate:
        generate_large_outputs()


def build_package() -> dict[str, object]:
    started = time.perf_counter()
    sample = read_statcan_2016_hierarchical_seed_sample(SOURCE)
    sample = filter_training_sample_by_geography(
        sample,
        geography_column="PR",
        geography_value="24",
    )
    (
        household_targets,
        household_conditions,
        person_targets,
        person_conditions,
        column_source,
    ) = resolve_tree_column_block_pair(
        sample,
        household_block="all",
        person_block="all",
    )
    household_targets, person_targets = apply_target_profile(
        household_target_columns=household_targets,
        person_target_columns=person_targets,
        target_profile="full",
    )

    household_rows, household_export = export_training_rows(
        sample,
        level="household",
        target_columns=household_targets,
        conditioning_columns=household_conditions,
    )
    person_rows, person_export = export_training_rows(
        sample,
        level="person",
        target_columns=person_targets,
        conditioning_columns=person_conditions,
    )

    household_model = train_tree_sample(
        tree_training_sample_from_export(rows=household_rows, export=household_export),
        method="conditional-frequency",
        random_seed=7,
        min_support=5,
        min_samples_leaf=5,
        max_depth=None,
    )
    person_model = train_tree_sample(
        tree_training_sample_from_export(rows=person_rows, export=person_export),
        method="conditional-frequency",
        random_seed=7,
        min_support=5,
        min_samples_leaf=5,
        max_depth=None,
    )

    household_model_path = WORK_DIR / "household-model.json"
    person_model_path = WORK_DIR / "person-model.json"
    training_manifest_path = WORK_DIR / "linked-training-manifest.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    write_tree_generation_manifest(
        training_manifest_path,
        {
            "schema_version": "synthpopcan-linked-tree-training-v1",
            "command": "library workflow",
            "source": {
                "path": str(SOURCE.relative_to(ROOT)),
                "source_format": sample.source_format,
                "records": len(sample.records),
                "households": sample.metadata.get("households", 0),
            },
            "column_source": column_source,
            "target_profile": "full",
            "geography_filter": geography_filter_manifest("PR", "24"),
            "method": "conditional-frequency",
            "random_seed": 7,
            "training": {
                "household": household_export,
                "person": person_export,
            },
            "models": {
                "household": model_manifest(household_model, household_model_path),
                "person": model_manifest(person_model, person_model_path),
            },
        },
    )

    household_release_path = WORK_DIR / "household-model-publishable.json"
    person_release_path = WORK_DIR / "person-model-publishable.json"
    household_release_manifest_path = WORK_DIR / "household-release-manifest.json"
    person_release_manifest_path = WORK_DIR / "person-release-manifest.json"
    prepare_publishable_model(
        model_path=household_model_path,
        out_path=household_release_path,
        manifest_path=household_release_manifest_path,
        review_note=(
            "Quebec PR=24 all-household/all-person-block household model reviewed "
            "with SynthPopCan release checks."
        ),
    )
    prepare_publishable_model(
        model_path=person_model_path,
        out_path=person_release_path,
        manifest_path=person_release_manifest_path,
        review_note=(
            "Quebec PR=24 all-household/all-person-block person model reviewed "
            "with SynthPopCan release checks."
        ),
    )

    source_provenance_path = WORK_DIR / "source-provenance.json"
    source_provenance_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "2016 Census Hierarchical Public Use Microdata File",
                "provider": "Statistics Canada",
                "access_class": "local restricted/source-controlled data root",
                "citation": (
                    "Statistics Canada, 2016 Census Hierarchical Public Use "
                    "Microdata File."
                ),
                "redistribution_note": (
                    "Do not redistribute source microdata. Package contains "
                    "model artifacts only."
                ),
                "local_path": str(SOURCE.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    household_publishable = read_tree_model(household_release_path)
    person_publishable = read_tree_model(person_release_path)
    household_audit = audit_tree_model(household_publishable)
    person_audit = audit_tree_model(person_publishable)
    package = {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "household_size_column": "household_size",
        "review_note": (
            "Quebec PR=24 all-household and all-person-block linked package "
            "reviewed by SynthPopCan release-readiness checks."
        ),
        "thresholds": {"min_support": 50.0, "max_purity": 0.95},
        "build": {
            "package_id": PACKAGE_ID,
            "script": "scripts/build_quebec_model_package.py",
            "seconds": round(time.perf_counter() - started, 3),
        },
        "training_manifest": json.loads(training_manifest_path.read_text()),
        "source_provenance": read_source_provenance(source_provenance_path),
        "release_manifests": {
            "household": read_model_release_manifest(household_release_manifest_path),
            "person": read_model_release_manifest(person_release_manifest_path),
        },
        "model_summaries": {
            "household": {
                **model_manifest(household_publishable, household_release_path),
                "bytes": household_release_path.stat().st_size,
            },
            "person": {
                **model_manifest(person_publishable, person_release_path),
                "bytes": person_release_path.stat().st_size,
            },
        },
        "models": {
            "household": household_publishable.to_dict(),
            "person": person_publishable.to_dict(),
        },
        "audits": {
            "household": household_audit,
            "person": person_audit,
        },
        "privacy": {
            "publishable_candidate": (
                household_audit["publishable_candidate"]
                and person_audit["publishable_candidate"]
            ),
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
        },
    }
    package = relativize_paths(package)
    print_release_summary(package)
    return package


def prepare_publishable_model(
    *,
    model_path: Path,
    out_path: Path,
    manifest_path: Path,
    review_note: str,
) -> object:
    model = read_tree_model(model_path)
    audit = audit_tree_model(model)
    blocking = release_blocking_issues(audit)
    if blocking:
        raise RuntimeError(f"{model_path} has release-blocking issues: {blocking}")
    candidate = replace(model, release_class="publishable_candidate")
    write_tree_model(out_path, candidate)
    write_tree_generation_manifest(
        manifest_path,
        {
            "schema_version": "synthpopcan-tree-release-manifest-v1",
            "command": "library workflow",
            "source_model": repo_path(model_path),
            "output_model": repo_path(out_path),
            "release_class": "publishable_candidate",
            "review_note": review_note,
            "thresholds": {"min_support": 50.0, "max_purity": 0.95},
            "audit": audit,
        },
    )
    return candidate


def generate_large_outputs() -> None:
    package = json.loads(PACKAGE_PATH.read_text())
    household_model = read_tree_model(WORK_DIR / "household-model-publishable.json")
    person_model = read_tree_model(WORK_DIR / "person-model-publishable.json")
    households_path = WORK_DIR / "synthetic-households-3.75m.csv"
    persons_path = WORK_DIR / "synthetic-persons-3.75m.csv"
    manifest_path = WORK_DIR / "synthetic-linked-3.75m-manifest.json"
    started = time.perf_counter()
    household_count, person_count = generate_linked_population_to_csv(
        household_model,
        person_model,
        households=HOUSEHOLDS,
        households_path=households_path,
        persons_path=persons_path,
        household_size_column=str(
            package.get("household_size_column", "household_size")
        ),
        random_seed=24,
    )
    elapsed = time.perf_counter() - started
    write_tree_generation_manifest(
        manifest_path,
        {
            "schema_version": "synthpopcan-tree-generation-manifest-v1",
            "command": "library workflow",
            "package": PACKAGE_ID,
            "outputs": {
                "households": repo_path(households_path),
                "persons": repo_path(persons_path),
            },
            "households": HOUSEHOLDS,
            "generated_households": household_count,
            "generated_persons": person_count,
            "random_seed": 24,
            "seconds": round(elapsed, 3),
        },
    )
    print(
        "Generated "
        f"{household_count:,} household rows and {person_count:,} person rows "
        f"in {elapsed:.2f}s"
    )
    print(f"Wrote {manifest_path.relative_to(ROOT)}")


def relativize_paths(value: object) -> object:
    """Return a JSON-like object with repo-local absolute paths made relative."""

    if isinstance(value, dict):
        return {key: relativize_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [relativize_paths(item) for item in value]
    if isinstance(value, str):
        return relativize_path_string(value)
    return value


def relativize_path_string(value: str) -> str:
    try:
        path = Path(value)
    except ValueError:
        return value
    if not path.is_absolute():
        return value
    try:
        return repo_path(path)
    except ValueError:
        return value


def repo_path(path: Path) -> str:
    """Return ``path`` relative to the repository root."""

    return str(path.resolve(strict=False).relative_to(ROOT))


def print_release_summary(package: dict[str, object]) -> None:
    audits = package["audits"]
    assert isinstance(audits, dict)
    for level in ("household", "person"):
        audit = audits[level]
        assert isinstance(audit, dict)
        summary = audit["summary"]
        assert isinstance(summary, dict)
        print(
            f"{level}: publishable={audit['publishable_candidate']} "
            f"groups={summary['groups_or_leaves']} "
            f"min_support={summary['minimum_support']}"
        )


if __name__ == "__main__":
    main()
