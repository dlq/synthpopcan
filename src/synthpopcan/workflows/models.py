"""File-backed prepared-model workflows shared by all adapters."""

from __future__ import annotations

__all__ = [
    "LOCAL_RUN_MAX_HOUSEHOLDS",
    "LOCAL_RUN_MAX_PERSONS",
    "PreparedModelRequest",
    "PreparedModelResult",
    "generate_prepared_model_files",
    "inspect_prepared_model",
    "read_prepared_model_package",
]

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.linked_schema import build_linked_population_contract
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    generate_linked_population_to_csv,
    validate_linked_population_files,
)
from synthpopcan.workflows.types import (
    ProgressReporter,
    ReproductionCommand,
    WorkflowProgress,
    WorkflowReproduction,
)

TreeModel = FrequencyTreeModel | CartTreeModel
LOCAL_RUN_MAX_HOUSEHOLDS = 250_000
LOCAL_RUN_MAX_PERSONS = 2_000_000


@dataclass(frozen=True)
class PreparedModelRequest:
    """One deterministic linked household/person generation request."""

    package_path: Path
    households_path: Path
    persons_path: Path
    report_path: Path
    households: int
    conditions: dict[str, str]
    random_seed: int | None = None
    household_size_column: str | None = None
    package_reference: str | None = None
    chunk_size: int = 1000
    max_households: int | None = None
    max_persons: int | None = None

    def reproduction(self) -> WorkflowReproduction:
        reference = self.package_reference or str(self.package_path)
        arguments = [
            "models",
            "generate",
            reference,
            "--households",
            str(self.households),
        ]
        for key, value in sorted(self.conditions.items()):
            arguments.extend(("--condition", f"{key}={value}"))
        if self.random_seed is not None:
            arguments.extend(("--random-seed", str(self.random_seed)))
        if self.household_size_column is not None:
            arguments.extend(("--household-size-column", self.household_size_column))
        arguments.extend(("--out", str(self.households_path.parent)))
        return WorkflowReproduction(
            request={
                "workflow": "model",
                "inputs": {"package": reference},
                "options": {
                    "households": self.households,
                    "conditions": self.conditions,
                    "random_seed": self.random_seed,
                    "household_size_column": self.household_size_column,
                },
                "outputs": {
                    "households": str(self.households_path),
                    "persons": str(self.persons_path),
                    "report": str(self.report_path),
                },
            },
            command=ReproductionCommand("synthpopcan", tuple(arguments)),
        )


@dataclass(frozen=True)
class PreparedModelResult:
    """Paths and diagnostics produced by prepared-model generation."""

    households_path: Path
    persons_path: Path
    report_path: Path
    household_count: int
    person_count: int
    report: dict[str, Any]
    reproduction: WorkflowReproduction


def read_prepared_model_package(path: Path) -> dict[str, Any]:
    """Read and validate one linked model package JSON object."""
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("linked model package must be a JSON object")
    if payload.get("schema_version") != "synthpopcan-linked-tree-package-v1":
        raise ValueError("unsupported linked model package schema")
    return payload


