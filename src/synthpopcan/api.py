"""Beginner-friendly public API for notebooks and short scripts.

This module is the small, stable Python surface intended for people who want to
use SynthPopCan without learning the internal command modules first. It favours
plain file paths, lists of row dictionaries, and a small number of workflow
functions that map directly to common beginner work:

* fit seed rows to margin/control totals with IPF;
* generate linked household/person rows from a prepared model package;
* calibrate generated linked rows to small-area household controls;
* render browser maps from calibrated small-area or national-plan output; and
* attach validated external-data sidecars without changing the base population.

Most users should import the top-level package and call these functions from
there::

    import synthpopcan as spc

    controls = spc.read_controls("controls.csv")
    fit = spc.fit_ipf("seed.csv", controls)
    spc.write_weights(fit, "synthetic-weights.csv")

    package = spc.fetch_model("demo-linked-household-person")
    population = spc.generate_from_model(package, households=100)
    spc.write_linked_population(population, "synthetic-population/")
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from synthpopcan.controls import ControlTable, read_control_table, write_control_table
from synthpopcan.enrichment import (
    ResourceRecord,
    SourceProfile,
    import_normalized_layer,
    read_resource_record,
    read_source_profile,
)
from synthpopcan.geography import GeographyUniverse
from synthpopcan.ipf import IPFMargin, IPFResult, expand_records
from synthpopcan.ipf import fit_ipf as fit_ipf_records
from synthpopcan.linked_schema import write_linked_population_contract
from synthpopcan.models import fetch_model_package
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
from synthpopcan.tabular import format_csv_number
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    generate_linked_population,
)
from synthpopcan.workflows.ipf import read_csv_records

_SeedInput = str | Path | Sequence[Mapping[str, object]]
_ControlInput = str | Path | ControlTable
_ModelPackageInput = str | Path | Mapping[str, object]
PopulationRows = list[dict[str, str]]

__all__ = [
    "ControlTable",
    "EnrichmentResult",
    "IPFResult",
    "LinkedPopulation",
    "LinkedPopulationFiles",
    "PopulationRows",
    "SmallAreaResult",
    "calibrate_small_area",
    "enrich_population",
    "expand_population",
    "fetch_model",
    "fit_ipf",
    "generate_from_model",
    "read_controls",
    "read_model_package",
    "read_seed",
    "render_small_area_map",
    "write_linked_population",
    "write_population",
    "write_weights",
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
    Pass a ``LinkedPopulation`` to :func:`write_linked_population` to write a
    directory containing ``households.csv`` and ``persons.csv``.
    """

    households: PopulationRows
    persons: PopulationRows


@dataclass(frozen=True)
class LinkedPopulationFiles:
    """Paths to linked household and person population CSVs.

    ``write_linked_population`` returns this object. Pass it to
    :func:`calibrate_small_area` or :func:`render_small_area_map` to continue a
    workflow without manually reconnecting the two filenames.
    """

    households: Path
    persons: Path
    manifest: Path | None = None


