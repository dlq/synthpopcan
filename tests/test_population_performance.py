"""CSV performance seams retain file semantics and independent validation."""

from __future__ import annotations

import csv
import io

import pytest

from synthpopcan._population_preparation import audit_population, combine_populations
from synthpopcan.linked_schema import (
    build_linked_population_contract,
    build_linked_population_contract_from_shapes,
    write_linked_population_contract_document,
)


def _write(path, fields, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _batch(root, name, geography, *, reverse=False, household_id=None):
    root = root / name
    root.mkdir()
    hh_id = household_id or name
    household = {
        "synthetic_household_id": hh_id,
        "household_size": "1",
        "ct": geography,
        "note": 'quoted, "value"\nsecond line',
    }
    person = {
        "synthetic_person_id": name + "-p",
        "synthetic_household_id": hh_id,
        "ct": geography,
        "category": "A",
        "gender": "F",
    }
    hf, pf = list(household), list(person)
    if reverse:
        household["extra"] = "001"
        person["extra"] = "002"
        hf, pf = list(reversed(household)), list(reversed(person))
    _write(root / "households.csv", hf, [household])
    _write(root / "persons.csv", pf, [person])
    write_linked_population_contract_document(
        root / "manifest.json",
        build_linked_population_contract(
            root / "households.csv", root / "persons.csv", geography_column="ct"
        ),
    )
    return root, household, person


def test_contract_from_writer_shapes_matches_file_builder_without_opening_files(
    tmp_path, monkeypatch
):
    source, _, _ = _batch(tmp_path, "source", "G1")
    expected = build_linked_population_contract(
        source / "households.csv", source / "persons.csv", geography_column="ct"
    )
    monkeypatch.setattr(
        "synthpopcan.linked_schema._csv_shape",
        lambda _: pytest.fail("must reuse measured shapes"),
    )
    actual = build_linked_population_contract_from_shapes(
        source / "households.csv",
        source / "persons.csv",
        household_columns=expected["tables"]["households"]["columns"],
        household_rows=1,
        person_columns=expected["tables"]["persons"]["columns"],
        person_rows=1,
        geography_column="ct",
    )
    assert actual == expected


def test_combine_preserves_union_column_order_strings_and_quoted_newlines(
    tmp_path, monkeypatch
):
    first, hh1, pp1 = _batch(tmp_path, "first", "G1")
    second, hh2, pp2 = _batch(tmp_path, "second", "G2", reverse=True)
    monkeypatch.setattr(
        "synthpopcan.linked_schema._csv_shape",
        lambda _: pytest.fail(
            "combined files are already counted and independently validated"
        ),
    )
    output = tmp_path / "combined"
    report = combine_populations((first, second), output, "ct")
    for entity, rows in [("households", [hh1, hh2]), ("persons", [pp1, pp2])]:
        fields = [*rows[0], "extra"]
        expected = io.StringIO(newline="")
        writer = csv.DictWriter(expected, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        assert (output / f"{entity}.csv").read_bytes() == expected.getvalue().encode()
    assert report["validation"]["passed"]
    assert report["assigned_households"] == report["assigned_persons"] == 2
    assert report["geographies"] == ["G1", "G2"]


def test_combine_retains_independent_duplicate_identifier_readback_check(tmp_path):
    first, _, _ = _batch(tmp_path, "first", "G1", household_id="duplicate")
    second, _, _ = _batch(tmp_path, "second", "G2", household_id="duplicate")
    with pytest.raises(ValueError, match="duplicate IDs"):
        combine_populations((first, second), tmp_path / "combined", "ct")


def test_combine_rejects_person_geography_mismatch_while_copying(tmp_path):
    first, _, _ = _batch(tmp_path, "first", "G1")
    second, _, person = _batch(tmp_path, "second", "G2")
    person["ct"] = "G1"
    _write(second / "persons.csv", list(person), [person])
    with pytest.raises(ValueError, match="Person geography"):
        combine_populations((first, second), tmp_path / "combined", "ct")


def test_combine_rejects_overlap(tmp_path):
    first, _, _ = _batch(tmp_path, "first", "G1")
    second, _, _ = _batch(tmp_path, "second", "G1")
    with pytest.raises(ValueError, match="disjoint"):
        combine_populations((first, second), tmp_path / "combined", "ct")


def test_audit_counts_single_and_joint_categories_with_quoted_fields(tmp_path):
    population, _, person = _batch(tmp_path, "population", "G1")
    person["category"] = 'quoted, "category"\nsecond line'
    _write(population / "persons.csv", list(person), [person])
    controls = tmp_path / "controls.csv"
    fields = ["margin", "dimensions", "ct", "category", "gender", "count"]
    _write(
        controls,
        fields,
        [
            {
                "margin": "single",
                "dimensions": "ct,category",
                "ct": "G1",
                "category": person["category"],
                "count": "1",
            },
            {
                "margin": "joint",
                "dimensions": "ct,category,gender",
                "ct": "G1",
                "category": person["category"],
                "gender": "F",
                "count": "1",
            },
        ],
    )
    result = audit_population(population, (), (controls,), tmp_path / "audit")
    assert result["control_cells"] == result["matched_exactly"] == 2
    assert result["max_abs_error"] == 0
    assert result["unexpected_categories"] == []


@pytest.mark.parametrize(
    "header,row",
    [
        ("ct,category,category", "G1,B,A"),
        ("ct,ct,category", "WRONG,G1,A"),
    ],
)
def test_audit_uses_last_duplicate_header_like_dictreader(tmp_path, header, row):
    population = tmp_path / "population"
    population.mkdir()
    (population / "persons.csv").write_text(header + "\n" + row + "\n")
    controls = tmp_path / "controls.csv"
    controls.write_text(
        'margin,dimensions,ct,category,count\nm,"ct,category",G1,A,1\n'
        'm,"ct,category",G1,B,0\n'
    )
    report = audit_population(population, (), (controls,), tmp_path / "audit")
    assert report["matched_exactly"] == 2
    assert report["max_abs_error"] == 0
    assert report["unexpected_categories"] == []


def test_buffered_csv_integrity_preserves_unicode_and_quoted_records(tmp_path):
    import hashlib

    import pandas as pd

    from synthpopcan.small_area_synthesis import _write_frame_with_integrity

    frame = pd.DataFrame({"value": ['Québec, "été"\nnext', "😀" * 1100000, ""]})
    expected = frame.to_csv(index=False).encode("utf-8")
    target = tmp_path / "population.csv"
    integrity = _write_frame_with_integrity(frame, target)
    assert target.read_bytes() == expected
    assert integrity == {
        "sha256": hashlib.sha256(expected).hexdigest(),
        "byte_size": len(expected),
    }


@pytest.mark.parametrize("late_quote", ["none", "households", "persons"])
def test_native_combination_matches_reference_bytes_with_union_and_late_fallback(
    tmp_path, monkeypatch, late_quote
):
    pytest.importorskip("polars", minversion="2.1")
    sources = []
    for name, geo, reverse in [("first", "G1", False), ("second", "G2", True)]:
        source, household, person = _batch(tmp_path, name, geo, reverse=reverse)
        households, persons = [], []
        for index in range(64):
            identifier = f"{name}-{index}"
            note = (
                'quoted, "été"\nsecond line'
                if late_quote == "households" and index == 40
                else "Québec"
            )
            households.append(
                {**household, "synthetic_household_id": identifier, "note": note}
            )
            persons.append(
                {
                    **person,
                    "synthetic_household_id": identifier,
                    "synthetic_person_id": identifier + "-p",
                    "category": 'quoted,"été"\nline'
                    if late_quote == "persons" and index == 40
                    else "",
                }
            )
        _write(
            source / "households.csv",
            list(reversed(household)) if reverse else list(household),
            households,
        )
        _write(
            source / "persons.csv",
            list(reversed(person)) if reverse else list(person),
            persons,
        )
        sources.append(source)
    monkeypatch.setattr("synthpopcan._columnar_csv.CSV_CHUNK_BYTES", 256)
    outputs = []
    for threshold in [10**15, 0]:
        monkeypatch.setattr("synthpopcan._columnar_csv.MIN_COLUMNAR_BYTES", threshold)
        out = tmp_path / str(threshold)
        result = combine_populations(tuple(sources), out, "ct")
        assert result["validation"]["passed"]
        assert result["assigned_households"] == result["assigned_persons"] == 128
        outputs.append(
            tuple((out / f"{e}.csv").read_bytes() for e in ["households", "persons"])
        )
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("problem", ["extra", "missing", "geography", "overlap"])
def test_native_combination_retains_reference_rejections(
    tmp_path, monkeypatch, problem
):
    pytest.importorskip("polars", minversion="2.1")
    first, hh1, _ = _batch(tmp_path, "first", "G1")
    second, hh2, person = _batch(
        tmp_path, "second", "G1" if problem == "overlap" else "G2"
    )
    for source, row in [(first, hh1), (second, hh2)]:
        row["note"] = "plain"
        _write(source / "households.csv", list(row), [row])
    if problem == "extra":
        with (second / "persons.csv").open("a") as handle:
            handle.write("extra,fields,beyond,the,original,header\n")
    elif problem == "missing":
        person["synthetic_household_id"] = ""
        _write(second / "persons.csv", list(person), [person])
    elif problem == "geography":
        person["ct"] = "wrong"
        _write(second / "persons.csv", list(person), [person])
    messages = []
    for threshold in [10**15, 0]:
        monkeypatch.setattr("synthpopcan._columnar_csv.MIN_COLUMNAR_BYTES", threshold)
        with pytest.raises(ValueError) as exc:
            combine_populations((first, second), tmp_path / str(threshold), "ct")
        messages.append(str(exc.value))
    assert messages[0] == messages[1]


@pytest.mark.parametrize(
    "problem",
    [
        "plain",
        "quotes",
        "missing",
        "late-missing",
        "carriage",
        "nul",
        "numeric",
        "unavailable",
    ],
)
def test_native_string_writer_preserves_pandas_bytes_and_integrity(
    tmp_path, monkeypatch, problem
):
    import hashlib

    import pandas as pd

    from synthpopcan import small_area_synthesis as synthesis

    pytest.importorskip("polars", minversion="2.1")
    values = ["Québec", "", "001", 'line\nwith,"quotes"', "tail"]
    if problem == "plain":
        values[3] = "ordinary"
    if problem in ["missing", "late-missing"]:
        values[4] = None
    if problem == "late-missing":
        values[0] = "😀" * 1100000
    if problem == "carriage":
        values[4] = "a\rb"
    if problem == "nul":
        values[4] = "a\x00b"
    frame = pd.DataFrame(
        {
            "value": pd.Series(values, dtype=pd.StringDtype()),
            "other": pd.Series(["x"] * 5, dtype=pd.StringDtype()),
        }
    )
    if problem == "numeric":
        frame["other"] = range(5)
    monkeypatch.setattr(synthesis, "_NATIVE_WRITE_ROWS", 0)
    monkeypatch.setattr(synthesis, "_NATIVE_WRITE_CHUNK_ROWS", 3)
    if problem == "unavailable":
        monkeypatch.setattr("synthpopcan._columnar_csv.load_polars", lambda: None)
    expected = frame.to_csv(index=False).encode("utf-8")
    path = tmp_path / "out.csv"
    result = synthesis._write_frame_with_integrity(frame, path)
    assert path.read_bytes() == expected
    assert result == {
        "sha256": hashlib.sha256(expected).hexdigest(),
        "byte_size": len(expected),
    }


def test_native_geography_index_preserves_labels_unknowns_and_restore_order():
    import numpy as np

    from synthpopcan._population_preparation import _HouseholdGeographyIndex

    pl = pytest.importorskip("polars", minversion="2.1")
    assignments = {"01": "001", "1": "1", "é": " 002 "}
    index = _HouseholdGeographyIndex(assignments, pl)
    pairs = pl.DataFrame({"id": ["01", "1", "é"], "geo": ["001", "1", " 002 "]})
    index.check(pairs)
    expressions = index._expressions
    index.check(pairs.reverse())
    assert index._expressions is expressions
    assignments.clear()
    index.restore(assignments)
    assert list(assignments.items()) == [("01", "001"), ("1", "1"), ("é", " 002 ")]
    for bad in [
        pl.DataFrame({"id": ["missing"], "geo": ["001"]}),
        pl.DataFrame({"id": ["01"], "geo": ["1"]}),
    ]:
        with pytest.raises(ValueError, match="Person geography"):
            index.check(bad)
    assert np.array_equal(index.codes, np.array([0, 1, 2]))


@pytest.mark.parametrize(
    "person_geo,late_quote", [("last", False), ("first", False), ("last", True)]
)
def test_duplicate_household_geography_uses_last_assignment_before_readback(
    tmp_path, monkeypatch, person_geo, late_quote
):
    pytest.importorskip("polars", minversion="2.1")
    first, hh, person = _batch(tmp_path, "first", "first")
    second, _, _ = _batch(tmp_path, "second", "second")
    hh["note"] = "plain"
    _write(first / "households.csv", list(hh), [hh, {**hh, "ct": "last"}])
    person["ct"] = person_geo
    if late_quote:
        person["category"] = 'quoted,"value"\nline'
    _write(first / "persons.csv", list(person), [person])
    messages = []
    for threshold in [10**15, 0]:
        monkeypatch.setattr("synthpopcan._columnar_csv.MIN_COLUMNAR_BYTES", threshold)
        with pytest.raises(ValueError) as exc:
            combine_populations((first, second), tmp_path / str(threshold), "ct")
        messages.append(str(exc.value))
    assert messages[0] == messages[1]
