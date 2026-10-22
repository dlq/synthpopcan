"""Transport-independent preflight for linked small-area runs."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from synthpopcan._runtime_schemas import (
    SmallAreaRunInputs,
    SmallAreaRunOptions,
    SmallAreaRunRequest,
)
from synthpopcan.control_packs import (
    ControlPackEvidence,
    ControlPackManifest,
    load_compatibility_registry,
    load_control_pack,
    load_control_pack_evidence,
    plan_control_pack,
    validate_control_pack_compatibility,
)
from synthpopcan.control_packs import (
    validate_control_pack_evidence_binding as _validate_control_pack_evidence_binding,
)
from synthpopcan.control_packs import (
    validate_control_pack_tables as _validate_control_pack_tables,
)
from synthpopcan.controls import ControlTable, read_control_table
from synthpopcan.geography import GeographyUniverse, statcan_geography_universe
from synthpopcan.models import model_payload
from synthpopcan.small_area_synthesis import estimate_small_area_run
from synthpopcan.tree import validate_linked_population_files
from synthpopcan.workflows.models import (
    LOCAL_RUN_MAX_HOUSEHOLDS,
    inspect_prepared_model,
    read_prepared_model_package,
)


class PreflightWorkspace(Protocol):
    root: Path

    def upload_path(
        self, upload_id: str, *, require_unclaimed: bool = False
    ) -> Path: ...


@dataclass(frozen=True)
class _Source:
    inputs: dict[str, str]
    inspection: dict[str, Any]
    package: dict[str, Any] | None
    households_path: Path | None
    persons_path: Path | None
    validation: dict[str, Any] | None


@dataclass(frozen=True)
class _Controls:
    inputs: dict[str, str]
    households: ControlTable
    persons: ControlTable | None
    pack: ControlPackManifest | None
    evidence: ControlPackEvidence | None
    boundaries_id: str | None


@dataclass(frozen=True)
class SmallAreaPreflightResult:
    ready: bool
    request: dict[str, Any]
    model_diagnostics: dict[str, Any]
    estimate: dict[str, Any]
    control_pack_plan: dict[str, Any] | None
    expected_artifacts: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Render the established HTTP/durable request representation."""
        return {
            "ready": self.ready,
            "request": self.request,
            "model_diagnostics": self.model_diagnostics,
            "estimate": self.estimate,
            "control_pack_plan": self.control_pack_plan,
            "expected_artifacts": self.expected_artifacts,
        }


def _csv_columns(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames
    if fieldnames is None:
        raise ValueError("CSV input has no header row")
    return list(fieldnames)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV input has no header row")
        return [dict(row) for row in reader]


def _pack_derived_dimensions(
    pack: ControlPackManifest,
    entity_level: str,
) -> set[str]:
    registry = load_compatibility_registry()
    controls = {control.identifier: control for control in registry.controls}
    return {
        derivation.output_field
        for margin in pack.margins
        if margin.entity_level == entity_level
        for derivation in controls[margin.control_identifier].candidate_derivations
        if derivation.output_field != derivation.source_field
    }


def _inspection_string_list(
    inspection: dict[str, Any],
    key: str,
) -> list[str]:
    value = inspection.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"model inspection {key} must be a list of strings")
    return value


def _csv_category_support(path: Path, dimensions: set[str]) -> dict[str, set[str]]:
    support = {dimension: set() for dimension in dimensions}
    if not dimensions:
        return support
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = dimensions - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "candidate CSV is missing columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            for dimension in dimensions:
                support[dimension].add(str(row[dimension]))
    return support


def _model_category_support(
    package: dict[str, Any], level: str, dimensions: set[str]
) -> dict[str, set[str]]:
    support = {dimension: set() for dimension in dimensions}
    models = package.get("models")
    model = models.get(level) if isinstance(models, dict) else None
    if not isinstance(model, dict):
        return support

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in support:
                    values = child if isinstance(child, list) else [child]
                    support[key].update(
                        str(item)
                        for item in values
                        if isinstance(item, str | int | float)
                    )
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(model)
    return support


