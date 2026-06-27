from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from synthpopcan.cli import main
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    controls_by_geography,
    fit_households_by_geography,
    realize_linked_geography_population,
)
from synthpopcan.tree import (
    TreeModelSpec,
    TreeTrainingSample,
    train_frequency_model,
    write_tree_model,
)


def _train_frequency_model_from_rows(
    spec: TreeModelSpec,
    *,
    rows: tuple[dict[str, str], ...],
):
    source = TreeTrainingSample(
        level=spec.level,
        source_format="csv-v1",
        records=rows,
        columns=(*spec.conditioning_columns, *spec.target_columns),
        target_columns=spec.target_columns,
        conditioning_columns=spec.conditioning_columns,
        geography_column=spec.geography_column,
        weight_column=spec.weight_column,
    )
    return train_frequency_model(source, random_seed=spec.random_seed)


def test_controls_by_geography_removes_target_geography_dimension() -> None:
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size by tenure",
                dimensions=("tract", "household_size", "TENUR"),
                cells=(
                    ControlCell(
                        {
                            "tract": "4620001.00",
                            "household_size": "1",
                            "TENUR": "owner",
                        },
                        10,
                    ),
                    ControlCell(
                        {
                            "tract": "4620001.00",
                            "household_size": "2",
                            "TENUR": "renter",
                        },
                        20,
                    ),
                    ControlCell(
                        {
                            "tract": "4620002.00",
                            "household_size": "1",
                            "TENUR": "owner",
                        },
                        30,
                    ),
                ),
            ),
        ),
        dimensions=("tract", "household_size", "TENUR"),
    )

    grouped = controls_by_geography(controls, geography_dimension="tract")

    assert sorted(grouped) == ["4620001.00", "4620002.00"]
    assert grouped["4620001.00"].dimensions == ("household_size", "TENUR")
    assert grouped["4620001.00"].margins[0].dimensions == (
        "household_size",
        "TENUR",
    )
    assert grouped["4620001.00"].margins[0].cells[0].categories == {
        "household_size": "1",
        "TENUR": "owner",
    }


def test_fit_households_by_geography_returns_weights_for_each_target() -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1", "TENUR": "owner"},
        {"synthetic_household_id": "h2", "household_size": "1", "TENUR": "renter"},
        {"synthetic_household_id": "h3", "household_size": "2", "TENUR": "owner"},
        {"synthetic_household_id": "h4", "household_size": "2", "TENUR": "renter"},
    ]
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("tract", "household_size"),
                cells=(
                    ControlCell({"tract": "4620001.00", "household_size": "1"}, 3),
                    ControlCell({"tract": "4620001.00", "household_size": "2"}, 1),
                    ControlCell({"tract": "4620002.00", "household_size": "1"}, 1),
                    ControlCell({"tract": "4620002.00", "household_size": "2"}, 3),
                ),
            ),
        ),
        dimensions=("tract", "household_size"),
    )

    result = fit_households_by_geography(
        households,
        controls,
        geography_dimension="tract",
        household_id_column="synthetic_household_id",
        max_iterations=50,
        tolerance=1e-9,
    )

    assert set(result.weights_by_geography) == {"4620001.00", "4620002.00"}
    assert result.weights_by_geography["4620001.00"] == [1.5, 1.5, 0.5, 0.5]
    assert result.weights_by_geography["4620002.00"] == [0.5, 0.5, 1.5, 1.5]
    assert result.reports["4620001.00"]["converged"] is True


def test_realize_linked_geography_population_preserves_person_links() -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1", "TENUR": "owner"},
        {"synthetic_household_id": "h2", "household_size": "2", "TENUR": "renter"},
    ]
    persons = [
        {
            "synthetic_person_id": "p1",
            "synthetic_household_id": "h1",
            "AGEGRP": "adult",
        },
        {
            "synthetic_person_id": "p2",
            "synthetic_household_id": "h2",
            "AGEGRP": "adult",
        },
        {
            "synthetic_person_id": "p3",
            "synthetic_household_id": "h2",
            "AGEGRP": "child",
        },
    ]

    assigned_households, assigned_persons = realize_linked_geography_population(
        households,
        persons,
        weights_by_geography={"4620001.00": [1.0, 1.0]},
        geography_column="tract",
        household_id_column="synthetic_household_id",
        person_id_column="synthetic_person_id",
    )

    assert [row["tract"] for row in assigned_households] == [
        "4620001.00",
        "4620001.00",
    ]
    assert [row["synthetic_household_id"] for row in assigned_households] == [
        "4620001.00-1",
        "4620001.00-2",
    ]
    assert {row["synthetic_household_id"] for row in assigned_persons} == {
        "4620001.00-1",
        "4620001.00-2",
    }
    assert len(assigned_persons) == 3


