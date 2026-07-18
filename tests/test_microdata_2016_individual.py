"""Tests for the explicit 2016 Census individuals PUMF adapter."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click
import pytest

from synthpopcan.cli import main
from synthpopcan.microdata import (
    export_training_rows,
    inspect_statcan_microdata,
    read_statcan_2016_individual_seed_sample,
)


def _write_individual(path: Path) -> None:
    path.write_text(
        "PPSORT,PR,CMA,AGEGRP,Sex,WEIGHT\n1,24,462,11,1,37.5\n2,35,535,13,2,42.0\n"
    )


def test_reads_inspects_and_exports_2016_individual_pumf(tmp_path: Path) -> None:
    source = tmp_path / "individual-2016.csv"
    _write_individual(source)

    sample = read_statcan_2016_individual_seed_sample(
        source,
        columns=("PR", "AGEGRP", "Sex"),
    )
    inspection = inspect_statcan_microdata(
        source,
        source_format="statcan-2016-individual",
    )
    rows, summary = export_training_rows(
        sample,
        level="person",
        target_columns=("AGEGRP", "Sex"),
        conditioning_columns=("PR",),
    )

    assert sample.source_format == "statcan-2016-individual"
    assert sample.metadata["census_year"] == 2016
    assert sample.metadata["linked_households"] is False
    assert inspection["census_year"] == 2016
    assert inspection["records"] == 2
    assert rows[0] == {
        "PPSORT": "1",
        "PR": "24",
        "AGEGRP": "11",
        "Sex": "1",
        "WEIGHT": "37.5",
    }
    assert summary["id_columns"] == ["PPSORT"]
    with pytest.raises(ValueError, match="only person-level"):
        export_training_rows(
            sample,
            level="household",
            target_columns=("AGEGRP",),
            conditioning_columns=("PR",),
        )


def test_cli_uses_explicit_2016_individual_format(tmp_path: Path, capsys) -> None:
    source = tmp_path / "individual-2016.csv"
    training = tmp_path / "person-training.csv"
    _write_individual(source)

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "statcan-2016-individual",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["census_year"] == 2016

    assert (
        main(
            [
                "microdata",
                "export-training",
                str(source),
                "--input-format",
                "statcan-2016-individual",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,Sex",
                "--conditioning-columns",
                "PR",
                "--out",
                str(training),
                "--format",
                "json",
            ]
        )
        == 0
    )
    with training.open(newline="") as handle:
        assert list(csv.DictReader(handle))[0]["PPSORT"] == "1"

    with pytest.raises(click.ClickException, match="cannot produce household"):
        main(
            [
                "microdata",
                "export-seed",
                str(source),
                "--input-format",
                "statcan-2016-individual",
                "--level",
                "household",
                "--columns",
                "AGEGRP",
                "--out",
                str(tmp_path / "invalid.csv"),
            ]
        )
