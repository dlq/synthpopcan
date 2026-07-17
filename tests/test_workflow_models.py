from __future__ import annotations

import csv
import json
import shlex
from pathlib import Path

import pytest

from synthpopcan.models import model_payload
from synthpopcan.tree import validate_linked_population_files
from synthpopcan.workflows.models import (
    PreparedModelRequest,
    generate_prepared_model_files,
    inspect_prepared_model,
)


def test_prepared_model_workflow_writes_deterministic_linked_artifacts(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(model_payload("demo-linked-household-person")))
    events = []
    request = PreparedModelRequest(
        package_path=package_path,
        households_path=tmp_path / "households.csv",
        persons_path=tmp_path / "persons.csv",
        report_path=tmp_path / "report.json",
        households=8,
        conditions={"geo": "Demo North"},
        random_seed=13,
        package_reference="demo-linked-household-person",
        chunk_size=2,
    )

    result = generate_prepared_model_files(request, progress=events.append)

    households = list(csv.DictReader(result.households_path.open()))
    persons = list(csv.DictReader(result.persons_path.open()))
    assert len(households) == 8
    assert len(persons) == result.person_count
    assert result.report["validation"]["passed"] is True
    assert {event.stage for event in events} >= {
        "checking-model",
        "generating",
        "validating",
        "completed",
    }
    assert shlex.split(result.reproduction.command.render())[:4] == [
        "synthpopcan",
        "models",
        "generate",
        "demo-linked-household-person",
    ]

    second = generate_prepared_model_files(
        PreparedModelRequest(
            **{
                **request.__dict__,
                "households_path": tmp_path / "households-2.csv",
                "persons_path": tmp_path / "persons-2.csv",
                "report_path": tmp_path / "report-2.json",
                "chunk_size": 3,
            }
        )
    )
    assert second.households_path.read_bytes() == result.households_path.read_bytes()
    assert second.persons_path.read_bytes() == result.persons_path.read_bytes()


def test_prepared_model_inspection_rejects_unpublishable_package() -> None:
    package = model_payload("demo-linked-household-person")
    package["privacy"] = {"publishable_candidate": False}
    with pytest.raises(ValueError, match="publishable candidate"):
        inspect_prepared_model(package)


def test_file_backed_link_validation_reports_errors_and_cleans_scratch(
    tmp_path: Path,
) -> None:
    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    households_path.write_text("synthetic_household_id,household_size\n1,2\n2,1\n")
    persons_path.write_text(
        "synthetic_person_id,synthetic_household_id\n1,1\n1,missing\n"
    )

    report = validate_linked_population_files(households_path, persons_path)

    assert report["passed"] is False
    assert report["summary"] == {
        "households": 2,
        "persons": 2,
        "households_with_size_mismatches": 2,
        "persons_with_unknown_households": 1,
        "issue_count": 4,
        "issue_details_truncated": False,
    }
    assert {issue["kind"] for issue in report["issues"]} == {
        "duplicate_person_identifier",
        "household_size_mismatch",
        "unknown_person_household",
    }
    assert list(tmp_path.glob(".linked-validation-*.sqlite3")) == []
