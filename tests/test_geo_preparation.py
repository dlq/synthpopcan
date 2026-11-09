"""CLI-only preparation and fitting, with independently checkable tiny populations."""

from __future__ import annotations

import csv
import json
from zipfile import ZipFile

import pytest
from click.testing import CliRunner

from synthpopcan._profile_preparation import (
    AGE_CONTROL,
    allocate_observed,
    observed_count,
    workflow_controls,
)
from synthpopcan.cli import cli
from synthpopcan.linked_schema import build_linked_population_contract
from synthpopcan.model_licensing import synthetic_demo_model_licensing

PROFILE = ["--source-profile", "statcan-hierarchical-2021"]


def invoke(*args):
    result = CliRunner().invoke(cli, [str(a) for a in args])
    assert result.exit_code == 0, result.output
    return result


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def inputs(tmp_path):
    pack, definitions = workflow_controls()
    rows = []
    for geo, total in [("462", 21), ("4620001.00", 11), ("4620002.00", 10)]:
        cells = {}
        for margin in pack.margins:
            control = definitions[margin.control_identifier]
            for axis in control.source_axes:
                for category in axis.categories:
                    for member in category.source_characteristic_ids:
                        cells[member] = {
                            "C1_COUNT_TOTAL": "0",
                            "C2_COUNT_MEN+": "0",
                            "C3_COUNT_WOMEN+": "0",
                        }
            first = control.source_axes[0].categories[0].source_characteristic_ids[0]
            cells[first] = {
                "C1_COUNT_TOTAL": "10",
                "C2_COUNT_MEN+": "0",
                "C3_COUNT_WOMEN+": "10",
            }
            cells[control.source.root_characteristic_id] = {
                "C1_COUNT_TOTAL": "10",
                "C2_COUNT_MEN+": "0",
                "C3_COUNT_WOMEN+": "10",
            }
        for member, value in {
            "1": total,
            "4": 10,
            "5": 20 if geo == "462" else 10,
            "8": total,
            "50": 20 if geo == "462" else 10,
            "56": 20 if geo == "462" else 10,
        }.items():
            cells[member] = {
                "C1_COUNT_TOTAL": str(value),
                "C2_COUNT_MEN+": "0",
                "C3_COUNT_WOMEN+": str(value),
            }
        for member, values in cells.items():
            rows.append(
                {
                    "CENSUS_YEAR": "2021",
                    "ALT_GEO_CODE": geo,
                    "GEO_LEVEL": "Census metropolitan area"
                    if geo == "462"
                    else "Census tract",
                    "CHARACTERISTIC_ID": member,
                    **values,
                }
            )
    profile = tmp_path / "profile.csv"
    write_csv(profile, rows)
    source = tmp_path / "candidates"
    source.mkdir()
    households = [
        {
            "synthetic_household_id": "h1",
            "household_size": "1",
            "TENUR": "1",
            "DTYPE": "1",
            "CONDO": "1",
            "BEDRM": "0",
            "ROOM": "1",
            "NOS": "1",
            "BUILT": "1",
            "REPAIR": "1",
        }
    ]
    persons = [
        {
            "synthetic_person_id": "p1",
            "synthetic_household_id": "h1",
            "AGEGRP": "1",
            "GENDER": "1",
            "CITIZEN": "1",
            "IMMSTAT": "1",
            "GENSTAT": "1",
            "VISMIN": "1",
        }
    ]
    # Include zero-target categories too: the calibrator checks category support.
    variants = []
    for margin in pack.margins:
        control = definitions[margin.control_identifier]
        if control.identifier == AGE_CONTROL:
            variants.extend(
                ("person", "AGEGRP", age, gender)
                for age in ("1", "3", "12")
                for gender in ("1", "2")
            )
            continue
        derivation = control.candidate_derivations[0]
        for category in control.source_axes[0].categories:
            target = category.target_category
            raw = next(
                (
                    raw
                    for raw, mapped in derivation.categories.items()
                    if mapped == target
                ),
                target,
            )
            variants.append((control.entity_level, derivation.source_field, raw, "1"))
    original_hh, original_pp = dict(households[0]), dict(persons[0])
    for number, (entity, field, value, gender) in enumerate(variants, 2):
        hh = {**original_hh, "synthetic_household_id": f"h{number}"}
        pp = {**original_pp, "synthetic_household_id": f"h{number}"}
        (hh if entity == "household" else pp)[field] = value
        pp["GENDER"] = gender
        households.append(hh)
        persons.extend(
            {**pp, "synthetic_person_id": f"p{number}_{i}"}
            for i in range(int(hh["household_size"]))
        )
    write_csv(source / "households.csv", households)
    write_csv(source / "persons.csv", persons)
    contract = build_linked_population_contract(
        source / "households.csv",
        source / "persons.csv",
        licensing=synthetic_demo_model_licensing(),
    )
    (source / "manifest.json").write_text(json.dumps(contract))
    return profile, source


