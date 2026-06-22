"""Tree generator commands for the SynthPopCan CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synthpopcan.cli_output import write_output
from synthpopcan.console import print_wrote
from synthpopcan.tree import (
    audit_tree_model,
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
@click.option("--random-seed", default=None, type=int)
def generate_tree_population(
    model_path: Path,
    rows: int,
    condition_values: tuple[str, ...],
    out_path: Path,
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
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    print_wrote(out_path)


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