def test_calibrate_linked_household_csvs_writes_outputs(tmp_path: Path) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    controls = tmp_path / "controls.csv"
    out_households = tmp_path / "small-area-households.csv"
    out_persons = tmp_path / "small-area-persons.csv"
    weights = tmp_path / "weights.csv"
    report = tmp_path / "report.json"

    households.write_text(
        "synthetic_household_id,household_size,TENUR\nh1,1,owner\nh2,2,renter\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h2,child\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",4620001.00,1,1\n'
        'size,"tract,household_size",4620001.00,2,1\n'
    )

    summary = calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=out_households,
        persons_out=out_persons,
        weights_out=weights,
        report_out=report,
        max_iterations=50,
        tolerance=1e-9,
    )

    assert summary["assigned_households"] == 2
    assert summary["assigned_persons"] == 3
    assert (
        out_households.read_text().splitlines()[0].startswith("synthetic_household_id,")
    )
    assert "4620001.00" in out_persons.read_text()
    assert weights.read_text().splitlines()[0] == (
        "target_geography,source_candidate_household_id,weight,integer_weight"
    )
    report_data = json.loads(report.read_text())
    assert report_data["summary"]["total_geographies"] == 1
    assert report_data["summary"]["converged_count"] == 1
    assert report_data["summary"]["non_converged_count"] == 0
    assert "margin_summaries" in report_data["geographies"]["4620001.00"]


def test_cli_calibrates_linked_households_to_small_area_controls(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    controls = tmp_path / "controls.csv"
    out_households = tmp_path / "small-area-households.csv"
    out_persons = tmp_path / "small-area-persons.csv"

    households.write_text(
        "synthetic_household_id,household_size,TENUR\nh1,1,owner\nh2,2,renter\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h2,child\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",4620001.00,1,1\n'
        'size,"tract,household_size",4620001.00,2,1\n'
    )

    exit_code = main(
        [
            "geo",
            "calibrate-linked",
            "--households",
            str(households),
            "--persons",
            str(persons),
            "--controls",
            str(controls),
            "--geo-dimension",
            "tract",
            "--geo-column",
            "tract",
            "--households-out",
            str(out_households),
            "--persons-out",
            str(out_persons),
        ]
    )

    assert exit_code == 0
    assert out_households.exists()
    assert out_persons.exists()


def _minimal_calibrate_files(tmp_path: Path) -> dict[str, Path]:
    """Return a dict of minimal CSV paths for the calibrate-linked command."""
    households = tmp_path / "households.csv"
    households.write_text(
        "synthetic_household_id,household_size,TENUR\nh1,1,owner\nh2,2,renter\n"
    )
    persons = tmp_path / "persons.csv"
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\np2,h2,adult\np3,h2,child\n"
    )
    controls = tmp_path / "controls.csv"
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",4620001.00,1,1\n'
        'size,"tract,household_size",4620001.00,2,1\n'
    )
    return {
        "households": households,
        "persons": persons,
        "controls": controls,
        "households_out": tmp_path / "hh-out.csv",
        "persons_out": tmp_path / "p-out.csv",
    }


def test_cli_calibrate_linked_weights_out_and_report_out(tmp_path: Path) -> None:
    f = _minimal_calibrate_files(tmp_path)
    weights = tmp_path / "weights.csv"
    report = tmp_path / "report.json"

    exit_code = main(
        [
            "geo",
            "calibrate-linked",
            "--households",
            str(f["households"]),
            "--persons",
            str(f["persons"]),
            "--controls",
            str(f["controls"]),
            "--geo-dimension",
            "tract",
            "--geo-column",
            "tract",
            "--households-out",
            str(f["households_out"]),
            "--persons-out",
            str(f["persons_out"]),
            "--weights-out",
            str(weights),
            "--report",
            str(report),
        ]
    )

    assert exit_code == 0
    assert weights.exists()
    assert report.exists()