def _unsupported_control_categories(
    controls: Any,
    support: dict[str, set[str]],
    *,
    ignored_dimensions: set[str],
) -> list[str]:
    problems = []
    for dimension in sorted(set(support) - ignored_dimensions):
        requested = controls.categories_for(dimension)
        missing = sorted(requested - support[dimension])
        if missing:
            problems.append(f"{dimension}: {', '.join(missing)}")
    return problems


def _resolve_source(store: PreflightWorkspace, inputs: SmallAreaRunInputs) -> _Source:
    model_id = inputs.model_id
    package_upload_id = inputs.package_upload_id
    candidate_households_id = inputs.candidate_households_upload_id
    candidate_persons_id = inputs.candidate_persons_upload_id
    if model_id and package_upload_id:
        raise ValueError("provide exactly one model_id or package_upload_id")
    has_model_source = bool(model_id) or bool(package_upload_id)
    has_candidate_source = bool(candidate_households_id) and bool(candidate_persons_id)
    if bool(candidate_households_id) != bool(candidate_persons_id):
        raise ValueError("provide both candidate household and person uploads")
    if has_model_source == has_candidate_source:
        raise ValueError("provide one model/package or one linked candidate pair")
    candidate_validation: dict[str, Any] | None = None
    candidate_households_path: Path | None = None
    candidate_persons_path: Path | None = None
    package: dict[str, Any] | None = None
    inspection: dict[str, Any]
    if model_id:
        package = model_payload(str(model_id))
        normalized_inputs: dict[str, str] = {"model_id": str(model_id)}
        inspection = inspect_prepared_model(package)
    elif package_upload_id:
        package_path = store.upload_path(str(package_upload_id), require_unclaimed=True)
        package = read_prepared_model_package(package_path)
        normalized_inputs = {"package_upload_id": str(package_upload_id)}
        inspection = inspect_prepared_model(package)
    else:
        candidate_households_path = store.upload_path(
            str(candidate_households_id), require_unclaimed=True
        )
        candidate_persons_path = store.upload_path(
            str(candidate_persons_id), require_unclaimed=True
        )
        candidate_validation = validate_linked_population_files(
            candidate_households_path, candidate_persons_path
        )
        if not candidate_validation["passed"]:
            raise ValueError("uploaded linked candidates failed validation")
        normalized_inputs = {
            "candidate_households_upload_id": str(candidate_households_id),
            "candidate_persons_upload_id": str(candidate_persons_id),
        }
        inspection = {
            "ready": True,
            "name": "Uploaded linked candidates",
            "conditions": [],
            "household_targets": _csv_columns(candidate_households_path),
            "person_targets": _csv_columns(candidate_persons_path),
            "privacy": {"publishable_candidate": None},
            "provenance": {},
        }

    return _Source(
        normalized_inputs,
        inspection,
        package,
        candidate_households_path,
        candidate_persons_path,
        candidate_validation,
    )


def _load_controls(store: PreflightWorkspace, inputs: SmallAreaRunInputs) -> _Controls:
    normalized_inputs: dict[str, str] = {}
    controls_id = inputs.controls_upload_id
    controls_path = store.upload_path(controls_id, require_unclaimed=True)
    controls = read_control_table(controls_path)
    if not controls.margins:
        raise ValueError("controls CSV has no control rows")
    normalized_inputs["controls_upload_id"] = controls_id
    person_controls_id = inputs.person_controls_upload_id
    person_controls = None
    if person_controls_id:
        person_controls_path = store.upload_path(
            str(person_controls_id), require_unclaimed=True
        )
        person_controls = read_control_table(person_controls_path)
        if not person_controls.margins:
            raise ValueError("person controls CSV has no control rows")
        normalized_inputs["person_controls_upload_id"] = str(person_controls_id)
    control_pack_id = inputs.control_pack_id
    control_pack_evidence_id = inputs.control_pack_evidence_upload_id
    if bool(control_pack_id) != bool(control_pack_evidence_id):
        raise ValueError("select a control pack and upload its evidence JSON")
    control_pack = None
    control_pack_evidence: ControlPackEvidence | None = None
    if control_pack_id:
        if person_controls is None:
            raise ValueError("control packs require a person controls CSV")
        control_pack = load_control_pack(str(control_pack_id))
        evidence_path = store.upload_path(
            str(control_pack_evidence_id), require_unclaimed=True
        )
        control_pack_evidence = load_control_pack_evidence(evidence_path)
        normalized_inputs["control_pack_id"] = control_pack.identifier
        normalized_inputs["control_pack_evidence_upload_id"] = str(
            control_pack_evidence_id
        )
    boundaries_id = inputs.boundaries_upload_id
    if boundaries_id:
        boundaries_path = store.upload_path(str(boundaries_id), require_unclaimed=True)
        boundaries = json.loads(boundaries_path.read_text())
        if (
            not isinstance(boundaries, dict)
            or boundaries.get("type") != "FeatureCollection"
        ):
            raise ValueError("boundaries must be a GeoJSON FeatureCollection")
        normalized_inputs["boundaries_upload_id"] = str(boundaries_id)

    return _Controls(
        normalized_inputs,
        controls,
        person_controls,
        control_pack,
        control_pack_evidence,
        boundaries_id,
    )


