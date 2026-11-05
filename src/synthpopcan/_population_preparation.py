"""Combine disjoint linked populations and independently audit realized controls."""

from __future__ import annotations

import csv
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import Any, cast

import numpy as np

from synthpopcan._columnar_csv import (
    BoundedCSVFallbackError,
    iter_string_frames,
    load_polars,
    should_use_polars,
)
from synthpopcan._profile_preparation import write_json
from synthpopcan.controls import read_control_table
from synthpopcan.linked_schema import (
    build_linked_population_contract_from_shapes,
    read_linked_population_contract,
)
from synthpopcan.tree import validate_linked_population_files


def _source_metadata(sources, geography):
    """Read descriptors and actual headers; row checks happen during copying."""
    fields = {"households": [], "persons": []}
    manifests = [read_linked_population_contract(p / "manifest.json") for p in sources]
    if any(m.get("licensing") != manifests[0].get("licensing") for m in manifests):
        raise ValueError(
            "Population batches have different licensing; combine "
            "only compatible inputs."
        )
    for source in sources:
        for entity in fields:
            with (source / f"{entity}.csv").open(newline="") as handle:
                columns = _table_columns(csv.reader(handle), source, entity, geography)
                fields[entity].extend(f for f in columns if f not in fields[entity])
    return fields, manifests[0].get("licensing")


def _table_columns(reader, source, entity, geography):
    columns = next(reader, [])
    if (
        not columns
        or any(not column for column in columns)
        or len(set(columns)) != len(columns)
    ):
        raise ValueError(f"{source}/{entity}.csv has an invalid or duplicate header.")
    if not {geography, "synthetic_household_id"} <= set(columns):
        raise ValueError(
            f"{source}/{entity}.csv is missing geography column {geography!r}."
        )
    return columns


def _population_rows(source, entity, geography, fields, assignments):
    with (source / f"{entity}.csv").open(newline="") as handle:
        reader = csv.reader(handle)
        columns = _table_columns(reader, source, entity, geography)
        positions = (
            None
            if columns == fields
            else [
                columns.index(field) if field in columns else None for field in fields
            ]
        )
        household_index = columns.index("synthetic_household_id")
        geography_index = columns.index(geography)
        width = len(columns)
        for row in reader:
            if not row:  # Match DictReader's handling of blank physical records.
                continue
            if len(row) > width:
                raise ValueError(
                    f"{source}/{entity}.csv has more fields than its header."
                )
            if len(row) < width:
                row.extend([""] * (width - len(row)))
            household_id, assigned = row[household_index], row[geography_index]
            if entity == "households":
                assignments[household_id] = assigned
            elif assigned != assignments.get(household_id):
                raise ValueError(
                    "Person geography must match its linked household "
                    "before combining batches."
                )
            yield (
                row
                if positions is None
                else [row[index] if index is not None else "" for index in positions]
            )


def _copy_population_table(
    source, entity, geography, fields, writer, assignments, handle
):
    path = source / f"{entity}.csv"
    if should_use_polars(path):
        count = _try_copy_native(path, entity, geography, fields, assignments, handle)
        if count is not None:
            return count
    count = 0
    batch = []
    for row in _population_rows(source, entity, geography, fields, assignments):
        batch.append(row)
        count += 1
        if len(batch) == 4096:
            writer.writerows(batch)
            batch.clear()
    writer.writerows(batch)
    return count


def _try_copy_native(path, entity, geography, fields, assignments, handle):
    """Restart this table on ambiguous CSV; never publish a partial native copy."""
    pl = load_polars()
    if pl is None:
        return None
    handle.flush()
    checkpoint = handle.tell()
    matcher = None
    try:
        if entity == "persons":
            matcher = _HouseholdGeographyIndex(assignments, pl)
            assignments.clear()
        return _copy_native(
            path, entity, geography, fields, assignments, handle, matcher
        )
    except (BoundedCSVFallbackError, pl.exceptions.PolarsError):
        handle.seek(checkpoint)
        handle.truncate()
        if entity == "households":
            assignments.clear()
        elif matcher is not None:
            matcher.restore(assignments)
        return None


class _HouseholdGeographyIndex:
    """Native dictionaries per source; last household assignment wins."""

    def __init__(self, assignments, polars):
        self.polars = polars
        self._expressions = None
        self.identifiers = polars.Enum(list(assignments))
        geographies = polars.Series(
            "geography", list(assignments.values()), dtype=polars.String
        )
        self.geographies = polars.Enum(geographies.unique(maintain_order=True))
        self.codes = geographies.cast(self.geographies).to_physical().to_numpy()

    def check(self, pairs):
        if self._expressions is None:
            # Freeze the enum dictionaries in native expressions once. Passing
            # Python Enum dtypes to Series.cast for every buffer rebuilds them.
            self._expressions = (
                self.polars.col(pairs.columns[0]).cast(self.identifiers, strict=False),
                self.polars.col(pairs.columns[1]).cast(self.geographies, strict=False),
            )
        encoded = pairs.select(self._expressions)
        identifiers, geographies = encoded.to_series(0), encoded.to_series(1)
        if identifiers.null_count() or geographies.null_count():
            self._mismatch()
        locations = identifiers.to_physical().to_numpy()
        observed = geographies.to_physical().to_numpy()
        if np.any(observed != self.codes[locations]):
            self._mismatch()

    def restore(self, assignments):
        assignments.update(
            zip(
                self.identifiers.categories.to_list(),
                self.geographies.categories.gather(self.codes).to_list(),
                strict=True,
            )
        )

    @staticmethod
    def _mismatch():
        raise ValueError(
            "Person geography must match its linked household before combining batches."
        )


