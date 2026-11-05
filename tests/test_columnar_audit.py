"""Native CSV counts preserve independent read-back and reference diagnostics."""

from __future__ import annotations

import csv

import pytest

from synthpopcan import _columnar_csv as columnar
from synthpopcan import _population_preparation as population
from synthpopcan._polars_audit import try_audit_counts


@pytest.fixture
def native_csv():
    return pytest.importorskip("polars")


@pytest.fixture
def audit_inputs(tmp_path):
    controls = tmp_path / "controls.csv"
    with controls.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["margin", "dimensions", "ct", "A", "B", "count"])
        for geo in ("001", "002"):
            writer.writerows(
                [
                    ["first", "ct,A", geo, "x", "", "1"],
                    ["second", "ct,B,A", geo, "x", "y", "1"],
                    ["total", "ct", geo, "", "", "1"],
                ]
            )
    return tmp_path, (controls,)


def _outcome(function):
    try:
        return function()
    except (ValueError, csv.Error, UnicodeDecodeError) as error:
        return type(error), str(error)


@pytest.mark.parametrize(
    "content",
    [
        "ct,A,B\n002,z,z\n001,x,y\n002,w,z\n001,z,y\n001,x,y\n",
        "ct,A,A,B\n001,wrong,x,y\n002,bad,z,y\n",
        "ct,A,B,ct\nwrong,x,y,001\n",
        "ct,A,B\n",
        "ct,A,B\n001,null,NA\n002,None,NaN\n",
        "ct,A,B\r\n001,été,français\r\n002,x,y",
    ],
    ids=[
        "unexpected-source-order",
        "duplicate-category",
        "duplicate-geography",
        "header-only",
        "literal-null",
        "split-utf8-crlf",
    ],
)
def test_native_counts_match_reference_across_small_record_blocks(
    audit_inputs, native_csv, monkeypatch, content
):
    root, paths = audit_inputs
    path = root / "households.csv"
    path.write_bytes(content.encode())
    _, specs = population._audit_targets(paths, "ct")
    expected = population._audit_counts_streaming(path, "household", "ct", specs)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 7)
    actual = try_audit_counts(path, "household", "ct", specs)
    assert actual is not None, "fixture must exercise the native path"
    assert list(actual.items()) == list(expected.items())


@pytest.mark.parametrize(
    "tail",
    [
        '002,"quoted,category",y\n',
        '002,"",y\n',
        "002,,y\n",
        "002,x\n",
        "002,x,y\r001,z,w\n",
        "002,x," + "z" * 140_000 + "\n",
        "002,x,y," + "z" * 140_000 + "\n",
        "002,x,\x00value\n",
        "\ufeff002,x,y\n",
        "   \n",
    ],
    ids=[
        "quote",
        "quoted-empty",
        "empty",
        "short",
        "bare-cr",
        "long-field",
        "long-unprojected",
        "nul",
        "data-bom",
        "space-record",
    ],
)
def test_late_native_fallback_restarts_actual_file_with_reference_semantics(
    audit_inputs, native_csv, monkeypatch, tail
):
    root, paths = audit_inputs
    (root / "households.csv").write_bytes(("ct,A,B\n001,x,y\n" + tail).encode())
    monkeypatch.setattr(population, "should_use_polars", lambda *_: False)
    expected = _outcome(
        lambda: population._audit_entity(root, "household", paths, "ct")
    )
    monkeypatch.setattr(population, "should_use_polars", lambda *_: True)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 17)
    streaming = population._audit_counts_streaming
    calls = []

    def reference(*args):
        calls.append(True)
        return streaming(*args)

    monkeypatch.setattr(population, "_audit_counts_streaming", reference)
    actual = _outcome(lambda: population._audit_entity(root, "household", paths, "ct"))
    assert actual == expected
    assert calls == [True], (
        "late ambiguity must restart, not retain partial native totals"
    )


@pytest.mark.parametrize(
    "content",
    [
        "ct,A,B\nzzz,x,y\naaa,z,y\n",
        "ct,A\n001,x\n",
        "ct,A,B\n\x1c001\x1f,x,y\n",
        "ct,A,B\n\ufeff001,x,y\n",
        "ct,A,B\n\n001,x,y\n\n",
        "ct,A,B\n001,x,y,ignored,extra\n",
    ],
    ids=[
        "first-unknown-geography",
        "missing-header",
        "c0-geography",
        "leading-data-bom",
        "blank-records",
        "extra-fields",
    ],
)
def test_native_dispatch_preserves_reference_results_and_diagnostics(
    audit_inputs, native_csv, monkeypatch, content
):
    root, paths = audit_inputs
    (root / "households.csv").write_text(content)
    monkeypatch.setattr(population, "should_use_polars", lambda *_: False)
    expected = _outcome(
        lambda: population._audit_entity(root, "household", paths, "ct")
    )
    monkeypatch.setattr(population, "should_use_polars", lambda *_: True)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 5)
    assert (
        _outcome(lambda: population._audit_entity(root, "household", paths, "ct"))
        == expected
    )