def _check_support(
    source: _Source,
    loaded: _Controls,
    options: SmallAreaRunOptions,
    geography_dimension: str,
) -> None:
    inspection = source.inspection
    package = source.package
    candidate_households_path = source.households_path
    controls = loaded.households
    person_controls = loaded.persons
    control_pack = loaded.pack
    conditions = options.conditions
    inspection_conditions = _inspection_string_list(inspection, "conditions")
    inspection_household_targets = _inspection_string_list(
        inspection, "household_targets"
    )
    unsupported = sorted(set(conditions) - set(inspection_conditions))
    if unsupported:
        raise ValueError(
            "unsupported model condition columns: " + ", ".join(unsupported)
        )
    chunk_size = options.chunk_size
    if chunk_size <= 0:
        raise ValueError("chunk size must be positive")
    max_household_size = options.max_household_size
    if max_household_size is not None and max_household_size <= 0:
        raise ValueError("maximum household size must be positive")
    group_column = options.household_size_group_column
    household_columns = {
        *inspection_conditions,
        *inspection_household_targets,
        geography_dimension,
    }
    if control_pack is not None:
        household_columns.update(
            dimension
            for margin in control_pack.margins
            if margin.entity_level == "household"
            for dimension in margin.dimensions
        )
    if max_household_size is not None:
        household_columns.add(group_column)
    unsupported_household_dimensions = sorted(
        {
            dimension
            for margin in controls.margins
            for dimension in margin.dimensions
            if dimension not in household_columns
        }
    )
    if unsupported_household_dimensions:
        raise ValueError(
            "household controls require unsupported candidate columns: "
            + ", ".join(unsupported_household_dimensions)
        )
    controlled_household_dimensions = {
        dimension
        for margin in controls.margins
        for dimension in margin.dimensions
        if dimension != geography_dimension
    }
    derived_household_dimensions = (
        _pack_derived_dimensions(control_pack, "household")
        if control_pack is not None
        else set()
    )
    household_support_dimensions = (
        controlled_household_dimensions - derived_household_dimensions
    )
    if candidate_households_path is not None:
        household_support = _csv_category_support(
            candidate_households_path, household_support_dimensions
        )
    else:
        household_support = _model_category_support(
            package or {}, "household", household_support_dimensions
        )
    unsupported_household_categories = _unsupported_control_categories(
        controls,
        household_support,
        ignored_dimensions=(
            ({group_column} if max_household_size is not None else set())
            | (derived_household_dimensions)
        ),
    )
    if unsupported_household_categories:
        raise ValueError(
            "household controls contain categories absent from candidates: "
            + "; ".join(unsupported_household_categories)
        )
    if person_controls is not None:
        _check_person_support(source, loaded, geography_dimension, household_columns)


