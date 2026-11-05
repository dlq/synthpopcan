"""Optional compiled IPU updates, with state owned by one calibration system."""

from __future__ import annotations

import importlib
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from synthpopcan._joint_calibration import IPUSupport

_MIN_PROFILES = 512
_MIN_REQUESTED_UPDATES = 100_000_000
_LOAD_LOCK = threading.Lock()
_LOAD_ATTEMPTED = False
_KERNEL: Any = None
_CAPABILITY_ERRORS: tuple[type[Exception], ...] = (ImportError, OSError, RuntimeError)


def _update_row(  # pragma: no cover - machine code checked by differential tests
    row, target, weights, codes, exponents, value_count, table
):
    current = np.dot(row, weights)
    if current <= 0.0:
        return
    log_ratio = np.log(target / current)
    if log_ratio < -50.0:
        log_ratio = -50.0
    elif log_ratio > 50.0:
        log_ratio = 50.0
    for value_index in range(value_count):
        table[value_index] = np.exp(log_ratio * exponents[value_index])
    for column_index in range(len(weights)):
        weights[column_index] *= table[codes[column_index]]


def _run(  # pragma: no cover - machine code checked by differential tests
    matrix,
    targets,
    weights,
    codes,
    exponents,
    value_counts,
    full_matrix,
    full_weights,
    active,
    max_iterations,
    tolerance,
):
    table = np.empty(exponents.shape[1], dtype=np.float64)
    max_abs_error = np.inf
    for iteration in range(1, max_iterations + 1):
        for row_index in range(matrix.shape[0]):
            target = targets[row_index]
            if target == 0.0:
                continue
            _update_row(
                matrix[row_index],
                target,
                weights,
                codes[row_index],
                exponents[row_index],
                value_counts[row_index],
                table,
            )
        if len(active):
            for index in range(len(active)):
                full_weights[active[index]] = weights[index]
        max_abs_error = np.max(np.abs(np.dot(full_matrix, full_weights) - targets))
        if max_abs_error <= tolerance:
            return full_weights, True, iteration, max_abs_error
    return full_weights, False, max_iterations, max_abs_error


def _kernel_compiler():
    """Share compiler settings and capability errors between numerical kernels."""
    global _CAPABILITY_ERRORS
    compiler = importlib.import_module("numba")
    errors = importlib.import_module("numba.core.errors")
    if errors.NumbaError not in _CAPABILITY_ERRORS:
        _CAPABILITY_ERRORS = (*_CAPABILITY_ERRORS, errors.NumbaError)
    return compiler.njit(nogil=True, fastmath=False, cache=False, error_model="numpy")


def _load_kernel():
    """Import only on a large fit; unavailable/unsupported BLAS keeps NumPy."""
    global _LOAD_ATTEMPTED, _KERNEL
    with _LOAD_LOCK:
        if not _LOAD_ATTEMPTED:
            _LOAD_ATTEMPTED = True
            try:
                compile_kernel = _kernel_compiler()
                importlib.import_module("scipy.linalg.cython_blas")
                importlib.import_module("scipy.linalg.cython_lapack")
                extension = importlib.import_module("numba.extending")
                extension.register_jitable(inline="always")(_update_row)
                _KERNEL = compile_kernel(_run)
            except _CAPABILITY_ERRORS:
                _KERNEL = None
    return _KERNEL


def _large_fit(matrix, max_iterations):
    return (
        isinstance(max_iterations, (int, np.integer))
        and matrix.shape[1] >= _MIN_PROFILES
        and matrix.size * int(max_iterations) >= _MIN_REQUESTED_UPDATES
    )


def _supported_arrays(matrix, targets, weights, tolerance):
    return (
        isinstance(targets, np.ndarray)
        and isinstance(tolerance, (int, float, np.floating))
        and matrix.dtype == np.float64
        and matrix.flags.c_contiguous
        and targets.ndim == weights.ndim == 1
        and targets.dtype == np.float64
        and targets.flags.c_contiguous
    )


def _eligible(support: IPUSupport, targets, max_iterations, tolerance):
    matrix, weights = support.full_matrix, support.full_weights
    if not _large_fit(matrix, max_iterations) or not _supported_arrays(
        matrix, targets, weights, tolerance
    ):
        return False
    return bool(
        np.all(np.isfinite(targets))
        and np.all(targets >= 0)
        and np.all(np.isfinite(weights))
        and np.isfinite(tolerance)
    )


class _PreparedIPU:
    def __init__(self, matrix, encoding, kernel):
        self.matrix, self.kernel = matrix, kernel
        self.codes = np.ascontiguousarray(np.stack([codes for codes, _ in encoding]))
        self.value_counts = np.array(
            [len(values) for _, values in encoding], dtype=np.int64
        )
        self.exponents = np.zeros((len(encoding), int(self.value_counts.max())))
        for index, (_, values) in enumerate(encoding):
            self.exponents[index, : len(values)] = values

    def fit(self, support, targets, max_iterations, tolerance):
        # The kernel receives private mutable arrays. A failed compile/run or
        # nonfinite result cannot damage the NumPy reference's starting state.
        full_weights = support.full_weights.copy()
        if support.active is None:
            weights, codes = full_weights, self.codes
            active = np.empty(0, dtype=np.int64)
        else:
            weights = support.weights.copy()
            codes = np.ascontiguousarray(self.codes[:, support.active])
            active = support.active
        return self.kernel(
            support.matrix,
            targets,
            weights,
            codes,
            self.exponents,
            self.value_counts,
            support.full_matrix,
            full_weights,
            active,
            int(max_iterations),
            float(tolerance),
        )


