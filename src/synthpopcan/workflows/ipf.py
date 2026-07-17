"""File-backed IPF workflows shared by command-line and HTTP adapters."""

from __future__ import annotations

__all__ = [
    "IPFNonConvergenceError",
    "check_ipf_inputs",
    "expand_ipf_weights",
    "fit_ipf_files",
    "read_csv_records",
    "read_population_artifact",
    "read_weighted_seed",
    "validate_ipf_artifact",
    "write_expanded_seed",
    "write_weighted_seed",
]

import csv
import json
from pathlib import Path
from typing import Any

from synthpopcan.controls import read_control_table
from synthpopcan.diagnostics import build_ipf_fit_report, build_ipf_input_report
from synthpopcan.ipf import fit_ipf, integerize_weights
from synthpopcan.tabular import format_csv_number
from synthpopcan.validation import build_control_validation_report
from synthpopcan.workflows.types import (
    IPFExpandRequest,
    IPFExpandResult,
    IPFFitRequest,
    IPFFitResult,
    IPFValidationRequest,
    IPFValidationResult,
    ProgressReporter,
    WorkflowProgress,
)


class IPFNonConvergenceError(RuntimeError):
    """Raised after diagnostics are available but before weights are written."""

    def __init__(self, report: dict[str, Any]) -> None:
        super().__init__("IPF did not converge")
        self.report = report


