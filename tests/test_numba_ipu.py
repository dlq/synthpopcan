"""Differential and failure checks for the optional compiled IPU backend."""

from __future__ import annotations

import gc
import weakref
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from synthpopcan import _numba_ipu as backend
from synthpopcan._joint_calibration import (
    IPUSupport,
    JointCalibrationSystem,
    encode_ipu_contributions,
)
from synthpopcan.ipf import integerize_weights
from synthpopcan.small_area_synthesis import _fit_joint_constraints


def fit(matrix, targets, initial, *, cache=None, iterations=40, tolerance=0.0):
    return _fit_joint_constraints(
        matrix,
        targets,
        initial_weights=initial,
        max_iterations=iterations,
        tolerance=tolerance,
        backend_cache=cache,
    )


@pytest.fixture
def enable_size(monkeypatch):
    # Mathematical fixtures remain small; the independent gate test verifies
    # that ordinary small fits do not load a compiler in normal use.
    monkeypatch.setattr(backend, "_MIN_PROFILES", 0)
    monkeypatch.setattr(backend, "_MIN_REQUESTED_UPDATES", 0)


@pytest.fixture
def compiled(enable_size):
    pytest.importorskip("numba")
    pytest.importorskip("scipy.linalg.cython_blas")
    pytest.importorskip("scipy.linalg.cython_lapack")
    kernel = backend._load_kernel()
    assert kernel is not None
    return kernel


def assert_matches(actual, expected, matrix):
    np.testing.assert_allclose(actual[0], expected[0], rtol=1e-11, atol=1e-12)
    assert actual[1:3] == expected[1:3]
    assert actual[3] == pytest.approx(expected[3], rel=1e-11, abs=1e-11)
    actual_integer = np.asarray(integerize_weights(actual[0]))
    expected_integer = np.asarray(integerize_weights(expected[0]))
    assert np.array_equal(actual_integer, expected_integer)
    assert np.array_equal(matrix @ actual_integer, matrix @ expected_integer)


def test_small_fits_stay_on_numpy_without_loading_compiler(monkeypatch):
    def unexpected():
        raise AssertionError("small fits must not import or compile Numba")

    monkeypatch.setattr(backend, "_load_kernel", unexpected)
    cache = backend.IPUBackendCache()
    actual = fit(
        np.ones((2, 600)),
        np.array([10.0, 10.0]),
        np.ones(600),
        cache=cache,
        tolerance=1e-9,
    )
    assert actual[1] and actual[2] == 1
    assert cache.compiled_signatures == ()


def compiler_modules(unavailable, calls, options):
    class CompilerError(Exception):
        pass

    dispatcher = SimpleNamespace(signatures=[])

    def njit(**kwargs):
        options.update(kwargs)
        return lambda _function: dispatcher

    def imported(name):
        calls.append(name)
        if name == unavailable:
            raise ImportError(f"missing optional {name}")
        if name == "numba":
            return SimpleNamespace(njit=njit)
        if name == "numba.core.errors":
            return SimpleNamespace(NumbaError=CompilerError)
        return SimpleNamespace(register_jitable=lambda **_kw: lambda function: function)

    return imported, dispatcher


@pytest.mark.parametrize(
    "unavailable", ["numba", "scipy.linalg.cython_blas", "scipy.linalg.cython_lapack"]
)
def test_missing_optional_capability_is_cached(monkeypatch, unavailable):
    calls, options = [], {}
    imported, _dispatcher = compiler_modules(unavailable, calls, options)
    monkeypatch.setattr(backend.importlib, "import_module", imported)
    monkeypatch.setattr(backend, "_LOAD_ATTEMPTED", False)
    monkeypatch.setattr(backend, "_KERNEL", None)
    monkeypatch.setattr(
        backend, "_CAPABILITY_ERRORS", (ImportError, OSError, RuntimeError)
    )
    assert backend._load_kernel() is None
    before = list(calls)
    assert backend._load_kernel() is None and calls == before


