"""Tree generator commands for the SynthPopCan CLI."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from synthpopcan.cli_output import format_file_access_error, write_output
from synthpopcan.console import print_table, print_wrote
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
from synthpopcan.models import model_catalogue, model_payload
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    TreeTrainingSample,
    audit_tree_model,
    generate_linked_population_to_csv,
    generate_tree_rows,
    parse_conditions,
    read_tree_model,
    read_tree_training_sample,
    train_cart_model,
    train_frequency_model,
    write_generated_rows,
    write_tree_model,
)

_PATH = click.Path(path_type=Path)


@click.group()
def tree() -> None:
    """Tree-based synthetic population generator."""


@tree.command("train")
@click.argument("source", type=_PATH)
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
@click.option("--out", "out_path", required=True, type=_PATH, help="Output model JSON.")
@click.option(
    "--random-seed",
    default=0,
    type=int,
    show_default=True,
    help="Random seed used by the training backend.",
)
@click.option(
    "--min-support",
    default=5,
    type=int,
    show_default=True,
    help="Minimum records required for conditional-frequency groups.",
)
@click.option(
    "--min-samples-leaf",
    default=5,
    type=int,
    show_default=True,
    help="Minimum samples allowed in each CART leaf.",
)
@click.option("--max-depth", default=None, type=int, help="Optional CART max depth.")
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
        write_tree_model(out_path, model)
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(exc, read_paths=(source,), write_paths=(out_path,))
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    print_wrote(out_path)


@tree.command("train-linked")
@click.argument("source", type=_PATH)
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
    help="Suggested household block to train. Use 'all' to combine household blocks.",
)
@click.option(
    "--person-block",
    default="person_demographics",
    show_default=True,
    help="Suggested person block to train. Use 'all' to combine person blocks.",
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
    type=_PATH,
    help="Output household model JSON.",
)
@click.option(
    "--person-model-out",
    required=True,
    type=_PATH,
    help="Output person model JSON.",
)
@click.option(
    "--manifest-out",
    required=True,
    type=_PATH,
    help="Output training manifest JSON.",
)
@click.option(
    "--method",
    default="conditional-frequency",
    type=click.Choice(["conditional-frequency", "cart"]),
    show_default=True,
    help="Training backend for both models.",
)
@click.option(
    "--random-seed",
    default=0,
    type=int,
    show_default=True,
    help="Random seed used by both training backends.",
)
@click.option(
    "--min-support",
    default=5,
    type=int,
    show_default=True,
    help="Minimum records required for conditional-frequency groups.",
)
@click.option(
    "--min-samples-leaf",
    default=5,
    type=int,
    show_default=True,
    help="Minimum samples allowed in each CART leaf.",
)
@click.option("--max-depth", default=None, type=int, help="Optional CART max depth.")
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
    if input_format != "statcan-2016-hierarchical":  # pragma: no cover
        raise click.ClickException(f"unsupported input format: {input_format}")
    if not suggested_blocks:
        raise click.ClickException(
            "train-linked currently requires --suggested-blocks. "
            "Use 'microdata suggest-tree-columns' to inspect available blocks."
        )
    try:
        progress_console = Console(stderr=True)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed:,}/{task.total:,} steps"),
            TimeElapsedColumn(),
            console=progress_console,
        ) as progress:
            task_id = progress.add_task("Reading source microdata", total=7)

            sample = read_statcan_2016_hierarchical_seed_sample(source)
            progress.advance(task_id)
            progress.update(task_id, description="Filtering and choosing columns")
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
            progress.advance(task_id)
            progress.update(task_id, description="Deriving household training rows")
            household_rows, household_export = export_training_rows(
                sample,
                level="household",
                target_columns=household_target_columns,
                conditioning_columns=household_conditioning_columns,
            )
            household_training = tree_training_sample_from_export(
                rows=household_rows,
                export=household_export,
            )
            progress.advance(task_id)
            progress.update(task_id, description="Deriving person training rows")
            person_rows, person_export = export_training_rows(
                sample,
                level="person",
                target_columns=person_target_columns,
                conditioning_columns=person_conditioning_columns,
            )
            person_training = tree_training_sample_from_export(
                rows=person_rows,
                export=person_export,
            )
            progress.advance(task_id)
            progress.update(task_id, description="Training household model")
            household_model = train_tree_sample(
                household_training,
                method=method,
                random_seed=random_seed,
                min_support=min_support,
                min_samples_leaf=min_samples_leaf,
                max_depth=max_depth,
            )
            progress.advance(task_id)
            progress.update(task_id, description="Training person model")
            person_model = train_tree_sample(
                person_training,
                method=method,
                random_seed=random_seed,
                min_support=min_support,
                min_samples_leaf=min_samples_leaf,
                max_depth=max_depth,
            )
            progress.advance(task_id)
            progress.update(task_id, description="Writing models and manifest")
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
                        "household": model_manifest(
                            household_model,
                            household_model_out,
                        ),
                        "person": model_manifest(person_model, person_model_out),
                    },
                },
            )
            progress.advance(task_id)
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(
                exc,
                read_paths=(source,),
                write_paths=(household_model_out, person_model_out, manifest_out),
            )
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    print_wrote(household_model_out)
    print_wrote(person_model_out)
    print_wrote(manifest_out)


@tree.command("generate")
@click.argument("model_path", type=_PATH)
@click.option("--rows", required=True, type=int, help="Number of rows to generate.")
@click.option(
    "--condition",
    "condition_values",
    multiple=True,
    help="Condition generated rows with COLUMN=VALUE. Repeat for multiple columns.",
)
@click.option(
    "--out", "out_path", required=True, type=_PATH, help="Output synthetic CSV."
)
@click.option(
    "--manifest-out",
    type=_PATH,
    default=None,
    help="Optional output JSON manifest with model and seed provenance.",
)
@click.option("--random-seed", default=None, type=int, help="Optional generation seed.")
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
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(
                exc,
                read_paths=(model_path,),
                write_paths=(out_path, manifest_out),
            )
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    print_wrote(out_path)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("generate-linked")
@click.option(
    "--household-model", required=True, type=_PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=_PATH, help="Person model JSON.")
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
    type=_PATH,
    help="Output household CSV.",
)
@click.option(
    "--persons-out",
    required=True,
    type=_PATH,
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
    type=_PATH,
    default=None,
    help="Optional output JSON manifest with model and seed provenance.",
)
@click.option("--random-seed", default=None, type=int, help="Optional generation seed.")
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
        generated_household_count, generated_person_count = (
            generate_linked_population_to_csv(
                household_model_payload,
                person_model_payload,
                households=households,
                households_path=households_out,
                persons_path=persons_out,
                household_conditions=household_conditions,
                household_size_column=household_size_column,
                random_seed=random_seed,
            )
        )
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
                    "generated_households": generated_household_count,
                    "generated_persons": generated_person_count,
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
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(
                exc,
                read_paths=(household_model, person_model),
                write_paths=(households_out, persons_out, manifest_out),
            )
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    print_wrote(households_out)
    print_wrote(persons_out)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("list-packages")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def list_tree_model_packages(output_format: str) -> None:
    """List packaged linked models."""
    catalogue = {"models": model_catalogue()}
    if output_format == "json":
        write_output(catalogue, "json")
        return
    table = Table(title="Model Packages")
    table.add_column("Package ID")
    table.add_column("Summary")
    for model in catalogue["models"]:
        default_generation = object_or_empty(model.get("default_generation"))
        table.add_row(
            str(model.get("id", "")),
            format_package_catalogue_summary(model, default_generation),
        )
    print_table(table)


@tree.command("generate-from-package")
@click.argument("package_path", metavar="PACKAGE")
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
    type=_PATH,
    help="Output household CSV.",
)
@click.option(
    "--persons-out",
    required=True,
    type=_PATH,
    help="Output person CSV.",
)
@click.option(
    "--household-size-column",
    default=None,
    help="Override package household-size linkage column.",
)
@click.option(
    "--manifest-out",
    type=_PATH,
    default=None,
    help="Optional output JSON manifest with package and seed provenance.",
)
@click.option("--random-seed", default=None, type=int, help="Optional generation seed.")
def generate_linked_tree_population_from_package(
    package_path: str,
    households: int,
    condition_values: tuple[str, ...],
    households_out: Path,
    persons_out: Path,
    household_size_column: str | None,
    manifest_out: Path | None,
    random_seed: int | None,
) -> None:
    """Generate linked household/person CSVs from a package path or bundled ID."""
    package_source_path: Path | None = None
    try:
        package, package_label, package_source_path = read_package_path_or_id(
            package_path
        )
        validate_package_allows_generation(package)
        package_inspection = build_linked_package_inspection(
            package,
            package_source_path,
        )
        package_inspection["package_path"] = package_label
        household_model_payload, person_model_payload = package_models(package)
        effective_household_size_column = household_size_column or str(
            package.get("household_size_column", "household_size")
        )
        household_conditions = parse_conditions(condition_values)
        progress_console = Console(stderr=True)
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed:,}/{task.total:,} households"),
            TextColumn("• {task.fields[persons]:,} people"),
            TimeElapsedColumn(),
            console=progress_console,
        ) as progress:
            task_id = progress.add_task(
                "Generating linked population",
                total=households,
                persons=0,
            )

            def update_progress(
                generated_households: int,
                generated_persons: int,
            ) -> None:
                progress.update(
                    task_id,
                    completed=generated_households,
                    persons=generated_persons,
                )

            generated_household_count, generated_person_count = (
                generate_linked_population_to_csv(
                    household_model_payload,
                    person_model_payload,
                    households=households,
                    households_path=households_out,
                    persons_path=persons_out,
                    household_conditions=household_conditions,
                    household_size_column=effective_household_size_column,
                    random_seed=random_seed,
                    progress_callback=update_progress,
                )
            )
        if manifest_out:
            write_tree_generation_manifest(
                manifest_out,
                {
                    "schema_version": "synthpopcan-tree-generation-manifest-v1",
                    "command": "tree generate-from-package",
                    "outputs": {
                        "households": str(households_out),
                        "persons": str(persons_out),
                    },
                    "households": households,
                    "generated_households": generated_household_count,
                    "generated_persons": generated_person_count,
                    "household_conditions": household_conditions,
                    "household_size_column": effective_household_size_column,
                    "random_seed": random_seed,
                    "effective_random_seed": effective_random_seed(
                        household_model_payload,
                        random_seed,
                    ),
                    "package": package_inspection,
                },
            )
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(
                exc,
                read_paths=(package_source_path, Path(package_path)),
                write_paths=(households_out, persons_out, manifest_out),
            )
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    print_wrote(households_out)
    print_wrote(persons_out)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("audit-model")
@click.argument("model_path", type=_PATH)
@click.option(
    "--min-support",
    default=50.0,
    type=float,
    show_default=True,
    help="Minimum acceptable support for each group or leaf.",
)
@click.option(
    "--max-purity",
    default=0.95,
    type=float,
    show_default=True,
    help="Maximum acceptable dominant-outcome purity.",
)
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
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(model_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
    write_output(report, output_format, title="Tree Model Audit")


@tree.command("package-model")
@click.argument("model_path", type=_PATH)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output flat tree model package JSON.",
)
@click.option(
    "--min-support",
    default=50.0,
    type=float,
    show_default=True,
    help="Minimum acceptable support for each group or leaf.",
)
@click.option(
    "--max-purity",
    default=0.95,
    type=float,
    show_default=True,
    help="Maximum acceptable dominant-outcome purity.",
)
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
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(model_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
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
    try:
        out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(out_path, "write", exc)
        ) from exc
    print_wrote(out_path)


@tree.command("prepare-model-release")
@click.argument("model_path", type=_PATH)
@click.option("--out", "out_path", required=True, type=_PATH)
@click.option(
    "--manifest-out",
    type=_PATH,
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
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(model_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc

    blocking_issues = release_blocking_issues(audit)
    if blocking_issues:
        raise click.ClickException(
            "Model release audit has blocking issues; inspect audit-model output "
            "before preparing a publishable candidate."
        )

    candidate = replace(model, release_class="publishable_candidate")
    try:
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
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or out_path, "write", exc)
        ) from exc
    print_wrote(out_path)
    if manifest_out:
        print_wrote(manifest_out)


@tree.command("release-readiness")
@click.option(
    "--household-model", required=True, type=_PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=_PATH, help="Person model JSON.")
@click.option(
    "--training-manifest",
    type=_PATH,
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
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or household_model, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc

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
    "--household-model", required=True, type=_PATH, help="Household model JSON."
)
@click.option("--person-model", required=True, type=_PATH, help="Person model JSON.")
@click.option(
    "--training-manifest",
    type=_PATH,
    default=None,
    help="Linked tree training manifest JSON for package provenance.",
)
@click.option(
    "--source-provenance",
    type=_PATH,
    default=None,
    help="Reviewed source provenance JSON for citation and access metadata.",
)
@click.option(
    "--household-release-manifest",
    type=_PATH,
    default=None,
    help="Optional household model release manifest from prepare-model-release.",
)
@click.option(
    "--person-release-manifest",
    type=_PATH,
    default=None,
    help="Optional person model release manifest from prepare-model-release.",
)
@click.option(
    "--review-note",
    default="",
    help="Short human review note to store in the linked package.",
)
@click.option("--out", "out_path", required=True, type=_PATH)
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
    training_manifest: Path | None,
    source_provenance: Path | None,
    household_release_manifest: Path | None,
    person_release_manifest: Path | None,
    review_note: str,
    out_path: Path,
    household_size_column: str,
    min_support: float,
    max_purity: float,
) -> None:
    """Package linked household/person models after clean privacy audits."""
    if training_manifest is None:
        raise click.ClickException(
            "Packaging linked models requires --training-manifest. Use the "
            "manifest written by `tree train-linked --manifest-out` so the "
            "package carries source, geography, target-profile, and model "
            "provenance."
        )
    if source_provenance is None:
        raise click.ClickException(
            "Packaging linked models requires --source-provenance with reviewed "
            "citation, access, and redistribution metadata for the source data."
        )
    if not review_note.strip():
        raise click.ClickException(
            "Packaging linked models requires --review-note with a short human "
            "review note, for example who reviewed the package and why it is "
            "being prepared for distribution."
        )
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
        release_manifests = {
            "household": read_model_release_manifest(household_release_manifest),
            "person": read_model_release_manifest(person_release_manifest),
        }
        source_provenance_payload = read_source_provenance(source_provenance)
        validate_linked_training_manifest_model_paths(
            training_provenance,
            household_model_path=household_model,
            person_model_path=person_model,
            release_manifests=release_manifests,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or household_model, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc
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
        "review_note": review_note.strip(),
        "thresholds": {
            "min_support": min_support,
            "max_purity": max_purity,
        },
        "training_manifest": training_provenance,
        "source_provenance": source_provenance_payload,
        "release_manifests": release_manifests,
        "model_summaries": {
            "household": {
                **model_manifest(household_model_payload, household_model),
                "bytes": household_model.stat().st_size,
            },
            "person": {
                **model_manifest(person_model_payload, person_model),
                "bytes": person_model.stat().st_size,
            },
        },
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
    try:
        out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(out_path, "write", exc)
        ) from exc
    print_wrote(out_path)


@tree.command("inspect-package")
@click.argument("package_path", metavar="PACKAGE")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_linked_tree_package_command(
    package_path: str,
    output_format: str,
) -> None:
    """Inspect a linked household/person model package path or bundled ID."""
    package_source_path: Path | None = None
    try:
        package, package_label, package_source_path = read_package_path_or_id(
            package_path
        )
        report = build_linked_package_inspection(package, package_source_path)
        report["package_path"] = package_label
    except OSError as exc:
        raise click.ClickException(
            _format_tree_file_error(
                exc,
                read_paths=(package_source_path, Path(package_path)),
            )
        ) from exc
    except ValueError as exc:
        raise click.ClickException(_format_tree_value_error(exc)) from exc

    if output_format == "json":
        write_output(report, "json")
    else:
        print_linked_package_inspection_table(report)


def parse_column_list(value: str, label: str) -> tuple[str, ...]:
    columns = tuple(column.strip() for column in value.split(",") if column.strip())
    if not columns:
        raise ValueError(f"at least one {label} value is required")
    return columns


def _format_tree_file_error(
    exc: OSError,
    *,
    read_paths: tuple[Path | None, ...] = (),
    write_paths: tuple[Path | None, ...] = (),
) -> str:
    """Format tree-command file errors with read/write-specific wording."""

    failing_path = Path(exc.filename) if exc.filename else None
    if failing_path is not None:
        for path in read_paths:
            if path is not None and same_model_path(failing_path, path):
                return format_file_access_error(path, "read", exc)
        for path in write_paths:
            if path is not None and same_model_path(failing_path, path):
                return format_file_access_error(path, "write", exc)
        return format_file_access_error(failing_path, "access", exc)
    if read_paths:
        first_read_path = next((path for path in read_paths if path is not None), None)
        if first_read_path is not None:
            return format_file_access_error(first_read_path, "read", exc)
    if write_paths:
        first_write_path = next(
            (path for path in write_paths if path is not None), None
        )
        if first_write_path is not None:
            return format_file_access_error(first_write_path, "write", exc)
    return format_file_access_error("file", "access", exc)


def _format_tree_value_error(exc: ValueError) -> str:
    """Convert tree/model validation errors into CLI-facing wording."""

    message = str(exc)
    schema_messages = {
        "unsupported linked model package schema": (
            "This file is not a supported linked household/person model package. "
            "Choose a package created by `tree package-linked-models` or use the "
            "web app's premade model chooser."
        ),
        "unsupported linked tree training manifest schema": (
            "This file is not a supported linked training manifest. Use the "
            "manifest written by `tree train-linked --manifest-out`."
        ),
        "unsupported tree release manifest schema": (
            "This file is not a supported tree release manifest. Use the manifest "
            "written by `tree prepare-model-release --manifest-out`."
        ),
        "unsupported source provenance schema": (
            "This file is not a supported source provenance file. Use a reviewed "
            "source provenance JSON with schema_version "
            "'synthpopcan-source-provenance-v1'."
        ),
        "unsupported tree model type in linked package": (
            "The linked package contains a model type SynthPopCan cannot generate "
            "from yet."
        ),
    }
    if message in schema_messages:
        return schema_messages[message]
    if message.endswith("must be a JSON object"):
        return message.replace(
            "must be a JSON object",
            "must contain a JSON object, not a list or plain value",
        )
    return message


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
    provenance = {
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
    if "models" in payload:
        provenance["models"] = payload.get("models")
    return provenance


def validate_linked_training_manifest_model_paths(
    training_provenance: dict[str, object] | None,
    *,
    household_model_path: Path,
    person_model_path: Path,
    release_manifests: dict[str, dict[str, object] | None] | None = None,
) -> None:
    if training_provenance is None:
        raise ValueError("linked model package requires a training manifest")

    models = training_provenance.get("models")
    if not isinstance(models, dict):
        raise ValueError(
            "training manifest must include models.household.path and "
            "models.person.path; rerun `tree train-linked --manifest-out` or "
            "use a reviewed manifest with model provenance"
        )
    expected = {
        "household": household_model_path,
        "person": person_model_path,
    }
    for level, actual_path in expected.items():
        entry = models.get(level)
        if not isinstance(entry, dict) or not entry.get("path"):
            raise ValueError(f"training manifest must include models.{level}.path")
        recorded_path = Path(str(entry["path"]))
        if same_model_path(recorded_path, actual_path):
            continue
        release_manifest = (release_manifests or {}).get(level)
        if release_manifest_matches_model_paths(
            release_manifest,
            source_model_path=recorded_path,
            output_model_path=actual_path,
        ):
            continue
        if release_manifest is None:
            raise ValueError(
                f"training manifest {level} model path does not match --{level}-model; "
                f"pass --{level}-release-manifest from `tree prepare-model-release` "
                "when packaging reviewed release copies"
            )
        else:
            raise ValueError(
                f"{level} release manifest does not connect the training manifest "
                f"model path to --{level}-model"
            )


def read_model_release_manifest(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("model release manifest must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-tree-release-manifest-v1":
        raise ValueError("unsupported tree release manifest schema")
    return {
        "path": str(path),
        "schema_version": payload.get("schema_version"),
        "command": payload.get("command"),
        "source_model": payload.get("source_model"),
        "output_model": payload.get("output_model"),
        "release_class": payload.get("release_class"),
        "review_note": payload.get("review_note"),
        "thresholds": payload.get("thresholds"),
        "audit": payload.get("audit"),
    }


def read_source_provenance(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("source provenance must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-source-provenance-v1":
        raise ValueError("unsupported source provenance schema")
    required_fields = (
        "title",
        "provider",
        "access_class",
        "citation",
        "redistribution_note",
    )
    missing = [
        field
        for field in required_fields
        if not isinstance(payload.get(field), str) or not payload[field].strip()
    ]
    if missing:
        raise ValueError(
            "source provenance missing required fields: " + ", ".join(missing)
        )
    provenance = {
        "path": str(path),
        "schema_version": payload["schema_version"],
        "title": payload["title"].strip(),
        "provider": payload["provider"].strip(),
        "access_class": payload["access_class"].strip(),
        "citation": payload["citation"].strip(),
        "redistribution_note": payload["redistribution_note"].strip(),
    }
    for optional_field in ("url", "license", "local_path", "checksum"):
        value = payload.get(optional_field)
        if isinstance(value, str) and value.strip():
            provenance[optional_field] = value.strip()
    return provenance


def read_linked_model_package(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("linked model package must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-linked-tree-package-v1":
        raise ValueError("unsupported linked model package schema")
    return payload


def read_package_path_or_id(
    package_path_or_id: str,
) -> tuple[dict[str, object], str, Path | None]:
    """Read a linked package from a local path or packaged model ID."""

    package_path = Path(package_path_or_id)
    if package_path.exists():
        return read_linked_model_package(package_path), str(package_path), package_path
    if package_path.is_absolute() or len(package_path.parts) > 1 or package_path.suffix:
        return read_linked_model_package(package_path), str(package_path), package_path
    try:
        package = model_payload(package_path_or_id)
    except KeyError as exc:
        raise ValueError(
            f"linked package not found: {package_path_or_id}. Use a package JSON path "
            "or a packaged model ID from `synthpopcan tree list-packages`."
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return package, package_path_or_id, None


def validate_package_allows_generation(package: dict[str, object]) -> None:
    privacy = object_or_empty(package.get("privacy"))
    if privacy.get("publishable_candidate") is not True:
        raise ValueError(
            "linked package is not marked as a publishable candidate; inspect the "
            "package before generating from it"
        )


def package_models(package: dict[str, object]):
    models = object_or_empty(package.get("models"))
    household_model = object_or_empty(models.get("household"))
    person_model = object_or_empty(models.get("person"))
    if not household_model or not person_model:
        raise ValueError("linked package must include household and person models")
    return tree_model_from_payload(household_model), tree_model_from_payload(
        person_model
    )


def tree_model_from_payload(payload: dict[str, object]):
    model_type = payload.get("model_type")
    if model_type == "conditional-frequency":
        return FrequencyTreeModel.from_dict(payload)
    if model_type == "cart":
        return CartTreeModel.from_dict(payload)
    raise ValueError("unsupported tree model type in linked package")


def build_linked_package_inspection(
    package: dict[str, object],
    package_path: Path,
) -> dict[str, object]:
    training_manifest = object_or_empty(package.get("training_manifest"))
    source_provenance = object_or_empty(
        package.get("source_provenance") or package.get("provenance")
    )
    privacy = object_or_empty(package.get("privacy"))
    thresholds = object_or_empty(package.get("thresholds"))
    model_summaries = object_or_empty(package.get("model_summaries"))
    embedded_models = object_or_empty(package.get("models"))
    audits = object_or_empty(package.get("audits"))
    release_manifests = object_or_empty(package.get("release_manifests"))
    review = object_or_empty(package.get("review"))

    return {
        "schema_version": "synthpopcan-linked-tree-package-inspection-v1",
        "package_path": str(package_path),
        "name": package.get("name"),
        "package_type": package.get("package_type"),
        "package_schema_version": package.get("schema_version"),
        "household_size_column": package.get("household_size_column"),
        "review_note": package.get("review_note") or review.get("note") or "",
        "source": {
            "title": source_provenance.get("title")
            or source_provenance.get("training_data")
            or source_provenance.get("source"),
            "provider": source_provenance.get("provider"),
            "access_class": source_provenance.get("access_class")
            or ("demo" if privacy.get("safe_demo") else None),
            "citation": source_provenance.get("citation"),
            "redistribution_note": source_provenance.get("redistribution_note"),
            "url": source_provenance.get("url"),
        },
        "training": {
            "target_profile": training_manifest.get("target_profile"),
            "geography_filter": training_manifest.get("geography_filter"),
            "method": training_manifest.get("method"),
            "random_seed": training_manifest.get("random_seed"),
            "source": training_manifest.get("source"),
        },
        "privacy": {
            "publishable_candidate": privacy.get("publishable_candidate"),
            "contains_raw_rows": privacy.get("contains_raw_rows"),
            "contains_source_identifiers": privacy.get("contains_source_identifiers"),
        },
        "thresholds": thresholds,
        "models": summarize_package_models(model_summaries or embedded_models),
        "audits": summarize_package_audits(audits),
        "release_manifests": summarize_release_manifests(release_manifests),
    }


def object_or_empty(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def summarize_package_models(
    model_summaries: dict[str, object],
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for level in ("household", "person"):
        summary = object_or_empty(model_summaries.get(level))
        spec = object_or_empty(summary.get("spec"))
        summaries[level] = {
            "level": summary.get("level") or spec.get("level"),
            "model_type": summary.get("model_type"),
            "release_class": summary.get("release_class"),
            "records_trained": summary.get("records_trained"),
            "bytes": summary.get("bytes"),
            "target_columns": summary.get("target_columns")
            or spec.get("target_columns"),
            "conditioning_columns": summary.get("conditioning_columns")
            or spec.get("conditioning_columns"),
        }
    return summaries


def summarize_package_audits(
    audits: dict[str, object],
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for level in ("household", "person"):
        audit = object_or_empty(audits.get(level))
        summary = object_or_empty(audit.get("summary"))
        issues = audit.get("issues")
        summaries[level] = {
            "passed": audit.get("passed"),
            "publishable_candidate": audit.get("publishable_candidate"),
            "release_class": audit.get("release_class"),
            "issue_count": len(issues) if isinstance(issues, list) else None,
            "groups_or_leaves": summary.get("groups_or_leaves"),
            "minimum_support": summary.get("minimum_support"),
            "below_min_support": summary.get("below_min_support"),
            "above_max_purity": summary.get("above_max_purity"),
        }
    return summaries


def summarize_release_manifests(
    release_manifests: dict[str, object],
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for level in ("household", "person"):
        manifest = object_or_empty(release_manifests.get(level))
        summaries[level] = {
            "path": manifest.get("path"),
            "source_model": manifest.get("source_model"),
            "output_model": manifest.get("output_model"),
            "release_class": manifest.get("release_class"),
            "review_note": manifest.get("review_note"),
        }
    return summaries


def print_linked_package_inspection_table(report: dict[str, object]) -> None:
    table = Table(title="Linked Model Package")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    source = object_or_empty(report.get("source"))
    training = object_or_empty(report.get("training"))
    privacy = object_or_empty(report.get("privacy"))
    models = object_or_empty(report.get("models"))
    audits = object_or_empty(report.get("audits"))

    add_optional_table_row(table, "Name", report.get("name"))
    table.add_row("Package", str(report.get("package_path", "")))
    add_optional_table_row(table, "Type", report.get("package_type"))
    add_optional_table_row(table, "Source", format_source_label(source))
    add_optional_table_row(table, "Access", source.get("access_class"))
    add_optional_table_row(table, "Redistribution", source.get("redistribution_note"))
    add_optional_table_row(
        table, "Geography", format_geography_filter(training.get("geography_filter"))
    )
    add_optional_table_row(table, "Target profile", training.get("target_profile"))
    add_optional_table_row(table, "Method", training.get("method"))
    table.add_row("Privacy", format_privacy_summary(privacy))
    table.add_row("Household model", format_model_summary(models.get("household")))
    table.add_row("Person model", format_model_summary(models.get("person")))
    add_optional_table_row(
        table, "Household audit", format_audit_summary(audits.get("household"))
    )
    add_optional_table_row(
        table, "Person audit", format_audit_summary(audits.get("person"))
    )
    add_optional_table_row(table, "Review note", report.get("review_note"))
    print_table(table)


def add_optional_table_row(table: Table, label: str, value: object) -> None:
    text = format_optional(value)
    if text:
        table.add_row(label, text)


def format_optional(value: object) -> str:
    return "" if value is None else str(value)


def format_source_label(source: dict[str, object]) -> str:
    title = source.get("title") or ""
    provider = source.get("provider") or ""
    return f"{provider}: {title}" if provider else str(title)


def format_geography_filter(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    column = value.get("column")
    filter_value = value.get("value")
    if column and filter_value:
        return f"{column}={filter_value}"
    return ""


def format_privacy_summary(privacy: dict[str, object]) -> str:
    status = (
        "Publishable candidate"
        if privacy.get("publishable_candidate")
        else "Not marked publishable"
    )
    raw_rows = _format_boolean_phrase(
        privacy.get("contains_raw_rows"),
        true_text="Contains raw rows",
        false_text="No raw rows",
    )
    source_ids = _format_boolean_phrase(
        privacy.get("contains_source_identifiers"),
        true_text="Contains source identifiers",
        false_text="No source identifiers",
    )
    return "; ".join(part for part in (status, raw_rows, source_ids) if part)


def format_model_summary(value: object) -> str:
    model = object_or_empty(value)
    if not model:
        return ""
    target_columns = model.get("target_columns")
    targets = len(target_columns) if isinstance(target_columns, list) else 0
    parts = [
        _format_level(model.get("level")),
        _format_model_type(model.get("model_type")),
        _format_release_class(model.get("release_class")),
    ]
    records = format_int_or_blank(model.get("records_trained"))
    if records:
        parts.append(f"{records} records")
    size = format_bytes_or_blank(model.get("bytes"))
    if size:
        parts.append(size)
    parts.append(f"{targets} targets")
    return "; ".join(part for part in parts if part)


def format_audit_summary(value: object) -> str:
    audit = object_or_empty(value)
    if not audit or not any(value is not None for value in audit.values()):
        return ""
    return (
        f"{_format_audit_passed(audit.get('passed'))}; "
        f"issues={format_int_or_blank(audit.get('issue_count'))}; "
        f"minimum support={format_number_or_blank(audit.get('minimum_support'))}; "
        f"high purity={format_int_or_blank(audit.get('above_max_purity'))}"
    )


def format_default_generation(value: dict[str, object]) -> str:
    parts: list[str] = []
    households = format_int_or_blank(value.get("households"))
    if households:
        parts.append(f"{households} households")
    conditions = value.get("conditions")
    if isinstance(conditions, str) and conditions:
        parts.append(conditions)
    return "; ".join(parts)


def format_package_catalogue_summary(
    model: dict[str, object],
    default_generation: dict[str, object],
) -> str:
    parts = [
        str(model.get("name", "")),
        f"Geography: {model.get('geography', '')}",
        f"Status: {model.get('release_status', '')}",
    ]
    if model.get("distribution") == "download" and not model.get("installed"):
        parts.append("Availability: download with `synthpopcan models fetch`")
    default_text = format_default_generation(default_generation)
    if default_text:
        parts.append(f"Default: {default_text}")
    return "\n".join(part for part in parts if part)


def _format_boolean_phrase(
    value: object,
    *,
    true_text: str,
    false_text: str,
) -> str:
    if value is True:
        return true_text
    if value is False:
        return false_text
    return ""


def _format_level(value: object) -> str:
    if value == "household":
        return "Household"
    if value == "person":
        return "Person"
    return format_optional(value)


def _format_model_type(value: object) -> str:
    if value == "conditional-frequency":
        return "Conditional frequency"
    if value == "cart":
        return "CART"
    return format_optional(value)


def _format_release_class(value: object) -> str:
    if value == "publishable_candidate":
        return "Publishable candidate"
    if value == "private_working":
        return "Private working model"
    return format_optional(value)


def _format_audit_passed(value: object) -> str:
    if value is True:
        return "Audit passed"
    if value is False:
        return "Audit has warnings"
    return "Audit not available"


def format_bytes_or_blank(value: object) -> str:
    if not isinstance(value, int | float):
        return ""
    bytes_value = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if bytes_value < 1024 or unit == "GiB":
            return (
                f"{bytes_value:.1f} {unit}" if unit != "B" else f"{int(bytes_value)} B"
            )
        bytes_value /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


def format_int_or_blank(value: object) -> str:
    if isinstance(value, int | float):
        return f"{int(value):,}"
    return ""


def format_number_or_blank(value: object) -> str:
    if isinstance(value, int | float):
        return f"{float(value):,.6g}"
    return ""


def release_manifest_matches_model_paths(
    release_manifest: dict[str, object] | None,
    *,
    source_model_path: Path,
    output_model_path: Path,
) -> bool:
    if release_manifest is None:
        return False
    source_model = release_manifest.get("source_model")
    output_model = release_manifest.get("output_model")
    if not isinstance(source_model, str) or not isinstance(output_model, str):
        return False
    return same_model_path(Path(source_model), source_model_path) and same_model_path(
        Path(output_model),
        output_model_path,
    )


def same_model_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve(strict=False) == right.expanduser().resolve(
        strict=False
    )


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
