"""Bounded independent file linkage validation with ordered reference fallback."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any


def _validate_linked_files(households_path, persons_path, options, native):
    household_id_column = options["household_id_column"]
    person_household_id_column = options["person_household_id_column"]
    person_id_column = options["person_id_column"]
    household_size_column = options["household_size_column"]
    max_issue_details = options["max_issue_details"]
    if max_issue_details < 0:
        raise ValueError("max issue details must not be negative")
    scratch = tempfile.NamedTemporaryFile(
        prefix=".linked-validation-",
        suffix=".sqlite3",
        dir=households_path.parent,
        delete=False,
    )
    scratch_path = Path(scratch.name)
    scratch.close()
    connection = sqlite3.connect(scratch_path)
    issues: list[dict[str, Any]] = []
    household_count = 0
    person_count = 0
    missing_household_ids = 0
    missing_person_ids = 0
    duplicate_household_ids = 0
    duplicate_person_ids = 0
    invalid_household_sizes = 0

    def add_issue(issue: dict[str, Any]) -> None:
        if len(issues) < max_issue_details:
            issues.append(issue)

    try:
        # Larger B-tree pages reduce scratch-index overhead without increasing
        # the byte-bounded cache or changing rollback/duplicate semantics.
        connection.execute("PRAGMA page_size=16384")
        connection.executescript(
            """
            CREATE TABLE households (
                identifier TEXT PRIMARY KEY,
                expected_persons INTEGER
            ) WITHOUT ROWID;
            CREATE TABLE person_ids (identifier TEXT PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE household_counts (
                identifier TEXT PRIMARY KEY,
                person_count INTEGER NOT NULL
            ) WITHOUT ROWID;
            """
        )
        # The database is disposable. Keep file-backed rollback/savepoints for
        # exact duplicate handling, without durable scratch-file synchronization.
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA cache_size=-262144")
        connection.execute("BEGIN")
        (
            household_count,
            missing_household_ids,
            duplicate_household_ids,
            invalid_household_sizes,
        ) = _load_validation_households(
            connection,
            households_path,
            household_id_column,
            household_size_column,
            add_issue,
            native,
        )
        person_count, missing_person_ids, duplicate_person_ids, null_households = (
            _load_validation_persons(
                connection,
                persons_path,
                person_id_column,
                person_household_id_column,
                add_issue,
                native,
            )
        )
        connection.commit()

        unknown_person_households = null_households + int(
            connection.execute(
                """
                SELECT COALESCE(SUM(c.person_count), 0)
                FROM household_counts AS c
                LEFT JOIN households AS h ON h.identifier = c.identifier
                WHERE h.identifier IS NULL
                """
            ).fetchone()[0]
        )
        size_mismatches = 0
        for identifier, expected, actual in connection.execute(
            """
            SELECT h.identifier, h.expected_persons, COALESCE(c.person_count, 0)
            FROM households AS h
            LEFT JOIN household_counts AS c ON c.identifier = h.identifier
            WHERE h.expected_persons IS NOT NULL
              AND h.expected_persons != COALESCE(c.person_count, 0)
            """
        ):
            size_mismatches += 1
            add_issue(
                {
                    "severity": "error",
                    "kind": "household_size_mismatch",
                    "household_id": identifier,
                    "expected_persons": expected,
                    "actual_persons": actual,
                    "message": (
                        f"household {identifier} expected {expected} persons "
                        f"but has {actual}."
                    ),
                }
            )

        for count, kind, message in (
            (
                missing_household_ids,
                "missing_household_identifier",
                f"{missing_household_ids} household rows have no identifier.",
            ),
            (
                missing_person_ids,
                "missing_person_identifier",
                f"{missing_person_ids} person rows have no identifier.",
            ),
            (
                unknown_person_households,
                "unknown_person_household",
                (
                    f"{unknown_person_households} person rows reference unknown "
                    "households."
                ),
            ),
        ):
            if count:
                add_issue(
                    {
                        "severity": "error",
                        "kind": kind,
                        "rows": count,
                        "message": message,
                    }
                )

        issue_count = (
            missing_household_ids
            + missing_person_ids
            + duplicate_household_ids
            + duplicate_person_ids
            + invalid_household_sizes
            + unknown_person_households
            + size_mismatches
        )
        return {
            "passed": issue_count == 0,
            "summary": {
                "households": household_count,
                "persons": person_count,
                "households_with_size_mismatches": size_mismatches,
                "persons_with_unknown_households": unknown_person_households,
                "issue_count": issue_count,
                "issue_details_truncated": issue_count > len(issues),
            },
            "household_id_column": household_id_column,
            "person_household_id_column": person_household_id_column,
            "household_size_column": household_size_column,
            "issues": issues,
        }
    finally:
        connection.close()
        scratch_path.unlink(missing_ok=True)


_VALIDATION_BATCH_ROWS = 4096


def _validation_file_batches(path, required, label, native):
    """Own the reader lifetime, including a failed optional native attempt."""
    from contextlib import closing

    return closing(_project_validation_batches(path, required, label, native))


def _project_validation_batches(path, required, label, native):
    if not native:
        with path.open(newline="") as handle:
            yield from _validation_batches(_validation_rows(handle, required, label))
        return
    from synthpopcan._columnar_csv import (
        BoundedCSVFallbackError,
        iter_string_frames,
        load_polars,
    )

    pl = load_polars()
    if pl is None:
        raise BoundedCSVFallbackError("compatible optional Polars is unavailable")
    pending = []
    try:
        for frame, _ in iter_string_frames(path, required, required=required):
            if any(frame[column].null_count() for column in required):
                # Empty fields and missing trailing fields have different size
                # diagnostics. Let DictReader-compatible projection decide.
                raise BoundedCSVFallbackError("empty or missing validation field")
            projected = frame.select(required)
            offset = 0
            while offset < projected.height:
                rows = projected.slice(
                    offset, _VALIDATION_BATCH_ROWS - len(pending)
                ).rows()
                offset += len(rows)
                if pending:
                    pending.extend(rows)
                else:
                    pending = rows
                if len(pending) == _VALIDATION_BATCH_ROWS:
                    yield pending
                    pending = []
        if pending:
            yield pending
    except pl.exceptions.PolarsError as exc:
        raise BoundedCSVFallbackError("unsupported native CSV") from exc


def _validation_batches(reader, size=_VALIDATION_BATCH_ROWS):
    """Bound temporary Python records independently of population size."""
    batch = []
    for row in reader:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert_validation_batch(connection, statement, records):
    """Use a bulk fast path, replaying only batches that contain duplicate IDs.

    The outer transaction is explicit so releasing each savepoint does not
    commit the database. Rollback removes partial executemany inserts before
    ordered replay, preserving first-seen rows and duplicate diagnostics.
    """
    connection.execute("SAVEPOINT validation_batch")
    try:
        connection.executemany(statement, records)
    except sqlite3.IntegrityError:
        connection.execute("ROLLBACK TO validation_batch")
        connection.execute("RELEASE validation_batch")
        duplicates = []
        for index, record in enumerate(records):
            try:
                connection.execute(statement, record)
            except sqlite3.IntegrityError:
                duplicates.append(index)
        return duplicates
    connection.execute("RELEASE validation_batch")
    return []


def _load_validation_households(
    connection, path, identifier_column, size_column, add_issue, native=False
):
    count = missing = duplicate_count = invalid_count = 0
    required = (
        (identifier_column, size_column)
        if size_column is not None
        else (identifier_column,)
    )
    with _validation_file_batches(path, required, "household", native) as batches:
        for batch in batches:
            records, row_issues = [], []
            for household in batch:
                count += 1
                identifier = household[0]
                if not identifier:
                    missing += 1
                    continue
                expected, issue = None, None
                if size_column is not None:
                    try:
                        expected = _parse_household_size(household[1], size_column)
                    except ValueError as exc:
                        invalid_count += 1
                        issue = {
                            "severity": "error",
                            "kind": "invalid_household_size",
                            "household_id": identifier,
                            "message": str(exc),
                        }
                records.append((identifier, expected))
                row_issues.append(issue)
            duplicates = set(
                _insert_validation_batch(
                    connection,
                    "INSERT INTO households VALUES (?, ?)",
                    records,
                )
            )
            duplicate_count += len(duplicates)
            if not duplicates and not any(row_issues):
                continue
            for index, (identifier, _expected) in enumerate(records):
                if row_issues[index] is not None:
                    add_issue(row_issues[index])
                if index in duplicates:
                    add_issue(
                        {
                            "severity": "error",
                            "kind": "duplicate_household_identifier",
                            "identifier": identifier,
                            "message": "household identifiers must be unique.",
                        }
                    )
    return count, missing, duplicate_count, invalid_count


def _load_validation_persons(
    connection, path, identifier_column, household_column, add_issue, native=False
):
    from operator import itemgetter

    count = missing = duplicate_count = null_households = 0
    with _validation_file_batches(
        path, (identifier_column, household_column), "person", native
    ) as batches:
        for batch in batches:
            records = [(identifier,) for identifier, _ in batch if identifier]
            count += len(batch)
            missing += len(batch) - len(records)
            household_counts = Counter(map(itemgetter(1), batch))
            # Missing trailing foreign keys are always unknown: household rows
            # without IDs are never inserted. Count them explicitly so the
            # remaining non-null keys can use a single WITHOUT ROWID index.
            null_households += household_counts.pop(None, 0)
            duplicates = _insert_validation_batch(
                connection,
                "INSERT INTO person_ids VALUES (?)",
                records,
            )
            duplicate_count += len(duplicates)
            for index in duplicates:
                add_issue(
                    {
                        "severity": "error",
                        "kind": "duplicate_person_identifier",
                        "identifier": records[index][0],
                        "message": "person identifiers must be unique.",
                    }
                )
            connection.executemany(
                """INSERT INTO household_counts VALUES (?, ?)
                ON CONFLICT(identifier) DO UPDATE
                SET person_count = person_count + excluded.person_count""",
                household_counts.items(),
            )
    return count, missing, duplicate_count, null_households


def _validation_rows(
    handle: Iterable[str], required: tuple[str, ...], label: str
) -> Iterator[tuple[Any, ...]]:
    """Project tuples while preserving duplicate-header and short-row semantics."""
    reader = csv.reader(handle)
    columns = next(reader, [])
    _require_csv_columns(columns, required, label)
    positions = {name: index for index, name in enumerate(columns)}
    indices = tuple(positions[name] for name in required)
    first = indices[0]
    second = indices[1] if len(indices) == 2 else None
    for values in reader:
        if values:  # DictReader ignores blank records, but counts quoted newlines.
            width = len(values)
            left = values[first] if first < width else None
            if second is None:
                yield (left,)
            else:
                yield (left, values[second] if second < width else None)


def _require_csv_columns(
    fieldnames: Sequence[str] | None,
    required: tuple[str, ...],
    label: str,
) -> None:
    missing = [column for column in required if column not in (fieldnames or [])]
    if missing:
        raise ValueError(f"{label} CSV is missing columns: {', '.join(missing)}")


def _parse_household_size(value, household_size_column):
    if value is None:
        raise ValueError(f"missing household size column: {household_size_column}")
    try:
        household_size = int(value)
    except ValueError as exc:
        raise ValueError(f"household size {value!r} is not a whole number") from exc
    if household_size <= 0:
        raise ValueError("household size must be greater than zero")
    return household_size