@dataclass(frozen=True)
class SmallAreaResult:
    """Artifacts and headline diagnostics from small-area calibration.

    The paired population paths can be passed directly to
    :func:`render_small_area_map`. ``details`` retains the complete report for
    research inspection and machine-readable downstream use.
    """

    population: LinkedPopulationFiles
    report_path: Path
    weights_path: Path | None
    assigned_households: int
    assigned_persons: int
    total_geographies: int
    converged: bool
    max_abs_error: float
    calibration_mode: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class EnrichmentResult:
    """Paths and validation returned by :func:`enrich_population`.

    ``layer`` is the copied normalized sidecar, ``manifest`` records its source,
    resource, geography, base-population hashes, and limitations, and
    ``validation`` contains the source-independent key and coverage checks. The
    result never represents a widened or rewritten household/person table.
    """

    layer: Path
    manifest: Path
    validation: Mapping[str, object]


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

    return read_csv_records(Path(path))


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
    seed: str | Path | Sequence[Mapping[str, object]],
    controls: str | Path | ControlTable,
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
        A path to a normalized control CSV or a
        :class:`synthpopcan.controls.ControlTable`.
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
) -> Path:
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

    Returns
    -------
    pathlib.Path
        The written CSV path.
    """

    if not result.records:
        raise ValueError("cannot write weights for an empty IPF result")
    rows = [_string_row(record) for record in result.records]
    output_weight_column = weight_column or _default_weight_column(rows)
    fieldnames = [*rows[0], output_weight_column]
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, weight in zip(rows, result.weights, strict=True):
            writer.writerow({**row, output_weight_column: format_csv_number(weight)})
    return output_path


def read_model_package(path: str | Path) -> dict[str, Any]:
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
    dict[str, Any]
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
    _validate_model_package_schema(payload)
    return payload


def fetch_model(model_id: str) -> dict[str, Any]:
    """Fetch and read a registered linked model package.

    The bundled teaching model loads without an internet connection. Larger
    public model packages are downloaded to SynthPopCan's local cache on first
    use and reused on later calls.

    Parameters
    ----------
    model_id:
        Package ID shown by ``synthpopcan models list``. Use
        ``demo-linked-household-person`` for the bundled synthetic teaching
        model.

    Returns
    -------
    dict[str, Any]
        A reviewed model package ready for :func:`generate_from_model`.

    Raises
    ------
    KeyError
        Raised when ``model_id`` is not in the public model catalogue.
    OSError
        Raised when a downloadable package cannot be retrieved or cached.
    ValueError
        Raised when a downloaded package fails verification or cannot be read.

    Examples
    --------
    >>> package = fetch_model("demo-linked-household-person")
    >>> population = generate_from_model(package, households=5, random_seed=13)
    >>> len(population.households)
    5
    """

    return read_model_package(fetch_model_package(model_id))


def generate_from_model(
    package: str | Path | Mapping[str, object],
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
    package_household_size_column = (
        str(household_size_column or package_payload.get("household_size_column", ""))
        or "household_size"
    )
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
    population: PopulationRows,
    path: str | Path,
) -> Path:
    """Write flat generated population rows to one CSV file.

    Parameters
    ----------
    population:
        A flat list of row dictionaries such as the result from
        :func:`expand_population`.
    path:
        Destination CSV path.

    Raises
    ------
    ValueError
        Raised when there are no rows to write.

    Returns
    -------
    pathlib.Path
        The written CSV path.

    Examples
    --------
    >>> fit = fit_ipf("seed.csv", "controls.csv")
    >>> rows = expand_population(fit)
    >>> write_population(rows, "expanded.csv")
    """

    if isinstance(population, LinkedPopulation):
        raise TypeError(
            "write_population writes one flat CSV; use write_linked_population "
            "for linked household/person rows"
        )
    output_path = Path(path)
    _write_rows(output_path, population)
    return output_path


def write_linked_population(
    population: LinkedPopulation,
    directory: str | Path,
) -> LinkedPopulationFiles:
    """Write linked household and person rows to a directory.

    Returns paired paths that can be passed directly to
    :func:`calibrate_small_area` or :func:`render_small_area_map`.
    """

    if not population.households:
        raise ValueError("cannot write a linked population without households")
    if not population.persons:
        raise ValueError("cannot write a linked population without persons")
    output_directory = Path(directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / "manifest.json"
    files = LinkedPopulationFiles(
        households=output_directory / "households.csv",
        persons=output_directory / "persons.csv",
        manifest=manifest_path,
    )
    _write_rows(files.households, population.households)
    _write_rows(files.persons, population.persons)
    write_linked_population_contract(
        manifest_path,
        files.households,
        files.persons,
    )
    return files


def calibrate_small_area(
    population: LinkedPopulation | LinkedPopulationFiles | str | Path,
    controls: str | Path | ControlTable,
    *,
    geography_dimension: str,
    output_dir: str | Path,
    person_controls: str | Path | ControlTable | None = None,
    geography_column: str | None = None,
    geography_universe: GeographyUniverse | Mapping[str, object] | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    pool_size: int | None = None,
    subsample_seed: int = 42,
    include_weights: bool = False,
) -> SmallAreaResult:
    """Calibrate a linked population to small-area controls.

    This is the composable beginner entry point. ``population`` may be the
    in-memory result of :func:`generate_from_model`, the paired paths returned by
    :func:`write_linked_population`, or a directory containing ``households.csv``
    and ``persons.csv``. Outputs use predictable names inside ``output_dir`` and
    the returned result can be passed directly to :func:`render_small_area_map`.

    Parameters
    ----------
    population:
        Linked household/person rows or their paired CSV files.
    controls:
        Normalized household controls as a path or :class:`ControlTable`.
    geography_dimension:
        Geography dimension in the controls, such as ``ct`` or ``ada``.
    output_dir:
        Directory for ``households.csv``, ``persons.csv``, and ``report.json``.
    person_controls:
        Optional linked-person controls as a path or :class:`ControlTable`.
    geography_column:
        Output geography column. Defaults to ``geography_dimension``.
    geography_universe:
        Versioned Census vintage, level, namespace, and identifier-column
        context. Omit only for legacy or non-Census workflows.
    max_iterations, tolerance:
        IPF convergence settings for each geography.
    pool_size, subsample_seed:
        Optional reproducible candidate-pool subsampling settings.
    include_weights:
        Also write the usually large ``weights.csv`` diagnostic artifact.

    Returns
    -------
    SmallAreaResult
        Typed headline diagnostics and paths to all written artifacts.
    """

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_population = LinkedPopulationFiles(
        households=destination / "households.csv",
        persons=destination / "persons.csv",
    )
    report_path = destination / "report.json"
    weights_path = destination / "weights.csv" if include_weights else None

    with TemporaryDirectory(prefix="synthpopcan-small-area-") as temporary:
        temporary_path = Path(temporary)
        if isinstance(population, LinkedPopulation):
            candidate_files = write_linked_population(
                population,
                temporary_path / "population",
            )
        else:
            candidate_files = _linked_population_files(population)
        _validate_linked_population_files(candidate_files)

        controls_path = _control_table_path(
            controls,
            temporary_path / "controls.csv",
        )
        person_controls_path = (
            _control_table_path(
                person_controls,
                temporary_path / "person-controls.csv",
            )
            if person_controls is not None
            else None
        )
        normalized_geography = (
            GeographyUniverse.from_dict(geography_universe)
            if isinstance(geography_universe, Mapping)
            else geography_universe
        )
        details = calibrate_linked_household_csvs(
            households_path=candidate_files.households,
            persons_path=candidate_files.persons,
            controls_path=controls_path,
            person_controls_path=person_controls_path,
            geography_dimension=geography_dimension,
            geography_column=geography_column or geography_dimension,
            geography_universe=normalized_geography,
            households_out=output_population.households,
            persons_out=output_population.persons,
            report_out=report_path,
            weights_out=weights_path,
            max_iterations=max_iterations,
            tolerance=tolerance,
            pool_size=pool_size,
            subsample_seed=subsample_seed,
        )

    summary = details.get("summary")
    if not isinstance(summary, Mapping):
        raise RuntimeError("small-area calibration returned an invalid summary")
    non_converged = int(summary.get("non_converged_count", 0))
    return SmallAreaResult(
        population=output_population,
        report_path=report_path,
        weights_path=weights_path,
        assigned_households=int(details["assigned_households"]),
        assigned_persons=int(details["assigned_persons"]),
        total_geographies=int(summary["total_geographies"]),
        converged=non_converged == 0,
        max_abs_error=float(summary["max_abs_error"]),
        calibration_mode=str(details["calibration_mode"]),
        details=details,
    )


def enrich_population(
    population: LinkedPopulationFiles | str | Path,
    layer: str | Path,
    *,
    source_profile: SourceProfile | str | Path,
    resource_record: ResourceRecord | str | Path,
    layer_id: str,
    layer_class: str,
    key_columns: Sequence[str],
    variables: Sequence[str],
    base_geography: GeographyUniverse | Mapping[str, object] | None = None,
    output_dir: str | Path,
    observed_status: str = "observed",
    limitations: Sequence[str] = (),
) -> EnrichmentResult:
    """Attach a validated normalized sidecar to a linked population.

    The function reads a versioned source profile and immutable resource record,
    validates the normalized layer's keys, variables, lineage, and optional
    geography against the linked-population manifest, then copies the sidecar
    and writes an enrichment manifest in ``output_dir``. It verifies that the
    original household, person, and linked-manifest bytes did not change.

    Parameters
    ----------
    population:
        Linked-population v1 directory or paired files returned by
        :func:`write_linked_population`.
    layer:
        Normalized CSV sidecar to validate and copy.
    source_profile, resource_record:
        Parsed records or paths to versioned JSON records describing the source
        and exact input bytes.
    layer_id, layer_class:
        Stable layer identifier and one supported structural class.
    key_columns, variables:
        CSV columns used for linkage and columns published as values.
    base_geography:
        Explicit geography universe for a geography-bearing layer.
    output_dir:
        Destination for the copied sidecar and ``manifest.json``.
    observed_status:
        Whether values are ``observed``, ``derived``, or ``modeled``.
    limitations:
        Reader-facing cautions that should travel with the bundle.

    Returns
    -------
    EnrichmentResult
        Written paths and the validation report.

    Raises
    ------
    ValueError
        If records, lineage, columns, keys, or geography are incompatible.
    RuntimeError
        If the base linked-population bytes change during publication.
    """
    if isinstance(population, LinkedPopulationFiles):
        population_directory = population.households.parent
    else:
        population_directory = Path(population)
    source = (
        source_profile
        if isinstance(source_profile, SourceProfile)
        else read_source_profile(Path(source_profile))
    )
    resource = (
        resource_record
        if isinstance(resource_record, ResourceRecord)
        else read_resource_record(Path(resource_record))
    )
    output_directory = Path(output_dir)
    normalized_base_geography = (
        GeographyUniverse.from_dict(base_geography)
        if isinstance(base_geography, Mapping)
        else base_geography
    )
    _, validation = import_normalized_layer(
        population_directory,
        Path(layer),
        output_directory,
        source=source,
        resource=resource,
        layer_id=layer_id,
        layer_class=layer_class,
        key_columns=key_columns,
        variables=variables,
        base_geography=normalized_base_geography,
        observed_status=observed_status,
        reproduction_request={
            "workflow": "enrichment",
            "operation": "import-normalized-layer",
            "population": str(population_directory),
            "layer": str(layer),
        },
        limitations=limitations,
    )
    return EnrichmentResult(
        layer=output_directory / Path(layer).name,
        manifest=output_directory / "manifest.json",
        validation=validation,
    )


def render_small_area_map(
    *,
    households: str | Path | LinkedPopulationFiles | SmallAreaResult,
    persons: str | Path | None = None,
    boundaries: str | Path | None = None,
    geography_column: str | None = None,
    geography_id_field: str | None = None,
    out: str | Path | None = None,
    title: str | None = None,
    coord_precision: int | None = None,
    jurisdiction_pruids: Sequence[str] | None = None,
    geography_universe: GeographyUniverse | Mapping[str, object] | None = None,
) -> Path:
    """Generate a MapLibre GL JS choropleth HTML file from synthesis output.

    The resulting file is self-contained and opens directly in any modern
    browser. A bounded study-area map is commonly ~3–10 MB; national size
    depends on display-boundary complexity. It uses WebGL for fast rendering
    and fetches base-map tiles from OpenFreeMap (requires an internet
    connection when viewing).

    Parameters
    ----------
    households:
        A :class:`SmallAreaResult`, paired :class:`LinkedPopulationFiles`, or a
        synthesis household CSV. A completed national ``plan.json`` or its
        containing directory is also accepted and automatically aggregates all
        batch household/person outputs. Passing a result or paired paths
        automatically supplies the person CSV too.
    persons:
        Optional synthesis person CSV when ``households`` is a household path.
    boundaries:
        StatCan boundary shapefile (``.shp``) or prepared WGS-84 GeoJSON for the
        target geography level. For census tracts, a source shapefile may be
        named ``lct_000b16a_e.shp``; for ADAs, ``lada000b16a_e.shp``. Source
        shapefiles may stay in their original Lambert Conformal Conic projection
        because reprojection to WGS-84 is automatic. Inferred from a national
        plan.
    geography_column:
        Column in ``households`` that holds the geography ID (e.g. ``ct``).
    geography_id_field:
        Attribute field in the shapefile matching that column (e.g. ``CTUID``
        or ``ADAUID``).
    out:
        Destination HTML file path. Defaults beside the input population.
    title:
        Map title shown in the side panel and browser tab.
    coord_precision:
        Decimal places kept in WGS-84 coordinates. Defaults to 5 for a single
        population and 3 for a national plan.
    jurisdiction_pruids:
        Optional province/territory PRUIDs selecting completed subsets from a
        partial national plan. Omit for a single population or complete plan.
    geography_universe:
        Optional explicit Census vintage, level, namespace, and identifier
        column embedded in the self-contained map.

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
    from synthpopcan.map_render import render_national_plan_map, render_synthesis_map

    national_plan_path: Path | None = None
    if isinstance(households, str | Path):
        input_path = Path(households)
        candidate = input_path / "plan.json" if input_path.is_dir() else input_path
        if candidate.is_file() and candidate.name == "plan.json":
            national_plan_path = candidate
    if national_plan_path is not None:
        if persons is not None:
            raise ValueError(
                "persons must be omitted when households is a national plan"
            )
        if any(
            value is not None
            for value in (boundaries, geography_column, geography_id_field)
        ):
            raise ValueError(
                "boundaries and geography arguments are inferred from a national plan"
            )
        payload = json.loads(national_plan_path.read_text())
        geography = payload.get("geography") if isinstance(payload, Mapping) else None
        if not isinstance(geography, Mapping):
            raise ValueError("national small-area plan geography is invalid")
        geography_level = geography.get("geography_level")
        identifier_column = geography.get("identifier_column")
        if not isinstance(geography_level, str) or not geography_level:
            raise ValueError("national small-area plan geography level is invalid")
        if not isinstance(identifier_column, str) or not identifier_column:
            raise ValueError("national small-area plan identifier column is invalid")
        out_path = (
            Path(out)
            if out is not None
            else national_plan_path.parent / "national-map.html"
        )
        if jurisdiction_pruids is not None:
            render_national_plan_map(
                plan_path=national_plan_path,
                geography_level=geography_level,
                geography_column=identifier_column,
                out_path=out_path,
                coord_precision=3 if coord_precision is None else coord_precision,
                title=title or "National Synthetic Population",
                jurisdiction_pruids=frozenset(jurisdiction_pruids),
            )
        else:
            render_national_plan_map(
                plan_path=national_plan_path,
                geography_level=geography_level,
                geography_column=identifier_column,
                out_path=out_path,
                coord_precision=3 if coord_precision is None else coord_precision,
                title=title or "National Synthetic Population",
            )
        return out_path

    if isinstance(households, SmallAreaResult):
        if persons is not None:
            raise ValueError(
                "persons must be omitted when households contains paired files"
            )
        household_path = households.population.households
        person_path = households.population.persons
    elif isinstance(households, LinkedPopulationFiles):
        if persons is not None:
            raise ValueError(
                "persons must be omitted when households contains paired files"
            )
        household_path = households.households
        person_path = households.persons
    elif isinstance(households, str | Path):
        household_path = Path(households)
        person_path = Path(persons) if persons is not None else None
    else:  # pragma: no cover - guarded by the public type annotation
        raise TypeError("households must be a result, paired files, or a CSV path")

    if boundaries is None:
        raise ValueError("boundaries is required for a household CSV")
    if geography_column is None:
        raise ValueError("geography_column is required for a household CSV")
    if geography_id_field is None:
        raise ValueError("geography_id_field is required for a household CSV")
    out_path = (
        Path(out)
        if out is not None
        else household_path.parent / f"{household_path.stem}-map.html"
    )

    return render_synthesis_map(
        households_path=household_path,
        persons_path=person_path,
        boundaries_path=Path(boundaries),
        geography_column=geography_column,
        geography_id_field=geography_id_field,
        out_path=out_path,
        title=title or "Synthetic Population",
        coord_precision=5 if coord_precision is None else coord_precision,
        geography_context=(
            GeographyUniverse.from_dict(geography_universe).as_dict()
            if isinstance(geography_universe, Mapping)
            else (
                geography_universe.as_dict() if geography_universe is not None else None
            )
        ),
    )


