"""Reject malformed conditional targets before any population is fitted."""

import json
from copy import deepcopy

import pytest

from synthpopcan._conditional_controls import (
    UNDER_15,
    ConditionalPersonTargets,
    classify_conditional_person_field,
    load_marital_status_controls,
    reconcile_conditional_person_margin,
)
from synthpopcan._conditional_universe import ConditionalPersonUniverse
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.geography import statcan_geography_universe


@pytest.fixture
def source():
    geography = statcan_geography_universe(2021, "ct", "ct")
    identifier = "4620053.00"
    universe = ConditionalPersonUniverse(
        geography.identity(identifier), 10, 8, 2, "fixture:reviewed"
    )
    target = ConditionalPersonTargets(universe, {"single": 3, "married": 5}, 2)
    margin = ControlMargin(
        "people",
        ("ct", "group"),
        (ControlCell({"ct": identifier, "group": "all"}, 10),),
    )
    return geography, identifier, target, ControlTable((margin,), ("ct", "group"))


def reconcile(
    source,
    *,
    categories=frozenset({"single", "married"}),
    targets=None,
    field="marital_status_15_plus",
    controls=None,
):
    geography, identifier, target, table = source
    return reconcile_conditional_person_margin(
        controls or table,
        geography=geography,
        geography_dimension="ct",
        field=field,
        eligible_categories=categories,
        targets={identifier: target} if targets is None else targets,
    )


@pytest.mark.parametrize(
    "categories", [frozenset(), frozenset({""}), frozenset({UNDER_15})]
)
def test_eligible_categories_cannot_be_empty_or_include_child_state(source, categories):
    with pytest.raises(ValueError, match="distinct eligible categories"):
        reconcile(source, categories=categories)


def test_conditional_field_cannot_duplicate_an_existing_dimension(source):
    with pytest.raises(ValueError, match="already controlled"):
        reconcile(source, field="group")


def test_conditional_targets_require_geography_evidence(source):
    with pytest.raises(ValueError, match="require geography evidence"):
        reconcile(source, targets={})


def test_conditional_targets_require_exhaustive_categories(source):
    with pytest.raises(ValueError, match="categories must be exhaustive"):
        reconcile(source, categories=frozenset({"single"}))


def test_existing_person_margins_must_have_matching_geography_and_totals(source):
    _, identifier, _, _ = source
    for cell, message in [
        (ControlCell({"ct": "4620054.00", "group": "all"}, 10), "geographies differ"),
        (ControlCell({"ct": identifier, "group": "all"}, 9), "does not match"),
    ]:
        margin = ControlMargin("people", ("ct", "group"), (cell,))
        with pytest.raises(ValueError, match=message):
            reconcile(source, controls=ControlTable((margin,), ("ct", "group")))


def test_under_15_must_agree_with_existing_age_margin(source):
    _, identifier, _, _ = source
    margin = ControlMargin(
        "ages",
        ("ct", "age_group_3"),
        (
            ControlCell({"ct": identifier, "age_group_3": "0_14"}, 3),
            ControlCell({"ct": identifier, "age_group_3": "15_plus"}, 7),
        ),
    )
    with pytest.raises(ValueError, match="under-15 target"):
        reconcile(source, controls=ControlTable((margin,), ("ct", "age_group_3")))


def test_children_do_not_require_adult_source_codes_but_adults_do():
    kwargs = dict(
        age_field="age",
        age_eligibility={"child": False, "adult": True},
        source_field="status",
        output_field="out",
        crosswalk={"m": "married"},
        eligible_categories=frozenset({"married"}),
    )
    result = classify_conditional_person_field(
        [{"age": "child", "status": "unknown"}], **kwargs
    )
    assert result[0]["out"] == UNDER_15
    with pytest.raises(ValueError, match="unknown age eligibility"):
        classify_conditional_person_field([{"age": "unknown"}], **kwargs)
    with pytest.raises(ValueError, match="unsupported eligible status"):
        classify_conditional_person_field(
            [{"age": "adult", "status": "unknown"}], **kwargs
        )


@pytest.fixture
def document(source):
    geography, identifier, _, _ = source
    return {
        "schema_version": "synthpopcan-marital-status-controls-v1",
        "age_eligibility": {"child": False, "adult": True},
        "crosswalk": {"s": "single", "m": "married"},
        "targets": [
            {
                "geography": geography.identity(identifier).as_dict(),
                "all_private_household_persons": 10,
                "age_15_plus_persons": 8,
                "under_15_persons": 2,
                "under_15_not_applicable": 2,
                "source_evidence": "fixture",
                "eligible_counts": {"single": 3, "married": 5},
            }
        ],
    }


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda d: d.update(schema_version="other"), "expected a synthpopcan"),
        (lambda d: d.update(age_eligibility={"adult": 1}), "valid age_eligibility"),
        (lambda d: d.update(crosswalk={"m": " "}), "categories must be nonblank"),
        (lambda d: d.update(targets=[]), "require per-geography targets"),
        (
            lambda d: d["targets"].append(deepcopy(d["targets"][0])),
            "duplicate marital-status geography",
        ),
        (
            lambda d: d["targets"][0].update(geography=None),
            "explicit geography identity",
        ),
        (
            lambda d: d["targets"][0].update(source_evidence=None),
            "require source evidence",
        ),
        (
            lambda d: d["targets"][0].update(eligible_counts=None),
            "require eligible_counts",
        ),
        (
            lambda d: d["targets"][0].update(under_15_not_applicable=True),
            "requires an observed count",
        ),
    ],
)
def test_invalid_explicit_source_evidence_fails_before_fitting(
    tmp_path, source, document, change, message
):
    change(document)
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(document))
    geography, _, _, controls = source
    with pytest.raises(ValueError, match=message):
        load_marital_status_controls(path, [], controls, geography, "ct")


@pytest.mark.parametrize(
    "contents,message",
    [
        ("wrong,header\na,b\n", "requires ct,marital_status,age_20,value"),
        ("ct,marital_status,age_20,value\n4620053.00,1,1,\n", "unavailable or invalid"),
        ("ct,marital_status,age_20,value\n4620053.00,1,1,3\n", "multiples of five"),
        (
            "ct,marital_status,age_20,value\n4620053.00,1,1,5\n4620053.00,1,1,10\n",
            "duplicate",
        ),
    ],
)
def test_marital_source_rejects_invalid_published_cells(tmp_path, contents, message):
    from synthpopcan._marital_status_packs import _read_cells

    path = tmp_path / "marital.csv"
    path.write_text(contents)
    with pytest.raises(ValueError, match=message):
        _read_cells(path, {"4620053.00"})


def test_marital_source_ignores_unselected_tracts_and_unused_cells(tmp_path):
    from synthpopcan._marital_status_packs import _read_cells

    path = tmp_path / "marital.csv"
    path.write_text(
        "ct,marital_status,age_20,value\n"
        "4620054.00,1,1,not-a-count\n"
        "4620053.00,99,1,not-a-count\n"
        "4620053.00,1,1,10\n"
    )
    assert _read_cells(path, {"4620053.00"}) == {"4620053.00": {(1, 1): 10}}
