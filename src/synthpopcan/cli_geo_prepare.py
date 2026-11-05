"""Composable file-backed preparation commands for the geo CLI."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import BadZipFile

import click

from synthpopcan._candidate_preparation import prepare_candidates
from synthpopcan._population_preparation import audit_population, combine_populations
from synthpopcan._profile_preparation import PROFILE, prepare_profile_controls
from synthpopcan.cli_errors import FriendlyCommand
from synthpopcan.cli_output import click_file_access_error, click_value_error
from synthpopcan.workflows.preparation import publish_preparation

_PATH = click.Path(path_type=Path)
_INPUT = click.Path(path_type=Path, exists=True)


def _invocation() -> dict:
    context = click.get_current_context()
    arguments = context.command_path.split()
    for param in context.command.params:
        value = context.params[param.name]
        if isinstance(param, click.Argument):
            arguments.extend(
                str(v) for v in value
            ) if param.nargs == -1 else arguments.append(str(value))
        elif isinstance(param, click.Option) and value is not None:
            if param.is_flag:
                if value:
                    arguments.append(param.opts[0])
            else:
                values = value if param.multiple else (value,)
                for item in values:
                    arguments.extend([param.opts[0], str(item)])
    return {"operation": context.command.name, "arguments": arguments}


def _publish(output, inputs, action, expected_sha256=None):
    try:
        result = publish_preparation(
            output, tuple(inputs), action, _invocation(), expected_sha256
        )
    except OSError as exc:
        raise click_file_access_error(
            exc.filename or output, "read or write", exc
        ) from exc
    except (ValueError, BadZipFile) as exc:
        raise click_value_error(ValueError(str(exc))) from exc
    _print_exclusion_warning(result, output)
    click.echo(
        json.dumps({"output": str(output), "summary": result}, ensure_ascii=False)
    )


def _print_exclusion_warning(summary, output):
    excluded = summary.get("excluded_geographies", summary.get("excluded_tracts", []))
    if not excluded:
        return
    click.echo(
        f"Warning: excluded {len(excluded):,} geographies; "
        "their households are not reassigned.",
        err=True,
    )
    coverage = summary.get("coverage", {})
    if coverage:
        click.echo(
            f"Coverage: {coverage['eligible_geographies']:,}/"
            f"{coverage['selected_geographies']:,} geographies; "
            f"{coverage['known_excluded_households']:,} known households omitted; "
            "areas with unknown household counts: "
            f"{len(coverage['unavailable_household_geographies']):,} (not zero).",
            err=True,
        )
    click.echo(f"Review exclusions and coverage in {output / 'plan.json'}.", err=True)


@click.command("prepare-controls", cls=FriendlyCommand)
@click.argument("profile", type=_INPUT)
@click.option(
    "--cma",
    type=click.STRING,
    help="Three-digit 2021 CMA code, e.g. 462 for Montréal.",
)
@click.option("--canada", is_flag=True, help="Select all Canadian Census 2021 ADAs.")
@click.option(
    "--province",
    type=click.STRING,
    help="Two-digit 2021 province/territory code, e.g. 24 for Québec; selects ADAs.",
)
@click.option(
    "--province-profile",
    "--national-profile",
    type=_INPUT,
    help="Separate 2021 Profile ZIP/CSV containing province or Canada totals.",
)
@click.option("--source-profile", required=True, type=click.Choice([PROFILE]))
@click.option(
    "--normalization",
    required=True,
    type=click.Choice(["observed-proportional"]),
    help=(
        "Explicitly normalize complete observed vectors by "
        "largest remainder; preserve source rows and zeros."
    ),
)
@click.option(
    "--profile-sha256",
    default=None,
    help="Expected SHA-256 of the input Profile ZIP/CSV.",
)
@click.option(
    "--incomplete-geographies",
    type=click.Choice(["error", "exclude"]),
    default="error",
    show_default=True,
    help=(
        "Reject unavailable tract counts, or explicitly exclude those tracts "
        "with recorded reasons."
    ),
)
@click.option("--out", "output", required=True, type=_PATH)
def prepare_controls_command(
    profile,
    cma,
    province,
    canada,
    province_profile,
    source_profile,
    normalization,
    profile_sha256,
    incomplete_geographies,
    output,
):
    """Prepare broad observed household/person controls from a 2021 Profile.

    Writes separate private-household and equal-universe age/gender batches.
    Select CMA tracts with --cma, provincial ADAs with --province, or all ADAs
    with --canada. --national-profile supplies the observed Canada totals.
    Missing/suppressed counts are rejected. No source counts are overwritten.
    """
    if sum((cma is not None, province is not None, canada)) != 1:
        raise click.UsageError("Supply exactly one of --cma, --province or --canada.")
    if cma is not None and (len(cma) != 3 or not cma.isdigit()):
        raise click.UsageError("--cma must be a three-digit Census 2021 CMA code.")
    if not canada:
        _validate_province(province, province_profile)
    _publish(
        output,
        [profile, *([province_profile] if province_profile is not None else [])],
        lambda stage: prepare_profile_controls(
            profile,
            cma,
            stage,
            incomplete_geographies,
            province=province,
            geo_level="ada" if province is not None or canada else "ct",
            canada=canada,
            province_profile=province_profile,
        ),
        profile_sha256,
    )


def _validate_province(province, province_profile):
    if province_profile is not None and province is None:
        raise click.UsageError("--province-profile requires --province.")
    if province is not None and province not in {
        "10",
        "11",
        "12",
        "13",
        "24",
        "35",
        "46",
        "47",
        "48",
        "59",
        "60",
        "61",
        "62",
    }:
        raise click.UsageError(
            "--province must be a two-digit Census province/territory code, "
            "such as 24 for Québec."
        )


@click.command("prepare-candidates", cls=FriendlyCommand)
@click.argument("population", type=_INPUT)
@click.option("--source-profile", required=True, type=click.Choice([PROFILE]))
@click.option(
    "--require-gender",
    is_flag=True,
    help=(
        "Exclude whole households containing unavailable "
        "gender, for age/gender controls."
    ),
)
@click.option(
    "--pool-size",
    type=click.IntRange(min=1),
    default=None,
    help=(
        "Subsample after complete-case screening; omit to "
        "retain all complete households."
    ),
)
@click.option("--subsample-seed", type=int, default=42, show_default=True)
@click.option(
    "--augment-support",
    is_flag=True,
    help=(
        "Augment the random pool with nonnegative LP "
        "supports. Requires the performance extra and "
        "both control files. Infeasible targets remain "
        "unchanged and are reported."
    ),
)
@click.option("--controls", type=_INPUT, default=None)
@click.option("--person-controls", type=_INPUT, default=None)
@click.option("--geo-dimension", default="ct", show_default=True)
@click.option("--out", "output", required=True, type=_PATH)
def prepare_candidates_command(
    population,
    source_profile,
    require_gender,
    pool_size,
    subsample_seed,
    augment_support,
    controls,
    person_controls,
    geo_dimension,
    output,
):
    """Screen whole linked households and derive source-specific control fields."""
    if augment_support and (
        pool_size is None or controls is None or person_controls is None
    ):
        raise click.UsageError(
            "--augment-support requires --pool-size, --controls and --person-controls."
        )
    inputs = [
        population / name for name in ("manifest.json", "households.csv", "persons.csv")
    ]
    inputs.extend(p for p in (controls, person_controls) if p is not None)
    _publish(
        output,
        inputs,
        lambda stage: prepare_candidates(
            population,
            stage,
            require_gender=require_gender,
            pool_size=pool_size,
            seed=subsample_seed,
            augment_support=augment_support,
            controls_path=controls,
            person_controls_path=person_controls,
            geography_dimension=geo_dimension,
        ),
    )


@click.command("combine", cls=FriendlyCommand)
@click.argument("populations", nargs=-1, required=True, type=_INPUT)
@click.option("--geo-column", default="ct", show_default=True)
@click.option("--out", "output", required=True, type=_PATH)
def combine_command(populations, geo_column, output):
    """Combine disjoint calibrated batches, validating household/person links."""
    inputs = [
        p / name
        for p in populations
        for name in ("manifest.json", "households.csv", "persons.csv")
    ]
    inputs.extend(
        p / "report.json" for p in populations if (p / "report.json").exists()
    )
    _publish(
        output,
        inputs,
        lambda stage: combine_populations(populations, stage, geo_column),
    )


@click.command("audit", cls=FriendlyCommand)
@click.argument("population", type=_INPUT)
@click.option(
    "--controls",
    multiple=True,
    type=_INPUT,
    help="Household controls; repeat for disjoint batches.",
)
@click.option(
    "--person-controls",
    multiple=True,
    type=_INPUT,
    help="Person controls; repeat for disjoint batches.",
)
@click.option("--geo-column", default="ct", show_default=True)
@click.option("--out", "output", required=True, type=_PATH)
def audit_command(population, controls, person_controls, geo_column, output):
    """Read assigned CSVs back and report residuals against every supplied target."""
    if not controls and not person_controls:
        raise click.UsageError("Supply --controls and/or --person-controls to audit.")
    inputs = [population / name for name in ("households.csv", "persons.csv")]
    inputs.extend([*controls, *person_controls])
    _publish(
        output,
        inputs,
        lambda stage: audit_population(
            population, controls, person_controls, stage, geo_column
        ),
    )


GEO_PREPARATION_COMMANDS = (
    prepare_controls_command,
    prepare_candidates_command,
    combine_command,
    audit_command,
)
