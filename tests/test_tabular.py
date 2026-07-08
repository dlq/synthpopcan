from __future__ import annotations

import pytest

from synthpopcan.tabular import format_csv_number, validate_columns


def test_format_csv_number_writes_whole_numbers_without_decimals() -> None:
    assert format_csv_number(2.0) == "2"
    assert format_csv_number(0.0) == "0"
    assert format_csv_number(1500.0) == "1500"


def test_format_csv_number_keeps_genuine_fractions() -> None:
    assert format_csv_number(1.25) == "1.25"
    assert format_csv_number(0.03) == "0.03"


def test_format_csv_number_absorbs_floating_point_noise() -> None:
    # The whole point of the shared round-with-tolerance formatter: IPF and
    # integerization artifacts just below/above an integer must not leak
    # decimals into otherwise-integer CSV output.
    assert format_csv_number(2.9999999998) == "3"
    assert format_csv_number(3.0000000002) == "3"


def test_validate_columns_passes_when_all_required_present() -> None:
    validate_columns(("a", "b", "c"), required=("a", "c"))


def test_validate_columns_raises_listing_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns: b, d"):
        validate_columns(("a", "c"), required=("a", "b", "d"))
