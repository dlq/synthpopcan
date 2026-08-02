"""Tests for the small-area control source-coverage audit."""

from __future__ import annotations

import importlib.util
import sys
from io import BytesIO
from pathlib import Path

_SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_small_area_control_coverage.py"
_SPEC = importlib.util.spec_from_file_location("audit_control_coverage", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
scan_profile = _MODULE.scan_profile


def test_scan_profile_counts_only_usable_target_geographies() -> None:
    profile = BytesIO(
        b"DGUID,GEO_LEVEL,CHARACTERISTIC_ID,C1_COUNT_TOTAL\n"
        b"A,Census tract,1,100\n"
        b"B,Census tract,1,0\n"
        b"C,Census tract,1,...\n"
        b"D,Census subdivision,1,50\n"
        b"A,Census tract,50,40\n"
        b"B,Census tract,50,0\n"
        b"C,Census tract,50,...\n"
        b"A,Census tract,1482,25\n"
        b"A,Census tract,1483,60.1\n"
        b"B,Census tract,1482,0\n"
        b"B,Census tract,1483,0\n"
    )

    result = scan_profile(profile, year=2021, level="ct")

    assert result["geographies"] == 3
    assert result["positive_population_geographies"] == 1
    families = result["families"]
    assert isinstance(families, dict)
    assert families["household_size"]["positive_denominator_geographies"] == 1
    assert families["mortgage_status"]["positive_denominator_geographies"] == 1
    assert families["tenure"]["positive_denominator_geographies"] == 0


def test_scan_profile_accepts_2016_geography_specific_headers() -> None:
    profile = BytesIO(
        b'ALT_GEO_CODE,GEO_LEVEL,"Member ID: Profile of Dissemination Areas '
        b'(2247)","Dim: Sex (3): Member ID: [1]: Total - Sex"\n'
        b"10011010732,4,1,36\n"
        b"10011010732,4,51,15\n"
    )

    result = scan_profile(profile, year=2016, level="da")

    assert result["geographies"] == 1
    assert result["positive_population_geographies"] == 1
    families = result["families"]
    assert isinstance(families, dict)
    assert families["household_size"]["positive_denominator_geographies"] == 1