def test_cli_preparation_calibration_combination_and_audit(tmp_path, inputs):
    profile, source = inputs
    controls = tmp_path / "controls"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        controls,
    )
    plan = json.loads((controls / "plan.json").read_text())
    assert plan["target_households"] == 20
    assert [b["tracts"] for b in plan["batches"]] == [["4620001.00"], ["4620002.00"]]
    batches = []
    for name in ["private-households", "zero-collective"]:
        prepared = tmp_path / (name + "-candidates")
        extra = ["--require-gender"] if name == "zero-collective" else []
        invoke("geo", "prepare-candidates", source, *PROFILE, *extra, "--out", prepared)
        candidates = list(csv.DictReader((prepared / "persons.csv").open()))
        assert candidates[0]["age_group_3"] == "0_14"
        assert candidates[0]["GENDER"] == "1"
        output = tmp_path / (name + "-population")
        invoke(
            "geo",
            "calibrate",
            prepared,
            "--controls",
            controls / name / "household-controls.csv",
            "--person-controls",
            controls / name / "person-controls.csv",
            "--geo-dimension",
            "ct",
            "--geo-column",
            "ct",
            "--out",
            output,
        )
        batches.append(output)
    combined = tmp_path / "combined"
    invoke("geo", "combine", *batches, "--out", combined)
    report = json.loads((combined / "report.json").read_text())
    assert report["assigned_households"] == report["assigned_persons"] == 20
    assert report["validation"]["passed"]
    audit = tmp_path / "audit"
    options = [
        a
        for name in ["private-households", "zero-collective"]
        for a in [
            "--controls",
            controls / name / "household-controls.csv",
            "--person-controls",
            controls / name / "person-controls.csv",
        ]
    ]
    invoke("geo", "audit", combined, *options, "--out", audit)
    result = json.loads((audit / "realized-control-audit.json").read_text())
    assert result["max_abs_error"] == 0
    assert result["unexpected_categories"] == []
    assert result["control_cells"] > 60
    receipt = json.loads((combined / "preparation.json").read_text())
    assert receipt["operation"] == "combine"
    assert all(len(r["sha256"]) == 64 for r in receipt["inputs"])


@pytest.mark.parametrize(
    "values,target,expected",
    [
        ([0, 5, 5], 3, [0, 2, 1]),
        ([0, 0], 0, [0, 0]),
        ([10**30, 1], 10**30 + 1, [10**30, 1]),
    ],
)
def test_observed_allocation_preserves_zeros_ties_and_integer_precision(
    values, target, expected
):
    assert allocate_observed(values, target) == expected


def test_zero_vector_cannot_invent_positive_targets():
    with pytest.raises(ValueError, match="all-zero"):
        allocate_observed([0, 0], 1)


@pytest.mark.parametrize("value", ["", "x", "..", "-1", "NaN", "Infinity", "1.5"])
def test_suppressed_missing_or_invalid_counts_are_rejected(value):
    with pytest.raises(ValueError, match="Missing, suppressed or invalid"):
        observed_count({"462": {"5": {"C1_COUNT_TOTAL": value}}}, "462", "5")


