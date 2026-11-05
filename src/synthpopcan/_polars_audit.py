"""Independent control counts from bounded, projected population CSV frames."""

from __future__ import annotations

from collections import Counter

from synthpopcan._columnar_csv import (
    BoundedCSVFallbackError,
    iter_string_frames,
    load_polars,
)


def _audit_groups(specs):
    by_dimensions, geography_margins = {}, {}
    for (geo, margin), dimensions in specs.items():
        margins = geography_margins.setdefault(geo, [])
        ordinal = len(margins)
        margins.append(margin)
        by_dimensions.setdefault(dimensions, {}).setdefault(geo, []).append(
            (margin, ordinal)
        )
    return by_dimensions, geography_margins


def _count_frames(path, entity, geography, specs, pl):
    by_dimensions, geography_margins = _audit_groups(specs)
    universe = set(geography_margins)
    universal = {
        dimensions
        for dimensions, geographies in by_dimensions.items()
        if set(geographies) == universe
    }
    selected = (geography, *dict.fromkeys(d for dims in specs.values() for d in dims))
    counts, first_seen = Counter(), {}
    category_type = pl.Categorical(pl.Categories.random())
    pieces = {dimensions: [] for dimensions in by_dimensions}
    for frame, _ in iter_string_frames(path, selected, required=selected):
        if any(frame[column].null_count() for column in selected):
            # Missing trailing fields and explicit empty strings have distinct
            # reference meanings but both parse as native nulls.
            raise BoundedCSVFallbackError("null or empty audit category")
        frame = frame.with_columns(pl.col(selected).cast(category_type))
        unknown = frame.filter(~pl.col(geography).is_in(list(geography_margins)))
        if unknown.height:
            geo = unknown.sort("__source_row")[geography][0]
            raise ValueError(
                f"No {entity} audit controls for assigned geography {geo}."
            )
        for dimensions, geographies in by_dimensions.items():
            names = list(dict.fromkeys((geography, *dimensions)))
            selected_frame = (
                frame
                if dimensions in universal
                else frame.filter(pl.col(geography).is_in(list(geographies)))
            )
            groups = selected_frame.group_by(names).agg(
                pl.len().cast(pl.UInt64).alias("_count"),
                pl.col("__source_row").min().alias("_first"),
            )
            pieces[dimensions].append(groups)
            if len(pieces[dimensions]) >= 16:
                pieces[dimensions] = [_merge_counts(pieces[dimensions], names, pl)]
    for dimensions, geographies in by_dimensions.items():
        if not pieces[dimensions]:
            continue
        names = list(dict.fromkeys((geography, *dimensions)))
        for row in _merge_counts(pieces[dimensions], names, pl).iter_rows(named=True):
            geo = row[geography]
            category = tuple(row[d] for d in dimensions)
            for margin, ordinal in geographies[geo]:
                key = (geo, margin, category)
                counts[key] = row["_count"]
                first_seen[key] = (row["_first"], ordinal)
    # Counter insertion order appears in unexpected-category reporting.
    return Counter(
        {key: counts[key] for key in sorted(counts, key=first_seen.__getitem__)}
    )


def _merge_counts(pieces, names, pl):
    return (
        pl.concat(pieces)
        .group_by(names)
        .agg(pl.col("_count").sum(), pl.col("_first").min())
    )


def try_audit_counts(path, entity, geography, specs):
    """Return native counts, or None to restart with the reference parser."""
    pl = load_polars()
    if pl is None:
        return None
    try:
        return _count_frames(path, entity, geography, specs, pl)
    except (BoundedCSVFallbackError, pl.exceptions.PolarsError):
        return None