def _check_person_support(
    source: _Source,
    loaded: _Controls,
    geography_dimension: str,
    household_columns: set[str],
) -> None:
    person_controls = loaded.persons
    assert person_controls is not None
    control_pack = loaded.pack
    candidate_persons_path = source.persons_path
    package = source.package
    inspection_person_targets = _inspection_string_list(
        source.inspection, "person_targets"
    )
    person_columns = {
        *household_columns,
        *inspection_person_targets,
    }
    if control_pack is not None:
        person_columns.update(
            dimension
            for margin in control_pack.margins
            if margin.entity_level == "person"
            for dimension in margin.dimensions
        )
    unsupported_person_dimensions = sorted(
        {
            dimension
            for margin in person_controls.margins
            for dimension in margin.dimensions
            if dimension not in person_columns
        }
    )
    if unsupported_person_dimensions:
        raise ValueError(
            "person controls require unsupported candidate columns: "
            + ", ".join(unsupported_person_dimensions)
        )
    controlled_person_dimensions = {
        dimension
        for margin in person_controls.margins
        for dimension in margin.dimensions
        if dimension != geography_dimension
    }
    derived_person_dimensions = (
        _pack_derived_dimensions(control_pack, "person")
        if control_pack is not None
        else set()
    )
    person_support_dimensions = controlled_person_dimensions - derived_person_dimensions
    if candidate_persons_path is not None:
        person_support = _csv_category_support(
            candidate_persons_path, person_support_dimensions
        )
    else:
        person_support = _model_category_support(
            package or {}, "person", person_support_dimensions
        )
    unsupported_person_categories = _unsupported_control_categories(
        person_controls,
        person_support,
        ignored_dimensions=(derived_person_dimensions),
    )
    if unsupported_person_categories:
        raise ValueError(
            "person controls contain categories absent from candidates: "
            + "; ".join(unsupported_person_categories)
        )


def _review_geography(
    source: _Source,
    loaded: _Controls,
    options: SmallAreaRunOptions,
    geography_dimension: str,
) -> tuple[str, GeographyUniverse | None, dict[str, Any] | None]:
    inspection_conditions = _inspection_string_list(source.inspection, "conditions")
    inspection_household_targets = _inspection_string_list(
        source.inspection, "household_targets"
    )
    inspection_person_targets = _inspection_string_list(
        source.inspection, "person_targets"
    )
    candidate_households_path = source.households_path
    candidate_persons_path = source.persons_path
    controls = loaded.households
    person_controls = loaded.persons
    control_pack = loaded.pack
    control_pack_evidence = loaded.evidence
    geography_column = options.geography_column or geography_dimension
    geography_payload = options.geography_universe
    if geography_payload is not None:
        if not isinstance(geography_payload, dict):
            raise ValueError("geography_universe must be an object")
        geography_universe = GeographyUniverse.from_dict(geography_payload)
        if geography_universe.identifier_column != geography_column:
            raise ValueError(
                "geography universe identifier column must match geography_column"
            )
    else:
        geography_universe = None
    control_pack_plan: dict[str, Any] | None = None
    if control_pack is not None:
        assert control_pack_evidence is not None
        assert person_controls is not None
        expected_universe = statcan_geography_universe(
            control_pack.census_vintage,
            control_pack.geography_level,
            geography_column,
        )
        if (
            geography_universe is not None
            and geography_universe.canonical_key != expected_universe.canonical_key
        ):
            raise ValueError(
                "geography universe is incompatible with the selected control pack"
            )
        geography_universe = expected_universe
        control_geographies = _validate_control_pack_tables(
            control_pack, controls, person_controls
        )
        _validate_control_pack_evidence_binding(
            control_pack,
            control_pack_evidence,
            controls,
            person_controls,
            control_geographies,
        )
        household_fields = (
            _csv_columns(candidate_households_path)
            if candidate_households_path is not None
            else [*inspection_conditions, *inspection_household_targets]
        )
        person_fields = (
            _csv_columns(candidate_persons_path)
            if candidate_persons_path is not None
            else [*inspection_conditions, *inspection_person_targets]
        )
        compatibility = validate_control_pack_compatibility(
            control_pack,
            census_vintage=control_pack_evidence.census_vintage,
            geography_level=control_pack_evidence.geography_level,
            linked_schema_version=control_pack.linked_schema_version,
            household_fields=household_fields,
            person_fields=person_fields,
        )
        if not compatibility["passed"]:
            raise ValueError(str(compatibility["issues"][0]["message"]))
        if candidate_households_path is not None and candidate_persons_path is not None:
            control_pack_plan = plan_control_pack(
                control_pack,
                _read_csv_rows(candidate_households_path),
                _read_csv_rows(candidate_persons_path),
                controls,
                person_controls,
                evidence=control_pack_evidence,
            )
            if not control_pack_plan["passed"]:
                raise ValueError(str(control_pack_plan["issues"][0]["message"]))
        else:
            control_pack_plan = {
                "schema_version": "synthpopcan-control-pack-web-preflight-v1",
                "passed": True,
                "pack": {
                    "identifier": control_pack.identifier,
                    "definition_sha256": control_pack.definition_sha256,
                    "census_vintage": control_pack.census_vintage,
                    "geography_level": control_pack.geography_level,
                    "identifier_namespace": control_pack.identifier_namespace,
                },
                "compatibility": compatibility,
                "deferred_checks": [
                    "candidate category support after deterministic generation",
                    "post-subsample structural support and whole-household "
                    "contribution",
                ],
            }
    return geography_column, geography_universe, control_pack_plan


