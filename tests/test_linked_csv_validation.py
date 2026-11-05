"""File validation projects fields without weakening record-level checks."""

import csv

import pytest

from synthpopcan.tree import validate_linked_population_files


@pytest.fixture(params=[False, True], autouse=True)
def native_parser(request, monkeypatch):
    if request.param:
        pytest.importorskip("polars", minversion="2.1")
    monkeypatch.setattr(
        "synthpopcan._columnar_csv.MIN_COLUMNAR_BYTES", 0 if request.param else 10**15
    )
    return request.param


def test_validation_preserves_diagnostics_with_custom_columns_and_quoted_newlines(
    tmp_path,
):
    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    with households.open("w", newline="") as h:
        writer = csv.writer(h)
        writer.writerows(
            [
                ["id", "size", "unused"],
                ["h1", 2, "two\nlines"],
                ["h2", 1, "fine"],
                ["h2", "bad", "duplicate"],
                ["", 1, "missing"],
            ]
        )
    with persons.open("w", newline="") as h:
        writer = csv.writer(h)
        writer.writerows(
            [
                ["pid", "owner", "unused"],
                ["p1", "h1", "two\nlines"],
                ["p2", "h1", "fine"],
                ["p2", "unknown", "duplicate"],
                ["", "h2", "missing"],
            ]
        )
    result = validate_linked_population_files(
        households,
        persons,
        household_id_column="id",
        household_size_column="size",
        person_household_id_column="owner",
        person_id_column="pid",
    )
    assert result["summary"] == {
        "households": 4,
        "persons": 4,
        "households_with_size_mismatches": 0,
        "persons_with_unknown_households": 1,
        "issue_count": 6,
        "issue_details_truncated": False,
    }
    assert [x["kind"] for x in result["issues"]] == [
        "invalid_household_size",
        "duplicate_household_identifier",
        "duplicate_person_identifier",
        "missing_household_identifier",
        "missing_person_identifier",
        "unknown_person_household",
    ]
    assert not list(tmp_path.glob(".linked-validation-*"))


def test_short_records_and_blank_lines_retain_missing_field_semantics(tmp_path):
    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,household_size,unused\nh1,1\n\nh2\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,unused\np1,h1\n\np2\n"
    )
    result = validate_linked_population_files(households, persons)
    assert result["summary"]["households"] == result["summary"]["persons"] == 2
    assert result["summary"]["persons_with_unknown_households"] == 1
    assert [x["kind"] for x in result["issues"]] == [
        "invalid_household_size",
        "unknown_person_household",
    ]


def test_duplicate_headers_still_use_last_value_as_dictreader_does(tmp_path):
    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    households.write_text(
        "synthetic_household_id,household_size,synthetic_household_id\nwrong,1,h1\n"
    )
    persons.write_text("synthetic_person_id,synthetic_household_id\np1,h1\n")
    assert validate_linked_population_files(households, persons)["passed"]


def test_bulk_replay_preserves_boundary_duplicates_and_issue_order(tmp_path):
    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    with households.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["synthetic_household_id", "household_size"])
        writer.writerow(["h0", 2])
        writer.writerows((f"h{i}", 1) for i in range(1, 4096))
        writer.writerow(["h4096", 1])
        writer.writerow(["h0", "bad"])
        writer.writerow(["h0", 2])
    with persons.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["synthetic_person_id", "synthetic_household_id"])
        writer.writerows([["p0", "h0"], ["p1", "h0"]])
        writer.writerows((f"p{i + 1}", f"h{i}") for i in range(1, 4097))
        writer.writerow(["p0", "unknown"])
        writer.writerow([""])
        writer.writerow(["p0", "h0"])
    expected_kinds = [
        "invalid_household_size",
        "duplicate_household_identifier",
        "duplicate_household_identifier",
        "duplicate_person_identifier",
        "duplicate_person_identifier",
        "household_size_mismatch",
        "missing_person_identifier",
        "unknown_person_household",
    ]
    for limit in [0, 1, 3, 100]:
        result = validate_linked_population_files(
            households, persons, max_issue_details=limit
        )
        assert result["summary"] == {
            "households": 4099,
            "persons": 4101,
            "households_with_size_mismatches": 1,
            "persons_with_unknown_households": 2,
            "issue_count": 9,
            "issue_details_truncated": True,
        }
        assert [issue["kind"] for issue in result["issues"]] == expected_kinds[:limit]
    assert not list(tmp_path.glob(".linked-validation-*"))


def test_partial_bulk_failure_cleans_disposable_database_and_preserves_inputs(
    tmp_path, monkeypatch
):
    import sqlite3

    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,household_size\nh1,1\n")
    persons.write_text("synthetic_person_id,synthetic_household_id\np1,h1\n")
    original = (households.read_bytes(), persons.read_bytes())
    connect = sqlite3.connect

    class BrokenBatch:
        def __init__(self, path):
            self.connection = connect(path)

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def executemany(self, statement, records):
            self.connection.executemany(statement, records)
            raise RuntimeError("injected failure after partial database work")

    monkeypatch.setattr("synthpopcan._linked_validation.sqlite3.connect", BrokenBatch)
    import pytest

    with pytest.raises(RuntimeError, match="injected failure"):
        validate_linked_population_files(households, persons)
    assert (households.read_bytes(), persons.read_bytes()) == original
    assert not list(tmp_path.glob(".linked-validation-*"))


def test_late_quoted_record_restarts_both_files_and_keeps_exact_diagnostics(
    tmp_path, monkeypatch, native_parser
):
    from synthpopcan import tree

    households, persons = tmp_path / "households.csv", tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,household_size\nh1,2\nh2,1\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,unused\n"
        + "p1,h1,ordinary\n" * 5000
        + 'p2,h2,"quoted\nrecord"\n'
        + "p3\np4,\n"
    )
    monkeypatch.setattr("synthpopcan._columnar_csv.CSV_CHUNK_BYTES", 1024)
    attempts = []
    original = tree._validate_linked_files

    def tracked(*args):
        attempts.append(args[-1])
        return original(*args)

    monkeypatch.setattr(tree, "_validate_linked_files", tracked)
    result = tree.validate_linked_population_files(households, persons)
    assert attempts == ([True, False] if native_parser else [False])
    assert result["summary"]["households"] == 2
    assert result["summary"]["persons"] == 5003
    assert result["summary"]["persons_with_unknown_households"] == 2
    assert result["summary"]["households_with_size_mismatches"] == 1
    assert result["summary"]["issue_count"] == 5002
    assert not list(tmp_path.glob(".linked-validation-*"))


def test_validation_batches_keep_boundaries_across_native_csv_buffers(
    tmp_path, monkeypatch, native_parser
):
    from synthpopcan import tree

    path = tmp_path / "people.csv"
    rows = [(f"é{i:05}", f"h{i % 17:03}") for i in range(8201)]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pid", "owner"])
        writer.writerows(rows)
    monkeypatch.setattr("synthpopcan._columnar_csv.CSV_CHUNK_BYTES", 8191)
    with tree._validation_file_batches(
        path, ("pid", "owner"), "person", native_parser
    ) as reader:
        batches = list(reader)
    assert list(map(len, batches)) == [4096, 4096, 9]
    assert [row for batch in batches for row in batch] == rows