def test_cli_control_preparation_reads_zip_and_corrects_source_gender(tmp_path, inputs):
    profile, _ = inputs
    archive = tmp_path / "profile.zip"
    with ZipFile(archive, "w") as handle:
        handle.write(profile, "example_English_CSV_data.csv")
    out = tmp_path / "controls"
    invoke(
        "geo",
        "prepare-controls",
        archive,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        out,
    )
    audit = json.loads((out / "zero-collective/normalization.json").read_text())
    age = next(a for a in audit if a["control"] == AGE_CONTROL)
    assert age["normalized_categories"]["0_14|1"] == 10
    assert age["normalized_categories"]["0_14|2"] == 0


def test_candidate_screening_excludes_whole_household_without_imputation(
    tmp_path, inputs
):
    _, source = inputs
    households = list(csv.DictReader((source / "households.csv").open()))
    persons = list(csv.DictReader((source / "persons.csv").open()))
    households.append(
        {**households[0], "synthetic_household_id": "bad", "household_size": "2"}
    )
    persons.extend(
        [
            {
                **persons[0],
                "synthetic_person_id": "bad1",
                "synthetic_household_id": "bad",
            },
            {
                **persons[0],
                "synthetic_person_id": "bad2",
                "synthetic_household_id": "bad",
                "AGEGRP": "88",
            },
        ]
    )
    write_csv(source / "households.csv", households)
    write_csv(source / "persons.csv", persons)
    out = tmp_path / "screened"
    invoke("geo", "prepare-candidates", source, *PROFILE, "--out", out)
    report = json.loads((out / "report.json").read_text())
    assert report["kept_households"] == len(households) - 1
    assert report["kept_persons"] == len(persons) - 2
    assert report["excluded_persons"] == 2
    assert report["reasons"] == {"person.AGEGRP": 1}


@pytest.mark.parametrize("problem", ["checksum", "duplicate", "vintage", "suppressed"])
def test_failed_preparation_publishes_no_partial_output(tmp_path, inputs, problem):
    profile, _ = inputs
    rows = list(csv.DictReader(profile.open()))
    if problem == "duplicate":
        rows.append(rows[0])
    elif problem == "vintage":
        rows[0]["CENSUS_YEAR"] = "2016"
    elif problem == "suppressed":
        next(
            r
            for r in rows
            if r["CHARACTERISTIC_ID"] == "50" and r["ALT_GEO_CODE"] != "462"
        )["C1_COUNT_TOTAL"] = "x"
    write_csv(profile, rows)
    out = tmp_path / "failed"
    args = [
        "geo",
        "prepare-controls",
        str(profile),
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        str(out),
    ]
    if problem == "checksum":
        args += ["--profile-sha256", "0" * 64]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert not list(tmp_path.glob(".synthpopcan-prepare-*"))


def test_preparation_refuses_to_overwrite_completed_output(tmp_path, inputs):
    profile, _ = inputs
    out = tmp_path / "existing"
    out.mkdir()
    (out / "keep").write_text("unchanged")
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "prepare-controls",
            str(profile),
            "--cma",
            "462",
            *PROFILE,
            "--normalization",
            "observed-proportional",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert (out / "keep").read_text() == "unchanged"