def test_compiler_configuration_is_sequential_and_loaded_once(monkeypatch):
    calls, options = [], {}
    imported, dispatcher = compiler_modules(None, calls, options)
    monkeypatch.setattr(backend.importlib, "import_module", imported)
    monkeypatch.setattr(backend, "_LOAD_ATTEMPTED", False)
    monkeypatch.setattr(backend, "_KERNEL", None)
    monkeypatch.setattr(
        backend, "_CAPABILITY_ERRORS", (ImportError, OSError, RuntimeError)
    )
    assert backend._load_kernel() is dispatcher
    assert backend._load_kernel() is dispatcher
    assert calls.count("numba") == 1
    assert options == dict(nogil=True, fastmath=False, cache=False, error_model="numpy")


def test_unavailable_backend_preserves_numpy_results(monkeypatch, enable_size):
    calls = []

    def unavailable():
        calls.append(1)
        return None

    monkeypatch.setattr(backend, "_load_kernel", unavailable)
    matrix, targets, initial = np.ones((2, 4)), np.array([3.0, 5.0]), np.ones(4)
    expected = fit(matrix, targets, initial)
    cache = backend.IPUBackendCache()
    assert_matches(fit(matrix, targets, initial, cache=cache), expected, matrix)
    assert_matches(fit(matrix, targets, initial, cache=cache), expected, matrix)
    assert calls == [1] and cache.compiled_signatures == ()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("BLAS/LAPACK integer ABI unsupported"),
        ImportError("optional runtime unavailable"),
        OSError("native library unavailable"),
    ],
)
def test_jit_failure_cannot_mutate_numpy_fallback(monkeypatch, enable_size, error):
    calls = []

    def broken(*arguments):
        calls.append(1)
        arguments[2][:] = 123
        arguments[7][:] = 456
        raise error

    monkeypatch.setattr(backend, "_load_kernel", lambda: broken)
    matrix, targets, initial = np.ones((2, 4)), np.array([3.0, 5.0]), np.ones(4)
    expected = fit(matrix, targets, initial)
    cache = backend.IPUBackendCache()
    assert_matches(fit(matrix, targets, initial, cache=cache), expected, matrix)
    assert_matches(fit(matrix, targets, initial, cache=cache), expected, matrix)
    assert calls == [1] and np.array_equal(initial, np.ones(4))


def test_nonfinite_native_result_restarts_reference(monkeypatch, enable_size):
    def nonfinite(*arguments):
        return np.full_like(arguments[7], np.nan), False, arguments[9], np.nan

    monkeypatch.setattr(backend, "_load_kernel", lambda: nonfinite)
    matrix, targets, initial = np.ones((2, 4)), np.array([3.0, 5.0]), np.ones(4)
    expected = fit(matrix, targets, initial)
    actual = fit(matrix, targets, initial, cache=backend.IPUBackendCache())
    assert_matches(actual, expected, matrix)


@pytest.mark.parametrize(
    "iterations,tolerance,initial,targets,message",
    [
        (0, 0.0, np.ones(4), np.ones(2), "max_iterations must be at least 1"),
        (10, -1.0, np.ones(4), np.ones(2), "tolerance must be non-negative"),
        (10, 0.0, np.ones(3), np.ones(2), "contributions do not match households"),
        (
            10,
            0.0,
            np.array([-1.0, 1.0, 1.0, 1.0]),
            np.ones(2),
            "weights must be non-negative",
        ),
        (
            10,
            0.0,
            np.ones(4),
            np.array([0.0, 1.0]),
            "after applying structural-zero controls",
        ),
    ],
)
def test_domain_errors_precede_backend(
    monkeypatch, enable_size, iterations, tolerance, initial, targets, message
):
    def unexpected():
        raise AssertionError("domain validation must precede optional compilation")

    monkeypatch.setattr(backend, "_load_kernel", unexpected)
    with pytest.raises(ValueError, match=message):
        fit(
            np.ones((2, 4)),
            targets,
            initial,
            cache=backend.IPUBackendCache(),
            iterations=iterations,
            tolerance=tolerance,
        )