def test_shared_reader_preserves_optional_defaults_duplicate_ids_and_source_order(
    tmp_path, native_csv, monkeypatch
):
    path = tmp_path / "rows.csv"
    path.write_bytes(b"id,id,value\r\nwrong,001,2\r\nwrong,002,3")
    frames = list(
        columnar.iter_string_frames(
            path,
            ("id", "missing", "value"),
            optional_defaults={"missing": ""},
            required=("id",),
            chunk_bytes=5,
        )
    )
    assert [row for frame, _ in frames for row in frame.iter_rows(named=True)] == [
        {"__source_row": 0, "id": "001", "missing": "", "value": "2"},
        {"__source_row": 1, "id": "002", "missing": "", "value": "3"},
    ]
    assert all(present == {"id", "value"} for _, present in frames)


def test_small_inputs_do_not_even_probe_optional_dependency(tmp_path, monkeypatch):
    path = tmp_path / "small.csv"
    path.write_text("id\n001\n")
    monkeypatch.setattr(columnar, "find_spec", lambda _: pytest.fail("small input"))
    assert not columnar.should_use_polars(path)


def test_large_inputs_keep_reference_when_optional_dependency_absent(
    tmp_path, monkeypatch
):
    path = tmp_path / "large.csv"
    path.write_text("id\n001\n")
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 1)
    monkeypatch.setattr(columnar, "find_spec", lambda _: None)
    assert not columnar.should_use_polars(path)


def test_audit_optional_import_failure_keeps_reference_available(tmp_path, monkeypatch):
    def unavailable(_):
        raise ImportError("optional Polars is unavailable")

    monkeypatch.setattr(columnar, "import_module", unavailable)
    assert try_audit_counts(tmp_path / "unused.csv", "household", "ct", {}) is None


def test_shared_reader_rejects_nonpositive_chunk_size(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("id\n001\n")
    with pytest.raises(ValueError, match="positive"):
        list(columnar._plain_blocks(path, 0))


@pytest.mark.parametrize("version", ["1.35.0", "2.0.0"])
def test_older_unrelated_polars_installation_keeps_reference_path(monkeypatch, version):
    from types import SimpleNamespace

    monkeypatch.setattr(
        columnar, "import_module", lambda _: SimpleNamespace(__version__=version)
    )
    assert columnar.load_polars() is None


def test_metadata_probe_failure_leaves_input_errors_to_reference(tmp_path):
    assert not columnar.should_use_polars(tmp_path / "missing.csv")


def test_unsupported_optional_module_probe_keeps_reference(tmp_path, monkeypatch):
    path = tmp_path / "rows.csv"
    path.write_text("id\n001\n")
    monkeypatch.setattr(columnar, "MIN_COLUMNAR_BYTES", 1)

    def unavailable(_):
        raise ValueError("module has no __spec__")

    monkeypatch.setattr(columnar, "find_spec", unavailable)
    assert not columnar.should_use_polars(path)


@pytest.mark.parametrize("limit", [0, 1, 8, 128])
@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"a",
        b"a\n",
        b"a\r\n",
        b"a\rb",
        b"a\r",
        b"\r\r\n",
        b"\x00",
        b'"',
        b"\xef\xbb\xbf",
        b"abcdefgh\nx",
        b"abcdefghx\nx",
    ],
)
def test_vector_record_guard_preserves_reference_boundaries(limit, data):
    # The guard deliberately allows a final CR until the next block arrives.
    # A full record is a conservative upper bound on every selected/unselected field.
    old = csv.field_size_limit(limit)
    try:
        remainder = data[:-1] if data.endswith(b"\r") else data
        rejected = (
            b'"' in data
            or b"\0" in data
            or b"\xef\xbb\xbf" in data
            or b"\r" in remainder.replace(b"\r\n", b"")
            or max(map(len, data.split(b"\n")), default=0) > limit
        )
        if rejected:
            with pytest.raises(columnar.BoundedCSVFallbackError):
                columnar._check_plain_records(data)
        else:
            columnar._check_plain_records(data)
    finally:
        csv.field_size_limit(old)


def test_native_audit_rolls_many_partial_counts_without_losing_source_order(
    audit_inputs, native_csv, monkeypatch
):
    root, paths = audit_inputs
    path = root / "households.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ct", "A", "B"])
        writer.writerows(
            [["002", "z", "y"], ["001", "x", "y"], ["002", "x", "z"]] * 200
        )
    _, specs = population._audit_targets(paths, "ct")
    expected = population._audit_counts_streaming(path, "household", "ct", specs)
    monkeypatch.setattr(columnar, "CSV_CHUNK_BYTES", 47)
    actual = try_audit_counts(path, "household", "ct", specs)
    assert actual is not None
    assert list(actual.items()) == list(expected.items())


def test_carriage_return_scan_matches_reference_for_all_short_boundaries():
    from itertools import product

    for length in range(7):
        for symbols in product((b"x", b"\r", b"\n"), repeat=length):
            data = b"".join(symbols)
            remainder = data[:-1] if data.endswith(b"\r") else data
            if b"\r" in remainder.replace(b"\r\n", b""):
                with pytest.raises(columnar.BoundedCSVFallbackError, match="carriage"):
                    columnar._check_plain_records(data)
            else:
                columnar._check_plain_records(data)
