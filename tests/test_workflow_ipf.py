from __future__ import annotations

import csv
import json
import shlex
from pathlib import Path

import pytest

from synthpopcan.cli import main
from synthpopcan.workflows.ipf import (
    IPFNonConvergenceError,
    check_ipf_inputs,
    expand_ipf_weights,
    fit_ipf_files,
    validate_ipf_artifact,
)
from synthpopcan.workflows.types import (
    IPFExpandRequest,
    IPFFitRequest,
    IPFValidationRequest,
    WorkflowProgress,
)


def test_file_backed_ipf_workflow_matches_cli_artifacts_byte_for_byte(
    tmp_path: Path,
) -> None:
    seed_path, controls_path = write_ipf_inputs(tmp_path)
    workflow_weights = tmp_path / "workflow-weights.csv"
    workflow_report = tmp_path / "workflow-report.json"
    cli_weights = tmp_path / "cli-weights.csv"
    cli_report = tmp_path / "cli-report.json"

    workflow_result = fit_ipf_files(
        IPFFitRequest(
            seed_path=seed_path,
            controls_path=controls_path,
            output_path=workflow_weights,
            report_path=workflow_report,
        )
    )
    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(cli_weights),
                "--report",
                str(cli_report),
            ]
        )
        == 0
    )

    assert workflow_weights.read_bytes() == cli_weights.read_bytes()
    assert workflow_report.read_bytes() == cli_report.read_bytes()
    assert workflow_result.report == json.loads(workflow_report.read_text())


def test_ipf_workflow_reports_structured_progress_and_reproduction(
    tmp_path: Path,
) -> None:
    spaced_root = tmp_path / "directory with spaces"
    spaced_root.mkdir()
    seed_path, controls_path = write_ipf_inputs(spaced_root)
    request = IPFFitRequest(
        seed_path=seed_path,
        controls_path=controls_path,
        output_path=spaced_root / "weights.csv",
        weight_column="starting_weight",
        max_iterations=25,
        tolerance=1e-8,
        allow_nonconverged=True,
        report_path=spaced_root / "report.json",
    )
    events: list[WorkflowProgress] = []

    result = fit_ipf_files(request, progress=events.append)

    assert [event.stage for event in events] == [
        "reading-inputs",
        "fitting",
        "writing-report",
        "writing-artifacts",
        "completed",
    ]
    assert events[0].as_dict() == {
        "stage": "reading-inputs",
        "message": "Reading seed records and controls",
        "completed": None,
        "total": None,
    }
    assert result.reproduction.request == request.as_dict()
    assert result.reproduction.command.as_dict() == {
        "program": "synthpopcan",
        "arguments": [
            "ipf",
            "fit",
            "--seed",
            str(seed_path),
            "--controls",
            str(controls_path),
            "--out",
            str(spaced_root / "weights.csv"),
            "--weight-column",
            "starting_weight",
            "--max-iterations",
            "25",
            "--tolerance",
            "1e-08",
            "--allow-nonconverged",
            "--report",
            str(spaced_root / "report.json"),
        ],
    }
    assert result.reproduction.as_dict()["shell"] == (
        result.reproduction.command.render()
    )
    assert shlex.split(result.reproduction.command.render()) == [
        "synthpopcan",
        *result.reproduction.command.arguments,
    ]
    request.output_path.unlink()
    assert request.report_path is not None
    request.report_path.unlink()
    rendered_arguments = shlex.split(result.reproduction.command.render())
    assert main(rendered_arguments[1:]) == 0
    assert request.output_path.is_file()
    assert request.report_path.is_file()


def test_ipf_nonconvergence_preserves_report_without_publishing_weights(
    tmp_path: Path,
) -> None:
    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"
    report_path = tmp_path / "report.json"
    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "50",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "80",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "20",
            },
        ],
    )

    with pytest.raises(IPFNonConvergenceError) as exc_info:
        fit_ipf_files(
            IPFFitRequest(
                seed_path=seed_path,
                controls_path=controls_path,
                output_path=output_path,
                max_iterations=2,
                report_path=report_path,
            )
        )

    assert exc_info.value.report["converged"] is False
    assert json.loads(report_path.read_text()) == exc_info.value.report
    assert not output_path.exists()


def test_ipf_check_expand_and_validation_workflows_compose(tmp_path: Path) -> None:
    seed_path, controls_path = write_ipf_inputs(tmp_path)
    weights_path = tmp_path / "weights.csv"
    population_path = tmp_path / "population.csv"

    input_report = check_ipf_inputs(seed_path, controls_path)
    fit_ipf_files(
        IPFFitRequest(
            seed_path=seed_path,
            controls_path=controls_path,
            output_path=weights_path,
        )
    )
    expansion = expand_ipf_weights(
        IPFExpandRequest(weights_path=weights_path, output_path=population_path)
    )
    validation = validate_ipf_artifact(
        IPFValidationRequest(
            population_path=population_path,
            controls_path=controls_path,
            artifact_kind="expanded",
        )
    )

    assert input_report["passed"] is True
    assert expansion.output_rows == 100
    assert validation.report["passed"] is True
    assert validation.report["population_records"] == 100
    assert expansion.reproduction.command.render().startswith("synthpopcan ipf expand")
    assert validation.reproduction.command.render().startswith(
        "synthpopcan validate ipf"
    )


def write_ipf_inputs(root: Path) -> tuple[Path, Path]:
    seed_path = root / "seed.csv"
    controls_path = root / "controls.csv"
    write_csv(
        seed_path,
        ["id", "age", "sex", "starting_weight"],
        [
            {"id": "1", "age": "young", "sex": "F", "starting_weight": "1"},
            {"id": "2", "age": "young", "sex": "M", "starting_weight": "1"},
            {"id": "3", "age": "old", "sex": "F", "starting_weight": "1"},
            {"id": "4", "age": "old", "sex": "M", "starting_weight": "1"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "60",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "40",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "50",
            },
        ],
    )
    return seed_path, controls_path


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