def _valid_row_encoding(width, codes, values):
    if (
        codes.shape != (width,)
        or values.ndim != 1
        or not len(values)
        or not np.issubdtype(codes.dtype, np.integer)
    ):
        return False
    return bool(
        np.all(codes >= 0)
        and np.all(codes < len(values))
        and np.all(np.isfinite(values))
        and np.all(values >= 0)
        and np.all(values <= 1)
    )


def _valid_encoding(matrix, encoding):
    if (
        len(encoding) != len(matrix)
        or not np.all(np.isfinite(matrix))
        or np.any(matrix < 0)
    ):
        return False
    for codes, values in encoding:
        if not _valid_row_encoding(matrix.shape[1], codes, values):
            return False
    return True


class IPUBackendCache:
    """One matrix's immutable encodings; no process-global matrix retention.

    Only systems with >=512 profiles and >=100 million requested cell updates
    pay compilation cost. Ordinary small fits stay on the NumPy reference.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._prepared: _PreparedIPU | None = None
        self._disabled = False

    @property
    def compiled_signatures(self) -> tuple[str, ...]:
        """Expose capability evidence without exposing mutable cached arrays."""
        if self._prepared is None:
            return ()
        return tuple(str(signature) for signature in self._prepared.kernel.signatures)

    def fit(
        self,
        support: IPUSupport,
        targets: np.ndarray,
        encoding: Sequence[tuple[np.ndarray, np.ndarray]],
        *,
        max_iterations: int,
        tolerance: float,
    ):
        if not _eligible(support, targets, max_iterations, tolerance):
            return None
        with self._lock:
            if self._disabled:
                return None
            if self._prepared is None:
                if not _valid_encoding(support.full_matrix, encoding):
                    return None
                kernel = _load_kernel()
                if kernel is None:
                    self._disabled = True
                    return None
                self._prepared = _PreparedIPU(support.full_matrix, encoding, kernel)
            prepared = self._prepared
            if prepared.matrix is not support.full_matrix:
                return None
        try:
            result = prepared.fit(support, targets, max_iterations, tolerance)
        except _CAPABILITY_ERRORS:
            with self._lock:
                self._disabled = True
            return None
        if not np.all(np.isfinite(result[0])) or not np.isfinite(result[3]):
            return None
        return result


_MIN_HOUSEHOLD_UPDATES = 100_000_000
_HOUSEHOLD_KERNEL: Any = None
_HOUSEHOLD_ATTEMPTED = False


def _run_household(  # pragma: no cover - differential machine-code tests
    codes, offsets, targets, targeted, weights, max_iterations, tolerance
):
    totals = np.zeros(len(targets), dtype=np.float64)
    ratios = np.ones(len(targets), dtype=np.float64)
    error = np.inf
    for iteration in range(1, max_iterations + 1):
        for margin in range(len(codes)):
            start, end = offsets[margin], offsets[margin + 1]
            for category in range(start, end):
                totals[category] = 0.0
                ratios[category] = 1.0
            for record in range(len(weights)):
                totals[start + codes[margin, record]] += weights[record]
            for category in range(start, end):
                if not np.isfinite(totals[category]):
                    return weights, False, iteration, np.inf
                if targeted[category] and totals[category] > 0:
                    ratios[category] = targets[category] / totals[category]
            for record in range(len(weights)):
                category = start + codes[margin, record]
                ratio = ratios[category]
                if np.isfinite(ratio) and not (targets[category] > 0 and ratio == 0):
                    weights[record] *= ratio
                elif targeted[category] and totals[category] > 0:
                    weights[record] = (
                        weights[record] / totals[category] * targets[category]
                    )
        error = 0.0
        for margin in range(len(codes)):
            start, end = offsets[margin], offsets[margin + 1]
            for category in range(start, end):
                totals[category] = 0.0
            for record in range(len(weights)):
                totals[start + codes[margin, record]] += weights[record]
            for category in range(start, end):
                if targeted[category]:
                    residual = abs(totals[category] - targets[category])
                    if not np.isfinite(residual):
                        return weights, False, iteration, np.inf
                    error = max(error, residual)
        if error <= tolerance:
            return weights, True, iteration, error
    return weights, False, max_iterations, error


def _load_household_kernel():
    """Own lazy household-kernel loading independently of fit execution."""
    global _HOUSEHOLD_ATTEMPTED, _HOUSEHOLD_KERNEL
    with _LOAD_LOCK:
        if not _HOUSEHOLD_ATTEMPTED:
            _HOUSEHOLD_ATTEMPTED = True
            try:
                _HOUSEHOLD_KERNEL = _kernel_compiler()(_run_household)
            except _CAPABILITY_ERRORS:
                _HOUSEHOLD_KERNEL = None
        return _HOUSEHOLD_KERNEL


def fit_household_compiled(
    codes: np.ndarray,
    offsets: np.ndarray,
    targets: Sequence[np.ndarray],
    masks: Sequence[np.ndarray],
    weights: np.ndarray,
    iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, bool, int, float] | None:
    """Optional categorical IPF; failed compilation leaves the reference untouched."""
    if codes.size < 100_000 and codes.size * iterations < _MIN_HOUSEHOLD_UPDATES:
        return None
    kernel = _load_household_kernel()
    if kernel is None:
        return None
    try:
        result = kernel(
            codes,
            offsets,
            np.concatenate(targets),
            np.concatenate(masks),
            weights.copy(),
            iterations,
            tolerance,
        )
    except _CAPABILITY_ERRORS:
        return None
    if not np.all(np.isfinite(result[0])) or not np.isfinite(result[3]):
        return None
    return result