def _copy_native(path, entity, geography, fields, assignments, handle, matcher):
    count = 0
    for frame, _ in iter_string_frames(
        path,
        fields,
        required=(geography, "synthetic_household_id"),
        optional_defaults={field: None for field in fields},
        truncate_ragged_lines=False,
    ):
        pairs = frame.select("synthetic_household_id", geography)
        if any(pairs[column].null_count() for column in pairs.columns):
            raise BoundedCSVFallbackError("empty or missing linkage/geography field")
        if matcher is None:
            assignments.update(pairs.iter_rows())
        else:
            matcher.check(pairs)
        # Native nulls represent reference empty strings/padded trailing fields.
        # Leave them null when writing so CSV uses empty, unquoted fields.
        handle.write(
            frame.select(fields).write_csv(
                include_header=False, line_terminator="\r\n", quote_style="necessary"
            )
        )
        count += frame.height
    return count


def combine_populations(
    sources: tuple[Path, ...], output: Path, geography: str
) -> dict[str, Any]:
    """Combine files and publish a standalone report with source diagnostics."""
    report = _combine_population_files(sources, output, geography)
    report["source_reports"] = _read_source_reports(sources)
    write_json(output / "report.json", report)
    return report


def _combine_population_files(
    sources: tuple[Path, ...], output: Path, geography: str
) -> dict[str, Any]:
    """Combine and validate files; the owning workflow publishes its report.

    Prepared calibration already holds the source diagnostics and builds its
    final report after the independent audit. Avoid loading/serializing an
    embedded source-report tree that this caller would immediately discard.
    """
    if len(sources) < 2:
        raise ValueError("Supply at least two disjoint linked population directories.")
    fields, licensing = _source_metadata(sources, geography)
    output.mkdir(parents=True, exist_ok=True)
    counts = {"households": 0, "persons": 0}
    seen = set()
    with ExitStack() as stack:
        handles = {
            entity: stack.enter_context(
                (output / f"{entity}.csv").open("w", newline="")
            )
            for entity in fields
        }
        writers = {entity: csv.writer(handle) for entity, handle in handles.items()}
        for entity, writer in writers.items():
            writer.writerow(fields[entity])
        for source in sources:
            assignments = {}
            counts["households"] += _copy_population_table(
                source,
                "households",
                geography,
                fields["households"],
                writers["households"],
                assignments,
                handles["households"],
            )
            geos = set(assignments.values())
            if "" in geos or seen & geos:
                raise ValueError(
                    "Population batches must have nonempty, disjoint "
                    "geography assignments."
                )
            seen.update(geos)
            counts["persons"] += _copy_population_table(
                source,
                "persons",
                geography,
                fields["persons"],
                writers["persons"],
                assignments,
                handles["persons"],
            )
            # Geography ownership is retained in `seen`; this source lookup is
            # no longer needed during independent final-file validation.
            assignments.clear()
    # Independently read back the actual output files, checking identifiers,
    # links, sizes and observed record counts rather than trusting descriptors.
    validation = validate_linked_population_files(
        output / "households.csv", output / "persons.csv"
    )
    if not validation["passed"] or any(
        validation["summary"][entity] != count for entity, count in counts.items()
    ):
        raise ValueError(
            "Combined population has duplicate IDs or invalid "
            "household/person linkage. Use disjoint calibrated "
            "batches with globally unique IDs."
        )
    contract = build_linked_population_contract_from_shapes(
        output / "households.csv",
        output / "persons.csv",
        household_columns=fields["households"],
        household_rows=counts["households"],
        person_columns=fields["persons"],
        person_rows=counts["persons"],
        geography_column=geography,
        licensing=licensing,
    )
    contract["source_manifests"] = [
        str((p / "manifest.json").resolve()) for p in sources
    ]
    write_json(output / "manifest.json", contract)
    report = {
        "assigned_households": counts["households"],
        "assigned_persons": counts["persons"],
        "geographies": sorted(seen),
        "validation": validation,
        "source_reports": [],
        "policy": (
            "Rows retained unchanged from disjoint batches; "
            "original targets, convergence diagnostics and "
            "residuals retained in source reports."
        ),
    }
    return report


def _read_source_reports(sources: tuple[Path, ...]) -> list[dict[str, Any]]:
    reports = []
    for source in sources:
        path = source / "report.json"
        reports.append(
            {
                "path": str(path.resolve()),
                "report": json.loads(path.read_text()) if path.exists() else None,
            }
        )
    return reports