@pytest.mark.parametrize("retry_numerical_failure", [False, True])
def test_cli_support_selection_preserves_targets_and_reports_feasibility(
    tmp_path, inputs, monkeypatch, retry_numerical_failure
):
    pytest.importorskip("scipy")
    from threading import Lock
    from types import SimpleNamespace

    from synthpopcan._candidate_preparation import _support_modules

    warning, actual, sparse = _support_modules()
    calls = []
    lock = Lock()

    def solve(*args, **kwargs):
        with lock:
            first_failure = retry_numerical_failure and not calls
            calls.append(kwargs["options"].copy())
        if first_failure:
            return SimpleNamespace(
                status=4, success=False, x=None, message="Numerical difficulty"
            )
        return actual(*args, **kwargs)

    monkeypatch.setattr(
        "synthpopcan._candidate_preparation._support_modules",
        lambda: (warning, solve, sparse),
    )
    profile, source = inputs
    controls = tmp_path / "controls"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        controls,
    )
    out = tmp_path / "supported"
    hh = controls / "zero-collective/household-controls.csv"
    pp = controls / "zero-collective/person-controls.csv"
    previous = (hh.read_bytes(), pp.read_bytes())
    invoke(
        "geo",
        "prepare-candidates",
        source,
        *PROFILE,
        "--require-gender",
        "--pool-size",
        "1",
        "--augment-support",
        "--controls",
        hh,
        "--person-controls",
        pp,
        "--out",
        out,
    )
    report = json.loads((out / "report.json").read_text())
    assert all(r["feasible"] for r in report["support_diagnostics"])
    assert report["selected_households"] >= 1
    assert calls[0]["presolve"] is False
    assert any(call["presolve"] for call in calls) is retry_numerical_failure
    assert (hh.read_bytes(), pp.read_bytes()) == previous


def test_explicit_exclusion_records_missing_tract_and_preserves_source(
    tmp_path, inputs
):
    profile, _ = inputs
    rows = list(csv.DictReader(profile.open()))
    next(
        r
        for r in rows
        if r["ALT_GEO_CODE"] == "4620001.00" and r["CHARACTERISTIC_ID"] == "50"
    )["C1_COUNT_TOTAL"] = "x"
    write_csv(profile, rows)
    original = profile.read_bytes()
    out = tmp_path / "excluded"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--incomplete-geographies",
        "exclude",
        "--out",
        out,
    )
    plan = json.loads((out / "plan.json").read_text())
    assert plan["tracts"] == ["4620002.00"]
    assert plan["excluded_tracts"][0]["ct"] == "4620001.00"
    assert "suppressed" in plan["excluded_tracts"][0]["reason"]
    assert profile.read_bytes() == original


def test_audit_reports_nonzero_residuals_and_uncontrolled_categories(tmp_path):
    from synthpopcan._population_preparation import audit_population

    population = tmp_path / "population"
    population.mkdir()
    write_csv(
        population / "households.csv",
        [{"ct": "G", "tenure": "owner"}, {"ct": "G", "tenure": "unknown"}],
    )
    controls = tmp_path / "controls.csv"
    write_csv(
        controls,
        [
            {
                "margin": "tenure",
                "dimensions": "ct,tenure",
                "ct": "G",
                "tenure": "owner",
                "count": "3",
            },
            {
                "margin": "tenure",
                "dimensions": "ct,tenure",
                "ct": "G",
                "tenure": "renter",
                "count": "0",
            },
        ],
    )
    result = audit_population(population, (controls,), (), tmp_path / "audit")
    assert result["max_abs_error"] == 2
    assert result["unexpected_categories"] == [
        {
            "entity": "household",
            "ct": "G",
            "margin": "tenure",
            "categories": ["unknown"],
            "realized": 1,
        }
    ]
    assert result["top_residuals"][0]["target"] == 3
    assert result["top_residuals"][0]["realized"] == 1


def test_combination_rejects_overlapping_tracts_without_publication(tmp_path, inputs):
    _, source = inputs
    # Assigned batches must not cover the same tract, even when paths differ.
    import shutil

    for name in ("households", "persons"):
        path = source / f"{name}.csv"
        rows = list(csv.DictReader(path.open()))
        write_csv(path, [{**row, "ct": "G"} for row in rows])
    contract = build_linked_population_contract(
        source / "households.csv",
        source / "persons.csv",
        geography_column="ct",
        licensing=synthetic_demo_model_licensing(),
    )
    (source / "manifest.json").write_text(json.dumps(contract))
    other = tmp_path / "other"
    shutil.copytree(source, other)
    out = tmp_path / "combined"
    result = CliRunner().invoke(
        cli, ["geo", "combine", str(source), str(other), "--out", str(out)]
    )
    assert result.exit_code == 1
    assert "disjoint" in result.output
    assert "geo combine --help" in result.output
    assert not out.exists()


