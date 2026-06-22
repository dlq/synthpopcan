import csv
import json
import shutil
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

from synthpopcan.cli import main
from synthpopcan.tree import (
    TreeModelSpec,
    TreeTrainingSample,
    train_frequency_model,
    write_tree_model,
)


def test_microdata_seed_to_validated_ipf_weights_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    microdata_path = tmp_path / "hierarchical.csv"
    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    microdata_path.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,1,adult,F,owner\n"
        "1,11,111,11102,1,child,M,owner\n"
    )
    controls_path.write_text(
        "margin,dimensions,AGEGRP,SEX,count\n"
        "age,AGEGRP,adult,,100\n"
        "age,AGEGRP,child,,100\n"
        "sex,SEX,,F,100\n"
        "sex,SEX,,M,100\n"
    )

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(seed_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--weight-field",
                "WEIGHT",
                "--out",
                str(weights_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
                "--format",
                "json",
            ]
        )
        == 0
    )

    seed_rows = list(csv.DictReader(seed_path.open(newline="")))
    weight_rows = list(csv.DictReader(weights_path.open(newline="")))
    validation_report = json.loads(capsys.readouterr().out)

    assert seed_rows == [
        {"PP_ID": "11101", "AGEGRP": "adult", "SEX": "F", "WEIGHT": "1"},
        {"PP_ID": "11102", "AGEGRP": "child", "SEX": "M", "WEIGHT": "1"},
    ]
    assert [row["weight"] for row in weight_rows] == ["100", "100"]
    assert json.loads(report_path.read_text())["converged"] is True
    assert validation_report["passed"] is True


