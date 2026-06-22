"""Tree generator commands for the SynthPopCan CLI."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import click

from synthpopcan.cli_output import write_output
from synthpopcan.console import print_wrote
from synthpopcan.microdata import (
    SeedSample,
    export_training_rows,
    minimal_household_targets,
    minimal_person_targets,
    read_statcan_2016_hierarchical_seed_sample,
    reduced_household_targets,
    reduced_person_targets,
    resolve_tree_column_block_pair,
)
from synthpopcan.tree import (
    TreeTrainingSample,
    audit_tree_model,
    generate_linked_population,
    generate_tree_rows,
    parse_conditions,
    read_tree_model,
    read_tree_training_sample,
    train_cart_model,
    train_frequency_model,
    write_generated_rows,
    write_tree_model,
)

PATH = click.Path(path_type=Path)


@click.group()
def tree() -> None:
    """Tree-based synthetic population generator."""


@tree.command("train")
@click.argument("source", type=PATH)
@click.option(
    "--method",
    default="conditional-frequency",
    type=click.Choice(["conditional-frequency", "cart"]),
    show_default=True,
    help="Training backend.",
)
@click.option(
    "--level",
    required=True,
    type=click.Choice(["household", "person"]),
    help="Training record level.",
)
@click.option(
    "--target-columns",
    required=True,
    help="Comma-separated columns to generate.",
)
@click.option(
    "--conditioning-columns",
    required=True,
    help="Comma-separated columns used to condition generation.",
)
@click.option(
    "--geography-column",
    default=None,
    help="Optional geography column in the training sample.",
)
@click.option(
    "--weight-column",
    default=None,
    help="Optional training weight column.",
)
@click.option("--out", "out_path", required=True, type=PATH, help="Output model JSON.")
@click.option("--random-seed", default=0, type=int, show_default=True)
@click.option("--min-support", default=5, type=int, show_default=True)
@click.option("--min-samples-leaf", default=5, type=int, show_default=True)
@click.option("--max-depth", default=None, type=int)
def train_tree_generator(
    source: Path,
    method: str,
    level: str,
    target_columns: str,
    conditioning_columns: str,
    geography_column: str | None,
    weight_column: str | None,
    out_path: Path,
    random_seed: int,
    min_support: int,
    min_samples_leaf: int,
    max_depth: int | None,
) -> None:
    """Train a tree generator model from a CSV sample."""
    try:
        sample = read_tree_training_sample(
            source,
            level=level,  # type: ignore[arg-type]
            target_columns=parse_column_list(target_columns, "target columns"),
            conditioning_columns=parse_column_list(
                conditioning_columns,
                "conditioning columns",
            ),
            geography_column=geography_column,
            weight_column=weight_column,
        )
        if method == "cart":
            model = train_cart_model(
                sample,
                random_seed=random_seed,
                min_samples_leaf=min_samples_leaf,
                max_depth=max_depth,
            )
        else:
            model = train_frequency_model(
                sample,
                random_seed=random_seed,
                min_support=min_support,
            )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_tree_model(out_path, model)
    print_wrote(out_path)


@tree.command("train-linked")
@click.argument("source", type=PATH)
@click.option(
    "--input-format",
    default="statcan-2016-hierarchical",
    type=click.Choice(["statcan-2016-hierarchical"]),
    show_default=True,
    help="Input microdata layout.",
)
@click.option(
    "--suggested-blocks",
    is_flag=True,
    help="Train from named microdata suggestion-profile blocks.",
)
@click.option(
    "--household-block",
    default="household_core",
    show_default=True,
    help="Suggested household block to train.",
)
@click.option(
    "--person-block",
    default="person_demographics",
    show_default=True,
    help="Suggested person block to train.",
)
@click.option(
    "--geography-column",
    default=None,
    help="Optional source geography column to filter before training, such as PR.",
)
@click.option(
    "--geography-value",
    default=None,
    help="Optional source geography value to train, such as 24 or 11.",
)
@click.option(
    "--target-profile",
    default="full",
    type=click.Choice(["full", "reduced", "minimal"]),
    show_default=True,
    help="Target set to train from the suggested blocks.",
)
@click.option(
    "--household-model-out",
    required=True,
    type=PATH,
    help="Output household model JSON.",
)
@click.option(
    "--person-model-out",
    required=True,
    type=PATH,
    help="Output person model JSON.",
)
@click.option(
    "--manifest-out",
    required=True,
    type=PATH,
    help="Output training manifest JSON.",
)
@click.option(
    "--method",
    default="conditional-frequency",
    type=click.Choice(["conditional-frequency", "cart"]),
    show_default=True,
    help="Training backend for both models.",
)
@click.option("--random-seed", default=0, type=int, show_default=True)
@click.option("--min-support", default=5, type=int, show_default=True)
@click.option("--min-samples-leaf", default=5, type=int, show_default=True)
@click.option("--max-depth", default=None, type=int)
def train_linked_tree_generator(
    source: Path,
    input_format: str,
    suggested_blocks: bool,
    household_block: str,
    person_block: str,
    geography_column: str | None,
    geography_value: str | None,
    target_profile: str,
    household_model_out: Path,
    person_model_out: Path,
    manifest_out: Path,
    method: str,
    random_seed: int,
    min_support: int,
    min_samples_leaf: int,
    max_depth: int | None,
) -> None:
    """Train linked household and person models from mixed microdata."""
    if input_format != "statcan-2016-hierarchical":
        raise click.ClickException(f"unsupported input format: {input_format}")
    if not suggested_blocks:
        raise click.ClickException(
            "train-linked currently requires --suggested-blocks. "
            "Use 'microdata suggest-tree-columns' to inspect available blocks."
        )
    try:
        sample = read_statcan_2016_hierarchical_seed_sample(source)
        sample = filter_training_sample_by_geography(
            sample,
            geography_column=geography_column,
            geography_value=geography_value,
        )
        (
            household_target_columns,
            household_conditioning_columns,
            person_target_columns,
            person_conditioning_columns,
            column_source,
        ) = resolve_tree_column_block_pair(
            sample,
            household_block=household_block,
            person_block=person_block,
        )
        household_target_columns, person_target_columns = apply_target_profile(
            household_target_columns=household_target_columns,
            person_target_columns=person_target_columns,
            target_profile=target_profile,
        )
        household_rows, household_export = export_training_rows(
            sample,
            level="household",
            target_columns=household_target_columns,
            conditioning_columns=household_conditioning_columns,
        )
        person_rows, person_export = export_training_rows(
            sample,
            level="person",
            target_columns=person_target_columns,
            conditioning_columns=person_conditioning_columns,
        )
        household_training = tree_training_sample_from_export(
            rows=household_rows,
            export=household_export,
        )
        person_training = tree_training_sample_from_export(
            rows=person_rows,
            export=person_export,
        )
        household_model = train_tree_sample(
            household_training,
            method=method,
            random_seed=random_seed,
            min_support=min_support,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
        )
        person_model = train_tree_sample(
            person_training,
            method=method,
            random_seed=random_seed,
            min_support=min_support,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    write_tree_model(household_model_out, household_model)
    write_tree_model(person_model_out, person_model)
    write_tree_generation_manifest(
        manifest_out,
        {
            "schema_version": "synthpopcan-linked-tree-training-v1",
            "command": "tree train-linked",
            "source": {
                "path": str(source),
                "source_format": sample.source_format,
                "records": len(sample.records),
                "households": sample.metadata.get("households", 0),
            },
            "column_source": column_source,
            "target_profile": target_profile,
            "geography_filter": geography_filter_manifest(
                geography_column,
                geography_value,
            ),
            "method": method,
            "random_seed": random_seed,
            "training": {
                "household": household_export,
                "person": person_export,
            },
            "models": {
                "household": model_manifest(household_model, household_model_out),
                "person": model_manifest(person_model, person_model_out),
            },
        },
    )
    print_wrote(household_model_out)
    print_wrote(person_model_out)
    print_wrote(manifest_out)


@tree.command("generate")
@click.argument("model_path", type=PATH)
@click.option("--rows", required=True, type=int, help="Number of rows to generate.")
@click.option(
    "--condition",
    "condition_values",
    multiple=True,
    help="Condition generated rows with COLUMN=VALUE. Repeat for multiple columns.",
)
@click.option(
    "--out", "out_path", required=True, type=PATH, help="Output synthetic CSV."
)
@click.option(
    "--manifest-out",
    type=PATH,
    default=None,
    help="Optional output JSON manifest with model and seed provenance.",
)
@click.option("--random-seed", default=None, type=int)
def generate_tree_population(
    model_path: Path,
    rows: int,
    condition_values: tuple[str, ...],
    out_path: Path,
    manifest_out: Path | None,
    random_seed: int | None,
) -> None:
    """Generate synthetic rows from a tree model."""
    try:
        model = read_tree_model(model_path)
        conditions = parse_conditions(condition_values)
        generated_rows = generate_tree_rows(
            model,
            rows=rows,
            conditions=conditions,
            random_seed=random_seed,
        )
        write_generated_rows(out_path, generated_rows)
        if manifest_out:
            write_tree_generation_manifest(
                manifest_out,
                {
                    "schema_version": "synthpopcan-tree-generation-manifest-v1",
                    "command": "tree generate",
                    "outputs": {"rows": str(out_path)},
                    "rows": rows,
                    "conditions": conditions,
                    "random_seed": random_seed,
                    "effective_random_seed": effective_random_seed(
                        model,
                        random_seed,
                    ),
                    "model": model_manifest(model, model_path),
                },
            )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    print_wrote(out_path)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("generate-linked")
@click.option(
    "--household-model", required=True, type=PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=PATH, help="Person model JSON.")
@click.option(
    "--households",
    required=True,
    type=int,
    help="Number of synthetic households to generate.",
)
@click.option(
    "--condition",
    "condition_values",
    multiple=True,
    help="Condition household generation with COLUMN=VALUE. Repeat as needed.",
)
@click.option(
    "--households-out",
    required=True,
    type=PATH,
    help="Output household CSV.",
)
@click.option(
    "--persons-out",
    required=True,
    type=PATH,
    help="Output person CSV.",
)
@click.option(
    "--household-size-column",
    default="household_size",
    show_default=True,
    help="Household column used as the number of persons to generate.",
)
@click.option(
    "--manifest-out",
    type=PATH,
    default=None,
    help="Optional output JSON manifest with model and seed provenance.",
)
@click.option("--random-seed", default=None, type=int)
def generate_linked_tree_population(
    household_model: Path,
    person_model: Path,
    households: int,
    condition_values: tuple[str, ...],
    households_out: Path,
    persons_out: Path,
    household_size_column: str,
    manifest_out: Path | None,
    random_seed: int | None,
) -> None:
    """Generate linked household and person CSVs from two tree models."""
    try:
        household_model_payload = read_tree_model(household_model)
        person_model_payload = read_tree_model(person_model)
        household_conditions = parse_conditions(condition_values)
        generated_households, generated_persons = generate_linked_population(
            household_model_payload,
            person_model_payload,
            households=households,
            household_conditions=household_conditions,
            household_size_column=household_size_column,
            random_seed=random_seed,
        )
        write_generated_rows(households_out, generated_households)
        write_generated_rows(persons_out, generated_persons)
        if manifest_out:
            write_tree_generation_manifest(
                manifest_out,
                {
                    "schema_version": "synthpopcan-tree-generation-manifest-v1",
                    "command": "tree generate-linked",
                    "outputs": {
                        "households": str(households_out),
                        "persons": str(persons_out),
                    },
                    "households": households,
                    "household_conditions": household_conditions,
                    "household_size_column": household_size_column,
                    "random_seed": random_seed,
                    "effective_random_seed": effective_random_seed(
                        household_model_payload,
                        random_seed,
                    ),
                    "household_model": model_manifest(
                        household_model_payload,
                        household_model,
                    ),
                    "person_model": model_manifest(person_model_payload, person_model),
                },
            )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    print_wrote(households_out)
    print_wrote(persons_out)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("audit-model")
@click.argument("model_path", type=PATH)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def audit_tree_model_command(
    model_path: Path,
    min_support: float,
    max_purity: float,
    output_format: str,
) -> None:
    """Audit a tree model artifact for release-oriented disclosure risks."""
    try:
        model = read_tree_model(model_path)
        report = audit_tree_model(
            model,
            min_support=min_support,
            max_purity=max_purity,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_output(report, output_format, title="Tree Model Audit")


@tree.command("package-model")
@click.argument("model_path", type=PATH)
@click.option("--out", "out_path", required=True, type=PATH)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
def package_tree_model_command(
    model_path: Path,
    out_path: Path,
    min_support: float,
    max_purity: float,
) -> None:
    """Package a tree model only after a clean audit."""
    try:
        model = read_tree_model(model_path)
        audit = audit_tree_model(
            model,
            min_support=min_support,
            max_purity=max_purity,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if audit["issues"]:
        raise click.ClickException(
            "Model audit did not pass without warnings; inspect audit-model "
            "output before packaging."
        )
    package = {
        "schema_version": "synthpopcan-tree-package-v1",
        "model": model.to_dict(),
        "audit": audit,
    }
    out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    print_wrote(out_path)


@tree.command("prepare-model-release")
@click.argument("model_path", type=PATH)
@click.option("--out", "out_path", required=True, type=PATH)
@click.option(
    "--manifest-out",
    type=PATH,
    default=None,
    help="Optional release-review manifest JSON.",
)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
@click.option(
    "--review-note",
    default="",
    help="Short human review note to store in the release manifest.",
)
def prepare_tree_model_release_command(
    model_path: Path,
    out_path: Path,
    manifest_out: Path | None,
    min_support: float,
    max_purity: float,
    review_note: str,
) -> None:
    """Write a publishable-candidate copy after release audit checks."""
    try:
        model = read_tree_model(model_path)
        audit = audit_tree_model(
            model,
            min_support=min_support,
            max_purity=max_purity,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    blocking_issues = release_blocking_issues(audit)
    if blocking_issues:
        raise click.ClickException(
            "Model release audit has blocking issues; inspect audit-model output "
            "before preparing a publishable candidate."
        )

    candidate = replace(model, release_class="publishable_candidate")
    write_tree_model(out_path, candidate)
    if manifest_out:
        write_tree_generation_manifest(
            manifest_out,
            {
                "schema_version": "synthpopcan-tree-release-manifest-v1",
                "command": "tree prepare-model-release",
                "source_model": str(model_path),
                "output_model": str(out_path),
                "release_class": "publishable_candidate",
                "review_note": review_note,
                "thresholds": {
                    "min_support": min_support,
                    "max_purity": max_purity,
                },
                "audit": audit,
            },
        )
    print_wrote(out_path)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("release-readiness")
@click.option(
    "--household-model", required=True, type=PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=PATH, help="Person model JSON.")
@click.option(
    "--training-manifest",
    type=PATH,
    default=None,
    help="Optional linked tree training manifest JSON for provenance.",
)
@click.option(
    "--household-size-column",
    default="household_size",
    show_default=True,
    help="Household size linkage column expected by linked generation.",
)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def linked_tree_release_readiness_command(
    household_model: Path,
    person_model: Path,
    training_manifest: Path | None,
    household_size_column: str,
    min_support: float,
    max_purity: float,
    output_format: str,
) -> None:
    """Report whether linked models are ready for release packaging."""
    try:
        household_model_payload = read_tree_model(household_model)
        person_model_payload = read_tree_model(person_model)
        validate_linked_model_package_inputs(
            household_model_payload,
            person_model_payload,
            household_size_column=household_size_column,
        )
        household_audit = audit_tree_model(
            household_model_payload,
            min_support=min_support,
            max_purity=max_purity,
        )
        person_audit = audit_tree_model(
            person_model_payload,
            min_support=min_support,
            max_purity=max_purity,
        )
        training_provenance = read_linked_training_manifest(training_manifest)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    report = build_linked_release_readiness_report(
        household_model=household_model_payload,
        person_model=person_model_payload,
        household_model_path=household_model,
        person_model_path=person_model,
        household_audit=household_audit,
        person_audit=person_audit,
        training_provenance=training_provenance,
        household_size_column=household_size_column,
        min_support=min_support,
        max_purity=max_purity,
    )
    write_output(report, output_format, title="Linked Model Release Readiness")


@tree.command("package-linked-models")
@click.option(
    "--household-model", required=True, type=PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=PATH, help="Person model JSON.")
@click.option("--out", "out_path", required=True, type=PATH)
@click.option(
    "--household-size-column",
    default="household_size",
    show_default=True,
    help="Household size linkage column expected by linked generation.",
)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
def package_linked_tree_models_command(
    household_model: Path,
    person_model: Path,
    out_path: Path,
    household_size_column: str,
    min_support: float,
    max_purity: float,
) -> None:
    """Package linked household/person models after clean privacy audits."""
    try:
        household_model_payload = read_tree_model(household_model)
        person_model_payload = read_tree_model(person_model)
        validate_linked_model_package_inputs(
            household_model_payload,
            person_model_payload,
            household_size_column=household_size_column,
        )
        household_audit = audit_tree_model(
            household_model_payload,
            min_support=min_support,
            max_purity=max_purity,
        )
        person_audit = audit_tree_model(
            person_model_payload,
            min_support=min_support,
            max_purity=max_purity,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if household_audit["issues"] or person_audit["issues"]:
        raise click.ClickException(
            "Linked model audit did not pass without warnings; inspect "
            "audit-model output for both household and person models before "
            "packaging."
        )
    package = {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "household_size_column": household_size_column,
        "models": {
            "household": household_model_payload.to_dict(),
            "person": person_model_payload.to_dict(),
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
    out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    print_wrote(out_path)


def parse_column_list(value: str, label: str) -> tuple[str, ...]:
    columns = tuple(column.strip() for column in value.split(",") if column.strip())
    if not columns:
        raise ValueError(f"at least one {label} value is required")
    return columns


def release_blocking_issues(audit: dict[str, object]) -> list[dict[str, object]]:
    issues = audit["issues"]
    if not isinstance(issues, list):
        raise ValueError("model audit issues must be a list")
    return [
        issue
        for issue in issues
        if isinstance(issue, dict)
        and issue.get("kind") != "private_working_release_class"
    ]


def build_linked_release_readiness_report(
    *,
    household_model,
    person_model,
    household_model_path: Path,
    person_model_path: Path,
    household_audit: dict[str, object],
    person_audit: dict[str, object],
    training_provenance: dict[str, object] | None,
    household_size_column: str,
    min_support: float,
    max_purity: float,
) -> dict[str, object]:
    readiness = classify_linked_release_readiness(household_audit, person_audit)
    return {
        "schema_version": "synthpopcan-linked-tree-readiness-v1",
        "command": "tree release-readiness",
        "package_type": "linked_household_person",
        "readiness": readiness,
        "package_allowed": readiness == "likely_publishable",
        "household_size_column": household_size_column,
        "thresholds": {
            "min_support": min_support,
            "max_purity": max_purity,
        },
        "models": {
            "household": {
                **model_manifest(household_model, household_model_path),
                "bytes": household_model_path.stat().st_size,
            },
            "person": {
                **model_manifest(person_model, person_model_path),
                "bytes": person_model_path.stat().st_size,
            },
        },
        "audits": {
            "household": household_audit,
            "person": person_audit,
        },
        "training_manifest": training_provenance,
        "next_steps": linked_release_next_steps(readiness),
    }


def read_linked_training_manifest(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("training manifest must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-linked-tree-training-v1":
        raise ValueError("unsupported linked tree training manifest schema")
    return {
        "path": str(path),
        "schema_version": payload.get("schema_version"),
        "source": payload.get("source"),
        "column_source": payload.get("column_source"),
        "target_profile": payload.get("target_profile"),
        "geography_filter": payload.get("geography_filter"),
        "method": payload.get("method"),
        "random_seed": payload.get("random_seed"),
        "training": payload.get("training"),
    }


def classify_linked_release_readiness(
    household_audit: dict[str, object],
    person_audit: dict[str, object],
) -> str:
    blocking_issues = [
        *release_blocking_issues(household_audit),
        *release_blocking_issues(person_audit),
    ]
    if blocking_issues:
        return "needs_changes"
    if (
        household_audit["publishable_candidate"]
        and person_audit["publishable_candidate"]
    ):
        return "likely_publishable"
    return "private_working"


def linked_release_next_steps(readiness: str) -> list[str]:
    if readiness == "likely_publishable":
        return ["Package the reviewed models with `tree package-linked-models`."]
    if readiness == "needs_changes":
        return [
            "Review audit issues, then prune, coarsen, aggregate, or retrain before "
            "preparing publishable-candidate models."
        ]
    return [
        (
            "Prepare reviewed publishable-candidate copies with "
            "`tree prepare-model-release`, then rerun this readiness report."
        )
    ]


def filter_training_sample_by_geography(
    sample: SeedSample,
    *,
    geography_column: str | None,
    geography_value: str | None,
) -> SeedSample:
    if geography_column is None and geography_value is None:
        return sample
    if not geography_column or geography_value is None:
        raise ValueError(
            "geography-column and geography-value must be provided together"
        )
    if geography_column not in sample.columns:
        raise ValueError(f"missing required columns: {geography_column}")
    records = tuple(
        record
        for record in sample.records
        if record.get(geography_column) == geography_value
    )
    if not records:
        raise ValueError(f"no records matched {geography_column}={geography_value}")
    household_ids = {record["HH_ID"] for record in records if record.get("HH_ID")}
    return replace(
        sample,
        records=records,
        metadata={
            **sample.metadata,
            "households": len(household_ids),
            "people": len(records),
            "geography_filter": {
                "column": geography_column,
                "value": geography_value,
            },
        },
    )


def apply_target_profile(
    *,
    household_target_columns: tuple[str, ...],
    person_target_columns: tuple[str, ...],
    target_profile: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if target_profile == "full":
        return household_target_columns, person_target_columns
    if target_profile == "reduced":
        return (
            tuple(reduced_household_targets(household_target_columns)),
            tuple(reduced_person_targets(person_target_columns)),
        )
    return (
        tuple(minimal_household_targets(household_target_columns)),
        tuple(minimal_person_targets(person_target_columns)),
    )


def geography_filter_manifest(
    geography_column: str | None,
    geography_value: str | None,
) -> dict[str, str] | None:
    if geography_column is None and geography_value is None:
        return None
    if not geography_column or geography_value is None:
        raise ValueError(
            "geography-column and geography-value must be provided together"
        )
    return {"column": geography_column, "value": geography_value}


def validate_linked_model_package_inputs(
    household_model,
    person_model,
    *,
    household_size_column: str,
) -> None:
    if household_model.spec.level != "household":
        raise ValueError("household model must have level 'household'")
    if person_model.spec.level != "person":
        raise ValueError("person model must have level 'person'")
    if household_size_column not in generated_model_columns(household_model):
        raise ValueError(
            f"household model must generate or condition on {household_size_column!r}"
        )
    if household_size_column not in person_model.spec.conditioning_columns:
        raise ValueError(f"person model must condition on {household_size_column!r}")


def generated_model_columns(model) -> set[str]:
    return set(model.spec.conditioning_columns) | set(model.spec.target_columns)


def tree_training_sample_from_export(
    *,
    rows: list[dict[str, str]],
    export: dict[str, object],
) -> TreeTrainingSample:
    return TreeTrainingSample(
        level=export["level"],  # type: ignore[arg-type]
        source_format=str(export["source_format"]),
        records=tuple(rows),
        columns=tuple(export["columns"]),  # type: ignore[arg-type]
        target_columns=tuple(export["target_columns"]),  # type: ignore[arg-type]
        conditioning_columns=tuple(export["conditioning_columns"]),  # type: ignore[arg-type]
        weight_column=str(export["weight_column"]),
    )


def train_tree_sample(
    sample: TreeTrainingSample,
    *,
    method: str,
    random_seed: int,
    min_support: int,
    min_samples_leaf: int,
    max_depth: int | None,
):
    if method == "cart":
        return train_cart_model(
            sample,
            random_seed=random_seed,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
        )
    return train_frequency_model(
        sample,
        random_seed=random_seed,
        min_support=min_support,
    )


def model_manifest(model, path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "model_type": model.model_type,
        "release_class": model.release_class,
        "level": model.spec.level,
        "records_trained": model.records_trained,
        "source_format": model.source_format,
        "target_columns": list(model.spec.target_columns),
        "conditioning_columns": list(model.spec.conditioning_columns),
    }


def effective_random_seed(model, random_seed: int | None) -> int:
    return model.spec.random_seed if random_seed is None else random_seed


def write_tree_generation_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
