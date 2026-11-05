"""Feasibility support uses the requested geography without changing controls."""

from __future__ import annotations

import csv

import pytest

from synthpopcan import _candidate_preparation as preparation
from synthpopcan.linked_schema import build_linked_population_contract


def _write(path, fields, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _candidates():
    households = [
        dict(synthetic_household_id="h1", household_size="1", TENUR="1"),
        dict(synthetic_household_id="h2", household_size="1", TENUR="2"),
    ]
    persons = [
        dict(synthetic_person_id="p1", synthetic_household_id="h1", GENDER="1"),
        dict(synthetic_person_id="p2", synthetic_household_id="h2", GENDER="2"),
    ]
    return households, persons


def _controls(tmp_path, dimension):
    files = []
    for entity, field in (("household", "TENUR"), ("person", "GENDER")):
        path = tmp_path / f"{entity}-controls.csv"
        rows = []
        for geography, counts in (("24010001", (1, 1)), ("24020001", (1, 2))):
            for category, count in zip(("1", "2"), counts, strict=True):
                rows.append(
                    {
                        "margin": f"{dimension} {field}",
                        "dimensions": f"{dimension},{field}",
                        dimension: geography,
                        field: category,
                        "count": count,
                    }
                )
        _write(path, ["margin", "dimensions", dimension, field, "count"], rows)
        files.append(path)
    return files


@pytest.mark.parametrize("dimension", ["ct", "ada"])
def test_support_selection_preserves_dimension_and_targets(tmp_path, dimension):
    pytest.importorskip("scipy")
    households, persons = _candidates()
    household_controls, person_controls = _controls(tmp_path, dimension)
    original = household_controls.read_bytes(), person_controls.read_bytes()
    kwargs = {} if dimension == "ct" else {"geography_dimension": dimension}
    selected, reports = preparation.select_support(
        households,
        persons,
        household_controls,
        person_controls,
        pool_size=0,
        seed=42,
        **kwargs,
    )
    assert selected == {0, 1}
    assert [report[dimension] for report in reports] == ["24010001", "24020001"]
    assert all(report["feasible"] for report in reports)
    assert all(report["support_households"] == 2 for report in reports)
    assert all(list(report)[0] == dimension for report in reports)
    assert (household_controls.read_bytes(), person_controls.read_bytes()) == original


def test_prepare_candidates_forwards_ada_dimension_into_support(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    households, persons = _candidates()
    hh_fields, pp_fields = list(households[0]), list(persons[0])
    _write(source / "households.csv", hh_fields, households)
    _write(source / "persons.csv", pp_fields, persons)
    contract = build_linked_population_contract(
        source / "households.csv", source / "persons.csv"
    )
    preparation.write_json(source / "manifest.json", contract)
    monkeypatch.setattr(
        preparation,
        "screen_candidates",
        lambda *_: (hh_fields, pp_fields, households, persons, {}),
    )
    dimensions = []

    def support(*_args, geography_dimension):
        dimensions.append(geography_dimension)
        return {0, 1}, [{geography_dimension: "24010001", "feasible": True}]

    monkeypatch.setattr(preparation, "select_support", support)
    result = preparation.prepare_candidates(
        source,
        tmp_path / "prepared",
        pool_size=1,
        augment_support=True,
        controls_path=tmp_path / "household-controls.csv",
        person_controls_path=tmp_path / "person-controls.csv",
        geography_dimension="ada",
    )
    assert dimensions == ["ada"]
    assert result["support_diagnostics"] == [{"ada": "24010001", "feasible": True}]
    assert result["selected_households"] == result["selected_persons"] == 2


def test_missing_scipy_recommends_consolidated_performance_extra(monkeypatch):
    import builtins

    original = builtins.__import__

    def missing_scipy(name, *args, **kwargs):
        if name.startswith("scipy"):
            raise ImportError("SciPy is unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_scipy)
    with pytest.raises(
        ValueError, match=r"synthpopcan\[performance\].*--augment-support"
    ):
        preparation._support_modules()