def test_independent_rounding_does_not_exclude_private_person_controls(
    tmp_path, inputs
):
    profile, _ = inputs
    rows = list(csv.DictReader(profile.open()))
    next(
        r
        for r in rows
        if r["ALT_GEO_CODE"] == "4620001.00" and r["CHARACTERISTIC_ID"] == "8"
    )["C1_COUNT_TOTAL"] = "9"
    write_csv(profile, rows)
    out = tmp_path / "rounding"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        out,
    )
    plan = json.loads((out / "plan.json").read_text())
    assert len(plan["tracts"]) == 2
    assert plan["excluded_tracts"] == []
    assert plan["batches"][0]["include_age_gender"] is False
    assert plan["batches"][0]["target_persons"] == 10


def test_prepare_candidates_accepts_models_generate_manifest(tmp_path, inputs):
    _, source = inputs
    path = source / "manifest.json"
    contract = json.loads(path.read_text())
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-tree-generation-manifest-v1",
                "command": "models generate",
                "licensing": contract["licensing"],
                "linked_population": contract,
            }
        )
    )
    out = tmp_path / "generated-input"
    invoke("geo", "prepare-candidates", source, *PROFILE, "--out", out)
    result = json.loads((out / "manifest.json").read_text())
    assert result["licensing"] == contract["licensing"]
    assert result["candidate_preparation"]["kept_households"] > 0
    assert (
        json.loads(path.read_text())["schema_version"]
        == "synthpopcan-tree-generation-manifest-v1"
    )


def test_calibrate_prepared_directory_owns_screening_batches_validation_and_audit(
    tmp_path, inputs
):
    profile, source = inputs
    controls = tmp_path / "controls"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        controls,
    )
    # This is the public output envelope of models generate.
    path = source / "manifest.json"
    contract = json.loads(path.read_text())
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-tree-generation-manifest-v1",
                "linked_population": contract,
                "licensing": contract["licensing"],
            }
        )
    )
    out = tmp_path / "assigned"
    invoke(
        "geo",
        "calibrate",
        source,
        "--controls",
        controls,
        "--geo-dimension",
        "ct",
        "--include-weights",
        "--out",
        out,
    )
    report = json.loads((out / "report.json").read_text())
    assert report["assigned_households"] == report["assigned_persons"] == 20
    assert report["summary"]["total_geographies"] == 2
    assert report["summary"]["non_converged_count"] == 0
    assert report["validation"]["passed"]
    assert report["realized_control_audit"]["max_abs_error"] == 0
    assert report["geography_universe"]["census_vintage"] == 2021
    assert (out / "weights.csv").exists()
    assert json.loads((out / "workflow.json").read_text())["status"] == "complete"
    boundary = tmp_path / "boundaries.geojson"
    from support.map_fixtures import _write_fake_geojson

    _write_fake_geojson(boundary, ["4620001.00", "4620002.00"])
    invoke(
        "geo",
        "map",
        out,
        "--both",
        "--person-profile",
        "statcan-hierarchical-2021",
        "--boundaries",
        boundary,
        "--geo-column",
        "ct",
        "--out",
        tmp_path / "maps.html",
    )
    assert (tmp_path / "maps-households.html").exists()
    assert (tmp_path / "maps-population.html").exists()


