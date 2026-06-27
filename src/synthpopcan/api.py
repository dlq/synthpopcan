"""Beginner-friendly public API for notebooks and short scripts.

This module is the small, stable Python surface intended for people who want to
use SynthPopCan without learning the internal command modules first. It favours
plain file paths, lists of row dictionaries, and a small number of workflow
functions that map directly to the two main beginner tasks:

* fit seed rows to margin/control totals with IPF;
* generate linked household/person rows from a prepared model package.
* calibrate generated linked rows to small-area household controls.

Most users should import the top-level package and call these functions from
there::

    import synthpopcan as spc

    controls = spc.read_controls("controls.csv")
    fit = spc.fit_ipf("seed.csv", controls)
    spc.write_weights(fit, "synthetic-weights.csv")

    package = spc.read_model_package("model-package.json")
    population = spc.generate_from_model(package, households=100)
    spc.write_population(population, "synthetic-population/")
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.controls import ControlTable, read_control_table
from synthpopcan.ipf import IPFMargin, IPFResult, Record, expand_records
from synthpopcan.ipf import fit_ipf as fit_ipf_records
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    generate_linked_population,
)

SeedInput = str | Path | Sequence[Record]
ControlInput = str | Path | ControlTable | Sequence[IPFMargin]
ModelPackageInput = str | Path | Mapping[str, object]
PopulationRows = list[dict[str, str]]

__all__ = [
    "LinkedPopulation",
    "PopulationRows",
    "read_seed",
    "read_controls",
    "fit_ipf",
    "expand_population",
    "write_weights",
    "read_model_package",
    "generate_from_model",
    "write_population",
    "calibrate_small_area_linked",
]


@dataclass(frozen=True)
class LinkedPopulation:
    """Household and person rows generated from a linked model package.

    A linked model package generates two related tables: one row per synthetic
    household, and one or more person rows inside those households. This object
    keeps those tables together so that downstream code does not accidentally
    lose the household/person relationship.

    Parameters
    ----------
    households:
        Synthetic household rows. The exact columns depend on the model package,
        but household identifiers are preserved when the package provides them.
    persons:
        Synthetic person rows. Person rows are generated inside the synthetic
        households and may include household identifiers or household-level
        context columns.

    Notes
    -----
    Pass a ``LinkedPopulation`` to :func:`write_population` to write a directory
    containing ``households.csv`` and ``persons.csv``.
    """

    households: PopulationRows
    persons: PopulationRows


def read_seed(path: str | Path) -> PopulationRows:
    """Read a seed CSV as plain row dictionaries.

    Seed rows are the starting records for IPF. Each row should already contain
    the columns used by the margin/control table, for example ``age`` and
    ``sex`` in a small age/sex example.

    Parameters
    ----------
    path:
        Path to a CSV file with a header row.

    Returns
    -------
    list[dict[str, str]]
        One dictionary per CSV row, using the CSV header values as keys.

    Examples
    --------
    >>> seed = read_seed("seed.csv")
    >>> seed[0]["age"]
    '18-64'
    """

    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_controls(path: str | Path) -> ControlTable:
    """Read a normalized SynthPopCan control CSV.

    A normalized control CSV contains margin totals in the format used by
    SynthPopCan. These files can come from the CLI, the local web app, or a
    hand-prepared CSV.

    Parameters
    ----------
    path:
        Path to a normalized margin/control CSV.

    Returns
    -------
    synthpopcan.controls.ControlTable
        A parsed control table that can be passed directly to :func:`fit_ipf`.

    See Also
    --------
    fit_ipf:
        Fit seed rows to the controls returned by this function.
    """

    return read_control_table(Path(path))


def fit_ipf(
    seed: SeedInput,
    controls: ControlInput,
    *,
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> IPFResult:
    """Fit seed records to controls with iterative proportional fitting.

    IPF adjusts weights on existing seed rows so that weighted totals match a
    set of margin/control totals. It does not create new categories or new
    variables. Every control dimension should already exist as a column in the
    seed rows.

    Parameters
    ----------
    seed:
        Either a path to a seed CSV or an in-memory sequence of row mappings.
        Each row should include the dimensions named in the controls.
    controls:
        A path to a normalized control CSV, a
        :class:`synthpopcan.controls.ControlTable`, or a sequence of lower-level
        :class:`synthpopcan.ipf.IPFMargin` objects.
    weight_field:
        Optional seed column containing starting weights. If omitted, every seed
        row starts with weight ``1``.
    max_iterations:
        Maximum number of IPF passes through the controls.
    tolerance:
        Stop once the maximum absolute control error is at or below this value.

    Returns
    -------
    synthpopcan.ipf.IPFResult
        The fitted records, fitted weights, convergence status, iteration count,
        and final maximum absolute error.

    Raises
    ------
    ValueError
        Raised when controls refer to missing seed columns or when a control
        cell cannot be represented by the available seed rows.

    Examples
    --------
    >>> fit = fit_ipf("seed.csv", "controls.csv")
    >>> fit.converged
    True
    >>> write_weights(fit, "synthetic-weights.csv")
    """

    seed_records = _seed_records(seed)
    margins = _control_margins(controls)
    return fit_ipf_records(
        seed_records,
        margins,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )


def expand_population(result: IPFResult, *, id_field: str = "id") -> PopulationRows:
    """Expand fitted IPF weights into full synthetic rows.

    Weighted output is usually the practical default for browser and notebook
    work. Expanded rows are useful when another tool expects one row per
    synthetic person, household, or record, but they can become very large.

    Parameters
    ----------
    result:
        A fitted IPF result from :func:`fit_ipf`.
    id_field:
        Source seed-record identifier column to copy into the ``seed_id`` field
        of expanded rows. Each expanded row also receives a new
        ``synthetic_id``.

    Returns
    -------
    list[dict[str, str]]
        A full synthetic dataset where each row represents one expanded record.

    Notes
    -----
    Expansion integerizes fitted weights before repeating records. If the fitted
    weights represent a large population, the returned list can use substantial
    memory.
    """

    return expand_records(result.records, result.weights, id_field=id_field)


def write_weights(
    result: IPFResult,
    path: str | Path,
    *,
    weight_column: str | None = None,
) -> None:
    """Write fitted seed records with a fitted-weight column.

    This is the recommended way to save IPF output for most workflows. It keeps
    one row per seed record and adds a column containing the fitted synthetic
    population weight.

    Parameters
    ----------
    result:
        A fitted IPF result from :func:`fit_ipf`.
    path:
        Destination CSV path.
    weight_column:
        Optional output column name for fitted weights. When omitted, the
        function uses ``weight`` unless that column already exists, in which case
        it uses ``fitted_weight``.

    Raises
    ------
    ValueError
        Raised when the IPF result has no records to write.
    """

    if not result.records:
        raise ValueError("cannot write weights for an empty IPF result")
    rows = [_string_row(record) for record in result.records]
    output_weight_column = weight_column or _default_weight_column(rows)
    fieldnames = [*rows[0], output_weight_column]
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, weight in zip(rows, result.weights, strict=True):
            writer.writerow({**row, output_weight_column: _format_weight(weight)})


def read_model_package(path: str | Path) -> dict[str, object]:
    """Read a linked household/person model package JSON.

    Model packages are prepared artifacts created by SynthPopCan tooling. They
    can represent linked household/person generation without exposing raw
    microdata rows.

    Parameters
    ----------
    path:
        Path to a linked model package JSON file.

    Returns
    -------
    dict[str, object]
        The parsed package payload. Pass it to :func:`generate_from_model`.

    Raises
    ------
    ValueError
        Raised when the file is not valid JSON, is not a JSON object, or uses an
        unsupported package schema.
    """

    try:
        payload = json.loads(Path(path).read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("model package must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-linked-tree-package-v1":
        raise ValueError("unsupported linked model package schema")
    return payload


def generate_from_model(
    package: ModelPackageInput,
    *,
    households: int,
    conditions: Mapping[str, str] | None = None,
    random_seed: int | None = None,
    household_size_column: str | None = None,
    require_publishable: bool = True,
) -> LinkedPopulation:
    """Generate linked household and person rows from a prepared package.

    This is the beginner-facing entry point for using an existing model package.
    It creates household rows first, then generates person rows inside those
    households using the package's linked household/person model design.

    Parameters
    ----------
    package:
        A path to a linked model package JSON file, or an already-loaded package
        mapping returned by :func:`read_model_package`.
    households:
        Number of synthetic households to generate.
    conditions:
        Optional fixed values for package condition columns. For example,
        ``{"geo": "Demo North"}`` asks the household model to generate rows for
        that geography when the package supports ``geo`` as a condition.
    random_seed:
        Optional random seed for reproducible generated rows.
    household_size_column:
        Optional override for the column that controls how many person rows are
        generated in each household. When omitted, the package setting is used,
        falling back to ``household_size``.
    require_publishable:
        When ``True``, reject packages that are not marked as publishable
        candidates. Keep this enabled for normal use; set it to ``False`` only
        while inspecting trusted local development packages.

    Returns
    -------
    LinkedPopulation
        Household and person rows generated from the package.

    Raises
    ------
    ValueError
        Raised when the package schema is invalid, required models are missing,
        an unsupported model type is encountered, or ``require_publishable`` is
        enabled for a package that is not marked as publishable.

    Examples
    --------
    >>> package = read_model_package("demo-linked-package.json")
    >>> population = generate_from_model(package, households=25, random_seed=13)
    >>> len(population.households)
    25
    """

    package_payload = _model_package(package)
    if require_publishable:
        _validate_publishable_package(package_payload)
    package_household_size_column = str(
        household_size_column or package_payload.get("household_size_column", "")
    )
    if not package_household_size_column:
        package_household_size_column = "household_size"
    household_model, person_model = _package_models(package_payload)
    household_rows, person_rows = generate_linked_population(
        household_model,
        person_model,
        households=households,
        household_conditions=dict(conditions or {}),
        household_size_column=package_household_size_column,
        random_seed=random_seed,
    )
    return LinkedPopulation(household_rows, person_rows)


def write_population(
    population: LinkedPopulation | PopulationRows,
    path: str | Path,
) -> None:
    """Write generated population rows to CSV.

    The output shape depends on the kind of population passed in:

    * a :class:`LinkedPopulation` is written to a directory containing
      ``households.csv`` and ``persons.csv``;
    * a flat list of row dictionaries is written to a single CSV file.

    Parameters
    ----------
    population:
        Either a linked household/person population from
        :func:`generate_from_model`, or a flat list of row dictionaries such as
        the result from :func:`expand_population`.
    path:
        Destination directory for linked output, or destination CSV path for
        flat output.

    Raises
    ------
    ValueError
        Raised when there are no rows to write.

    Examples
    --------
    >>> fit = fit_ipf("seed.csv", "controls.csv")
    >>> rows = expand_population(fit)
    >>> write_population(rows, "expanded.csv")
    """

    output_path = Path(path)
    if isinstance(population, LinkedPopulation):
        output_path.mkdir(parents=True, exist_ok=True)
        _write_rows(output_path / "households.csv", population.households)
        _write_rows(output_path / "persons.csv", population.persons)
        return
    _write_rows(output_path, population)


def calibrate_small_area_linked(
    *,
    households: str | Path,
    persons: str | Path,
    controls: str | Path,
    geography_dimension: str,
    geography_column: str,
    households_out: str | Path,
    persons_out: str | Path,
    report_out: str | Path | None = None,
    weights_out: str | Path | None = None,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    pool_size: int | None = None,
) -> dict[str, Any]:
    """Calibrate linked household/person candidates to small-area controls.

    This is the beginner-friendly Python entry point for the small-area
    workflow. It takes linked household and person candidate CSVs, assigns
    household rows to a target geography such as census tract (``ct``) or
    aggregate dissemination area (``ada``), and writes new household/person CSVs
    that preserve the household/person links.

    The first implementation calibrates household-level controls. Person rows
    inherit the geography of their assigned household. Use linked-output
    validation afterward when person-level geography totals matter.

    Parameters
    ----------
    households:
        Candidate household CSV, usually generated from a prepared linked model
        package.
    persons:
        Candidate person CSV linked to ``households`` by the household ID
        column.
    controls:
        Normalized control CSV with one dimension naming the target geography
        and one or more household dimensions available in ``households``.
    geography_dimension:
        Name of the geography dimension in the control CSV, for example ``ct``
        or ``ada``.
    geography_column:
        Output column name to write on assigned household and person rows.
    households_out:
        Destination CSV for assigned household rows.
    persons_out:
        Destination CSV for assigned person rows.
    report_out:
        Optional JSON report path containing convergence and assigned-row
        counts by geography.
    weights_out:
        Optional CSV path for fitted household weights. This can be very large
        for many small areas, so it is usually omitted.
    household_id_column:
        Household ID column shared by the candidate household and person CSVs.
    person_id_column:
        Person ID column in the candidate person CSV.
    weight_field:
        Optional candidate-household starting weight column.
    max_iterations:
        Maximum IPF iterations for each geography-specific household fit.
    tolerance:
        Convergence tolerance for each geography-specific household fit.
    pool_size:
        Maximum candidate households to use.  Values of 5 000–10 000
        reproduce aggregate statistics with near-identical accuracy to the
        full pool and run ~10× faster.  Pass ``None`` (default) to use the
        full pool, which is needed when individual-household uniqueness matters.

    Returns
    -------
    dict[str, Any]
        A summary report with total assigned household/person counts,
        geography counts, and per-geography fit diagnostics.

    Examples
    --------
    >>> summary = calibrate_small_area_linked(
    ...     households="candidate-households.csv",
    ...     persons="candidate-persons.csv",
    ...     controls="ct-tenure-controls.csv",
    ...     geography_dimension="ct",
    ...     geography_column="ct",
    ...     households_out="synthetic-households.csv",
    ...     persons_out="synthetic-persons.csv",
    ...     report_out="small-area-report.json",
    ... )
    >>> summary["assigned_households"] > 0
    True
    """

    return calibrate_linked_household_csvs(
        households_path=Path(households),
        persons_path=Path(persons),
        controls_path=Path(controls),
        geography_dimension=geography_dimension,
        geography_column=geography_column,
        households_out=Path(households_out),
        persons_out=Path(persons_out),
        weights_out=Path(weights_out) if weights_out is not None else None,
        report_out=Path(report_out) if report_out is not None else None,
        household_id_column=household_id_column,
        person_id_column=person_id_column,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
        pool_size=pool_size,
    )


def render_small_area_map(
    *,
    households: str | Path,
    persons: str | Path | None = None,
    boundaries: str | Path,
    geography_column: str,
    geography_id_field: str,
    out: str | Path,
    title: str = "Synthetic Population",
    coord_precision: int = 5,
) -> Path:
    """Generate a MapLibre GL JS choropleth HTML file from synthesis output.

    The resulting file is self-contained (~3–10 MB) and opens directly in any
    modern browser. It uses WebGL for fast rendering and fetches base-map tiles
    from OpenFreeMap (requires an internet connection when viewing).

    Parameters
    ----------
    households:
        Synthesis household CSV (output of :func:`calibrate_small_area_linked`).
    boundaries:
        StatCan boundary shapefile (.shp) for the target geography level.
        For census tracts use ``lct_000b16a_e.shp``; for ADAs use
        ``lada000b16a_e.shp``.  The file may stay in its original Lambert
        Conformal Conic projection — reprojection to WGS-84 is automatic.
    geography_column:
        Column in ``households`` that holds the geography ID (e.g. ``ct``).
    geography_id_field:
        Attribute field in the shapefile matching that column (e.g. ``CTUID``
        or ``ADAUID``).
    out:
        Destination HTML file path.
    title:
        Map title shown in the side panel and browser tab.
    coord_precision:
        Decimal places kept in WGS-84 coordinates.  5 gives ≈ 1 m accuracy
        (default); 3 reduces file size ~50 % with ≈ 110 m accuracy, adequate
        for province-wide ADA maps.

    Returns
    -------
    pathlib.Path
        The path of the written HTML file.

    Examples
    --------
    >>> path = render_small_area_map(
    ...     households="synthetic-households.csv",
    ...     boundaries="lct_000b16a_e.shp",
    ...     geography_column="ct",
    ...     geography_id_field="CTUID",
    ...     out="montreal-ct-map.html",
    ...     title="Montreal Census Tracts",
    ... )
    """
    from synthpopcan.map_render import render_synthesis_map

    return render_synthesis_map(
        households_path=Path(households),
        persons_path=Path(persons) if persons is not None else None,
        boundaries_path=Path(boundaries),
        geography_column=geography_column,
        geography_id_field=geography_id_field,
        out_path=Path(out),
        title=title,
        coord_precision=coord_precision,
    )


def _seed_records(seed: SeedInput) -> list[Record]:
    if isinstance(seed, str | Path):
        return read_seed(seed)
    return list(seed)


def _control_margins(controls: ControlInput) -> list[IPFMargin]:
    if isinstance(controls, str | Path):
        return read_controls(controls).to_ipf_margins()
    if isinstance(controls, ControlTable):
        return controls.to_ipf_margins()
    return list(controls)


def _model_package(package: ModelPackageInput) -> dict[str, object]:
    if isinstance(package, str | Path):
        return read_model_package(package)
    return dict(package)


def _validate_publishable_package(package: Mapping[str, object]) -> None:
    privacy = package.get("privacy")
    if (
        not isinstance(privacy, Mapping)
        or privacy.get("publishable_candidate") is not True
    ):
        raise ValueError(
            "model package is not marked as a publishable candidate; inspect the "
            "package before generating from it"
        )


def _package_models(
    package: Mapping[str, object],
) -> tuple[FrequencyTreeModel | CartTreeModel, FrequencyTreeModel | CartTreeModel]:
    models = package.get("models")
    if not isinstance(models, Mapping):
        raise ValueError("linked model package must include models")
    household_model = _tree_model_from_payload(models.get("household"))
    person_model = _tree_model_from_payload(models.get("person"))
    return household_model, person_model


def _tree_model_from_payload(payload: object) -> FrequencyTreeModel | CartTreeModel:
    if not isinstance(payload, dict):
        raise ValueError(
            "linked model package must include household and person models"
        )
    model_type = payload.get("model_type")
    if model_type == "conditional-frequency":
        return FrequencyTreeModel.from_dict(payload)
    if model_type == "cart":
        return CartTreeModel.from_dict(payload)
    raise ValueError("unsupported tree model type in linked package")


def _write_rows(path: Path, rows: PopulationRows) -> None:
    if not rows:
        raise ValueError(f"cannot write empty rows to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _string_row(record: Mapping[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in record.items()}


def _default_weight_column(rows: PopulationRows) -> str:
    return "weight" if "weight" not in rows[0] else "fitted_weight"


def _format_weight(weight: float) -> str:
    return str(int(weight)) if weight.is_integer() else f"{weight:.12g}"
