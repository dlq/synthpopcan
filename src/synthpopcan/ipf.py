"""Iterative proportional fitting for seed records and margin tables."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

Record = Mapping[str, Any]
CategoryKey = tuple[str, ...]

__all__ = [
    "CategoryKey",
    "IPFMargin",
    "IPFResult",
    "NumpyIPFIndex",
    "Record",
    "calculate_max_abs_error",
    "expand_records",
    "fit_ipf",
    "fit_ipf_numpy",
    "integerize_weights",
    "validate_margin_coverage",
    "weighted_totals",
]


@dataclass(frozen=True)
class IPFMargin:
    """A target margin used to calibrate seed records with IPF.

    Parameters
    ----------
    dimensions:
        Ordered column names that identify the category cells in this margin.
    targets:
        Mapping from category tuples to the desired weighted count for each
        cell. Each key must have the same length and order as ``dimensions``.
    """

    dimensions: tuple[str, ...]
    targets: Mapping[CategoryKey, float]

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise ValueError("margin dimensions must not be empty")
        for key, value in self.targets.items():
            if len(key) != len(self.dimensions):
                raise ValueError(
                    f"target key {key!r} does not match dimensions {self.dimensions!r}"
                )
            if value < 0:
                raise ValueError(f"target {key!r} must be non-negative")


@dataclass(frozen=True)
class IPFResult:
    """Result returned by :func:`fit_ipf`.

    The result keeps the original records alongside calibrated weights so
    callers can inspect convergence, validate totals, or expand the weighted
    seed records into integer synthetic rows.

    Parameters
    ----------
    records:
        Original seed records passed to :func:`fit_ipf`.
    weights:
        Calibrated weight for each seed record, in the same order as
        ``records``.
    converged:
        Whether the fit reached the requested tolerance before exhausting the
        iteration limit.
    iterations:
        Number of full IPF adjustment passes completed.
    max_abs_error:
        Largest absolute residual between a target cell and the fitted weighted
        total when fitting stopped.
    """

    records: Sequence[Record]
    weights: list[float]
    converged: bool
    iterations: int
    max_abs_error: float

    def margin_totals(self, dimensions: tuple[str, ...]) -> dict[CategoryKey, float]:
        """Calculate weighted totals for one set of dimensions."""

        totals: dict[CategoryKey, float] = {}
        for record, weight in zip(self.records, self.weights, strict=True):
            key = _category_key(record, dimensions)
            totals[key] = totals.get(key, 0.0) + weight
        return totals


@dataclass(frozen=True)
class _IndexedMargin:
    margin: IPFMargin
    record_indexes: Mapping[CategoryKey, tuple[int, ...]]


def expand_records(
    records: Sequence[Record],
    weights: Sequence[float],
    *,
    id_field: str = "id",
) -> list[dict[str, str]]:
    """Expand weighted seed records into integer synthetic records.

    Fractional weights are rounded with :func:`integerize_weights`. The output
    includes ``synthetic_id`` and ``seed_id`` columns so generated rows can be
    traced back to their seed-record source without exposing private data.

    Parameters
    ----------
    records:
        Seed records whose calibrated weights should be expanded.
    weights:
        Non-negative weights in the same order as ``records``.
    id_field:
        Optional seed-record column to copy into ``seed_id``. If the column is
        missing, the one-based record index is used.
    """

    counts = integerize_weights(weights)
    expanded: list[dict[str, str]] = []
    synthetic_id = 1

    for source_index, record in enumerate(records, start=1):
        seed_id = str(record.get(id_field, source_index))
        attributes = {
            str(key): str(value) for key, value in record.items() if key != id_field
        }
        for _ in range(counts[source_index - 1]):
            expanded.append(
                {
                    "synthetic_id": str(synthetic_id),
                    "seed_id": seed_id,
                    **attributes,
                }
            )
            synthetic_id += 1

    return expanded


def integerize_weights(weights: Sequence[float]) -> list[int]:
    """Convert non-negative fractional weights to integer replication counts.

    Uses systematic sampling: the cumulative weight axis is divided into N
    equal-width intervals and one sample is drawn from each interval starting
    at the mid-point of the first. This is deterministic and preserves
    proportional distributions regardless of weight magnitude.

    The largest-remainder method (the prior implementation) degenerates when
    all weights are less than 1 — every floor is 0 and the N remainder bumps
    all land on whichever group has the highest per-candidate weight, discarding
    the margin structure entirely. This arises in small-area synthesis when a
    large candidate pool (e.g. 50 000 records) is fitted to a small per-CT
    target (e.g. 1 400 households), giving every candidate a weight of ~0.03.

    Raises
    ------
    ValueError
        If any weight is negative.
    """

    if any(weight < 0 for weight in weights):
        raise ValueError("weights must be non-negative")

    arr = np.asarray(weights, dtype=np.float64)
    total = float(arr.sum())
    n = round(total)
    if n < 0:
        raise ValueError("integerized total cannot be negative")
    if n == 0:
        return [0] * len(weights)

    step = total / n
    points = (np.arange(n, dtype=np.float64) + 0.5) * step
    cumulative = arr.cumsum()
    # searchsorted(cumulative - 1e-10, points, 'right') mirrors the Python
    # version's `while next_point < cumulative - 1e-10` boundary condition.
    bucket_ids = np.searchsorted(cumulative - 1e-10, points, side="right")
    np.clip(bucket_ids, 0, len(weights) - 1, out=bucket_ids)
    counts = np.bincount(bucket_ids, minlength=len(weights))
    return counts[: len(weights)].tolist()


def fit_ipf(
    records: Sequence[Record],
    margins: Sequence[IPFMargin],
    *,
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> IPFResult:
    """Fit record weights so seed records match supplied control margins.

    Parameters
    ----------
    records:
        Seed records containing the categorical columns named by each margin.
    margins:
        Target totals that the weighted records should match.
    weight_field:
        Optional seed-record column containing starting weights. If omitted,
        every seed record starts with weight ``1.0``.
    max_iterations:
        Maximum number of full adjustment passes over all margins.
    tolerance:
        Stop once the largest absolute residual is at or below this value.

    Raises
    ------
    ValueError
        If records or margins are empty, if weights are invalid, or if a
        positive target cell has no seed records that can represent it.

    Notes
    -----
    IPF can only adjust weights for category combinations represented in the
    seed records. A missing positive target cell is a structural problem in the
    seed/control design, not a convergence problem.
    """

    if not records:
        raise ValueError("IPF requires at least one seed record")
    if not margins:
        raise ValueError("IPF requires at least one margin")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    weights = _initial_weights(records, weight_field)
    indexed_margins = _index_margins(records, margins)

    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for indexed_margin in indexed_margins:
            for key, target in indexed_margin.margin.targets.items():
                indexes = indexed_margin.record_indexes.get(key, ())
                current = sum(weights[index] for index in indexes)
                if current == 0.0:
                    if target == 0.0:
                        continue
                    raise ValueError(
                        f"margin {indexed_margin.margin.dimensions!r} target {key!r} "
                        "has no seed records"
                    )
                ratio = target / current
                for index in indexes:
                    weights[index] *= ratio

        max_abs_error = _calculate_indexed_max_abs_error(weights, indexed_margins)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights, True, iteration, max_abs_error)

    return IPFResult(records, weights, False, max_iterations, max_abs_error)


@dataclass(frozen=True)
class _NumpyEncoding:
    dimensions: tuple[str, ...]
    cat_ids: np.ndarray
    key_to_id: dict[CategoryKey, int]
    n_cats: int


class NumpyIPFIndex:
    """Pre-built category index for vectorized numpy IPF.

    Build once for a fixed candidate pool, then pass to :func:`fit_ipf_numpy`
    for each target geography.  The records and margin dimensions must be the
    same across all geography fits — only the target counts change.

    Parameters
    ----------
    records:
        Candidate pool whose columns define the category encodings.
    margins:
        Margins whose ``.dimensions`` are encoded.  Only the dimension
        structure is used here; targets are supplied per geography to
        :func:`fit_ipf_numpy`.
    """

    def __init__(
        self,
        records: Sequence[Record],
        encodings: list[_NumpyEncoding],
    ) -> None:
        self.records = records
        self.encodings = encodings

    @classmethod
    def build(
        cls,
        records: Sequence[Record],
        margins: Sequence[IPFMargin],
    ) -> NumpyIPFIndex:
        """Encode *records* for every margin in *margins*."""
        encodings: list[_NumpyEncoding] = []
        for margin in margins:
            keys = [_category_key(record, margin.dimensions) for record in records]
            unique = sorted(set(keys))
            key_to_id = {k: i for i, k in enumerate(unique)}
            cat_ids = np.array([key_to_id[k] for k in keys], dtype=np.int32)
            encodings.append(
                _NumpyEncoding(
                    dimensions=margin.dimensions,
                    cat_ids=cat_ids,
                    key_to_id=key_to_id,
                    n_cats=len(unique),
                )
            )
        return cls(records, encodings)

    def fit(
        self,
        margins: Sequence[IPFMargin],
        *,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> tuple[np.ndarray, bool, int, float]:
        """Run numpy IPF; return ``(weights, converged, iterations, max_abs_error)``.

        The returned ``weights`` is a float64 numpy array — no Python list
        conversion.  Use this inside tight loops when you need the numpy array
        immediately (e.g. to compute weighted totals via :meth:`compute_totals`)
        and will convert to a list only once at the end.
        """

        if len(margins) != len(self.encodings):
            raise ValueError(
                f"margins count {len(margins)} does not match index encodings "
                f"{len(self.encodings)}"
            )

        t_arrays: list[np.ndarray] = []
        for enc, margin in zip(self.encodings, margins, strict=True):
            t = np.zeros(enc.n_cats, dtype=np.float64)
            for key, val in margin.targets.items():
                cid = enc.key_to_id.get(key)
                if cid is not None:
                    t[cid] = float(val)
                elif float(val) > 0:
                    raise ValueError(
                        f"margin {margin.dimensions!r} target {key!r} "
                        "has no seed records"
                    )
            t_arrays.append(t)

        weights = np.ones(len(self.records), dtype=np.float64)

        max_abs_error = float("inf")
        for iteration in range(1, max_iterations + 1):
            for enc, t in zip(self.encodings, t_arrays, strict=True):
                current = np.bincount(
                    enc.cat_ids, weights=weights, minlength=enc.n_cats
                )
                safe = np.where(current > 0, current, 1.0)
                ratio = np.where(current > 0, t / safe, 1.0)
                weights *= ratio[enc.cat_ids]

            max_abs_error = max(
                float(
                    np.max(
                        np.abs(
                            np.bincount(
                                enc.cat_ids, weights=weights, minlength=enc.n_cats
                            )
                            - t
                        )
                    )
                )
                for enc, t in zip(self.encodings, t_arrays, strict=True)
            )
            if max_abs_error <= tolerance:
                return weights, True, iteration, max_abs_error

        return weights, False, max_iterations, max_abs_error

    def compute_totals(
        self, weights: np.ndarray
    ) -> dict[tuple[str, ...], dict[CategoryKey, float]]:
        """Return ``{dimensions: {category_key: total}}`` for all encodings.

        Uses numpy ``bincount`` — O(n_records) in C rather than in Python.
        Pass results to :func:`~synthpopcan.diagnostics.build_ipf_fit_report`
        via its ``precomputed_totals`` parameter to skip the Python
        ``weighted_totals`` loop.
        """

        out: dict[tuple[str, ...], dict[CategoryKey, float]] = {}
        for enc in self.encodings:
            current = np.bincount(enc.cat_ids, weights=weights, minlength=enc.n_cats)
            out[enc.dimensions] = {
                key: float(current[idx]) for key, idx in enc.key_to_id.items()
            }
        return out


def fit_ipf_numpy(
    index: NumpyIPFIndex,
    margins: Sequence[IPFMargin],
    *,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> IPFResult:
    """Vectorized IPF using a pre-built :class:`NumpyIPFIndex`.

    Equivalent to :func:`fit_ipf` but uses numpy ``bincount`` and array
    multiplication instead of Python loops.  Call :meth:`NumpyIPFIndex.build`
    once for a candidate pool, then call this function once per geography.

    Parameters
    ----------
    index:
        Pre-built index for the candidate pool.  Must have been built with the
        same margin dimension structure as *margins*.
    margins:
        Per-geography :class:`IPFMargin` targets.  The dimensions of each
        margin must match the corresponding encoding in *index*.
    """

    if not margins:
        raise ValueError("IPF requires at least one margin")
    weights, converged, iteration, max_abs_error = index.fit(
        margins, max_iterations=max_iterations, tolerance=tolerance
    )
    return IPFResult(
        index.records, weights.tolist(), converged, iteration, max_abs_error
    )


def _initial_weights(
    records: Sequence[Record], weight_field: str | None
) -> list[float]:
    if weight_field is None:
        return [1.0 for _ in records]

    weights: list[float] = []
    for record in records:
        try:
            weight = float(record[weight_field])
        except KeyError as exc:
            raise ValueError(f"weight field {weight_field!r} is missing") from exc
        if weight < 0:
            raise ValueError("seed weights must be non-negative")
        weights.append(weight)
    return weights


def _index_margins(
    records: Sequence[Record], margins: Sequence[IPFMargin]
) -> list[_IndexedMargin]:
    indexed_margins: list[_IndexedMargin] = []
    for margin in margins:
        indexes: dict[CategoryKey, list[int]] = {}
        for index, record in enumerate(records):
            key = _category_key(record, margin.dimensions)
            indexes.setdefault(key, []).append(index)

        for key, target in margin.targets.items():
            if target > 0 and key not in indexes:
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )
        indexed_margins.append(
            _IndexedMargin(
                margin,
                {key: tuple(value) for key, value in indexes.items()},
            )
        )
    return indexed_margins


def validate_margin_coverage(
    records: Sequence[Record], margins: Sequence[IPFMargin]
) -> None:
    """Check that every positive target cell is represented by seed records.

    Use this before fitting when you want to report unsupported controls as an
    input-design problem. The function returns ``None`` when all positive target
    cells have at least one matching seed record and raises ``ValueError`` for
    the first unsupported target.
    """

    _index_margins(records, margins)


def weighted_totals(
    records: Sequence[Record],
    weights: Sequence[float],
    dimensions: tuple[str, ...],
) -> dict[CategoryKey, float]:
    """Aggregate weighted records by a tuple of categorical dimensions.

    The keys in the returned dictionary are ordered tuples of string category
    values matching ``dimensions``. This is the same representation used by
    :class:`IPFMargin`.
    """

    totals: dict[CategoryKey, float] = {}
    for record, weight in zip(records, weights, strict=True):
        key = _category_key(record, dimensions)
        totals[key] = totals.get(key, 0.0) + weight
    return totals


def calculate_max_abs_error(
    records: Sequence[Record],
    weights: Sequence[float],
    margins: Sequence[IPFMargin],
) -> float:
    """Return the largest absolute residual across all margin cells.

    This helper is useful when validating saved weights or comparing an IPF
    result after additional filtering or expansion.
    """

    max_abs_error = 0.0
    for margin in margins:
        totals = weighted_totals(records, weights, margin.dimensions)
        for key, target in margin.targets.items():
            max_abs_error = max(max_abs_error, abs(totals.get(key, 0.0) - target))
    return max_abs_error


def _calculate_indexed_max_abs_error(
    weights: Sequence[float],
    indexed_margins: Sequence[_IndexedMargin],
) -> float:
    max_abs_error = 0.0
    for indexed_margin in indexed_margins:
        for key, target in indexed_margin.margin.targets.items():
            total = sum(
                weights[index] for index in indexed_margin.record_indexes.get(key, ())
            )
            max_abs_error = max(max_abs_error, abs(total - target))
    return max_abs_error


def _category_key(record: Record, dimensions: Iterable[str]) -> CategoryKey:
    """Build the ordered category key for a record and set of dimensions."""

    key: list[str] = []
    for dimension in dimensions:
        try:
            value = record[dimension]
        except KeyError as exc:
            raise ValueError(f"record is missing dimension {dimension!r}") from exc
        key.append(str(value))
    return tuple(key)