@pytest.mark.parametrize(
    ("problem", "message"),
    [
        ("overlap", "disjoint"),
        ("duplicate", "duplicate IDs"),
        ("batch-total", "declares target_households"),
        ("plan-total", "declares target_persons"),
        ("control-bytes", "recorded fingerprint"),
    ],
)
def test_prepared_calibration_rejects_invalid_plan_before_fitting(
    tmp_path, inputs, problem, message
):
    profile, source = inputs
    controls = tmp_path / "controls"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--cma",
        "462",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        controls,
    )
    path = controls / "plan.json"
    plan = json.loads(path.read_text())
    if problem == "control-bytes":
        table = controls / "private-households" / "household-controls.csv"
        table.write_bytes(table.read_bytes() + b"\n")
    else:
        if problem == "overlap":
            plan["batches"][1]["tracts"] = plan["batches"][0]["tracts"]
        elif problem == "duplicate":
            plan["batches"][0]["tracts"] *= 2
        elif problem == "batch-total":
            plan["batches"][0]["target_households"] += 1
        else:
            plan["target_persons"] += 1
        path.write_text(json.dumps(plan))
    out = tmp_path / "failed"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(source),
            "--controls",
            str(controls),
            "--geo-dimension",
            "ct",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert message in result.output
    assert not (out / "work").exists()


