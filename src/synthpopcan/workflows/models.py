"""File-backed prepared-model workflows shared by all adapters."""

from __future__ import annotations

__all__ = [
    "LOCAL_RUN_MAX_HOUSEHOLDS",
    "LOCAL_RUN_MAX_PERSONS",
    "PreparedModelPackageError",
    "PreparedModelRequest",
    "ResolvedPreparedModel",
    "PreparedModelResult",
    "generate_prepared_model_files",
    "inspect_prepared_model",
    "normalize_prepared_model_package",
    "prepared_model_models",
    "read_prepared_model_package",
    "resolve_prepared_model_package",
    "tree_model_from_prepared_payload",
    "validate_prepared_model_package_schema",
    "validate_prepared_model_publishable",
]

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from synthpopcan.linked_schema import build_linked_population_contract
from synthpopcan.model_licensing import normalize_prepared_model_licensing
from synthpopcan.models import model_payload
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
_PREPARED_MODEL_SCHEMA_VERSION = "synthpopcan-linked-tree-package-v1"

PreparedModelErrorReason = Literal[
    "missing-model-collection",
    "missing-model-pair",
    "not-json-object",
    "unpublishable",
    "unsupported-model-type",
    "unsupported-schema",
]


class PreparedModelPackageError(ValueError):
    """A classified prepared-model contract failure.

    Adapters use :attr:`reason` only to preserve their established user-facing
    wording. Package interpretation and model conversion remain centralized in
    this workflow module.
    """

    def __init__(self, reason: PreparedModelErrorReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class ResolvedPreparedModel:
    """A normalized package plus its user-facing and on-disk identities."""

    package: dict[str, Any]
    label: str
    source_path: Path | None


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
    output_dir_reference: str | None = None

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
        output_dir = self.output_dir_reference or str(self.households_path.parent)
        arguments.extend(("--out", output_dir))
        output_paths = (
            {
                "households": str(Path(output_dir) / "households.csv"),
                "persons": str(Path(output_dir) / "persons.csv"),
                "report": str(Path(output_dir) / "generation-report.json"),
            }
            if self.output_dir_reference is not None
            else {
                "households": str(self.households_path),
                "persons": str(self.persons_path),
                "report": str(self.report_path),
            }
        )
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
                "outputs": output_paths,
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


def read_prepared_model_package(
    path: Path,
    *,
    object_label: str = "linked model package",
) -> dict[str, Any]:
    """Read, validate, and normalize one linked model package JSON object."""

    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise PreparedModelPackageError(
            "not-json-object",
            f"{object_label} must be a JSON object",
        )
    return normalize_prepared_model_package(payload)


def normalize_prepared_model_package(
    package: Mapping[str, object],
) -> dict[str, Any]:
    """Validate package identity and return its normalized licensing contract."""

    validate_prepared_model_package_schema(package)
    return normalize_prepared_model_licensing(package)


def validate_prepared_model_package_schema(package: Mapping[str, object]) -> None:
    """Reject package mappings outside the supported linked-tree schema."""

    if package.get("schema_version") != _PREPARED_MODEL_SCHEMA_VERSION:
        raise PreparedModelPackageError(
            "unsupported-schema",
            "unsupported linked model package schema",
        )


def resolve_prepared_model_package(package_path_or_id: str) -> ResolvedPreparedModel:
    """Resolve a local package path or a registered model ID once.

    Values that look path-like retain the CLI's fail-closed path semantics: a
    missing ``model.json`` is a missing file, not an attempted catalogue ID.
    """

    package_path = Path(package_path_or_id)
    if (
        package_path.exists()
        or package_path.is_absolute()
        or len(package_path.parts) > 1
        or package_path.suffix
    ):
        return ResolvedPreparedModel(
            package=read_prepared_model_package(package_path),
            label=str(package_path),
            source_path=package_path,
        )
    try:
        package = model_payload(package_path_or_id)
    except KeyError as exc:
        raise ValueError(
            f"linked package not found: {package_path_or_id}. Use a package JSON "
            "path or a model ID from `synthpopcan models list`."
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return ResolvedPreparedModel(
        package=normalize_prepared_model_package(package),
        label=package_path_or_id,
        source_path=None,
    )


def validate_prepared_model_publishable(package: Mapping[str, object]) -> None:
    """Require the package's explicit publishable-candidate privacy decision."""

    privacy = package.get("privacy")
    if (
        not isinstance(privacy, Mapping)
        or privacy.get("publishable_candidate") is not True
    ):
        raise PreparedModelPackageError(
            "unpublishable",
            "linked package is not marked as a publishable candidate; inspect the "
            "package before generating from it",
        )


def prepared_model_models(package: Mapping[str, object]) -> tuple[TreeModel, TreeModel]:
    """Convert the linked package's household and person model payloads."""

    models = package.get("models")
    if not isinstance(models, Mapping):
        raise PreparedModelPackageError(
            "missing-model-collection",
            "linked model package must include models",
        )
    household_model = tree_model_from_prepared_payload(models.get("household"))
    person_model = tree_model_from_prepared_payload(models.get("person"))
    return household_model, person_model


def tree_model_from_prepared_payload(payload: object) -> TreeModel:
    """Convert one supported prepared-model payload to its runtime tree model."""

    if not isinstance(payload, dict):
        raise PreparedModelPackageError(
            "missing-model-pair",
            "linked model package must include household and person models",
        )
    model_type = payload.get("model_type")
    if model_type == "conditional-frequency":
        return FrequencyTreeModel.from_dict(payload)
    if model_type == "cart":
        return CartTreeModel.from_dict(payload)
    raise PreparedModelPackageError(
        "unsupported-model-type",
        "unsupported tree model type in linked package",
    )


def inspect_prepared_model(package: dict[str, Any]) -> dict[str, Any]:
    """Return generation readiness, provenance, privacy, and model dimensions."""
    package = normalize_prepared_model_package(package)
    privacy = _object(package.get("privacy"))
    if privacy.get("publishable_candidate") is not True:
        raise ValueError("linked model package is not a publishable candidate")
    try:
        household_model, person_model = prepared_model_models(package)
    except PreparedModelPackageError as exc:
        if exc.reason in {
            "missing-model-collection",
            "missing-model-pair",
            "unsupported-model-type",
        }:
            raise ValueError(
                "linked package must include supported household and person models"
            ) from exc
        raise
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
        "licensing": package["licensing"],
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
    household_model, person_model = prepared_model_models(package)
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
            licensing=package["licensing"],
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
