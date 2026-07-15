"""Versioned public-data reference workflow correctness checks."""

from __future__ import annotations

import csv
from pathlib import Path
from zipfile import ZipFile

from synthpopcan.controls import (
    read_category_mapping,
    read_wds_control_table,
    read_wds_selection,
    write_control_table,
)
from synthpopcan.ipf import fit_ipf

FIXTURE = Path("tests/fixtures/correctness/statcan_17100005_yukon_2025")


def test_pinned_statcan_wds_slice_matches_independent_expected_controls(
    tmp_path: Path,
) -> None:
    with (FIXTURE / "source.csv").open(newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    assert [(row["VECTOR"], int(row["VALUE"])) for row in source_rows] == [
        ("v470185", 231),
        ("v470186", 210),
    ]
    assert sum(int(row["VALUE"]) for row in source_rows) == 441

    source_zip = tmp_path / "17100005-eng.zip"
    with ZipFile(source_zip, "w") as archive:
        archive.write(FIXTURE / "source.csv", "17100005.csv")
    controls = read_wds_control_table(
        source_zip,
        dimensions=("Gender", "Age group"),
        count_column="VALUE",
        margin_name="population",
        category_mapping=read_category_mapping(FIXTURE / "mapping.json"),
        selection=read_wds_selection(FIXTURE / "selection.json"),
    )
    actual_controls = tmp_path / "controls.csv"
    write_control_table(actual_controls, controls)

    assert (
        actual_controls.read_text() == (FIXTURE / "expected-controls.csv").read_text()
    )

    seed = [
        {"Gender": "M", "Age group": "age_000"},
        {"Gender": "F", "Age group": "age_000"},
    ]
    result = fit_ipf(seed, controls.to_ipf_margins(), tolerance=1e-12)
    assert result.converged
    assert result.weights == [231.0, 210.0]
    assert sum(result.weights) == 441.0