def test_cli_calibrate_linked_format_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json as _json

    f = _minimal_calibrate_files(tmp_path)

    exit_code = main(
        [
            "geo",
            "calibrate-linked",
            "--households",
            str(f["households"]),
            "--persons",
            str(f["persons"]),
            "--controls",
            str(f["controls"]),
            "--geo-dimension",
            "tract",
            "--geo-column",
            "tract",
            "--households-out",
            str(f["households_out"]),
            "--persons-out",
            str(f["persons_out"]),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = _json.loads(out)
    assert "assigned_households" in parsed


def test_cli_calibrate_linked_oserror(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    f = _minimal_calibrate_files(tmp_path)

    with patch(
        "synthpopcan.cli_geo.calibrate_linked_household_csvs",
        side_effect=OSError("no space"),
    ):
        with pytest.raises(click.ClickException, match="no space"):
            main(
                [
                    "geo",
                    "calibrate-linked",
                    "--households",
                    str(f["households"]),
                    "--persons",
                    str(f["persons"]),
                    "--controls",
                    str(f["controls"]),
                    "--geo-dimension",
                    "tract",
                    "--geo-column",
                    "tract",
                    "--households-out",
                    str(f["households_out"]),
                    "--persons-out",
                    str(f["persons_out"]),
                ]
            )


def test_cli_calibrate_linked_value_error(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    f = _minimal_calibrate_files(tmp_path)

    with patch(
        "synthpopcan.cli_geo.calibrate_linked_household_csvs",
        side_effect=ValueError("bad controls"),
    ):
        with pytest.raises(click.ClickException, match="bad controls"):
            main(
                [
                    "geo",
                    "calibrate-linked",
                    "--households",
                    str(f["households"]),
                    "--persons",
                    str(f["persons"]),
                    "--controls",
                    str(f["controls"]),
                    "--geo-dimension",
                    "tract",
                    "--geo-column",
                    "tract",
                    "--households-out",
                    str(f["households_out"]),
                    "--persons-out",
                    str(f["persons_out"]),
                ]
            )


def _write_minimal_linked_package(tmp_path: Path) -> Path:
    household_model = replace(
        _train_frequency_model_from_rows(
            TreeModelSpec(
                level="household",
                target_columns=("household_size", "TENUR"),
                conditioning_columns=("geo",),
                geography_column="geo",
            ),
            rows=({"geo": "QC", "household_size": "1", "TENUR": "owner"},),
        ),
        release_class="publishable_candidate",
    )
    person_model = replace(
        _train_frequency_model_from_rows(
            TreeModelSpec(
                level="person",
                target_columns=("AGEGRP",),
                conditioning_columns=("geo", "household_size", "TENUR"),
                geography_column="geo",
            ),
            rows=(
                {
                    "geo": "QC",
                    "household_size": "1",
                    "TENUR": "owner",
                    "AGEGRP": "adult",
                },
            ),
        ),
        release_class="publishable_candidate",
    )
    hh_path = tmp_path / "hh-model.json"
    p_path = tmp_path / "p-model.json"
    write_tree_model(hh_path, household_model)
    write_tree_model(p_path, person_model)

    training_manifest = tmp_path / "training-manifest.json"
    training_manifest.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-linked-tree-training-v1",
                "source": {
                    "path": "data/private/census.csv",
                    "source_format": "statcan-2016-hierarchical",
                    "records": 10,
                    "households": 5,
                },
                "target_profile": "minimal",
                "geography_filter": {"column": "geo", "value": "QC"},
                "method": "conditional-frequency",
                "random_seed": 7,
                "training": {"household": {"records": 5}, "person": {"records": 5}},
                "models": {
                    "household": {"path": str(hh_path)},
                    "person": {"path": str(p_path)},
                },
            }
        )
    )
    source_provenance = tmp_path / "source-provenance.json"
    source_provenance.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "Test Census",
                "provider": "Statistics Canada",
                "access_class": "restricted",
                "citation": "Statistics Canada. Test.",
                "redistribution_note": "Do not redistribute.",
            }
        )
    )
    package_path = tmp_path / "package.json"
    exit_code = main(
        [
            "tree",
            "package-linked-models",
            "--household-model",
            str(hh_path),
            "--person-model",
            str(p_path),
            "--training-manifest",
            str(training_manifest),
            "--source-provenance",
            str(source_provenance),
            "--review-note",
            "test fixture",
            "--out",
            str(package_path),
            "--min-support",
            "1",
            "--max-purity",
            "1",
        ]
    )
    assert exit_code == 0, "package-linked-models failed"
    return package_path


def test_cli_synthesize_from_package(tmp_path: Path) -> None:
    package_path = _write_minimal_linked_package(tmp_path)
    controls = tmp_path / "controls.csv"
    households_out = tmp_path / "households.csv"
    persons_out = tmp_path / "persons.csv"
    report_out = tmp_path / "report.json"

    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",4620001.00,1,5\n'
        'size,"tract,household_size",4620002.00,1,3\n'
    )

    exit_code = main(
        [
            "geo",
            "synthesize-from-package",
            str(package_path),
            "--households",
            "4",
            "--controls",
            str(controls),
            "--geo-dimension",
            "tract",
            "--geo-column",
            "tract",
            "--households-out",
            str(households_out),
            "--persons-out",
            str(persons_out),
            "--report",
            str(report_out),
        ]
    )

    assert exit_code == 0
    assert households_out.exists()
    assert persons_out.exists()
    report = json.loads(report_out.read_text())
    assert report["summary"]["total_geographies"] == 2
    assert report["summary"]["converged_count"] == 2
    assert report["assigned_households"] == 8