def test_profile_worker_launch_records_command_and_checks_result(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from synthpopcan.workflows.profiling import profile_cli_worker

    calls = []

    def launch(command, **kwargs):
        calls.append(command)
        (tmp_path / "batch.json").write_text("{}")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("synthpopcan.workflows.profiling.subprocess.run", launch)
    profile_cli_worker(["geo", "calibrate", "candidates"], "batch", tmp_path)
    assert calls[0][-3:] == ["geo", "calibrate", "candidates"]
    assert "--cpu-only" in calls[0]
    assert json.loads((tmp_path / "batch-command.json").read_text()) == calls[0]
    (tmp_path / "batch.json").unlink()
    monkeypatch.setattr(
        "synthpopcan.workflows.profiling.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=2),
    )
    with pytest.raises(ValueError, match="failed.*batch.log"):
        profile_cli_worker([], "batch", tmp_path)
    monkeypatch.setattr(
        "synthpopcan.workflows.profiling.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0),
    )
    with pytest.raises(ValueError, match="did not produce"):
        profile_cli_worker([], "batch", tmp_path)


def test_profiled_batch_preserves_cli_parameters(tmp_path, monkeypatch):
    from synthpopcan.geography import GeographyUniverse
    from synthpopcan.workflows.prepared_calibration import _fit_batch
    from synthpopcan.workflows.small_area import SmallAreaCalibrationRequest

    out = tmp_path / "batch"
    out.mkdir()
    (out / "report.json").write_text('{"summary": {}}')
    calls = []
    monkeypatch.setenv("SYNTHPOPCAN_PROFILE_WORKERS", str(tmp_path / "profiles"))
    monkeypatch.setattr(
        "synthpopcan.workflows.profiling.profile_cli_worker",
        lambda arguments, name, directory: calls.append((arguments, name, directory)),
    )
    request = SmallAreaCalibrationRequest(
        candidate_households_path=tmp_path / "households.csv",
        candidate_persons_path=tmp_path / "persons.csv",
        controls_path=tmp_path / "controls.csv",
        person_controls_path=tmp_path / "person-controls.csv",
        output_dir=out,
        geography_dimension="ct",
        geography_column="ct",
        geography_universe=GeographyUniverse(
            2021, "ct", "statcan:census:2021:ct", "ct"
        ),
        pool_size=20000,
        max_iterations=3000,
        tolerance=0.01,
        include_weights=True,
    )
    result = _fit_batch(request)
    assert result.report_path == out / "report.json"
    arguments, name, directory = calls.pop()
    assert name == "batch"
    assert directory == tmp_path / "profiles"
    assert arguments[arguments.index("--max-iterations") + 1] == "3000"
    assert arguments[arguments.index("--pool-size") + 1] == "20000"
    assert arguments[arguments.index("--tolerance") + 1] == "0.01"
    assert "--include-weights" in arguments


@pytest.mark.parametrize("archive", [False, True], ids=["csv", "zip"])
def test_profile_selection_preserves_csv_record_semantics(tmp_path, archive):
    """Selection preserves Latin-1, quoted records and duplicate-header rules."""
    import io

    from synthpopcan._profile_preparation import select_profile

    columns = [
        "CENSUS_YEAR",
        "ALT_GEO_CODE",
        "GEO_LEVEL",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "C2_COUNT_MEN+",
        "C3_COUNT_WOMEN+",
        "SYMBOL",
        "NOTE",
        "SYMBOL",
    ]
    cma = [
        "2021",
        "462",
        "Census metropolitan area",
        "50",
        "2",
        "1",
        "1",
        "first",
        'Montréal, "Été"\nsecond line',
        "last",
    ]
    tract = [
        "2021",
        "4620001.00",
        "Census tract",
        "50",
        "2",
        "1",
        "1",
        "ignored duplicate",
    ]
    unrelated = [
        "2016",
        "999",
        "Census tract",
        "50",
        "1",
        "0",
        "1",
        "x",
        "unrelated",
        "y",
        "ignored extra field",
    ]
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(columns)
    writer.writerows([[], unrelated, cma, [], tract, []])
    content = text.getvalue().encode("latin-1")
    source = tmp_path / ("profile.zip" if archive else "profile.csv")
    if archive:
        with ZipFile(source, "w") as zipped:
            zipped.writestr("nested/English_CSV_data.csv", content)
    else:
        source.write_bytes(content)
    output = tmp_path / "selected.csv"

    cells = select_profile(source, "462", output)

    assert list(cells) == ["462", "4620001.00"]
    assert cells["462"]["50"]["NOTE"] == 'Montréal, "Été"\nsecond line'
    assert cells["462"]["50"]["SYMBOL"] == "last"
    # A missing final duplicate overwrites its earlier, present value.
    assert cells["4620001.00"]["50"]["SYMBOL"] is None
    assert cells["4620001.00"]["50"]["NOTE"] is None
    expected = io.StringIO(newline="")
    expected_writer = csv.DictWriter(expected, fieldnames=columns)
    expected_writer.writeheader()
    expected_writer.writerows([cells["462"]["50"], cells["4620001.00"]["50"]])
    assert output.read_bytes() == expected.getvalue().encode("latin-1")


def test_profile_selection_uses_final_duplicate_selector_columns(tmp_path):
    from synthpopcan._profile_preparation import select_profile

    columns = [
        "CENSUS_YEAR",
        "ALT_GEO_CODE",
        "GEO_LEVEL",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "C2_COUNT_MEN+",
        "C3_COUNT_WOMEN+",
        "ALT_GEO_CODE",
        "CHARACTERISTIC_ID",
        "GEO_LEVEL",
        "CENSUS_YEAR",
    ]
    source = tmp_path / "duplicate-selectors.csv"
    with source.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for geo, level in [
            ("462", "Census metropolitan area"),
            ("4620001.00", "Census tract"),
        ]:
            writer.writerow(
                [
                    "2016",
                    "999",
                    "Other geography",
                    "not needed",
                    "2",
                    "1",
                    "1",
                    geo,
                    "50",
                    level,
                    "2021",
                ]
            )

    cells = select_profile(source, "462", tmp_path / "selected.csv")

    assert list(cells) == ["462", "4620001.00"]
    assert all(rows["50"]["CENSUS_YEAR"] == "2021" for rows in cells.values())


@pytest.mark.parametrize("problem", ["extra", "short"])
def test_profile_selection_preserves_malformed_record_errors(tmp_path, problem):
    from synthpopcan._profile_preparation import select_profile

    columns = [
        "CENSUS_YEAR",
        "ALT_GEO_CODE",
        "GEO_LEVEL",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "C2_COUNT_MEN+",
        "C3_COUNT_WOMEN+",
    ]
    row = ["2021", "462", "Census metropolitan area", "50", "2", "1", "1"]
    row = [*row, "extra"] if problem == "extra" else row[:2]
    source = tmp_path / "malformed.csv"
    with source.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerow(row)
    expected = ValueError if problem == "extra" else AttributeError

    with pytest.raises(expected):
        select_profile(source, "462", tmp_path / "selected.csv")


@pytest.mark.parametrize("augment_support", [False, True])
def test_cli_province_ada_preparation_calibration_and_both_maps(
    tmp_path, inputs, augment_support
):
    """The ordinary four-stage path supports all province-wide ADA dimensions."""
    original, source = inputs
    with original.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping = {"462": "24", "4620001.00": "24000001", "4620002.00": "24000002"}
    for row in rows:
        row["ALT_GEO_CODE"] = mapping[row["ALT_GEO_CODE"]]
        row["GEO_LEVEL"] = (
            "Province"
            if row["ALT_GEO_CODE"] == "24"
            else "Aggregate dissemination area"
        )
    profile = tmp_path / "province-ada.csv"
    write_csv(profile, rows)
    controls = tmp_path / "province-controls"
    invoke(
        "geo",
        "prepare-controls",
        profile,
        "--province",
        "24",
        *PROFILE,
        "--normalization",
        "observed-proportional",
        "--out",
        controls,
    )
    plan = json.loads((controls / "plan.json").read_text())
    assert plan["target_households"] == 20
    assert plan["target_persons"] == 20
    assert plan["geography_dimension"] == plan["geography_level"] == "ada"
    assert plan["geographies"] == ["24000001", "24000002"]
    assert plan["coverage"]["household_coverage_complete"]
    assigned = tmp_path / "assigned"
    invoke(
        "geo",
        "calibrate",
        source,
        "--controls",
        controls,
        "--geo-dimension",
        "ada",
        "--pool-size",
        "200",
        *(["--augment-support"] if augment_support else []),
        "--workers",
        "1",
        "--joint-solver",
        "hybrid",
        "--zero-target-policy",
        "observed",
        "--max-iterations",
        "100",
        "--out",
        assigned,
    )
    report = json.loads((assigned / "report.json").read_text())
    assert report["assigned_households"] == report["assigned_persons"] == 20
    assert report["validation"]["passed"]
    assert report["zero_target_policy"]["requested"] == "observed"
    assert sum(report["zero_target_policy"]["effective_counts"].values()) == 2
    assert report["geography_universe"]["geography_level"] == "ada"
    assert (
        report["geography_universe"]["identifier_namespace"]
        == "statcan:census:2021:ada"
    )
    assert report["realized_control_audit"]["max_abs_error"] == 0
    with (assigned / "persons.csv").open(newline="") as handle:
        assert {row["ada"] for row in csv.DictReader(handle)} == {
            "24000001",
            "24000002",
        }
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": geo, "LANDAREA": 1},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [index, 0],
                                    [index + 1, 0],
                                    [index + 1, 1],
                                    [index, 1],
                                    [index, 0],
                                ]
                            ],
                        },
                    }
                    for index, geo in enumerate(plan["geographies"])
                ],
            }
        )
    )
    invoke(
        "geo",
        "map",
        assigned,
        "--both",
        "--person-profile",
        "statcan-hierarchical-2021",
        "--boundaries",
        boundaries,
        "--geo-column",
        "ada",
        "--geo-id-field",
        "geo_id",
        "--census-vintage",
        "2021",
        "--geo-level",
        "ada",
        "--geo-namespace",
        "statcan:census:2021:ada",
        "--out",
        tmp_path / "quebec.html",
    )
    assert (tmp_path / "quebec-households.html").is_file()
    assert (tmp_path / "quebec-population.html").is_file()


@pytest.mark.parametrize(
    "scope,reason",
    [
        ([], "exactly one"),
        (["--cma", "462", "--province", "24"], "exactly one"),
        (["--province", "QC"], "two-digit"),
        (["--cma", "462", "--province-profile", "PROFILE_PATH"], "requires --province"),
    ],
)
def test_prepare_controls_rejects_ambiguous_or_invalid_scope(
    tmp_path, inputs, scope, reason
):
    profile, _ = inputs
    scope = [str(profile) if arg == "PROFILE_PATH" else arg for arg in scope]
    output = tmp_path / "controls"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "prepare-controls",
            str(profile),
            *scope,
            *PROFILE,
            "--normalization",
            "observed-proportional",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 2
    assert reason in result.output
    assert not output.exists()
