"""Tree generator commands for the SynthPopCan CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synthpopcan.cli_output import write_output
from synthpopcan.console import print_wrote
from synthpopcan.tree import (
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


def parse_column_list(value: str, label: str) -> tuple[str, ...]:
    columns = tuple(column.strip() for column in value.split(",") if column.strip())
    if not columns:
        raise ValueError(f"at least one {label} value is required")
    return columns


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