def preflight_small_area_run(
    store: PreflightWorkspace, request_data: SmallAreaRunRequest
) -> SmallAreaPreflightResult:
    """Resolve sources, validate support and return a normalized bounded run."""
    inputs = request_data.inputs
    options = request_data.options
    source = _resolve_source(store, inputs)
    loaded = _load_controls(store, inputs)
    normalized_inputs = {**source.inputs, **loaded.inputs}
    inspection = source.inspection
    controls = loaded.households
    control_pack = loaded.pack
    boundaries_id = loaded.boundaries_id
    geography_dimension = options.geography_dimension.strip()
    if not geography_dimension:
        raise ValueError("geography dimension is required")
    if (
        control_pack is not None
        and geography_dimension != control_pack.geography_column
    ):
        raise ValueError(
            f"control pack {control_pack.identifier!r} requires geography "
            f"dimension {control_pack.geography_column!r}"
        )
    candidate_validation = source.validation
    candidate_households = options.candidate_households
    if candidate_validation is not None:
        candidate_households = int(candidate_validation["summary"]["households"])
    if candidate_households <= 0:
        raise ValueError("candidate households must be positive")
    if candidate_households > LOCAL_RUN_MAX_HOUSEHOLDS:
        raise ValueError(
            f"local web runs are limited to {LOCAL_RUN_MAX_HOUSEHOLDS:,} candidate "
            "households; use the CLI for a reviewed larger run"
        )
    pool_size = options.pool_size
    estimate = estimate_small_area_run(
        controls,
        geography_dimension=geography_dimension,
        candidate_households=candidate_households,
        pool_size=pool_size,
        average_persons_per_household=options.average_persons_per_household,
    )
    _check_support(source, loaded, options, geography_dimension)
    estimated_bytes = max(8192, int(estimate["estimated_total_output_rows"]) * 256)
    disk_free = shutil.disk_usage(store.root).free
    enough_disk = disk_free >= estimated_bytes * 2
    geography_column, geography_universe, control_pack_plan = _review_geography(
        source, loaded, options, geography_dimension
    )
    conditions = options.conditions
    max_household_size = options.max_household_size
    group_column = options.household_size_group_column
    chunk_size = options.chunk_size
    normalized_options = {
        "candidate_households": candidate_households,
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "geography_universe": (
            geography_universe.as_dict() if geography_universe is not None else None
        ),
        "conditions": conditions,
        "random_seed": options.random_seed,
        "pool_size": pool_size,
        "subsample_seed": options.subsample_seed,
        "max_household_size": max_household_size,
        "household_size_group_column": group_column,
        "include_weights": options.include_weights,
        "chunk_size": chunk_size,
        "geography_id_field": options.geography_id_field,
        "map_title": options.map_title,
    }
    return SmallAreaPreflightResult(
        **{
            "ready": enough_disk,
            "request": {
                "workflow": "small_area",
                "inputs": normalized_inputs,
                "options": normalized_options,
            },
            "model_diagnostics": inspection,
            "estimate": {
                **estimate,
                "output_bytes": estimated_bytes,
                "disk_free_bytes": disk_free,
                "enough_disk": enough_disk,
            },
            "control_pack_plan": control_pack_plan,
            "expected_artifacts": [
                "households",
                "persons",
                "linked_population_manifest",
                "small_area_report",
                *(["map"] if boundaries_id else []),
            ],
        }
    )
