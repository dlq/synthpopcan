import csv
import json
from pathlib import Path

import pytest

from synthpopcan.ipf import IPFMargin, expand_records, fit_ipf


def test_fit_ipf_matches_two_one_way_margins() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "young", "sex": "M"},
        {"age": "old", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0}),
        IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0}),
    ]

    result = fit_ipf(records, margins, tolerance=1e-9)

    assert result.converged
    assert result.iterations > 0
    assert result.weights == pytest.approx([30.0, 30.0, 20.0, 20.0])
    assert result.margin_totals(("age",)) == pytest.approx(
        {("young",): 60.0, ("old",): 40.0}
    )
    assert result.margin_totals(("sex",)) == pytest.approx({("F",): 50.0, ("M",): 50.0})


def test_fit_ipf_reports_missing_seed_cells() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "old", "sex": "F"},
    ]
    margins = [
        IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0}),
    ]

    with pytest.raises(ValueError, match="no seed records"):
        fit_ipf(records, margins)


def test_expand_records_integerizes_weights_with_seed_ids() -> None:
    records = [
        {"id": "a", "age": "young", "sex": "F"},
        {"id": "b", "age": "old", "sex": "M"},
    ]

    expanded = expand_records(records, [1.2, 2.8])

    assert expanded == [
        {"synthetic_id": "1", "seed_id": "a", "age": "young", "sex": "F"},
        {"synthetic_id": "2", "seed_id": "b", "age": "old", "sex": "M"},
        {"synthetic_id": "3", "seed_id": "b", "age": "old", "sex": "M"},
        {"synthetic_id": "4", "seed_id": "b", "age": "old", "sex": "M"},
    ]


def test_cli_runs_ipf_from_csv_files_as_expanded_synthetic_data(
    tmp_path: Path,
) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
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
                str(weights_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert rows[0] == {
        "synthetic_id": "1",
        "seed_id": "1",
        "age": "young",
        "sex": "F",
    }
    assert len(rows) == 100
    assert count_rows(rows, "age") == {"young": 60, "old": 40}
    assert count_rows(rows, "sex") == {"F": 50, "M": 50}


def test_cli_runs_ipf_from_csv_files_as_weights_by_default(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
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
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert [row["weight"] for row in rows] == ["30", "30", "20", "20"]


def test_cli_fit_writes_diagnostics_report(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
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
                str(output_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )

    report = json.loads(report_path.read_text())
    assert report["converged"] is True
    assert report["iterations"] > 0
    assert report["max_abs_error"] == pytest.approx(0.0)
    assert report["seed_records"] == 4
    assert report["margins"][0] == {
        "name": "age",
        "dimensions": ["age"],
        "cells": [
            {
                "categories": {"age": "young"},
                "target": 60.0,
                "fitted": 60.0,
                "residual": 0.0,
            },
            {
                "categories": {"age": "old"},
                "target": 40.0,
                "fitted": 40.0,
                "residual": 0.0,
            },
        ],
    }


def test_cli_expands_fitted_weight_when_seed_has_initial_weight(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"

    write_csv(
        seed_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "1"},
            {"id": "2", "age": "old", "weight": "1"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "count"],
        [
            {"margin": "age", "dimensions": "age", "age": "young", "count": "10"},
            {"margin": "age", "dimensions": "age", "age": "old", "count": "20"},
        ],
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
                str(weights_path),
                "--weight-field",
                "weight",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert len(rows) == 30
    assert count_rows(rows, "age") == {"young": 10, "old": 20}


def test_cli_expands_rows_without_materializing_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from synthpopcan.cli import main

    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"
    write_csv(
        weights_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "2"},
            {"id": "2", "age": "old", "weight": "1"},
        ],
    )

    def fail_if_materialized(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("expand_records should not be used by CLI expansion")

    monkeypatch.setattr("synthpopcan.ipf.expand_records", fail_if_materialized)

    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert rows == [
        {"synthetic_id": "1", "seed_id": "1", "age": "young"},
        {"synthetic_id": "2", "seed_id": "1", "age": "young"},
        {"synthetic_id": "3", "seed_id": "2", "age": "old"},
    ]


def test_cli_fit_fails_when_ipf_does_not_converge(tmp_path: Path) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"

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

    with pytest.raises(ClickException, match="IPF did not converge"):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(output_path),
                "--max-iterations",
                "2",
            ]
        )
    assert not output_path.exists()


def count_rows(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[field]] = counts.get(row[field], 0) + 1
    return counts


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