def _audit_targets(paths, geography):
    targets = []
    specs = {}
    seen = set()
    for path in paths:
        table = read_control_table(path)
        for margin in table.margins:
            if geography not in margin.dimensions:
                raise ValueError(f"Audit controls must include {geography!r}: {path}")
            dimensions = tuple(d for d in margin.dimensions if d != geography)
            for cell in margin.cells:
                geo = cell.categories[geography]
                spec = (geo, margin.name)
                if spec in specs and specs[spec] != dimensions:
                    raise ValueError(
                        f"Conflicting audit dimensions for {geo}, {margin.name}."
                    )
                specs[spec] = dimensions
                category = tuple(cell.categories[d] for d in dimensions)
                key = (*spec, category)
                if key in seen:
                    raise ValueError(
                        f"Duplicate audit target: {geo}, {margin.name}, {category}."
                    )
                seen.add(key)
                targets.append((key, dimensions, cell.count))
    return targets, specs


def _audit_entity(population, entity, paths, geography):
    targets, specs = _audit_targets(paths, geography)
    path = population / f"{entity}s.csv"
    totals = None
    if should_use_polars(path):
        from synthpopcan._polars_audit import try_audit_counts

        totals = try_audit_counts(path, entity, geography, specs)
    if totals is None:
        totals = _audit_counts_streaming(path, entity, geography, specs)
    return _audit_residuals(entity, geography, targets, totals)


def _audit_counts_streaming(path, entity, geography, specs):
    totals: Counter = Counter()
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        columns = next(reader, [])
        required = {geography, *(d for dims in specs.values() for d in dims)}
        if missing := required - set(columns):
            raise ValueError(
                f"Audit {entity} CSV is missing fields: {', '.join(sorted(missing))}."
            )
        positions = {name: index for index, name in enumerate(columns)}
        geography_index = positions[geography]
        width = len(columns)
        by_geo: dict[str, list] = {}
        for (geo, margin), dims in specs.items():
            indexes = tuple(positions[d] for d in dims)
            scalar = indexes[0] if len(indexes) == 1 else None
            by_geo.setdefault(geo, []).append((margin, scalar, indexes))
        for row in reader:
            if not row:
                continue
            if len(row) < width:
                # DictReader represented absent trailing fields as None.
                row = cast(list[Any], row)
                row.extend([None] * (width - len(row)))
            geo = row[geography_index]
            if geo not in by_geo:
                raise ValueError(
                    f"No {entity} audit controls for assigned geography {geo}."
                )
            for margin, scalar, indexes in by_geo[geo]:
                category = (
                    (row[scalar],)
                    if scalar is not None
                    else tuple(row[index] for index in indexes)
                )
                totals[(geo, margin, category)] += 1
    return totals


def _audit_residuals(entity, geography, targets, totals):
    residuals = []
    keys = set()
    for key, dims, target in targets:
        keys.add(key)
        geo, margin, category = key
        realized = totals[key]
        residuals.append(
            {
                "entity": entity,
                geography: geo,
                "margin": margin,
                "categories": dict(zip(dims, category, strict=True)),
                "target": target,
                "realized": realized,
                "residual": realized - target,
                "abs_error": abs(realized - target),
            }
        )
    unexpected = [
        {
            "entity": entity,
            geography: key[0],
            "margin": key[1],
            "categories": list(key[2]),
            "realized": count,
        }
        for key, count in totals.items()
        if key not in keys
    ]
    return residuals, unexpected


def audit_population(
    population: Path,
    household_controls: tuple[Path, ...],
    person_controls: tuple[Path, ...],
    output: Path,
    geography="ct",
) -> dict[str, Any]:
    residuals, unexpected = [], []
    for entity, paths in [
        ("household", household_controls),
        ("person", person_controls),
    ]:
        if paths:
            rows, extra = _audit_entity(population, entity, paths, geography)
            residuals.extend(rows)
            unexpected.extend(extra)
    if not residuals:
        raise ValueError(
            "Supply at least one nonempty household or person control table."
        )
    residuals.sort(key=lambda row: (-row["abs_error"], row[geography], row["margin"]))
    output.mkdir(parents=True, exist_ok=True)
    with (output / "realized-control-residuals.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(residuals[0]))
        writer.writeheader()
        writer.writerows(
            {**row, "categories": json.dumps(row["categories"], sort_keys=True)}
            for row in residuals
        )
    errors = [r["abs_error"] for r in residuals]
    report = {
        "control_cells": len(errors),
        "matched_exactly": sum(e == 0 for e in errors),
        "max_abs_error": max(errors),
        "median_abs_error": float(np.median(errors)),
        "p95_abs_error": float(np.percentile(errors, 95)),
        "unexpected_categories": unexpected,
        "top_residuals": residuals[:20],
        "aggregation": (
            "Independent streaming read-back of assigned "
            "household and person CSVs; prepared targets "
            "unmodified. Residuals are diagnostic, not a claim of "
            "exact integer convergence."
        ),
    }
    write_json(output / "realized-control-audit.json", report)
    return report
