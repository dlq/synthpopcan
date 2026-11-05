"""Differential coverage for bounded optional map statistics and exact fallback."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from support.map_fixtures import _write_fake_geojson

from synthpopcan import _columnar_csv as columnar
from synthpopcan import _map_statistics as maps
from synthpopcan import _polars_map_statistics as native
from synthpopcan.map_render import _render_statistics_map


@pytest.fixture
def polars():
    return pytest.importorskip("polars", minversion="2.1")


@pytest.fixture
def population(tmp_path):
    households = [
        dict(
            ct="001.00",
            synthetic_household_id="NA",
            household_size="2",
            TENUR="1",
            DTYPE="1",
            REPAIR="1",
            SHELCO="1001",
        ),
        dict(
            ct="001.00",
            synthetic_household_id="002",
            household_size="1",
            TENUR="2",
            DTYPE="8",
            REPAIR="3",
            SHELCO="1002",
        ),
        dict(
            ct="Gé",
            synthetic_household_id="003-é",
            household_size="2",
            TENUR="3",
            DTYPE="2",
            REPAIR="2",
            SHELCO="88888888",
        ),
        dict(
            ct="No people",
            synthetic_household_id="none",
            household_size="1",
            TENUR="1",
            DTYPE="1",
            REPAIR="1",
            SHELCO="0",
        ),
    ]
    fields = (
        "AGEGRP GENDER CITIZEN IMMSTAT GENSTAT VISMIN MARSTH HDGREE LFACT "
        "FPTWK MTNEN MTNFR HLMOSTEN HLMOSTFR MTNNO HLMOSTNO TOTINC EMPIN"
    ).split()
    people = []
    for index, (geo, household, age, income) in enumerate(
        (
            ("001.00", "NA", "4", "-1"),
            ("001.00", "NA", "2", "1"),
            ("001.00", "002", "13", "1"),
            ("Gé", "003-é", "12", "-100"),
            ("Gé", "003-é", "3", "200"),
            ("Elsewhere", "outside", "88", "99999999"),
        )
    ):
        row = dict(
            ct=geo,
            synthetic_person_id=f"p{index}",
            synthetic_household_id=household,
            **dict.fromkeys(fields, "1"),
        )
        row.update(AGEGRP=age, TOTINC=income, EMPIN="-25" if index % 2 else "1000")
        people.append(row)
    people[0].update(HDGREE="7", LFACT="9")
    people[2].update(HDGREE="88", LFACT="14")
    return tmp_path / "households.csv", tmp_path / "persons.csv", households, people


def _write(path, fields, records, *, extra=False, short=False, blank=False):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for index, record in enumerate(records):
            row = [record.get(name, "") for name in fields]
            if short and index == 1:
                row = row[:-1]
            if extra and index == 0:
                row.append("ignored extra")
            writer.writerow(row)
            if blank and index == 0:
                writer.writerow([])


def _publish(population, *, duplicate=False, missing_ids=False, **options):
    hh, pp, households, people = population
    hh_fields, pp_fields = list(households[0]), list(people[0])
    if duplicate:
        hh_fields.append("TENUR")
        pp_fields.append("AGEGRP")
    if missing_ids:
        hh_fields.remove("synthetic_household_id")
        pp_fields.remove("synthetic_household_id")
    _write(hh, hh_fields, households, **options)
    _write(pp, pp_fields, people, **options)
    return hh, pp


def _assert_exact(actual, expected):
    # Serialized comparison includes insertion order and int-versus-float types.
    assert json.dumps(actual, ensure_ascii=False) == json.dumps(
        expected, ensure_ascii=False
    )


@pytest.mark.parametrize("chunk_bytes", [17, 128, 4 * 1024 * 1024])
@pytest.mark.parametrize("explicit", [False, True])
def test_native_summaries_match_reference_across_csv_and_household_boundaries(
    population, monkeypatch, polars, chunk_bytes, explicit
):
    if explicit:
        for index, row in enumerate(population[3]):
            row.update(
                age_under_20="" if index == 0 else str(index % 2),
                age_65_plus="0",
                visible_minority="1",
            )
    hh, pp = _publish(population)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", chunk_bytes)
    expected = maps._compute_linked_statistics_reference(hh, pp, "ct")
    actual = native.try_compute_linked_statistics(hh, pp, "ct")
    assert actual is not None
    _assert_exact(actual, expected)
    assert actual[0]["001.00"]["median_hh_income"] == 0  # median(0, 1) rounds to even.
    assert actual[0]["001.00"]["median_shelter_cost"] == 1002
    assert actual[1]["001.00"]["median_personal_income"] == 0.0
    assert type(actual[1]["001.00"]["median_personal_income"]) is float
    assert actual[0]["No people"]["median_hh_income"] is None
    assert actual[1]["001.00"]["pct_bachelor_plus_known"] == 1
    assert actual[1]["001.00"]["pct_bachelor_plus_eligible"] == 2
    assert actual[1]["001.00"]["unemployment_rate_known"] == 2
    assert actual[1]["001.00"]["unemployment_rate_n"] == 1


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "short_numeric",
        "extra",
        "blank",
        "missing_ids",
        "unicode_integer",
        "underscore",
        "huge_size",
        "sentinel",
        "minimum_int64",
        "nan",
        "control_whitespace",
        "missing_income",
        "all_missing_sizes",
    ],
)
def test_dispatch_keeps_reference_semantics_for_edge_records(
    population, monkeypatch, polars, case
):
    households, people = population[2:]
    options = {}
    if case == "duplicate":
        options["duplicate"] = True
    elif case == "short_numeric":
        options["short"] = True
    elif case in {"extra", "blank", "missing_ids"}:
        options[case] = True
    elif case in {"unicode_integer", "underscore", "sentinel", "minimum_int64", "nan"}:
        people[0]["TOTINC"] = {
            "unicode_integer": "１２",
            "underscore": "1_0",
            "sentinel": "-88888888",
            "minimum_int64": "-9223372036854775808",
            "nan": "NaN",
        }[case]
    elif case == "huge_size":
        households[0]["household_size"] = "10000000000000000000000000000000000001"
    elif case == "control_whitespace":
        households[0]["ct"] = "\x1c001.00\x1f"
        people[0]["ct"] = "\x1c001.00\x1f"
    elif case == "missing_income":
        for row in people:
            row.pop("TOTINC")
    elif case == "all_missing_sizes":
        for row in households:
            row.update(household_size="NaN", SHELCO="99999999")
    hh, pp = _publish(population, **options)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 67)
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 0)
    expected = maps._compute_linked_statistics_reference(hh, pp, "ct")
    _assert_exact(maps.compute_linked_statistics(hh, pp, "ct"), expected)


@pytest.mark.parametrize("ending", [b"", b"\n"])
def test_native_last_record_and_crlf_utf8_splits_are_exact(
    population, monkeypatch, polars, ending
):
    hh, pp = _publish(population, duplicate=True)
    for path in (hh, pp):
        path.write_bytes(path.read_bytes().rstrip(b"\r\n") + ending)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 1)
    actual = native.try_compute_linked_statistics(hh, pp, "ct")
    assert actual is not None
    _assert_exact(actual, maps._compute_linked_statistics_reference(hh, pp, "ct"))


@pytest.mark.parametrize(
    "problem",
    ["quote", "short_identifier", "empty_geography", "whitespace_geography"],
)
def test_late_ambiguous_record_discards_partial_native_results(
    population, monkeypatch, polars, problem
):
    hh, pp = _publish(population)
    data = pp.read_text()
    if problem == "quote":
        data = data.replace("Elsewhere", '"Elsewhere"')
    elif problem == "short_identifier":
        fields = list(population[3][0])
        fields.remove("synthetic_household_id")
        fields.append("synthetic_household_id")
        _write(pp, fields, population[3])
        lines = pp.read_text().splitlines()
        lines[-1] = lines[-1].rsplit(",", 1)[0]
        data = "\n".join(lines) + "\n"
    else:
        data = data.replace("Elsewhere", "" if problem == "empty_geography" else " \t ")
    pp.write_text(data)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 31)
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 0)
    prepared_people = []
    prepare = native._MapStatistics.prepare

    def observe(self, frame, fields, **kwargs):
        if "AGEGRP" in fields:
            prepared_people.append(frame.height)
        return prepare(self, frame, fields, **kwargs)

    monkeypatch.setattr(native._MapStatistics, "prepare", observe)
    reference = maps._compute_linked_statistics_reference
    reference_calls = []

    def fallback(*args):
        reference_calls.append(args)
        return reference(*args)

    monkeypatch.setattr(maps, "_compute_linked_statistics_reference", fallback)
    if problem in {"empty_geography", "whitespace_geography"}:
        with pytest.raises(ValueError, match="has no ct assignment"):
            maps.compute_linked_statistics(hh, pp, "ct")
    else:
        _assert_exact(
            maps.compute_linked_statistics(hh, pp, "ct"), reference(hh, pp, "ct")
        )
    assert len(prepared_people) >= 2
    assert reference_calls == [(hh, pp, "ct")]


@pytest.mark.parametrize("empty", ["households", "persons"])
def test_header_only_input_delegates_exactly(population, monkeypatch, polars, empty):
    hh, pp = _publish(population)
    path = hh if empty == "households" else pp
    path.write_text(path.read_text().splitlines()[0] + "\n")
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 0)
    assert native.try_compute_linked_statistics(hh, pp, "ct") is None
    _assert_exact(
        maps.compute_linked_statistics(hh, pp, "ct"),
        maps._compute_linked_statistics_reference(hh, pp, "ct"),
    )


def test_native_and_reference_render_both_views_identically(
    population, tmp_path, polars
):
    hh, pp = _publish(population)
    old = maps._compute_linked_statistics_reference(hh, pp, "ct")
    new = native.try_compute_linked_statistics(hh, pp, "ct")
    assert new is not None
    boundary = tmp_path / "boundary.geojson"
    _write_fake_geojson(boundary, ["001.00", "Gé", "No people", "Elsewhere"])
    for index, person_attributes in enumerate((False, True)):
        outputs = []
        for name, statistics in (("old", old[index]), ("new", new[index])):
            path = tmp_path / f"{name}-{index}.html"
            _render_statistics_map(
                stats=statistics,
                boundaries_path=boundary,
                geography_id_field="CTUID",
                out_path=path,
                title="Exact map",
                coord_precision=5,
                geography_context=None,
                person_attributes=person_attributes,
            )
            outputs.append(path.read_bytes())
        assert outputs[0] == outputs[1]


def test_map_import_keeps_polars_unloaded():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import synthpopcan._polars_map_statistics; "
            "assert 'polars' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_small_inputs_keep_the_reference_path(population, monkeypatch):
    hh, pp = _publish(population)
    monkeypatch.setattr(
        native,
        "try_compute_linked_statistics",
        lambda *_: pytest.fail("small maps should not start Polars"),
    )
    _assert_exact(
        maps.compute_linked_statistics(hh, pp, "ct"),
        maps._compute_linked_statistics_reference(hh, pp, "ct"),
    )


@pytest.mark.parametrize("available", [False, "old"])
def test_optional_unavailable_or_old_polars_uses_reference(
    population, monkeypatch, available
):
    hh, pp = _publish(population)

    def importing(_name):
        if not available:
            raise ImportError("optional Polars unavailable")
        return SimpleNamespace(__version__="1.38.0")

    monkeypatch.setattr(columnar, "import_module", importing)
    monkeypatch.setattr(columnar, "should_use_polars", lambda *_: True)
    _assert_exact(
        maps.compute_linked_statistics(hh, pp, "ct"),
        maps._compute_linked_statistics_reference(hh, pp, "ct"),
    )


def test_native_attempt_keeps_actual_file_errors_visible(tmp_path, polars):
    with pytest.raises(FileNotFoundError):
        native.try_compute_linked_statistics(
            tmp_path / "missing.csv", tmp_path / "persons.csv", "ct"
        )


def test_sum_guards_cover_per_block_and_merged_overflow(monkeypatch, polars):
    monkeypatch.setattr(native, "_INT64_MAX", 100)
    monkeypatch.setattr(native, "_MAX_INCOME", 60)
    engine = native._MapStatistics(polars, "ct")
    with pytest.raises(columnar.BoundedCSVFallbackError, match="block"):
        engine._check_sums(
            polars.DataFrame({"__number_TOTINC": [50, 51]}), households=False
        )
    engine._check_sums(polars.DataFrame({"__number_TOTINC": [50]}), households=False)
    with pytest.raises(columnar.BoundedCSVFallbackError, match="totals"):
        engine._check_sums(
            polars.DataFrame({"__number_TOTINC": [51]}), households=False
        )


def test_precision_bound_discards_partial_maps_before_float_median_loss(
    population, monkeypatch, polars
):
    hh, pp = _publish(population)
    monkeypatch.setattr(native, "_MAX_EXACT_SUM", 10)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 31)
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 0)
    assert native.try_compute_linked_statistics(hh, pp, "ct") is None
    _assert_exact(
        maps.compute_linked_statistics(hh, pp, "ct"),
        maps._compute_linked_statistics_reference(hh, pp, "ct"),
    )