@pytest.mark.parametrize("initial_zero", [False, True])
def test_compacted_support_keeps_full_row_normalizer(compiled, initial_zero):
    matrix = np.tile(np.array([[2.0, 5.0, 0.0], [0.0, 0.0, 1.0]]), 200)
    initial, targets = np.ones(600), np.array([10.0, 8.0])
    if initial_zero:
        initial[1::3] = 0
    else:
        matrix = np.vstack([matrix, np.tile([0.0, 1.0, 0.0], 200)])
        targets = np.append(targets, 0.0)
    expected = fit(matrix, targets, initial)
    cache = backend.IPUBackendCache()
    actual = fit(matrix, targets, initial, cache=cache)
    assert cache.compiled_signatures
    assert_matches(actual, expected, matrix)
    assert np.all(actual[0][1::3] == 0)


@pytest.mark.parametrize("targets", [np.array([30.0, 70.0, 40.0, 60.0]), np.zeros(4)])
def test_compiled_convergence_matches_reference(compiled, targets):
    matrix = np.tile(
        np.array(
            [
                [1.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 1.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
            ]
        ),
        150,
    )
    initial = np.ones(600)
    expected = fit(matrix, targets, initial, tolerance=1e-10)
    cache = backend.IPUBackendCache()
    actual = fit(matrix, targets, initial, cache=cache, tolerance=1e-10)
    assert cache.compiled_signatures
    assert_matches(actual, expected, matrix)


@pytest.mark.parametrize(
    "target,initial", [(1e300, 1e-300), (1e-300, 1e300), (1.0, 4.0)]
)
def test_compiled_clipping_matches_reference(compiled, target, initial):
    matrix, targets, weights = (
        np.ones((1, 600)),
        np.array([target]),
        np.full(600, initial),
    )
    cache = backend.IPUBackendCache()
    with np.errstate(over="ignore", under="ignore", divide="ignore"):
        expected = fit(matrix, targets, weights, iterations=1)
        actual = fit(matrix, targets, weights, cache=cache, iterations=1)
    assert cache.compiled_signatures
    np.testing.assert_allclose(actual[0], expected[0], rtol=1e-14, atol=0)
    assert actual[1:3] == expected[1:3]
    # BLAS may use a different reduction for a one-row matrix and a vector;
    # the update itself and stopping result must still agree exactly.
    assert actual[3] == pytest.approx(expected[3], rel=1e-12, abs=1e-12)


def test_real_budget_gate_produces_compiled_signature():
    pytest.importorskip("numba")
    pytest.importorskip("scipy.linalg.cython_blas")
    cache = backend.IPUBackendCache()
    # Large requested budget, but an analytically satisfied fit takes one
    # actual sweep. Exercise the real gate without a slow test workload.
    matrix = np.ones((2, 512))
    actual = fit(
        matrix,
        np.array([512.0, 512.0]),
        np.ones(512),
        cache=cache,
        iterations=100000,
        tolerance=1e-9,
    )
    assert cache.compiled_signatures
    np.testing.assert_array_equal(actual[0], np.ones(512))
    assert actual[1:] == (True, 1, 0.0)


def test_concurrent_fits_reuse_one_backend_without_shared_mutation(
    compiled, monkeypatch
):
    matrix = np.tile(
        np.array(
            [
                [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                [2.0, 5.0, 1.0, 3.0, 4.0, 2.0],
                [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
            ]
        ),
        100,
    )
    initial = np.ones(600)
    targets = [np.array([0.0, 10.0, 40.0, 0.0]), np.array([10.0, 0.0, 30.0, 0.0])]
    reference = [fit(matrix, target, initial) for target in targets]
    created = []
    constructor = backend._PreparedIPU.__init__

    def prepared(self, *args):
        created.append(1)
        constructor(self, *args)

    monkeypatch.setattr(backend._PreparedIPU, "__init__", prepared)
    cache = backend.IPUBackendCache()
    with ThreadPoolExecutor(max_workers=2) as executor:
        actual = list(
            executor.map(lambda b: fit(matrix, b, initial, cache=cache), targets)
        )
    assert created == [1] and cache.compiled_signatures
    assert_matches(actual[0], reference[0], matrix)
    assert_matches(actual[1], reference[1], matrix)
    assert np.array_equal(initial, np.ones(600))


def test_backend_lifetime_is_owned_by_calibration_system(compiled):
    def build_and_fit():
        matrix = np.ones((2, 600))
        system = JointCalibrationSystem.build(matrix)
        system.fit(
            np.array([600.0, 600.0]),
            np.ones(600),
            max_iterations=1,
            tolerance=0.0,
            solver="ipu",
            legacy=_fit_joint_constraints,
        )
        assert system._ipu_backend.compiled_signatures
        return (
            weakref.ref(system),
            weakref.ref(system._ipu_backend),
            weakref.ref(matrix),
        )

    references = build_and_fit()
    gc.collect()
    assert all(reference() is None for reference in references)


def test_cache_does_not_reuse_encodings_for_another_matrix(monkeypatch, enable_size):
    def completed(*arguments):
        return arguments[7], True, 1, 0.0

    monkeypatch.setattr(backend, "_load_kernel", lambda: completed)
    matrix = np.ones((2, 4))
    encoding = encode_ipu_contributions(matrix)
    support = IPUSupport.prepare(matrix, np.ones(4), encoding)
    cache = backend.IPUBackendCache()
    assert (
        cache.fit(
            support, np.array([4.0, 4.0]), encoding, max_iterations=1, tolerance=0.0
        )
        is not None
    )
    other = IPUSupport.prepare(matrix.copy(), np.ones(4), encoding)
    assert (
        cache.fit(
            other, np.array([4.0, 4.0]), encoding, max_iterations=1, tolerance=0.0
        )
        is None
    )


@pytest.mark.parametrize(
    "codes,values",
    [
        (np.zeros(3, dtype=int), np.array([1.0])),
        (np.zeros(4, dtype=float), np.array([1.0])),
        (np.full(4, -1, dtype=int), np.array([1.0])),
        (np.ones(4, dtype=int), np.array([1.0])),
        (np.zeros(4, dtype=int), np.array([])),
        (np.zeros(4, dtype=int), np.array([[1.0]])),
        (np.zeros(4, dtype=int), np.array([np.nan])),
        (np.zeros(4, dtype=int), np.array([-1.0])),
        (np.zeros(4, dtype=int), np.array([2.0])),
    ],
)
def test_unsupported_lookup_tables_remain_on_numpy(
    monkeypatch, enable_size, codes, values
):
    def unexpected():
        raise AssertionError("unsafe custom lookup table must not reach native code")

    monkeypatch.setattr(backend, "_load_kernel", unexpected)
    matrix, encoding = np.ones((1, 4)), ((codes, values),)
    support = IPUSupport.prepare(matrix, np.ones(4), encoding)
    assert (
        backend.IPUBackendCache().fit(
            support, np.array([4.0]), encoding, max_iterations=1, tolerance=0.0
        )
        is None
    )


@pytest.mark.parametrize(
    "matrix,targets,weights,tolerance",
    [
        (np.ones((2, 4), dtype=int), np.ones(2), np.ones(4), 0.0),
        (np.ones((4, 2)).T, np.ones(2), np.ones(4), 0.0),
        (np.ones((2, 4)), [1.0, 1.0], np.ones(4), 0.0),
        (np.ones((2, 4)), np.ones(2, dtype=int), np.ones(4), 0.0),
        (np.ones((2, 4)), np.ones(2), np.ones((4, 1)), 0.0),
        (np.ones((2, 4)), np.ones(2), np.ones(4), "0"),
    ],
)
def test_unsupported_array_representations_keep_reference(
    matrix, targets, weights, tolerance
):
    assert not backend._supported_arrays(matrix, targets, weights, tolerance)


@pytest.mark.parametrize("zero,partial", [(False, False), (True, False), (False, True)])
def test_compiled_household_ipf_matches_numpy(monkeypatch, zero, partial):
    pytest.importorskip("numba")
    from synthpopcan.ipf import IPFMargin, NumpyIPFIndex

    records = [{"x": str(i % 2), "y": str((i // 2) % 2)} for i in range(1024)]
    margins = [
        IPFMargin(("x",), {("0",): 0 if zero else 400, ("1",): 600}),
        IPFMargin(("y",), {("0",): 300} if partial else {("0",): 300, ("1",): 700}),
    ]
    index = NumpyIPFIndex.build(records, margins)
    monkeypatch.setattr(backend, "_MIN_HOUSEHOLD_UPDATES", 0)
    initial = np.ones(len(records))
    initial[0] = 0
    actual = index.fit(
        margins, max_iterations=50, tolerance=1e-8, initial_weights=initial
    )
    assert backend._HOUSEHOLD_KERNEL.signatures
    monkeypatch.setattr(backend, "fit_household_compiled", lambda *args: None)
    expected = index.fit(
        margins, max_iterations=50, tolerance=1e-8, initial_weights=initial
    )
    np.testing.assert_allclose(actual[0], expected[0], rtol=1e-13, atol=1e-13)
    assert actual[1:3] == expected[1:3]
    assert actual[3] == pytest.approx(expected[3], abs=1e-10)
    assert actual[0][0] == 0
    assert initial[1] == 1


def test_household_compile_failure_falls_back_without_mutating_prior(monkeypatch):
    def fail(*args):
        args[4][:] = 123
        raise RuntimeError("unsupported compiler")

    monkeypatch.setattr(backend, "_MIN_HOUSEHOLD_UPDATES", 0)
    monkeypatch.setattr(backend, "_HOUSEHOLD_ATTEMPTED", True)
    monkeypatch.setattr(backend, "_HOUSEHOLD_KERNEL", fail)
    prior = np.ones(4)
    assert (
        backend.fit_household_compiled(
            np.zeros((1, 4), dtype=np.int32),
            np.array([0, 1]),
            [np.array([4.0])],
            [np.array([True])],
            prior,
            10,
            0.0,
        )
        is None
    )
    np.testing.assert_array_equal(prior, np.ones(4))


def test_both_kernel_loaders_share_settings_and_register_error_once(monkeypatch):
    calls, options = [], {}
    imported, dispatcher = compiler_modules(None, calls, options)
    monkeypatch.setattr(backend.importlib, "import_module", imported)
    monkeypatch.setattr(backend, "_LOAD_ATTEMPTED", False)
    monkeypatch.setattr(backend, "_KERNEL", None)
    monkeypatch.setattr(backend, "_HOUSEHOLD_ATTEMPTED", False)
    monkeypatch.setattr(backend, "_HOUSEHOLD_KERNEL", None)
    monkeypatch.setattr(
        backend, "_CAPABILITY_ERRORS", (ImportError, OSError, RuntimeError)
    )
    assert backend._load_kernel() is dispatcher
    assert backend._load_household_kernel() is dispatcher
    assert len(backend._CAPABILITY_ERRORS) == 4
    assert options == dict(nogil=True, fastmath=False, cache=False, error_model="numpy")
    before = list(calls)
    assert backend._load_household_kernel() is dispatcher
    assert calls == before


@pytest.mark.parametrize("unavailable", ["numba", "numba.core.errors"])
def test_missing_household_compiler_is_cached(monkeypatch, unavailable):
    calls, options = [], {}
    imported, _dispatcher = compiler_modules(unavailable, calls, options)
    monkeypatch.setattr(backend.importlib, "import_module", imported)
    monkeypatch.setattr(backend, "_HOUSEHOLD_ATTEMPTED", False)
    monkeypatch.setattr(backend, "_HOUSEHOLD_KERNEL", None)
    monkeypatch.setattr(
        backend, "_CAPABILITY_ERRORS", (ImportError, OSError, RuntimeError)
    )
    assert backend._load_household_kernel() is None
    before = list(calls)
    assert backend._load_household_kernel() is None
    assert calls == before