def _seed_records(seed: _SeedInput) -> Sequence[Mapping[str, object]]:
    if isinstance(seed, str | Path):
        return read_seed(seed)
    return list(seed)


def _control_margins(controls: _ControlInput) -> list[IPFMargin]:
    if isinstance(controls, str | Path):
        return read_controls(controls).to_ipf_margins()
    return controls.to_ipf_margins()


def _linked_population_files(
    population: LinkedPopulationFiles | str | Path,
) -> LinkedPopulationFiles:
    if isinstance(population, LinkedPopulationFiles):
        return population
    directory = Path(population)
    return LinkedPopulationFiles(
        households=directory / "households.csv",
        persons=directory / "persons.csv",
        manifest=(
            directory / "manifest.json"
            if (directory / "manifest.json").is_file()
            else None
        ),
    )


def _validate_linked_population_files(files: LinkedPopulationFiles) -> None:
    for label, path in (
        ("household", files.households),
        ("person", files.persons),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"linked population {label} CSV not found: {path}")


def _control_table_path(
    controls: str | Path | ControlTable,
    output_path: Path,
) -> Path:
    if isinstance(controls, str | Path):
        return Path(controls)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_control_table(output_path, controls)
    return output_path


def _model_package(package: _ModelPackageInput) -> dict[str, Any]:
    if isinstance(package, str | Path):
        return read_model_package(package)
    payload = dict(package)
    _validate_model_package_schema(payload)
    return payload


def _validate_model_package_schema(package: Mapping[str, object]) -> None:
    if package.get("schema_version") != "synthpopcan-linked-tree-package-v1":
        raise ValueError("unsupported linked model package schema")


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