def test_tracked_microdata_ipf_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/workflows/microdata_ipf")
    microdata_path = tmp_path / "hierarchical.csv"
    controls_path = tmp_path / "controls.csv"
    seed_path = tmp_path / "seed.csv"
    weights_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    shutil.copyfile(fixture_root / "hierarchical.csv", microdata_path)
    shutil.copyfile(fixture_root / "controls.csv", controls_path)

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(seed_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert seed_path.read_text() == (fixture_root / "expected-seed.csv").read_text()

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--weight-field",
                "WEIGHT",
                "--out",
                str(weights_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True


def test_tracked_wds_ipf_mapping_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/workflows/wds_ipf")
    wds_zip_path = tmp_path / "wds.zip"
    mapping_template_path = tmp_path / "categories-template.json"
    mapping_path = tmp_path / "categories.json"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"
    seed_path = tmp_path / "seed.csv"

    shutil.copyfile(fixture_root / "seed.csv", seed_path)
    shutil.copyfile(fixture_root / "categories-filled.json", mapping_path)
    with ZipFile(wds_zip_path, "w") as archive:
        archive.write(fixture_root / "wds-table.csv", "wds-table.csv")

    assert (
        main(
            [
                "controls",
                "wds",
                "mapping-template",
                str(wds_zip_path),
                "--dimensions",
                "Sex",
                "--out",
                str(mapping_template_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert json.loads(mapping_template_path.read_text()) == json.loads(
        (fixture_root / "categories-template.json").read_text()
    )

    assert (
        main(
            [
                "controls",
                "from-wds",
                str(wds_zip_path),
                "--dimensions",
                "Sex",
                "--count-column",
                "VALUE",
                "--margin-name",
                "sex",
                "--mapping",
                str(mapping_path),
                "--out",
                str(controls_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        controls_path.read_text()
        == (fixture_root / "expected-controls.csv").read_text()
    )

    assert (
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    input_report = json.loads(capsys.readouterr().out)
    assert input_report["passed"] is True
    assert input_report["suggested_next_steps"] == []

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
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert json.loads(report_path.read_text())["converged"] is True

    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
                "--format",
                "json",
            ]
        )
        == 0
    )
    validation_report = json.loads(capsys.readouterr().out)
    assert validation_report["passed"] is True


def test_tracked_microdata_tree_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/workflows/microdata_tree")
    microdata_path = tmp_path / "hierarchical.csv"
    training_path = tmp_path / "person-training.csv"
    model_path = tmp_path / "person-model.json"
    generated_path = tmp_path / "synthetic-people.csv"

    shutil.copyfile(fixture_root / "hierarchical.csv", microdata_path)

    assert (
        main(
            [
                "microdata",
                "export-training",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--out",
                str(training_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        training_path.read_text()
        == (fixture_root / "expected-person-training.csv").read_text()
    )

    assert (
        main(
            [
                "tree",
                "train",
                str(training_path),
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--weight-column",
                "WEIGHT",
                "--out",
                str(model_path),
                "--random-seed",
                "7",
            ]
        )
        == 0
    )
    capsys.readouterr()

    model = json.loads(model_path.read_text())
    assert model["model_type"] == "conditional-frequency"
    assert model["privacy"]["contains_raw_rows"] is False

    assert (
        main(
            [
                "tree",
                "generate",
                str(model_path),
                "--rows",
                "2",
                "--condition",
                "TENUR=owner",
                "--condition",
                "household_size=2",
                "--out",
                str(generated_path),
            ]
        )
        == 0
    )

    generated_rows = list(csv.DictReader(generated_path.open(newline="")))
    assert generated_rows == [
        {
            "synthetic_id": "1",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "adult",
            "SEX": "F",
        },
        {
            "synthetic_id": "2",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "adult",
            "SEX": "F",
        },
    ]

    assert (
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--weight-field",
                "WEIGHT",
                "--tolerance",
                "0.5",
                "--format",
                "json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["artifact_kind"] == "tree-output"


def test_tracked_model_output_to_ipf_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_doc = Path("docs/workflows/model-output-to-ipf.md")
    assert workflow_doc.exists()
    workflow_text = workflow_doc.read_text()
    assert "IPF cannot create missing variables" in workflow_text
    assert "tree generate-from-package" in workflow_text
    assert "ipf check-inputs" in workflow_text

    household_model_path, person_model_path = _write_publishable_linked_models(tmp_path)
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    households_path = tmp_path / "candidate-households.csv"
    persons_path = tmp_path / "candidate-persons.csv"
    controls_path = tmp_path / "household-controls.csv"
    weights_path = tmp_path / "calibrated-household-weights.csv"
    expanded_path = tmp_path / "calibrated-households.csv"
    fit_report_path = tmp_path / "fit-report.json"

    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    controls_path.write_text("margin,dimensions,tenure,count\nhousing,tenure,owner,6\n")

    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package for workflow test",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "tree",
                "generate-from-package",
                str(package_path),
                "--households",
                "3",
                "--condition",
                "geo=QC",
                "--households-out",
                str(households_path),
                "--persons-out",
                str(persons_path),
                "--random-seed",
                "11",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    linked_report = json.loads(capsys.readouterr().out)
    assert linked_report["passed"] is True

    assert (
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(households_path),
                "--controls",
                str(controls_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    input_report = json.loads(capsys.readouterr().out)
    assert input_report["passed"] is True
    assert input_report["suggested_next_steps"] == []

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(households_path),
                "--controls",
                str(controls_path),
                "--out",
                str(weights_path),
                "--report",
                str(fit_report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert json.loads(fit_report_path.read_text())["converged"] is True

    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(expanded_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(expanded_path),
                "--controls",
                str(controls_path),
                "--kind",
                "expanded",
                "--format",
                "json",
            ]
        )
        == 0
    )
    validation_report = json.loads(capsys.readouterr().out)
    expanded_rows = list(csv.DictReader(expanded_path.open(newline="")))
    assert validation_report["passed"] is True
    assert len(expanded_rows) == 6
    assert {row["tenure"] for row in expanded_rows} == {"owner"}


def _write_publishable_linked_models(tmp_path: Path) -> tuple[Path, Path]:
    household_model = replace(
        _train_frequency_model_from_rows(
            TreeModelSpec(
                level="household",
                target_columns=("household_size", "tenure"),
                conditioning_columns=("geo",),
                geography_column="geo",
            ),
            rows=(
                {
                    "geo": "QC",
                    "household_size": "2",
                    "tenure": "owner",
                },
            ),
        ),
        release_class="publishable_candidate",
    )
    person_model = replace(
        _train_frequency_model_from_rows(
            TreeModelSpec(
                level="person",
                target_columns=("age_group", "sex"),
                conditioning_columns=("geo", "household_size", "tenure"),
                geography_column="geo",
            ),
            rows=(
                {
                    "geo": "QC",
                    "household_size": "2",
                    "tenure": "owner",
                    "age_group": "adult",
                    "sex": "F",
                },
            ),
        ),
        release_class="publishable_candidate",
    )
    household_model_path = tmp_path / "household-model.json"
    person_model_path = tmp_path / "person-model.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    return household_model_path, person_model_path


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


def _write_linked_training_manifest(
    path: Path,
    *,
    household_model_path: Path,
    person_model_path: Path,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-linked-tree-training-v1",
                "source": {
                    "path": "data/private/census/hierarchical.csv",
                    "source_format": "statcan-2016-hierarchical",
                    "records": 100,
                    "households": 40,
                },
                "target_profile": "minimal",
                "geography_filter": {"column": "PR", "value": "24"},
                "method": "conditional-frequency",
                "random_seed": 7,
                "training": {
                    "household": {"records": 40},
                    "person": {"records": 100},
                },
                "models": {
                    "household": {"path": str(household_model_path)},
                    "person": {"path": str(person_model_path)},
                },
            }
        )
        + "\n"
    )


def _write_source_provenance(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "2016 Census Public Use Microdata File, hierarchical",
                "provider": "Statistics Canada",
                "access_class": "restricted",
                "citation": "Statistics Canada. 2016 Census PUMF, hierarchical.",
                "redistribution_note": "Do not redistribute source microdata.",
                "url": "https://www.statcan.gc.ca/",
            }
        )
        + "\n"
    )
