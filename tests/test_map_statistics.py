"""Map statistics behaviour and regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from support.map_fixtures import (
    _hh_row,
    _person_row,
    _write_households,
    _write_persons,
)

from synthpopcan.map_render import (
    _compute_geo_stats,
)


def test_compute_geo_stats_counts_households(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1200",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "3",
                "TENUR": "2",
                "DTYPE": "2",
                "REPAIR": "1",
                "SHELCO": "900",
            },
            {
                "synthetic_household_id": "h3",
                "ct": "G2",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "3",
                "SHELCO": "800",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["n_households"] == 2
    assert stats["G2"]["n_households"] == 1


def test_compute_geo_stats_avg_hh_size(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "4",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["avg_hh_size"] == 3.0


def test_compute_geo_stats_pct_owner(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "2",
                "DTYPE": "2",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["pct_owner"] == 50.0


def test_compute_geo_stats_pct_major_repairs(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "3",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h3",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h4",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["pct_major_repairs"] == 25.0


def test_compute_geo_stats_skips_sentinel_shelter_cost(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "99999999",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1200",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["median_shelter_cost"] == 1200


def test_compute_geo_stats_person_counts(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "50000",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "2",
                "IMMSTAT": "2",
                "VISMIN": "1",
                "TOTINC": "30000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["n_persons"] == 2


def test_compute_geo_stats_pct_senior_agegrp88(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "88",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_senior"] == 50.0


def test_compute_geo_stats_vismin_coding(tmp_path: Path) -> None:
    """VISMIN=1 is visible minority (opposite of standard PUMF)."""
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "1",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_vismin"] == 50.0


def test_compute_geo_stats_median_hh_income(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "40000",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "20000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    # Both persons in h1 → household income = 60000
    assert stats["G1"]["median_hh_income"] == 60000


def test_compute_geo_stats_pct_immigrant(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            # IMMSTAT 2 = immigrant; 3 = non-permanent resident is distinct.
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "2",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "3",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p3",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_immigrant"] == pytest.approx(33.3, abs=0.05)


def test_compute_geo_stats_skips_rows_with_no_geo(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            _hh_row("h1", "G1"),
            _hh_row("h2", ""),  # empty geo — should be skipped
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert "G1" in stats
    assert "" not in stats
    assert stats["G1"]["n_households"] == 1


def test_compute_geo_stats_non_numeric_shelco_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1", shelco="x")])

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["median_shelter_cost"] is None


def test_compute_geo_stats_non_numeric_hhsize_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1", household_size="x")])

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["avg_hh_size"] is None


def test_compute_geo_stats_person_in_unknown_geo_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            _person_row("p1", "h1", "G1"),
            _person_row("p2", "h2", "NOWHERE"),  # geo not in stats → skipped
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["n_persons"] == 1


def test_compute_geo_stats_non_numeric_agegrp_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", agegrp="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_senior"] is None
    assert stats["G1"]["pct_child"] is None


def test_compute_geo_stats_non_numeric_immstat_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", immstat="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_immigrant"] is None


def test_compute_geo_stats_non_numeric_vismin_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", vismin="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_vismin"] is None


def test_compute_geo_stats_non_numeric_totinc_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", totinc="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["median_hh_income"] is None


def test_absent_map_fields_remain_unknown_and_are_not_offered(tmp_path):
    from synthpopcan.map_render import _map_variable_specs

    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,ct,household_size\nh1,G1,1\n")
    persons.write_text("synthetic_person_id,synthetic_household_id,ct\np1,h1,G1\n")
    stats = _compute_geo_stats(households, "ct", persons)
    assert stats["G1"]["median_hh_income"] is None
    assert stats["G1"]["pct_immigrant"] is None
    assert stats["G1"]["pct_owner"] is None
    assert {variable["field"] for variable in _map_variable_specs(stats)} == {
        "n_households",
        "n_persons",
        "avg_hh_size",
    }


def test_partial_household_income_is_unknown_but_observed_zero_is_zero(tmp_path):
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,ct,household_size\nh1,G1,2\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ct,TOTINC\n"
        "p1,h1,G1,100\np2,h1,G1,\n"
    )
    assert (
        _compute_geo_stats(households, "ct", persons)["G1"]["median_hh_income"] is None
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ct,TOTINC\np1,h1,G1,0\np2,h1,G1,0\n"
    )
    assert _compute_geo_stats(households, "ct", persons)["G1"]["median_hh_income"] == 0