def inspect_prepared_model(package: dict[str, Any]) -> dict[str, Any]:
    """Return generation readiness, provenance, privacy, and model dimensions."""
    if package.get("schema_version") != "synthpopcan-linked-tree-package-v1":
        raise ValueError("unsupported linked model package schema")
    privacy = _object(package.get("privacy"))
    if privacy.get("publishable_candidate") is not True:
        raise ValueError("linked model package is not a publishable candidate")
    models = _object(package.get("models"))
    household_model = _tree_model(_object(models.get("household")))
    person_model = _tree_model(_object(models.get("person")))
    provenance = _object(package.get("source_provenance") or package.get("provenance"))
    catalogue = _object(package.get("catalogue_metadata"))
    return {
        "ready": True,
        "name": (
            package.get("name") or package.get("description") or "Linked model package"
        ),
        "schema_version": package["schema_version"],
        "household_size_column": str(
            package.get("household_size_column") or "household_size"
        ),
        "privacy": {
            "publishable_candidate": True,
            "safe_demo": bool(privacy.get("safe_demo", False)),
            "contains_raw_rows": privacy.get("contains_raw_rows"),
            "contains_source_identifiers": privacy.get("contains_source_identifiers"),
            "review_status": catalogue.get("privacy_review_status"),
        },
        "provenance": {
            "title": provenance.get("title") or provenance.get("training_data"),
            "provider": provenance.get("provider"),
            "access_class": provenance.get("access_class"),
            "citation": provenance.get("citation"),
            "census_vintage": catalogue.get("census_vintage"),
            "release_version": catalogue.get("release_version"),
        },
        "conditions": list(household_model.spec.conditioning_columns),
        "household_targets": list(household_model.spec.target_columns),
        "person_targets": list(person_model.spec.target_columns),
    }


def generate_prepared_model_files(
    request: PreparedModelRequest,
    *,
    progress: ProgressReporter | None = None,
) -> PreparedModelResult:
    """Generate linked CSVs directly to disk and write validation diagnostics."""
    if (
        request.max_households is not None
        and request.households > request.max_households
    ):
        raise ValueError(
            f"generated household limit exceeded ({request.max_households:,})"
        )
    package = read_prepared_model_package(request.package_path)
    inspection = inspect_prepared_model(package)
    models = _object(package["models"])
    household_model = _tree_model(_object(models.get("household")))
    person_model = _tree_model(_object(models.get("person")))
    household_size_column = request.household_size_column or str(
        inspection["household_size_column"]
    )
    _emit(progress, "checking-model", "Checking package provenance and privacy")

    def generation_progress(households: int, persons: int) -> None:
        _emit(
            progress,
            "generating",
            f"Generated {households:,} households and {persons:,} people",
            completed=households,
            total=request.households,
        )

    household_count, person_count = generate_linked_population_to_csv(
        household_model,
        person_model,
        households=request.households,
        households_path=request.households_path,
        persons_path=request.persons_path,
        household_conditions=request.conditions,
        household_size_column=household_size_column,
        random_seed=request.random_seed,
        progress_callback=generation_progress,
        progress_interval=request.chunk_size,
        max_persons=request.max_persons,
    )
    _emit(progress, "validating", "Validating household and person linkage")
    validation = validate_linked_population_files(
        request.households_path,
        request.persons_path,
        household_size_column=household_size_column,
    )
    report = {
        "schema_version": "synthpopcan-prepared-model-report-v1",
        "generated_households": household_count,
        "generated_persons": person_count,
        "household_size_column": household_size_column,
        "conditions": request.conditions,
        "random_seed": request.random_seed,
        "package": inspection,
        "validation": validation,
        "linked_population": build_linked_population_contract(
            request.households_path,
            request.persons_path,
        ),
    }
    request.report_path.write_text(json.dumps(report, indent=2) + "\n")
    _emit(progress, "completed", "Prepared-model generation completed")
    return PreparedModelResult(
        households_path=request.households_path,
        persons_path=request.persons_path,
        report_path=request.report_path,
        household_count=household_count,
        person_count=person_count,
        report=report,
        reproduction=request.reproduction(),
    )


def _tree_model(payload: dict[str, Any]) -> TreeModel:
    model_type = payload.get("model_type")
    if model_type == "conditional-frequency":
        return FrequencyTreeModel.from_dict(payload)
    if model_type == "cart":
        return CartTreeModel.from_dict(payload)
    raise ValueError(
        "linked package must include supported household and person models"
    )


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _emit(
    progress: ProgressReporter | None,
    stage: str,
    message: str,
    *,
    completed: int | None = None,
    total: int | None = None,
) -> None:
    if progress is not None:
        progress(WorkflowProgress(stage, message, completed, total))
