import csv
from pathlib import Path

import pytest

from synthpopcan.ipf import IPFMargin, fit_ipf


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


def test_cli_runs_ipf_from_csv_files(tmp_path: Path) -> None:
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
                "run",
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


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
