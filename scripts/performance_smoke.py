"""Smoke-test installed optional native backends outside the source checkout."""

from __future__ import annotations

import os
from collections import Counter
from importlib.metadata import metadata, requires
from importlib.metadata import version as distribution_version
from pathlib import Path

import numpy as np

import synthpopcan
from synthpopcan._map_statistics import compute_linked_statistics
from synthpopcan._numba_ipu import IPUBackendCache
from synthpopcan._observed_calibration import fit_observed_constraints
from synthpopcan._polars_audit import try_audit_counts
from synthpopcan._polars_map_statistics import try_compute_linked_statistics
from synthpopcan.small_area_synthesis import _fit_joint_constraints


def check_installed_metadata() -> Path:
    """Require the built distribution and its declared optional dependencies."""
    package_path = Path(synthpopcan.__file__).resolve()
    source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
    expected_version = os.environ["SYNTHPOPCAN_EXPECTED_VERSION"]
    if source_root in package_path.parents:
        raise RuntimeError(f"performance smoke imported from checkout: {package_path}")
    assert "site-packages" in package_path.parts
    assert distribution_version("synthpopcan") == expected_version
    assert synthpopcan.__version__ == expected_version
    assert "performance" in metadata("synthpopcan").get_all("Provides-Extra", [])
    requirements = requires("synthpopcan") or []
    for name in ("numba", "scipy", "polars"):
        assert any(
            requirement.startswith(name)
            and "extra == 'performance'" in requirement.replace('"', "'")
            for requirement in requirements
        ), f"performance extra does not declare {name}"
        assert distribution_version(name)
    return package_path


def check_compiled_ipu() -> None:
    """Cross the native admission gate, then converge in one actual update."""
    contributions = np.ones((2, 512), dtype=np.float64)
    targets = np.array([512.0, 512.0])
    initial_weights = np.ones(512, dtype=np.float64)
    cache = IPUBackendCache()
    weights, converged, iterations, max_error = _fit_joint_constraints(
        contributions,
        targets,
        initial_weights=initial_weights,
        max_iterations=100_000,
        tolerance=1e-8,
        backend_cache=cache,
    )
    assert cache.compiled_signatures, "Numba IPU silently used the reference fallback"
    np.testing.assert_array_equal(weights, np.ones(512))
    np.testing.assert_array_equal(initial_weights, np.ones(512))
    assert converged
    assert iterations == 1
    assert max_error == 0.0


def check_observed_conflicts() -> None:
    """Require the installed approximate solver and honest residual status."""
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    targets = np.array([10.0, 0.0, 0.0])
    original = targets.copy()
    weights, converged, _iterations, error, details = fit_observed_constraints(
        matrix,
        targets,
        np.ones(2),
        household_total=10.0,
        max_iterations=100,
        tolerance=1e-6,
    )
    assert not converged and error > 0
    assert np.isclose(weights.sum(), 10.0) and np.all(weights > 0)
    assert details["zero_target_policy"] == "observed"
    assert details["controls_converged"] is False
    np.testing.assert_array_equal(targets, original)


def check_columnar_statistics() -> None:
    """Require actual native counts and exact linked summaries on known rows."""
    households = Path("households.csv")
    persons = Path("persons.csv")
    households.write_text(
        "ct,synthetic_household_id,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "G1,h1,2,1,1,3,1000\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ct,AGEGRP,GENDER,TOTINC,EMPIN\n"
        "p1,h1,G1,4,1,10,-25\n"
        "p2,h1,G1,2,2,20,1000\n"
    )
    household_counts = try_audit_counts(
        households, "household", "ct", {("G1", "tenure"): ("TENUR",)}
    )
    assert household_counts is not None, "Polars audit used the reference fallback"
    assert household_counts == Counter({("G1", "tenure", ("1",)): 1})
    person_counts = try_audit_counts(
        persons, "person", "ct", {("G1", "age"): ("AGEGRP",)}
    )
    assert person_counts == Counter(
        {("G1", "age", ("4",)): 1, ("G1", "age", ("2",)): 1}
    )

    native = try_compute_linked_statistics(households, persons, "ct")
    assert native is not None, "Polars maps used the reference fallback"
    # Tiny files stay on the reference implementation through the normal entry
    # point, so compare every field in addition to known independent results.
    assert native == compute_linked_statistics(households, persons, "ct")
    household_summary, person_summary = native[0]["G1"], native[1]["G1"]
    assert household_summary["n_households"] == 1
    assert household_summary["n_persons"] == 2
    assert household_summary["median_hh_income"] == 30
    assert household_summary["pct_owner"] == 100.0
    assert person_summary["n_persons"] == 2
    assert person_summary["n_persons_15_plus"] == 1
    assert person_summary["median_personal_income"] == 10
    assert person_summary["median_employment_income"] == -25
    assert person_summary["pct_age_0_14"] == 50.0


if __name__ == "__main__":
    installed_path = check_installed_metadata()
    check_compiled_ipu()
    check_observed_conflicts()
    check_columnar_statistics()
    print(f"Installed performance smoke passed: {installed_path}")
