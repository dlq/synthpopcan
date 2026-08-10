"""Independent 0.9 methodological diagnostics and evidence fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.geography import GeographyIdentity, statcan_geography_universe
from synthpopcan.methodological_validation import (
    EXTERNAL_COMPARISON_SCHEMA_VERSION,
    FieldValidationSpec,
    ValidationCellSpec,
    build_calibration_validation_profile,
    build_linked_calibration_validation_profile,
    read_external_comparison_descriptor,
    resolve_external_comparison_archive,
    validate_external_comparison_fixture,
)

_ROOT = Path(__file__).parents[1]
_EXTERNAL_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "build_external_canadian_comparison",
    _ROOT / "scripts" / "build_external_canadian_comparison.py",
)
assert _EXTERNAL_SCRIPT_SPEC is not None and _EXTERNAL_SCRIPT_SPEC.loader is not None
_EXTERNAL_SCRIPT = importlib.util.module_from_spec(_EXTERNAL_SCRIPT_SPEC)
_EXTERNAL_SCRIPT_SPEC.loader.exec_module(_EXTERNAL_SCRIPT)
build_aggregate_comparison = _EXTERNAL_SCRIPT.build_aggregate_comparison

_MULTISCALE_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "build_multiscale_validation_evidence",
    _ROOT / "scripts" / "build_multiscale_validation_evidence.py",
)
assert (
    _MULTISCALE_SCRIPT_SPEC is not None and _MULTISCALE_SCRIPT_SPEC.loader is not None
)
_MULTISCALE_SCRIPT = importlib.util.module_from_spec(_MULTISCALE_SCRIPT_SPEC)
_MULTISCALE_SCRIPT_SPEC.loader.exec_module(_MULTISCALE_SCRIPT)
render_evidence = _MULTISCALE_SCRIPT.render_evidence

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "correctness"
_MULTISCALE = _FIXTURE_ROOT / "small_area_0_9_multiscale" / "cases.json"
_MULTISCALE_EVIDENCE = _MULTISCALE.with_name("evidence.json")
_EXTERNAL = _FIXTURE_ROOT / "predhumeau_manley_2021" / "descriptor.json"


def _one_margin_controls(
    cells: list[tuple[str, str, float]],
    *,
    geography_dimension: str = "geo",
    category_dimension: str = "kind",
) -> ControlTable:
    return ControlTable(
        margins=(
            ControlMargin(
                "target",
                (geography_dimension, category_dimension),
                tuple(
                    ControlCell(
                        {
                            geography_dimension: geography,
                            category_dimension: category,
                        },
                        count,
                    )
                    for geography, category, count in cells
                ),
            ),
        ),
        dimensions=(geography_dimension, category_dimension),
    )


def _linked_profile(
    *,
    households: list[dict[str, str]] | None = None,
    persons: list[dict[str, str]] | None = None,
    household_controls: ControlTable | None = None,
    person_controls: ControlTable | None = None,
    fractional: dict[str, list[float]] | None = None,
    integer: dict[str, list[int]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    candidate_households = (
        households
        if households is not None
        else [
            {"hid": "h1", "kind": "a", "uncontrolled": "x"},
            {"hid": "h2", "kind": "b", "uncontrolled": "y"},
        ]
    )
    controls = (
        household_controls
        if household_controls is not None
        else _one_margin_controls([("G", "a", 1), ("G", "b", 1)])
    )
    return build_linked_calibration_validation_profile(
        candidate_households,
        persons if persons is not None else [],
        controls,
        person_controls,
        fractional if fractional is not None else {"G": [1.0, 1.0]},
        integer if integer is not None else {"G": [1, 1]},
        geography_dimension="geo",
        geography_column="GEOUID",
        household_id_column="hid",
        **kwargs,
    )


def test_bounded_multiscale_cases_have_explicit_correct_geography_identities() -> None:
    fixture = json.loads(_MULTISCALE.read_text())
    expected_columns = {
        "csd": "CSDUID",
        "ct": "CTUID",
        "ada": "ADAUID",
        "da": "DAUID",
    }

    assert fixture["schema_version"] == (
        "synthpopcan-multiscale-calibration-fixture-v1"
    )
    assert {case["identity"]["geography_level"] for case in fixture["geographies"]} == {
        "csd",
        "ct",
        "ada",
        "da",
    }
    for case in fixture["geographies"]:
        identity = GeographyIdentity.from_dict(case["identity"])
        expected_column = expected_columns[identity.geography_level]
        universe = statcan_geography_universe(
            2021,
            identity.geography_level,
            expected_column,
            dguid_column="DGUID",
        )
        assert identity.universe_key == universe.canonical_key
        assert case["identifier_column"] == expected_column
        assert identity.dguid is not None
        assert identity.dguid.startswith("2021")
        assert case["source_url"].startswith("https://www12.statcan.gc.ca/")


def test_multiscale_profile_recomputes_all_bounded_diagnostics() -> None:
    committed = json.loads(_MULTISCALE_EVIDENCE.read_text())

    assert render_evidence(_MULTISCALE) == _MULTISCALE_EVIDENCE.read_text()
    assert committed["passed"] is True
    assert committed["checks"] == {
        "all_fitters_converged": True,
        "all_independent_profiles_pass": True,
        "fractional_error_within_bound": True,
        "parent_child_fractional_counts_reconcile": True,
        "parent_child_realized_counts_reconcile": True,
        "parent_child_targets_reconcile": True,
        "realized_error_within_bound": True,
    }
    cases = committed["cases"]
    assert len(cases) == 5
    assert all(case["fitter"]["converged"] for case in cases.values())
    assert all(
        case["independent_validation"]["fit_evidence_status"]
        == "verified-fractional-residual"
        for case in cases.values()
    )
    csd_cells = cases["montreal-csd-2021"]["independent_validation"]["cells"]
    assert {cell["unit"] for cell in csd_cells} == {"household", "person"}
    person_cell = next(
        cell
        for cell in csd_cells
        if cell["unit"] == "person" and cell["categories"] == {"AGE_BAND": "child"}
    )
    assert person_cell["candidate_rows"] == 5
    assert person_cell["supporting_households"] == 5
    assert person_cell["target_count"] == 10.0
    reconciliation = committed["parent_child_reconciliation"]
    assert reconciliation["target_max_abs_error"] == 0.0
    assert reconciliation["fractional_max_abs_error"] == 0.0
    assert reconciliation["realized_max_abs_error"] == 0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"households": []}, "at least one candidate household"),
        ({"rare_threshold": 0.0}, "rare_threshold"),
        ({"fractional_tolerance": -1.0}, "fractional_tolerance"),
        ({"zero_tolerance": float("nan")}, "zero_tolerance"),
        ({"fractional": {"X": [1.0, 1.0]}}, "fractional weights"),
        ({"integer": {"X": [1, 1]}}, "integer weights"),
        ({"fractional": {"G": [0.0, 0.0]}}, "positive mass"),
    ],
)
def test_linked_profile_rejects_invalid_arguments_and_weight_geographies(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _linked_profile(**overrides)


def test_linked_profile_requires_matching_household_and_person_geographies() -> None:
    person_controls = _one_margin_controls(
        [("OTHER", "young", 1)], category_dimension="age"
    )

    with pytest.raises(ValueError, match="same target geographies"):
        _linked_profile(person_controls=person_controls)


@pytest.mark.parametrize(
    ("controls", "message"),
    [
        (
            ControlTable(
                margins=(
                    ControlMargin(
                        "target",
                        ("kind",),
                        (ControlCell({"kind": "a"}, 1),),
                    ),
                ),
                dimensions=("kind",),
            ),
            "does not include geography",
        ),
        (
            ControlTable(
                margins=(
                    ControlMargin("target", ("geo",), (ControlCell({"geo": "G"}, 1),)),
                ),
                dimensions=("geo",),
            ),
            "non-geography dimension",
        ),
        (
            ControlTable(
                margins=(
                    ControlMargin(
                        "target",
                        ("geo", "kind"),
                        (ControlCell({"kind": "a"}, 1),),
                    ),
                ),
                dimensions=("geo", "kind"),
            ),
            "cell without",
        ),
        (
            ControlTable(
                margins=(
                    ControlMargin(
                        "target",
                        ("geo", "kind"),
                        (ControlCell({"geo": "G"}, 1),),
                    ),
                ),
                dimensions=("geo", "kind"),
            ),
            "cell is missing",
        ),
        (
            _one_margin_controls([("G", "a", 1), ("G", "a", 2)]),
            "duplicate household control cell",
        ),
        (ControlTable(margins=(), dimensions=()), "no target geographies"),
    ],
)
def test_linked_profile_rejects_malformed_control_structures(
    controls: ControlTable, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _linked_profile(household_controls=controls)


@pytest.mark.parametrize(
    ("households", "message"),
    [
        ([{"kind": "a"}], "requires 'hid'"),
        (
            [{"hid": "same", "kind": "a"}, {"hid": "same", "kind": "b"}],
            "duplicate candidate household ID",
        ),
    ],
)
def test_linked_profile_rejects_missing_or_duplicate_household_linkage_keys(
    households: list[dict[str, str]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _linked_profile(
            households=households,
            fractional={"G": [1.0] * len(households)},
            integer={"G": [1] * len(households)},
        )


def test_linked_profile_reports_unlinked_people_and_household_only_fields() -> None:
    person_controls = _one_margin_controls(
        [("G", "young", 0)], category_dimension="age"
    )
    profile = _linked_profile(
        persons=[
            {"hid": "missing", "age": "young"},
            {"hid": "h1", "age": "not-targeted"},
        ],
        person_controls=person_controls,
    )
    household_only = _linked_profile(
        households=[
            {"hid": "h1", "kind": "a", "GEOUID": "old"},
            {"hid": "h2", "kind": "b", "GEOUID": "old"},
        ]
    )

    assert profile["passed"] is True
    assert profile["linkage"]["linked_person_rows"] == 1
    assert profile["linkage"]["unlinked_person_rows"] == 1
    assert profile["geographies"]["G"]["zero_target_constraints"][0]["unit"] == "person"
    assert household_only["field_status"]["person"] == []
    geography_field = next(
        field
        for field in household_only["field_status"]["household"]
        if field["field"] == "GEOUID"
    )
    assert geography_field["role"] == "output-geography"


def test_linked_profile_surfaces_support_residual_zero_and_rare_failures() -> None:
    unsupported = _linked_profile(
        household_controls=_one_margin_controls([("G", "absent", 1)])
    )
    violated = _linked_profile(
        household_controls=_one_margin_controls([("G", "a", 2), ("G", "b", 0)]),
        fractional={"G": [1.0, 0.25]},
        integer={"G": [0, 1]},
    )

    assert unsupported["passed"] is False
    assert {issue["kind"] for issue in unsupported["geographies"]["G"]["issues"]} >= {
        "unsupported_positive_target",
        "fractional_residual_exceeds_tolerance",
    }
    assert violated["geographies"]["G"]["fit_evidence_status"] == (
        "failed-fractional-residual"
    )
    assert {issue["kind"] for issue in violated["geographies"]["G"]["issues"]} == {
        "fractional_residual_exceeds_tolerance",
        "rare_category_lost_in_realization",
        "zero_target_constraint_violation",
    }


def test_profile_flags_structural_zero_violation_and_rare_category_loss() -> None:
    records = [
        {"kind": "ordinary", "controlled": "yes"},
        {"kind": "rare", "controlled": "yes"},
        {"kind": "forbidden", "controlled": "yes"},
    ]
    profile = build_calibration_validation_profile(
        records,
        [2.0, 0.0, 0.1],
        [2, 0, 1],
        field_specs=[
            FieldValidationSpec(
                "controlled", "household", "controlled", "private", "margin"
            )
        ],
        category_cells=[
            ValidationCellSpec(
                "rare",
                "household",
                ("kind",),
                {"kind": "rare"},
                1.0,
                "fixture target",
            )
        ],
        structural_zero_cells=[
            ValidationCellSpec(
                "forbidden",
                "household",
                ("kind",),
                {"kind": "forbidden"},
                0.0,
                "fixture structural-zero declaration",
            )
        ],
    )

    assert profile["passed"] is False
    assert {issue["kind"] for issue in profile["issues"]} == {
        "rare_category_lost_in_realization",
        "structural_zero_violation",
    }
    assert profile["structural_zeros"]["violations"] == 1


@pytest.mark.parametrize(
    ("fractional", "integer", "message"),
    [
        ([1.0], [1, 0], "fractional weights"),
        ([1.0, float("nan")], [1, 0], "finite"),
        ([1.0, 0.0], [1, -1], "non-negative integers"),
        ([0.0, 0.0], [0, 0], "positive total"),
    ],
)
def test_profile_rejects_invalid_weight_vectors(
    fractional: list[float], integer: list[int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_calibration_validation_profile(
            [{"field": "a"}, {"field": "b"}],
            fractional,
            integer,
            field_specs=[],
        )


def test_profile_rejects_invalid_field_and_cell_contracts() -> None:
    with pytest.raises(ValueError, match="control margin"):
        FieldValidationSpec("field", "household", "controlled", "private")
    with pytest.raises(ValueError, match="unsupported"):
        FieldValidationSpec("field", "household", "local", "private")
    with pytest.raises(ValueError, match="match its dimensions"):
        ValidationCellSpec(
            "cell", "household", ("field",), {"other": "x"}, 1.0, "fixture"
        )
    duplicate = FieldValidationSpec("field", "household", "uncontrolled", "private")
    with pytest.raises(ValueError, match="unique"):
        build_calibration_validation_profile(
            [{"field": "a"}],
            [1.0],
            [1],
            field_specs=[duplicate, duplicate],
        )
    with pytest.raises(ValueError, match="reference_count=0"):
        build_calibration_validation_profile(
            [{"field": "a"}],
            [1.0],
            [1],
            field_specs=[],
            structural_zero_cells=[
                ValidationCellSpec(
                    "cell",
                    "household",
                    ("field",),
                    {"field": "a"},
                    1.0,
                    "fixture",
                )
            ],
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"field": "", "unit": "household", "status": "derived", "universe": "u"},
            "field",
        ),
        (
            {"field": "f", "unit": "", "status": "derived", "universe": "u"},
            "field unit",
        ),
        (
            {"field": "f", "unit": "household", "status": "derived", "universe": ""},
            "field universe",
        ),
        (
            {
                "field": "f",
                "unit": "household",
                "status": "derived",
                "universe": "u",
                "margin": "",
            },
            "control margin",
        ),
        (
            {
                "field": "f",
                "unit": "household",
                "status": "derived",
                "universe": "u",
                "limitation": "",
            },
            "field limitation",
        ),
    ],
)
def test_field_spec_rejects_blank_contract_text(
    kwargs: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        FieldValidationSpec(**kwargs)


@pytest.mark.parametrize(
    ("dimensions", "categories", "reference_count", "message"),
    [
        ((), {}, 0.0, "non-empty and distinct"),
        (("field", "field"), {"field": "a"}, 0.0, "non-empty and distinct"),
        (("",), {"": "a"}, 0.0, "cell dimension"),
        (("field",), {"field": ""}, 0.0, "cell category"),
        (("field",), {"field": "a"}, -1.0, "finite and non-negative"),
        (("field",), {"field": "a"}, float("inf"), "finite and non-negative"),
    ],
)
def test_cell_spec_rejects_invalid_contract_values(
    dimensions: tuple[str, ...],
    categories: dict[str, str],
    reference_count: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ValidationCellSpec(
            "cell",
            "household",
            dimensions,
            categories,
            reference_count,
            "fixture",
        )


@pytest.mark.parametrize(
    ("records", "fractional", "integer", "kwargs", "message"),
    [
        ([], [], [], {}, "at least one"),
        ([{"f": "a"}], [1.0], [1], {"rare_threshold": 0}, "rare_threshold"),
        ([{"f": "a"}], [1.0], [1], {"tolerance": -1}, "tolerance"),
        ([{"f": "a"}], [1.0], [], {}, "integer weights"),
        ([{"f": "a"}], [1.0], [True], {}, "non-negative integers"),
    ],
)
def test_profile_rejects_invalid_top_level_contract(
    records: list[dict[str, str]],
    fractional: list[float],
    integer: list[int],
    kwargs: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_calibration_validation_profile(
            records,
            fractional,
            integer,
            field_specs=[],
            **kwargs,
        )


def test_profile_reports_unsupported_rare_cell_and_empty_realization() -> None:
    profile = build_calibration_validation_profile(
        [{"kind": "ordinary"}],
        [1.0],
        [0],
        field_specs=[],
        category_cells=[
            ValidationCellSpec(
                "missing-rare",
                "household",
                ("kind",),
                {"kind": "rare"},
                1.0,
                "fixture",
            )
        ],
    )

    assert profile["passed"] is False
    assert profile["candidate_reuse"]["realized_records"] == 0
    assert profile["candidate_reuse"]["unique_copy_share"] == 0.0
    assert profile["candidate_reuse"]["realized_share_from_reused_candidates"] == 0.0
    assert profile["issues"][0]["kind"] == "unsupported_rare_category"


def test_missing_controlled_field_is_an_error_but_uncontrolled_is_descriptive() -> None:
    profile = build_calibration_validation_profile(
        [{"present": "yes"}],
        [1.0],
        [1],
        field_specs=[
            FieldValidationSpec(
                "missing", "household", "controlled", "private", "margin"
            ),
            FieldValidationSpec(
                "also_missing", "household", "uncontrolled", "candidate"
            ),
        ],
    )

    assert profile["passed"] is False
    assert [issue["kind"] for issue in profile["issues"]] == ["missing_fitted_field"]
    fields = {item["field"]: item for item in profile["fields"]["items"]}
    assert fields["missing"]["fit_evidence_status"] == "not_assessed"
    assert fields["also_missing"]["fit_evidence_status"] == "not_assessed"
    assert "local_representativeness_claim_allowed" not in fields["missing"]


def test_external_comparison_descriptor_and_schema_fixture_are_offline_and_pinned() -> (
    None
):
    descriptor = read_external_comparison_descriptor(_EXTERNAL)
    report = validate_external_comparison_fixture(_EXTERNAL)

    assert descriptor["schema_version"] == EXTERNAL_COMPARISON_SCHEMA_VERSION
    assert descriptor["source"]["doi"] == "10.5281/zenodo.7572117"
    assert descriptor["source"]["version"] == "2.1.0"
    assert descriptor["source"]["license"] == "CC-BY-4.0"
    assert descriptor["resource"]["byte_size"] == 9_573_036_764
    assert descriptor["resource"]["checksum"] == (
        "md5:b9f4b9db45aed0169d1a86af77fa9298"
    )
    assert descriptor["download_policy"] == {
        "default": "disabled",
        "explicit_opt_in_required": True,
        "cache_outside_git": True,
        "maximum_bytes": 10_000_000_000,
        "default_tests": "offline",
        "reason": "The pinned archive is approximately 9.6 GB.",
    }
    assert descriptor["fixture"]["contains_external_records"] is False
    assert report["passed"] is True
    assert report["network_accessed"] is False
    assert report["contains_external_records"] is False
    assert report["rows"] == 2
    assert report["fixture_checksum"] == descriptor["fixture"]["checksum"]
    empirical = report["empirical_aggregate_evidence"]
    assert empirical is not None
    assert empirical["aggregate_only"] is True
    assert (
        empirical["checksum"]
        == (descriptor["empirical_aggregate_evidence"]["checksum"])
    )


def test_external_aggregate_builder_is_deterministic_and_keeps_only_aggregates(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external.csv"
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    external.write_text(
        "HID,sex,area\nh1,0,62000001\nh1,1,62000001\nh2,0,62000002\n-1,1,62000002\n"
    )
    households.write_text(
        "synthetic_household_id,DAUID,household_size\na,62000011,1\nb,62000012,2\n"
    )
    persons.write_text(
        "synthetic_household_id,DAUID,GENDER\n"
        "a,62000011,1\n"
        "b,62000012,2\n"
        "b,62000012,8\n"
    )

    first = build_aggregate_comparison(
        external, households, persons, expected_external_sha256=None
    )
    second = build_aggregate_comparison(
        external, households, persons, expected_external_sha256=None
    )

    assert first == second
    assert first["public_safety"] == {
        "aggregate_only": True,
        "contains_direct_identifiers": False,
        "contains_source_rows": False,
        "minimum_released_unit": "territory",
    }
    assert first["external_aggregates"]["person_rows"] == 4
    assert first["external_aggregates"]["derived_linked_households"] == 2
    assert first["external_aggregates"]["unlinked_person_rows"] == 1
    assert first["synthpopcan_aggregates"]["orphan_person_rows"] == 0
    assert (
        first["comparison"]["metric_deltas"]["linked_person_rows"][
            "synthpopcan_minus_external"
        ]
        == 0
    )

    with pytest.raises(ValueError, match="SHA-256"):
        build_aggregate_comparison(
            external, households, persons, expected_external_sha256="0" * 64
        )


def _write_small_descriptor(tmp_path: Path, resource: bytes) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = tmp_path / "schema.csv"
    fixture.write_text("field\nfictional\n")
    descriptor = {
        "schema_version": EXTERNAL_COMPARISON_SCHEMA_VERSION,
        "comparison_id": "test-comparison",
        "title": "Test comparison",
        "source": {
            "doi": "10.0000/test",
            "version": "1",
            "license": "CC0-1.0",
            "record_url": "https://example.test/record",
        },
        "resource": {
            "filename": "archive.bin",
            "url": "https://example.test/archive.bin",
            "byte_size": len(resource),
            "checksum": ("sha256:" + hashlib.sha256(resource).hexdigest()),
        },
        "download_policy": {
            "default": "disabled",
            "explicit_opt_in_required": True,
            "cache_outside_git": True,
            "maximum_bytes": len(resource),
        },
        "schema_crosswalk": {"external_fields": ["field"]},
        "fixture": {
            "path": fixture.name,
            "checksum": "sha256:" + hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "contains_external_records": False,
        },
    }
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(descriptor))
    return path


def _write_empirical_descriptor(
    tmp_path: Path,
    artifact_payload: object = None,
) -> tuple[Path, Path]:
    descriptor_path = _write_small_descriptor(tmp_path, b"archive")
    empirical_path = tmp_path / "aggregate.json"
    payload = (
        {
            "schema_version": "synthpopcan-external-aggregate-comparison-v1",
            "public_safety": {
                "aggregate_only": True,
                "contains_source_rows": False,
            },
        }
        if artifact_payload is None
        else artifact_payload
    )
    empirical_path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload)
    )
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["empirical_aggregate_evidence"] = {
        "path": empirical_path.name,
        "checksum": "sha256:" + hashlib.sha256(empirical_path.read_bytes()).hexdigest(),
        "contains_external_records": False,
        "aggregate_only": True,
    }
    descriptor_path.write_text(json.dumps(descriptor))
    return descriptor_path, empirical_path


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("nonobject", "must be an object"),
        ("md5", "requires SHA-256"),
        ("external-rows", "must not contain external rows"),
        ("not-aggregate", "must be aggregate-only"),
    ],
)
def test_external_descriptor_rejects_unsafe_empirical_metadata(
    tmp_path: Path, mutation: str, message: str
) -> None:
    descriptor_path, _ = _write_empirical_descriptor(tmp_path / mutation)
    descriptor = json.loads(descriptor_path.read_text())
    empirical = descriptor["empirical_aggregate_evidence"]
    if mutation == "nonobject":
        descriptor["empirical_aggregate_evidence"] = []
    elif mutation == "md5":
        empirical["checksum"] = "md5:" + "0" * 32
    elif mutation == "external-rows":
        empirical["contains_external_records"] = True
    else:
        empirical["aggregate_only"] = False
    descriptor_path.write_text(json.dumps(descriptor))

    with pytest.raises(ValueError, match=message):
        read_external_comparison_descriptor(descriptor_path)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing", "is missing"),
        ("checksum", "checksum does not match"),
        ("invalid-json", "could not read empirical"),
        ("schema", "unsupported empirical"),
        ("safety", "aggregate-only safety"),
        ("source-rows", "may not contain source rows"),
    ],
)
def test_external_empirical_aggregate_validation_fails_closed(
    tmp_path: Path, failure: str, message: str
) -> None:
    case = tmp_path / failure
    artifact: object = None
    if failure == "invalid-json":
        artifact = "{"
    elif failure == "schema":
        artifact = {"schema_version": "unsupported", "public_safety": {}}
    elif failure == "safety":
        artifact = {
            "schema_version": "synthpopcan-external-aggregate-comparison-v1",
            "public_safety": [],
        }
    elif failure == "source-rows":
        artifact = {
            "schema_version": "synthpopcan-external-aggregate-comparison-v1",
            "public_safety": {
                "aggregate_only": True,
                "contains_source_rows": True,
            },
        }
    descriptor_path, empirical_path = _write_empirical_descriptor(case, artifact)
    descriptor = json.loads(descriptor_path.read_text())
    if failure == "missing":
        empirical_path.unlink()
    elif failure == "checksum":
        descriptor["empirical_aggregate_evidence"]["checksum"] = "sha256:" + "0" * 64
        descriptor_path.write_text(json.dumps(descriptor))

    with pytest.raises(ValueError, match=message):
        validate_external_comparison_fixture(descriptor_path)


def test_external_empirical_aggregate_rejects_symlink_escape(tmp_path: Path) -> None:
    descriptor_path = _write_small_descriptor(tmp_path / "descriptor", b"archive")
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-external-aggregate-comparison-v1",
                "public_safety": {
                    "aggregate_only": True,
                    "contains_source_rows": False,
                },
            }
        )
    )
    link = descriptor_path.parent / "aggregate.json"
    link.symlink_to(outside)
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["empirical_aggregate_evidence"] = {
        "path": link.name,
        "checksum": "sha256:" + hashlib.sha256(outside.read_bytes()).hexdigest(),
        "contains_external_records": False,
        "aggregate_only": True,
    }
    descriptor_path.write_text(json.dumps(descriptor))

    with pytest.raises(ValueError, match="escapes"):
        validate_external_comparison_fixture(descriptor_path)


def test_external_archive_resolution_requires_opt_in_and_verifies_cache(
    tmp_path: Path,
) -> None:
    resource = b"pinned archive"
    descriptor = _write_small_descriptor(tmp_path, resource)
    cache = tmp_path / "cache"

    with pytest.raises(FileNotFoundError, match="opt-in"):
        resolve_external_comparison_archive(descriptor, cache)
    with pytest.raises(ValueError, match="explicit downloader"):
        resolve_external_comparison_archive(descriptor, cache, allow_download=True)

    calls: list[tuple[str, int]] = []

    def downloader(url: str, path: Path, maximum_bytes: int) -> None:
        calls.append((url, maximum_bytes))
        path.write_bytes(resource)

    resolved = resolve_external_comparison_archive(
        descriptor,
        cache,
        allow_download=True,
        downloader=downloader,
    )
    assert resolved.read_bytes() == resource
    assert calls == [("https://example.test/archive.bin", len(resource))]
    assert resolve_external_comparison_archive(descriptor, cache) == resolved

    resolved.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="byte size"):
        resolve_external_comparison_archive(descriptor, cache)


def test_external_descriptor_and_fixture_fail_closed(tmp_path: Path) -> None:
    resource = b"archive"
    descriptor_path = _write_small_descriptor(tmp_path, resource)
    descriptor = json.loads(descriptor_path.read_text())

    descriptor["download_policy"]["default"] = "enabled"
    descriptor_path.write_text(json.dumps(descriptor))
    with pytest.raises(ValueError, match="disabled by default"):
        read_external_comparison_descriptor(descriptor_path)

    descriptor["download_policy"]["default"] = "disabled"
    descriptor["fixture"]["checksum"] = "sha256:" + "0" * 64
    descriptor_path.write_text(json.dumps(descriptor))
    with pytest.raises(ValueError, match="checksum"):
        validate_external_comparison_fixture(descriptor_path)


def _replace_nested(payload: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    target: dict[str, Any] = payload
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


@pytest.mark.parametrize(
    ("keys", "value", "message"),
    [
        (("schema_version",), "unsupported", "unsupported"),
        (("source", "license"), "", "source license"),
        (("source",), [], "requires object"),
        (("resource", "filename"), "../archive.bin", "plain filename"),
        (("resource", "url"), "http://example.test/file", "HTTPS"),
        (("resource", "byte_size"), 0, "positive integer"),
        (("resource", "checksum"), "not-a-checksum", "algorithm"),
        (("resource", "checksum"), "sha256:XYZ", "lowercase"),
        (("download_policy", "explicit_opt_in_required"), False, "explicit opt-in"),
        (("download_policy", "cache_outside_git"), False, "outside git"),
        (("download_policy", "maximum_bytes"), 1, "smaller"),
        (("fixture", "contains_external_records"), True, "must not contain"),
        (("fixture", "path"), "../schema.csv", "below the descriptor"),
        (("fixture", "checksum"), "md5:" + "0" * 32, "SHA-256"),
    ],
)
def test_external_descriptor_rejects_unsafe_or_incomplete_metadata(
    tmp_path: Path,
    keys: tuple[str, ...],
    value: Any,
    message: str,
) -> None:
    descriptor_path = _write_small_descriptor(tmp_path / "case", b"archive")
    payload = json.loads(descriptor_path.read_text())
    _replace_nested(payload, keys, value)
    descriptor_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match=message):
        read_external_comparison_descriptor(descriptor_path)


def test_external_descriptor_rejects_unreadable_nonobject_and_missing_keys(
    tmp_path: Path,
) -> None:
    path = tmp_path / "descriptor.json"
    path.write_text("{")
    with pytest.raises(ValueError, match="could not read"):
        read_external_comparison_descriptor(path)

    path.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        read_external_comparison_descriptor(path)

    path.write_text(json.dumps({"schema_version": EXTERNAL_COMPARISON_SCHEMA_VERSION}))
    with pytest.raises(ValueError, match="comparison_id"):
        read_external_comparison_descriptor(path)


def test_external_fixture_rejects_missing_bad_crosswalk_and_missing_columns(
    tmp_path: Path,
) -> None:
    descriptor_path = _write_small_descriptor(tmp_path / "missing", b"archive")
    (descriptor_path.parent / "schema.csv").unlink()
    with pytest.raises(ValueError, match="fixture is missing"):
        validate_external_comparison_fixture(descriptor_path)

    descriptor_path = _write_small_descriptor(tmp_path / "crosswalk", b"archive")
    payload = json.loads(descriptor_path.read_text())
    payload["schema_crosswalk"]["external_fields"] = "field"
    descriptor_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="string list"):
        validate_external_comparison_fixture(descriptor_path)

    descriptor_path = _write_small_descriptor(tmp_path / "columns", b"archive")
    payload = json.loads(descriptor_path.read_text())
    payload["schema_crosswalk"]["external_fields"] = ["field", "missing"]
    descriptor_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="missing fields"):
        validate_external_comparison_fixture(descriptor_path)


def test_external_fixture_rejects_symlink_escape(tmp_path: Path) -> None:
    descriptor_path = _write_small_descriptor(tmp_path / "descriptor", b"archive")
    outside = tmp_path / "outside.csv"
    outside.write_text("field\nfictional\n")
    link = descriptor_path.parent / "linked.csv"
    link.symlink_to(outside)
    payload = json.loads(descriptor_path.read_text())
    payload["fixture"]["path"] = link.name
    payload["fixture"]["checksum"] = (
        "sha256:" + hashlib.sha256(outside.read_bytes()).hexdigest()
    )
    descriptor_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="escapes"):
        validate_external_comparison_fixture(descriptor_path)


def test_external_archive_rejects_checksum_mismatch_and_existing_temporary(
    tmp_path: Path,
) -> None:
    resource = b"correct"
    descriptor = _write_small_descriptor(tmp_path / "checksum", resource)
    cache = tmp_path / "checksum-cache"
    cache.mkdir()
    (cache / "archive.bin").write_bytes(b"incorrect")
    payload = json.loads(descriptor.read_text())
    payload["resource"]["byte_size"] = len(b"incorrect")
    payload["download_policy"]["maximum_bytes"] = len(b"incorrect")
    descriptor.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="checksum"):
        resolve_external_comparison_archive(descriptor, cache)

    descriptor = _write_small_descriptor(tmp_path / "temporary", resource)
    cache = tmp_path / "temporary-cache"
    cache.mkdir()
    (cache / ".archive.bin.download").write_bytes(b"partial")
    with pytest.raises(ValueError, match="temporary"):
        resolve_external_comparison_archive(
            descriptor,
            cache,
            allow_download=True,
            downloader=lambda _url, _path, _maximum: None,
        )


def test_external_archive_failed_download_is_removed_and_md5_cache_is_supported(
    tmp_path: Path,
) -> None:
    resource = b"md5-pinned"
    descriptor = _write_small_descriptor(tmp_path / "md5", resource)
    payload = json.loads(descriptor.read_text())
    payload["resource"]["checksum"] = (
        "md5:" + hashlib.md5(resource, usedforsecurity=False).hexdigest()
    )
    descriptor.write_text(json.dumps(payload))
    cache = tmp_path / "md5-cache"
    cache.mkdir()
    cached = cache / "archive.bin"
    cached.write_bytes(resource)
    assert resolve_external_comparison_archive(descriptor, cache) == cached

    descriptor = _write_small_descriptor(tmp_path / "failed", b"correct")
    failed_cache = tmp_path / "failed-cache"

    def wrong_download(_url: str, path: Path, _maximum: int) -> None:
        path.write_bytes(b"wrongee")

    with pytest.raises(ValueError, match="checksum"):
        resolve_external_comparison_archive(
            descriptor,
            failed_cache,
            allow_download=True,
            downloader=wrong_download,
        )
    assert not (failed_cache / ".archive.bin.download").exists()
