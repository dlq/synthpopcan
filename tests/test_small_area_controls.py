"""Tests for small_area_controls — profile parsing, scaling, and CSV writing."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from synthpopcan.cli import main
from synthpopcan.small_area_controls import (
    _GEO_LEVEL_FOR_COLUMN,
    _HHSIZE_MEMBERS,
    _TENURE_MEMBERS,
    _find_col,
    extract_controls_from_profile,
    scale_and_validate_controls,
    write_controls_csv,
    write_recoded_candidates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_profile(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a minimal census-profile-shaped CSV."""
    fieldnames = [
        "GEO_LEVEL",
        "GEO_CODE (POR)",
        "Member ID: Profile of Census Tracts (2247)",
        "Dim: Sex (3): Member ID: [1]: Total - Sex",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _profile_row(
    geo_level: str,
    geo_code: str,
    member_id: str,
    value: str,
) -> dict[str, str]:
    return {
        "GEO_LEVEL": geo_level,
        "GEO_CODE (POR)": geo_code,
        "Member ID: Profile of Census Tracts (2247)": member_id,
        "Dim: Sex (3): Member ID: [1]: Total - Sex": value,
    }


def _minimal_profile(path: Path) -> None:
    """Two geo units: G1 (complete) and G2 (complete), using ADA GEO_LEVEL 3."""
    rows = [
        # G1 hhsize
        _profile_row("3", "G1", "52", "10"),  # 1-person: 10
        _profile_row("3", "G1", "53", "20"),  # 2-person: 20
        _profile_row("3", "G1", "54", "30"),  # 3-person: 30
        _profile_row("3", "G1", "55", "15"),  # 4-person: 15
        _profile_row("3", "G1", "56", "5"),  # 5+: 5   → total 80
        # G1 tenure
        _profile_row("3", "G1", "1618", "50"),  # Owner: 50
        _profile_row("3", "G1", "1619", "30"),  # Renter: 30  → total 80
        # G2 hhsize
        _profile_row("3", "G2", "52", "40"),
        _profile_row("3", "G2", "53", "60"),  # total 100
        # G2 tenure
        _profile_row("3", "G2", "1618", "70"),
        _profile_row("3", "G2", "1619", "30"),  # total 100
        # noise — different GEO_LEVEL, should be ignored
        _profile_row("1", "CANADA", "52", "9999"),
    ]
    _write_profile(path, rows)


# ---------------------------------------------------------------------------
# _find_col
# ---------------------------------------------------------------------------


def test_find_col_returns_matching_column() -> None:
    assert _find_col(
        ["GEO_CODE (POR)", "GEO_LEVEL", "Member ID: Profile"], "Member ID"
    ) == ("Member ID: Profile")


def test_find_col_raises_on_missing() -> None:
    with pytest.raises(ValueError, match="Could not find"):
        _find_col(["a", "b"], "xyz")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_hhsize_members_covers_five_categories() -> None:
    assert set(_HHSIZE_MEMBERS.values()) == {"1", "2", "3", "4", "5"}


def test_tenure_members_covers_two_categories() -> None:
    assert set(_TENURE_MEMBERS.values()) == {"1", "2"}


def test_geo_level_for_column_known_geographies() -> None:
    assert _GEO_LEVEL_FOR_COLUMN["ada"] == "3"
    assert _GEO_LEVEL_FOR_COLUMN["ct"] == "2"


# ---------------------------------------------------------------------------
# extract_controls_from_profile
# ---------------------------------------------------------------------------


def test_extract_controls_reads_hhsize_and_tenure(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    raw = extract_controls_from_profile(profile, "ada")

    assert set(raw) == {"G1", "G2"}
    assert raw["G1"]["hhsize"]["1"] == 10.0
    assert raw["G1"]["hhsize"]["5"] == 5.0
    assert raw["G1"]["tenure"]["1"] == 50.0
    assert raw["G1"]["tenure"]["2"] == 30.0
    assert raw["G2"]["hhsize"]["1"] == 40.0


def test_extract_controls_filters_by_geo_prefix(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    raw = extract_controls_from_profile(profile, "ada", geo_prefix="G1")

    assert set(raw) == {"G1"}


def test_extract_controls_ignores_wrong_geo_level(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    raw = extract_controls_from_profile(profile, "ada")

    assert "CANADA" not in raw


def test_extract_controls_geo_level_override(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    # GEO_LEVEL "1" has the CANADA row
    raw = extract_controls_from_profile(profile, "ada", geo_level_value="1")

    assert "CANADA" in raw


def test_extract_controls_raises_for_unknown_geography(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    with pytest.raises(ValueError, match="Unknown geography"):
        extract_controls_from_profile(profile, "unknown_geo")


def test_extract_controls_skips_non_numeric_values(tmp_path: Path) -> None:
    rows = [
        _profile_row("3", "G1", "52", "x"),  # non-numeric → skip
        _profile_row("3", "G1", "53", "10"),
        _profile_row("3", "G1", "1618", "5"),
        _profile_row("3", "G1", "1619", "5"),
    ]
    profile = tmp_path / "profile.csv"
    _write_profile(profile, rows)

    raw = extract_controls_from_profile(profile, "ada")

    assert "1" not in raw["G1"]["hhsize"]  # member 52 → cat "1" was skipped
    assert "2" in raw["G1"]["hhsize"]


# ---------------------------------------------------------------------------
# scale_and_validate_controls
# ---------------------------------------------------------------------------


def test_scale_and_validate_scales_to_target(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    raw = extract_controls_from_profile(profile, "ada")

    scaled, dropped = scale_and_validate_controls(raw, 900)

    # G1 hhsize total = 80, G2 = 100, grand = 180; scale = 900/180 = 5
    assert dropped == []
    g1_hhsize_total = sum(scaled["G1"]["hhsize"].values())
    g2_hhsize_total = sum(scaled["G2"]["hhsize"].values())
    assert g1_hhsize_total == 400  # 80 * 5
    assert g2_hhsize_total == 500  # 100 * 5


def test_scale_and_validate_tenure_matches_hhsize(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    raw = extract_controls_from_profile(profile, "ada")

    scaled, _ = scale_and_validate_controls(raw, 900)

    for geo in scaled:
        assert sum(scaled[geo]["hhsize"].values()) == sum(
            scaled[geo]["tenure"].values()
        )


def test_scale_and_validate_drops_geo_missing_tenure(tmp_path: Path) -> None:
    rows = [
        # G1: has hhsize, no tenure
        _profile_row("3", "G1", "52", "10"),
        # G2: complete
        _profile_row("3", "G2", "52", "20"),
        _profile_row("3", "G2", "1618", "15"),
        _profile_row("3", "G2", "1619", "5"),
    ]
    profile = tmp_path / "profile.csv"
    _write_profile(profile, rows)
    raw = extract_controls_from_profile(profile, "ada")

    scaled, dropped = scale_and_validate_controls(raw, 100)

    assert "G1" in dropped
    assert "G2" in scaled


def test_scale_and_validate_drops_geo_missing_hhsize(tmp_path: Path) -> None:
    rows = [
        # G1: has tenure, no hhsize
        _profile_row("3", "G1", "1618", "10"),
        # G2: complete
        _profile_row("3", "G2", "52", "20"),
        _profile_row("3", "G2", "1618", "15"),
        _profile_row("3", "G2", "1619", "5"),
    ]
    profile = tmp_path / "profile.csv"
    _write_profile(profile, rows)
    raw = extract_controls_from_profile(profile, "ada")

    _, dropped = scale_and_validate_controls(raw, 100)

    assert "G1" in dropped


def test_scale_and_validate_raises_when_nothing_left() -> None:
    with pytest.raises(ValueError, match="No household-size totals"):
        scale_and_validate_controls({}, 1000)


# ---------------------------------------------------------------------------
# write_controls_csv
# ---------------------------------------------------------------------------


def test_write_controls_csv_produces_correct_margins(tmp_path: Path) -> None:
    scaled = {
        "G1": {
            "hhsize": {"1": 10, "2": 20},
            "tenure": {"1": 18, "2": 12},
        }
    }
    out = tmp_path / "controls.csv"
    write_controls_csv(scaled, out, "ada")

    rows = list(csv.DictReader(out.open()))
    tenure_rows = [r for r in rows if r["margin"] == "ada tenure"]
    hhsize_rows = [r for r in rows if r["margin"] == "ada hhsize"]

    assert len(tenure_rows) == 2
    assert len(hhsize_rows) == 2
    assert all(r["ada"] == "G1" for r in rows)
    assert {r["TENUR"] for r in tenure_rows} == {"1", "2"}
    assert {r["household_size"] for r in hhsize_rows} == {"1", "2"}


def test_write_controls_csv_dimensions_column(tmp_path: Path) -> None:
    scaled = {"G1": {"hhsize": {"1": 5}, "tenure": {"1": 5}}}
    out = tmp_path / "controls.csv"
    write_controls_csv(scaled, out, "ct")

    rows = list(csv.DictReader(out.open()))
    dim_values = {r["dimensions"] for r in rows}
    assert "ct,TENUR" in dim_values
    assert "ct,household_size" in dim_values


def test_write_controls_csv_creates_parent_dir(tmp_path: Path) -> None:
    scaled = {"G1": {"hhsize": {"1": 5}, "tenure": {"1": 5}}}
    out = tmp_path / "subdir" / "controls.csv"
    write_controls_csv(scaled, out, "ada")
    assert out.exists()


# ---------------------------------------------------------------------------
# write_recoded_candidates
# ---------------------------------------------------------------------------


def test_write_recoded_candidates_caps_hhsize(tmp_path: Path) -> None:
    src = tmp_path / "households.csv"
    src.write_text("synthetic_household_id,household_size\nh1,3\nh2,6\nh3,1\n")
    out = tmp_path / "recoded.csv"

    n = write_recoded_candidates(src, out)

    rows = list(csv.DictReader(out.open()))
    assert n == 3
    assert rows[0]["household_size"] == "3"
    assert rows[1]["household_size"] == "5"  # capped from 6
    assert rows[2]["household_size"] == "1"


def test_write_recoded_candidates_custom_cap(tmp_path: Path) -> None:
    src = tmp_path / "households.csv"
    src.write_text("synthetic_household_id,household_size\nh1,4\n")
    out = tmp_path / "recoded.csv"

    write_recoded_candidates(src, out, cap=3)

    rows = list(csv.DictReader(out.open()))
    assert rows[0]["household_size"] == "3"


def test_write_recoded_candidates_preserves_all_columns(tmp_path: Path) -> None:
    src = tmp_path / "households.csv"
    src.write_text("synthetic_household_id,household_size,TENUR\nh1,2,1\n")
    out = tmp_path / "recoded.csv"
    write_recoded_candidates(src, out)

    rows = list(csv.DictReader(out.open()))
    assert rows[0]["TENUR"] == "1"


def test_write_recoded_candidates_creates_parent_dir(tmp_path: Path) -> None:
    src = tmp_path / "households.csv"
    src.write_text("synthetic_household_id,household_size\nh1,1\n")
    out = tmp_path / "sub" / "out.csv"
    write_recoded_candidates(src, out)
    assert out.exists()


# ---------------------------------------------------------------------------
# CLI: small-area build-controls
# ---------------------------------------------------------------------------


def test_cli_build_controls_writes_outputs(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    candidates = tmp_path / "households.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,3\nh2,6\n")

    controls_out = tmp_path / "controls.csv"
    candidates_out = tmp_path / "recoded.csv"

    exit_code = main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ada",
            "--target",
            "900",
            "--candidates",
            str(candidates),
            "--controls-out",
            str(controls_out),
            "--candidates-out",
            str(candidates_out),
        ]
    )

    assert exit_code == 0
    assert controls_out.exists()
    assert candidates_out.exists()

    # Controls should have both margin types
    control_rows = list(csv.DictReader(controls_out.open()))
    margins = {r["margin"] for r in control_rows}
    assert "ada hhsize" in margins
    assert "ada tenure" in margins

    # Recoded candidates should cap hhsize at 5
    recoded_rows = list(csv.DictReader(candidates_out.open()))
    assert recoded_rows[1]["household_size"] == "5"  # h2 was 6, now capped


def test_cli_build_controls_default_output_paths(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    candidates = tmp_path / "households.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    exit_code = main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ada",
            "--target",
            "900",
            "--candidates",
            str(candidates),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "households-controls-900.csv").exists()
    assert (tmp_path / "households-recoded.csv").exists()


def test_cli_build_controls_geo_prefix_filter(tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)

    candidates = tmp_path / "households.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,1\n")

    controls_out = tmp_path / "controls.csv"
    candidates_out = tmp_path / "recoded.csv"

    exit_code = main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ada",
            "--geo-prefix",
            "G1",
            "--target",
            "400",
            "--candidates",
            str(candidates),
            "--controls-out",
            str(controls_out),
            "--candidates-out",
            str(candidates_out),
        ]
    )

    assert exit_code == 0
    rows = list(csv.DictReader(controls_out.open()))
    geos = {r["ada"] for r in rows}
    assert geos == {"G1"}
    assert "G2" not in geos


def test_scale_and_validate_corrects_rounding_drift() -> None:
    # Use banker's rounding to force drift: round(2.5)=2 and round(2.5)=2 → total 4,
    # but hhsize_total=5. The correction (lines 155-156) adjusts the largest category.
    raw = {
        "G1": {
            "hhsize": {"1": 1, "2": 2},  # grand_total=3; scale=5/3→hhsize={1:2,2:3}→5
            "tenure": {
                "1": 1,
                "2": 1,
            },  # tenure_scale=5/2=2.5; both round to 2 → total 4
        }
    }
    scaled, _ = scale_and_validate_controls(raw, 5)
    hhsize_sum = sum(scaled["G1"]["hhsize"].values())
    tenure_sum = sum(scaled["G1"]["tenure"].values())
    assert hhsize_sum == tenure_sum  # correction restored equality
    assert tenure_sum == 5  # drift was corrected upward (+1)


def test_write_recoded_candidates_handles_non_numeric_hhsize(tmp_path: Path) -> None:
    src = tmp_path / "households.csv"
    # Non-numeric household_size should pass through unchanged (except clause)
    src.write_text("synthetic_household_id,household_size\nh1,x\n")
    out = tmp_path / "recoded.csv"

    n = write_recoded_candidates(src, out)

    rows = list(csv.DictReader(out.open()))
    assert n == 1
    assert rows[0]["household_size"] == "x"


# ---------------------------------------------------------------------------
# CLI: build-controls — error-handler branches
# ---------------------------------------------------------------------------


def _profile_with_dropped_geo(path: Path) -> None:
    """G1 is complete; G3 has hhsize only (no tenure) — will be dropped."""
    rows = [
        _profile_row("3", "G1", "52", "10"),
        _profile_row("3", "G1", "1618", "6"),
        _profile_row("3", "G1", "1619", "4"),
        _profile_row("3", "G3", "52", "20"),  # no tenure rows → dropped
    ]
    _write_profile(path, rows)


def test_cli_build_controls_reports_dropped_geos(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = tmp_path / "profile.csv"
    _profile_with_dropped_geo(profile)
    candidates = tmp_path / "c.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    exit_code = main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ada",
            "--target",
            "100",
            "--candidates",
            str(candidates),
        ]
    )

    assert exit_code == 0
    assert "Dropped" in capsys.readouterr().out


def test_cli_build_controls_oserror_on_profile(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    profile = tmp_path / "profile.csv"
    profile.touch()
    candidates = tmp_path / "c.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    with patch(
        "synthpopcan.small_area_controls.extract_controls_from_profile",
        side_effect=OSError("no disk"),
    ):
        with pytest.raises(click.ClickException, match="no disk"):
            main(
                [
                    "geo",
                    "build-controls",
                    "--profile",
                    str(profile),
                    "--geo-column",
                    "ada",
                    "--target",
                    "100",
                    "--candidates",
                    str(candidates),
                ]
            )


def test_cli_build_controls_value_error_on_profile(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    profile = tmp_path / "profile.csv"
    profile.touch()
    candidates = tmp_path / "c.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    with patch(
        "synthpopcan.small_area_controls.extract_controls_from_profile",
        side_effect=ValueError("bad column"),
    ):
        with pytest.raises(click.ClickException, match="bad column"):
            main(
                [
                    "geo",
                    "build-controls",
                    "--profile",
                    str(profile),
                    "--geo-column",
                    "ada",
                    "--target",
                    "100",
                    "--candidates",
                    str(candidates),
                ]
            )


def test_cli_build_controls_oserror_on_write_controls(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    candidates = tmp_path / "c.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    with patch(
        "synthpopcan.small_area_controls.write_controls_csv",
        side_effect=OSError("disk full"),
    ):
        with pytest.raises(click.ClickException, match="disk full"):
            main(
                [
                    "geo",
                    "build-controls",
                    "--profile",
                    str(profile),
                    "--geo-column",
                    "ada",
                    "--target",
                    "100",
                    "--candidates",
                    str(candidates),
                ]
            )


def test_cli_build_controls_oserror_on_write_candidates(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    candidates = tmp_path / "c.csv"
    candidates.write_text("synthetic_household_id,household_size\nh1,2\n")

    with patch(
        "synthpopcan.small_area_controls.write_recoded_candidates",
        side_effect=OSError("no space"),
    ):
        with pytest.raises(click.ClickException, match="no space"):
            main(
                [
                    "geo",
                    "build-controls",
                    "--profile",
                    str(profile),
                    "--geo-column",
                    "ada",
                    "--target",
                    "100",
                    "--candidates",
                    str(candidates),
                ]
            )