def check_ipf_inputs(
    seed_path: Path,
    controls_path: Path,
    *,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    """Read and diagnose file-backed IPF inputs without fitting."""
    _emit(progress, "reading-inputs", "Reading seed records and controls")
    seed_rows = read_csv_records(seed_path)
    control_table = read_control_table(controls_path)
    _emit(progress, "checking-inputs", "Checking IPF input coverage")
    report = build_ipf_input_report(seed_rows, control_table)
    _emit(progress, "completed", "IPF input checks completed")
    return report


def fit_ipf_files(
    request: IPFFitRequest,
    *,
    progress: ProgressReporter | None = None,
) -> IPFFitResult:
    """Fit IPF from CSV files and write compact fitted weights and diagnostics."""
    _emit(progress, "reading-inputs", "Reading seed records and controls")
    seed_rows = read_csv_records(request.seed_path)
    control_table = read_control_table(request.controls_path)
    _emit(progress, "fitting", "Fitting seed weights to control margins")
    result = fit_ipf(
        seed_rows,
        control_table.to_ipf_margins(),
        weight_field=request.weight_column,
        max_iterations=request.max_iterations,
        tolerance=request.tolerance,
    )
    report = build_ipf_fit_report(control_table, result)
    if request.report_path is not None:
        _emit(progress, "writing-report", "Writing IPF fit diagnostics")
        request.report_path.write_text(json.dumps(report, indent=2) + "\n")
    if not result.converged and not request.allow_nonconverged:
        raise IPFNonConvergenceError(report)
    _emit(progress, "writing-artifacts", "Writing compact fitted weights")
    write_weighted_seed(request.output_path, seed_rows, result.weights)
    _emit(progress, "completed", "IPF fitting completed")
    return IPFFitResult(
        output_path=request.output_path,
        report_path=request.report_path,
        report=report,
        reproduction=request.reproduction(),
    )


def expand_ipf_weights(
    request: IPFExpandRequest,
    *,
    progress: ProgressReporter | None = None,
) -> IPFExpandResult:
    """Stream an expanded synthetic CSV from compact fitted weights."""
    _emit(progress, "reading-inputs", "Reading fitted seed weights")
    seed_rows, weights = read_weighted_seed(request.weights_path, request.weight_column)
    _emit(progress, "writing-artifacts", "Writing expanded synthetic records")
    output_rows = write_expanded_seed(request.output_path, seed_rows, weights)
    _emit(
        progress,
        "completed",
        "IPF expansion completed",
        completed=output_rows,
        total=output_rows,
    )
    return IPFExpandResult(
        output_path=request.output_path,
        output_rows=output_rows,
        reproduction=request.reproduction(),
    )


def validate_ipf_artifact(
    request: IPFValidationRequest,
    *,
    progress: ProgressReporter | None = None,
) -> IPFValidationResult:
    """Validate a weighted or expanded population against its controls."""
    _emit(progress, "reading-inputs", "Reading population artifact and controls")
    control_table = read_control_table(request.controls_path)
    rows, weights = read_population_artifact(
        request.population_path,
        request.artifact_kind,
        request.weight_column,
    )
    _emit(progress, "validating", "Validating population against controls")
    report = build_control_validation_report(
        control_table,
        rows,
        weights,
        tolerance=request.tolerance,
        artifact_kind=request.artifact_kind,
    )
    _emit(progress, "completed", "IPF validation completed")
    return IPFValidationResult(report=report, reproduction=request.reproduction())


def read_csv_records(path: Path) -> list[dict[str, str]]:
    """Read a CSV file as string-valued row dictionaries."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_weighted_seed(
    path: Path, weight_field: str
) -> tuple[list[dict[str, str]], list[float]]:
    """Read compact weighted IPF output into seed rows and fitted weights."""
    rows: list[dict[str, str]] = []
    weights: list[float] = []
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            selected_weight_field = (
                "fitted_weight"
                if weight_field == "weight" and "fitted_weight" in row
                else weight_field
            )
            try:
                weight_value = row.pop(selected_weight_field)
            except KeyError as exc:
                raise ValueError(
                    f"weights CSV requires a {weight_field!r} column"
                ) from exc
            try:
                weights.append(float(weight_value))
            except ValueError as exc:
                raise ValueError(
                    f"weights row {row_number} has invalid weight"
                ) from exc
            rows.append(row)
    return rows, weights


def read_population_artifact(
    path: Path,
    artifact_kind: str,
    weight_field: str,
) -> tuple[list[dict[str, str]], list[float]]:
    """Read a weighted or expanded population artifact for validation."""
    if artifact_kind == "weights":
        return read_weighted_seed(path, weight_field)
    if artifact_kind == "expanded":
        rows = read_csv_records(path)
        return rows, [1.0 for _row in rows]
    raise ValueError(f"unknown population artifact kind {artifact_kind!r}")


def write_weighted_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> None:
    """Write seed rows plus fitted IPF weights as compact output."""
    if not rows:
        raise ValueError("cannot write weighted output for empty seed rows")
    weight_column = "weight" if "weight" not in rows[0] else "fitted_weight"
    fieldnames = [*rows[0].keys(), weight_column]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, weight in zip(rows, weights, strict=True):
            writer.writerow({**row, weight_column: format_csv_number(weight)})


def write_expanded_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> int:
    """Write expanded records incrementally and return the emitted row count."""
    counts = integerize_weights(weights)
    output_rows = sum(counts)
    if output_rows == 0:
        raise ValueError("expanded synthetic population is empty")
    fieldnames = [
        "synthetic_id",
        "seed_id",
        *(field for field in rows[0] if field != "id"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        synthetic_id = 1
        for source_index, row in enumerate(rows, start=1):
            seed_id = str(row.get("id", source_index))
            attributes = {key: value for key, value in row.items() if key != "id"}
            for _ in range(counts[source_index - 1]):
                writer.writerow(
                    {
                        "synthetic_id": str(synthetic_id),
                        "seed_id": seed_id,
                        **attributes,
                    }
                )
                synthetic_id += 1
    return output_rows


def _emit(
    progress: ProgressReporter | None,
    stage: str,
    message: str,
    *,
    completed: int | None = None,
    total: int | None = None,
) -> None:
    if progress is not None:
        progress(
            WorkflowProgress(
                stage=stage,
                message=message,
                completed=completed,
                total=total,
            )
        )
