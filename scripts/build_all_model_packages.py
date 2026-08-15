"""Build all province- and CMA-level linked model packages for release.

Trains, audits, and packages a linked household/person model for every
Canadian province (and PEI at minimal profile) and the five PUMF-coded CMAs.
Output packages land in ``data/derived/models/release-assets/`` ready for
upload as GitHub Release assets.

Usage::

    uv run python scripts/build_all_model_packages.py
    uv run python scripts/build_all_model_packages.py --year 2021
    uv run python scripts/build_all_model_packages.py --only ontario-2016 toronto-cma-2016
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import click

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
    read_statcan_2021_hierarchical_seed_sample,
    resolve_tree_column_block_pair,
)
from synthpopcan.model_licensing import statcan_prepared_model_licensing
from synthpopcan.tree import (
    audit_tree_model,
    read_tree_model,
    write_tree_model,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    2016: ROOT
    / "data/raw/statcan/census/2016/pumf/hierarchical"
    / "data_donnees_2016_hier.csv",
    2021: ROOT
    / "data/raw/statcan/census/2021/pumf/hierarchical"
    / "data_donnees_2021_hier_v2.csv",
}
ASSETS_DIR = ROOT / "data/derived/models/release-assets"

# ---------------------------------------------------------------------------
# Target definitions
# ---------------------------------------------------------------------------
# Each target produces one linked model package.
# "profile" is "full" for geographies with ≥2 000 households; "minimal" for
# smaller ones where the full column set would produce sparse / unpublishable
# models.
# Quebec (PR=24) and Montreal (CMA=462) are excluded. Their currently published
# packages were prepared separately and are not reconstructed by this batch tool.
# Territories (PR=70, ~402 hh) are excluded — too small to be publishable.

TARGETS: list[dict] = [
    # ---- provinces & territories ----
    dict(
        id="ontario-2016",
        geo_column="PR",
        geo_value="35",
        name="Ontario",
        profile="full",
        package_file="ontario-2016-all-fields-package.json",
        review_note="Ontario PR=35 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="bc-2016",
        geo_column="PR",
        geo_value="59",
        name="British Columbia",
        profile="full",
        package_file="bc-2016-all-fields-package.json",
        review_note="British Columbia PR=59 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="alberta-2016",
        geo_column="PR",
        geo_value="48",
        name="Alberta",
        profile="full",
        package_file="alberta-2016-all-fields-package.json",
        review_note="Alberta PR=48 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="manitoba-2016",
        geo_column="PR",
        geo_value="46",
        name="Manitoba",
        profile="full",
        package_file="manitoba-2016-all-fields-package.json",
        review_note="Manitoba PR=46 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="saskatchewan-2016",
        geo_column="PR",
        geo_value="47",
        name="Saskatchewan",
        profile="full",
        package_file="saskatchewan-2016-all-fields-package.json",
        review_note="Saskatchewan PR=47 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="nova-scotia-2016",
        geo_column="PR",
        geo_value="12",
        name="Nova Scotia",
        profile="full",
        package_file="nova-scotia-2016-all-fields-package.json",
        review_note="Nova Scotia PR=12 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="new-brunswick-2016",
        geo_column="PR",
        geo_value="13",
        name="New Brunswick",
        profile="full",
        package_file="new-brunswick-2016-all-fields-package.json",
        review_note="New Brunswick PR=13 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="newfoundland-2016",
        geo_column="PR",
        geo_value="10",
        name="Newfoundland and Labrador",
        profile="full",
        package_file="newfoundland-2016-all-fields-package.json",
        review_note="Newfoundland and Labrador PR=10 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="pei-2016",
        geo_column="PR",
        geo_value="11",
        name="Prince Edward Island",
        profile="minimal",
        package_file="pei-2016-minimal-package.json",
        review_note="Prince Edward Island PR=11 minimal-profile linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    # ---- CMAs ----
    dict(
        id="toronto-cma-2016",
        geo_column="CMA",
        geo_value="535",
        name="Toronto CMA",
        profile="full",
        package_file="toronto-cma-2016-all-fields-package.json",
        review_note="Toronto CMA=535 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="vancouver-cma-2016",
        geo_column="CMA",
        geo_value="933",
        name="Vancouver CMA",
        profile="full",
        package_file="vancouver-cma-2016-all-fields-package.json",
        review_note="Vancouver CMA=933 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="calgary-cma-2016",
        geo_column="CMA",
        geo_value="825",
        name="Calgary CMA",
        profile="full",
        package_file="calgary-cma-2016-all-fields-package.json",
        review_note="Calgary CMA=825 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
    dict(
        id="edmonton-cma-2016",
        geo_column="CMA",
        geo_value="835",
        name="Edmonton CMA",
        profile="full",
        package_file="edmonton-cma-2016-all-fields-package.json",
        review_note="Edmonton CMA=835 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
    ),
]


def targets_for_year(year: int) -> list[dict]:
    """Return the established regional targets for one census vintage."""

    targets = [
        {
            **target,
            "id": target["id"].replace("-2016", f"-{year}"),
            "package_file": target["package_file"].replace("-2016", f"-{year}"),
            "review_note": target["review_note"].replace("2016", str(year)),
        }
        for target in TARGETS
    ]
    if year == 2021:
        targets.extend(
            [
                dict(
                    id="quebec-2021",
                    geo_column="PR",
                    geo_value="24",
                    name="Quebec",
                    profile="full",
                    package_file="quebec-2021-all-fields-package.json",
                    review_note="Quebec PR=24 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
                ),
                dict(
                    id="montreal-cma-2021",
                    geo_column="CMA",
                    geo_value="462",
                    name="Montreal CMA",
                    profile="full",
                    package_file="montreal-cma-2021-all-fields-package.json",
                    review_note="Montreal CMA=462 all-fields linked package reviewed by SynthPopCan release-readiness checks.",
                ),
                dict(
                    id="canada-2021",
                    geo_column=None,
                    geo_value=None,
                    name="Canada",
                    profile="full",
                    package_file="canada-2021-all-fields-package.json",
                    review_note="Canada all-fields linked package reviewed by SynthPopCan release-readiness checks.",
                ),
            ]
        )
    return targets


# ---------------------------------------------------------------------------
# Build logic
# ---------------------------------------------------------------------------


def build_package(target: dict, sample_all, *, source: Path, year: int) -> dict:
    geo_column = target["geo_column"]
    geo_value = target["geo_value"]
    profile = target["profile"]
    package_id = target["id"]
    review_note = target["review_note"]

    work_dir = ROOT / "data/work/models/builds" / f"tree-release-{year}-{package_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()

    sample = filter_training_sample_by_geography(
        sample_all,
        geography_column=geo_column,
        geography_value=geo_value,
    )
    households = sample.metadata.get("households", 0)
    print(f"  {households:,} households, {len(sample.records):,} person records")

    hh_block = "all" if profile == "full" else "household_core"
    p_block = "all" if profile == "full" else "person_demographics"

    (
        household_targets,
        household_conditions,
        person_targets,
        person_conditions,
        column_source,
    ) = resolve_tree_column_block_pair(
        sample,
        household_block=hh_block,
        person_block=p_block,
    )
    household_targets, person_targets = apply_target_profile(
        household_target_columns=household_targets,
        person_target_columns=person_targets,
        target_profile=profile,
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

    household_model, household_method = _train_release_ready_model(
        tree_training_sample_from_export(
            rows=household_rows,
            export=household_export,
        )
    )
    person_model, person_method = _train_release_ready_model(
        tree_training_sample_from_export(
            rows=person_rows,
            export=person_export,
        )
    )

    household_model_path = work_dir / "household-model.json"
    person_model_path = work_dir / "person-model.json"
    training_manifest_path = work_dir / "linked-training-manifest.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    write_tree_generation_manifest(
        training_manifest_path,
        {
            "schema_version": "synthpopcan-linked-tree-training-v1",
            "command": "library workflow",
            "source": {
                "path": str(source.relative_to(ROOT)),
                "source_format": sample.source_format,
                "records": len(sample.records),
                "households": households,
            },
            "column_source": column_source,
            "target_profile": profile,
            "geography_filter": geography_filter_manifest(geo_column, geo_value),
            "method": (
                household_method if household_method == person_method else "mixed"
            ),
            "methods": {
                "household": household_method,
                "person": person_method,
            },
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

    household_release_path = work_dir / "household-model-publishable.json"
    person_release_path = work_dir / "person-model-publishable.json"
    household_release_manifest_path = work_dir / "household-release-manifest.json"
    person_release_manifest_path = work_dir / "person-release-manifest.json"

    _prepare_publishable_model(
        model_path=household_model_path,
        out_path=household_release_path,
        manifest_path=household_release_manifest_path,
        review_note=review_note,
    )
    _prepare_publishable_model(
        model_path=person_model_path,
        out_path=person_release_path,
        manifest_path=person_release_manifest_path,
        review_note=review_note,
    )

    source_provenance_path = work_dir / "source-provenance.json"
    source_provenance_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": f"{year} Census Hierarchical Public Use Microdata File",
                "provider": "Statistics Canada",
                "access_class": "local restricted/source-controlled data root",
                "citation": (
                    f"Statistics Canada, {year} Census Hierarchical Public Use "
                    "Microdata File."
                ),
                "redistribution_note": (
                    "Do not redistribute source microdata. Package contains "
                    "model artifacts only."
                ),
                "local_path": str(source.relative_to(ROOT)),
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
        "review_note": review_note,
        "thresholds": {"min_support": 50.0, "max_purity": 0.95},
        "build": {
            "package_id": package_id,
            "script": "scripts/build_all_model_packages.py",
            "seconds": round(time.perf_counter() - started, 3),
        },
        "licensing": statcan_prepared_model_licensing(year),
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
    package = _relativize_paths(package)
    return package


def _train_release_ready_model(sample):
    """Prefer frequency models, falling back to privacy-safe CART leaves."""

    model = train_tree_sample(
        sample,
        method="conditional-frequency",
        random_seed=7,
        min_support=5,
        min_samples_leaf=5,
        max_depth=None,
    )
    if not release_blocking_issues(audit_tree_model(model)):
        return model, "conditional-frequency"
    model = train_tree_sample(
        sample,
        method="cart",
        random_seed=7,
        min_support=50,
        min_samples_leaf=50,
        max_depth=None,
    )
    return model, "cart"


def _prepare_publishable_model(
    *,
    model_path: Path,
    out_path: Path,
    manifest_path: Path,
    review_note: str,
) -> None:
    model = read_tree_model(model_path)
    audit = audit_tree_model(model)
    blocking = release_blocking_issues(audit)
    if blocking:
        raise RuntimeError(f"{model_path.name} has release-blocking issues: {blocking}")
    candidate = replace(model, release_class="publishable_candidate")
    write_tree_model(out_path, candidate)
    write_tree_generation_manifest(
        manifest_path,
        {
            "schema_version": "synthpopcan-tree-release-manifest-v1",
            "command": "library workflow",
            "source_model": _repo_path(model_path),
            "output_model": _repo_path(out_path),
            "release_class": "publishable_candidate",
            "review_note": review_note,
            "thresholds": {"min_support": 50.0, "max_purity": 0.95},
            "audit": audit,
        },
    )


def _relativize_paths(value: object) -> object:
    if isinstance(value, dict):
        return {k: _relativize_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_relativize_paths(v) for v in value]
    if isinstance(value, str):
        try:
            p = Path(value)
        except ValueError:
            return value
        if not p.is_absolute():
            return value
        try:
            return _repo_path(p)
        except ValueError:
            pass
    return value


def _repo_path(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT))


@click.command()
@click.option(
    "--year",
    type=click.Choice(["2016", "2021"]),
    default="2016",
    show_default=True,
    help="Census vintage to build.",
)
@click.option(
    "--only",
    multiple=True,
    metavar="ID",
    help="Build only these package IDs (e.g. ontario-2016 toronto-cma-2016). Repeat as needed.",
)
def main(year: str, only: tuple[str, ...]) -> None:
    """Build all province- and CMA-level linked model packages."""
    census_year = int(year)
    source = SOURCES[census_year]
    targets = targets_for_year(census_year)
    if only:
        ids = set(only)
        targets = [t for t in targets if t["id"] in ids]
        missing = ids - {t["id"] for t in targets}
        if missing:
            raise click.UsageError(f"Unknown package IDs: {sorted(missing)}")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading source microdata from {source.relative_to(ROOT)} …")
    if census_year == 2016:
        sample_all = read_statcan_2016_hierarchical_seed_sample(source)
    else:
        sample_all = read_statcan_2021_hierarchical_seed_sample(source)
    print(f"  {sample_all.metadata.get('households', 0):,} total households loaded\n")

    results = []
    for target in targets:
        print(
            f"Building {target['name']} ({target['id']}, profile={target['profile']}) …"
        )
        try:
            package = build_package(
                target,
                sample_all,
                source=source,
                year=census_year,
            )
            publishable = package["privacy"]["publishable_candidate"]
            hh_summary = package["audits"]["household"]["summary"]
            p_summary = package["audits"]["person"]["summary"]
            out_path = ASSETS_DIR / target["package_file"]
            out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
            status = "✓ publishable" if publishable else "⚠ NOT publishable"
            print(
                f"  {status} — hh groups={hh_summary['groups_or_leaves']} "
                f"min_support={hh_summary['minimum_support']} | "
                f"person groups={p_summary['groups_or_leaves']} "
                f"min_support={p_summary['minimum_support']}"
            )
            print(f"  Wrote {out_path.relative_to(ROOT)}")
            results.append((target["id"], publishable, None))
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            results.append((target["id"], False, str(exc)))
        print()

    print("=== Summary ===")
    for pkg_id, publishable, err in results:
        if err:
            print(f"  ✗ {pkg_id}: {err}")
        elif publishable:
            print(f"  ✓ {pkg_id}: publishable")
        else:
            print(f"  ⚠ {pkg_id}: built but NOT publishable — audit thresholds not met")


if __name__ == "__main__":
    main()
