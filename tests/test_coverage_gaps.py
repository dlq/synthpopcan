"""Tests targeting specific coverage gaps in cli_geo, cli_ipf, and cli_microdata."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click import ClickException

from synthpopcan.cli import main
from synthpopcan.cli_geo import _cap_column_inplace

# ---------------------------------------------------------------------------
# Helpers shared by geo tests
# ---------------------------------------------------------------------------

_PROFILE_FIELDNAMES = [
    "GEO_LEVEL",
    "GEO_CODE (POR)",
    "Member ID: Profile of Census Tracts (2247)",
    "Dim: Sex (3): Member ID: [1]: Total - Sex",
]


def _write_profile(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_PROFILE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _profile_row(
    geo_level: str, geo_code: str, member_id: str, value: str
) -> dict[str, str]:
    return {
        "GEO_LEVEL": geo_level,
        "GEO_CODE (POR)": geo_code,
        "Member ID: Profile of Census Tracts (2247)": member_id,
        "Dim: Sex (3): Member ID: [1]: Total - Sex": value,
    }


def _minimal_profile(path: Path) -> None:
    """Write a minimal two-geography profile valid for CT (GEO_LEVEL 2)."""
    rows = [
        _profile_row("2", "G1", "52", "10"),
        _profile_row("2", "G1", "53", "20"),
        _profile_row("2", "G1", "54", "30"),
        _profile_row("2", "G1", "55", "15"),
        _profile_row("2", "G1", "56", "5"),
        _profile_row("2", "G1", "1618", "50"),
        _profile_row("2", "G1", "1619", "30"),
        _profile_row("2", "G2", "52", "40"),
        _profile_row("2", "G2", "53", "60"),
        _profile_row("2", "G2", "1618", "70"),
        _profile_row("2", "G2", "1619", "30"),
    ]
    _write_profile(path, rows)


# ---------------------------------------------------------------------------
# cli_geo.py — extract-controls without --candidates (lines 531, 611-612)
# ---------------------------------------------------------------------------


def test_extract_controls_no_candidates_uses_geo_column_default_name(
    tmp_path, monkeypatch, capsys
) -> None:
    """Line 531: controls_out defaults to '<geo-column>-controls-<target>.csv'."""
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    # Work from tmp_path so the default output file lands there.
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ct",
            "--target",
            "100",
        ]
    )

    assert result == 0
    # The default output path should follow the geo-column-based pattern.
    assert (tmp_path / "ct-controls-100.csv").exists()


def test_extract_controls_no_candidates_prints_synthesize_from_package_next_step(
    tmp_path, monkeypatch, capsys
) -> None:
    """Lines 611-612: without candidates the 'else' branch prints synthesize-from-package."""
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    monkeypatch.chdir(tmp_path)

    main(
        [
            "geo",
            "build-controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ct",
            "--target",
            "100",
        ]
    )

    output = capsys.readouterr().out
    assert "synthesize-from-package" in output


# ---------------------------------------------------------------------------
# cli_geo.py — synthesize-from-package error branches (lines 830-836)
# ---------------------------------------------------------------------------


def test_synthesize_from_package_missing_file_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 830-831: non-existent package path raises ClickException."""
    missing = tmp_path / "nonexistent-package.json"

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize-from-package",
                str(missing),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


def test_synthesize_from_package_invalid_json_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 830-831: invalid JSON in package path raises ClickException."""
    bad_package = tmp_path / "bad.json"
    bad_package.write_text("not valid json{{{")

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize-from-package",
                str(bad_package),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


def test_synthesize_from_package_not_publishable_candidate_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 835-836: package without privacy.publishable_candidate=true raises ClickException."""
    # A minimal package JSON that reads without error but fails validation.
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps(
            {
                "version": "1",
                "privacy": {"publishable_candidate": False},
                "household_model": {},
                "person_model": {},
            }
        )
    )

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize-from-package",
                str(package),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


# ---------------------------------------------------------------------------
# cli_geo.py — _cap_column_inplace (lines 891-906)
# ---------------------------------------------------------------------------


def test_cap_column_inplace_caps_values_above_limit(tmp_path) -> None:
    """Lines 900-902: integer values above cap are replaced with the cap."""
    csv_path = tmp_path / "households.csv"
    csv_path.write_text("household_id,household_size\n1,3\n2,5\n3,7\n4,10\n")

    _cap_column_inplace(csv_path, "household_size", 5)

    rows = list(csv.DictReader(csv_path.open()))
    assert rows[0]["household_size"] == "3"
    assert rows[1]["household_size"] == "5"
    assert rows[2]["household_size"] == "5"
    assert rows[3]["household_size"] == "5"


def test_cap_column_inplace_leaves_values_at_or_below_cap_unchanged(tmp_path) -> None:
    """Lines 900-902: values at or below the cap are not modified."""
    csv_path = tmp_path / "households.csv"
    csv_path.write_text("household_id,household_size\n1,1\n2,5\n")

    _cap_column_inplace(csv_path, "household_size", 5)

    rows = list(csv.DictReader(csv_path.open()))
    assert rows[0]["household_size"] == "1"
    assert rows[1]["household_size"] == "5"


def test_cap_column_inplace_ignores_non_numeric_values(tmp_path) -> None:
    """Lines 903-904: non-integer values in the column are left unchanged."""
    csv_path = tmp_path / "households.csv"
    csv_path.write_text("household_id,household_size\n1,N/A\n2,3\n")

    _cap_column_inplace(csv_path, "household_size", 5)

    rows = list(csv.DictReader(csv_path.open()))
    assert rows[0]["household_size"] == "N/A"
    assert rows[1]["household_size"] == "3"


def test_cap_column_inplace_missing_column_leaves_rows_unchanged(tmp_path) -> None:
    """Lines 903-904: KeyError when column is absent is silently swallowed."""
    csv_path = tmp_path / "households.csv"
    csv_path.write_text("household_id,other_col\n1,hello\n")

    _cap_column_inplace(csv_path, "household_size", 5)

    rows = list(csv.DictReader(csv_path.open()))
    assert rows[0]["other_col"] == "hello"


# ---------------------------------------------------------------------------
# cli_ipf.py — check-inputs OSError (lines 65-68)
# ---------------------------------------------------------------------------


def test_ipf_check_inputs_oserror_on_seed_read(tmp_path) -> None:
    """Lines 65-68: OSError reading seed raises ClickException."""
    missing_seed = tmp_path / "missing_seed.csv"
    controls = tmp_path / "controls.csv"
    controls.write_text(
        "margin,dimensions,age,count\nage,age,young,50\nage,age,old,50\n"
    )

    with pytest.raises(ClickException):
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(missing_seed),
                "--controls",
                str(controls),
            ]
        )


# ---------------------------------------------------------------------------
# cli_ipf.py — suggest-controls OSError (lines 104-107)
# ---------------------------------------------------------------------------


def test_ipf_suggest_controls_oserror_on_seed_read(tmp_path) -> None:
    """Lines 104-107: OSError reading seed raises ClickException."""
    missing_seed = tmp_path / "no_such_seed.csv"

    with pytest.raises(ClickException):
        main(
            [
                "ipf",
                "suggest-controls",
                "--seed",
                str(missing_seed),
            ]
        )


# ---------------------------------------------------------------------------
# cli_ipf.py — fit OSError on read (lines 165-168)
# ---------------------------------------------------------------------------


def test_ipf_fit_oserror_on_missing_seed(tmp_path) -> None:
    """Lines 165-168: missing seed CSV raises ClickException."""
    missing_seed = tmp_path / "missing.csv"
    controls = tmp_path / "controls.csv"
    controls.write_text(
        "margin,dimensions,age,count\nage,age,young,50\nage,age,old,50\n"
    )
    out = tmp_path / "out.csv"

    with pytest.raises(ClickException):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(missing_seed),
                "--controls",
                str(controls),
                "--out",
                str(out),
            ]
        )


# ---------------------------------------------------------------------------
# cli_ipf.py — fit non-convergence (line 179-180)
# ---------------------------------------------------------------------------


def test_ipf_fit_nonconvergence_raises_click_exception(tmp_path) -> None:
    """Lines 179-180: non-converged IPF without --allow-nonconverged raises ClickException."""
    seed = tmp_path / "seed.csv"
    # Multi-dimensional seed so conflicting margins cause non-convergence.
    seed.write_text("age,sex\nyoung,M\nyoung,F\nold,M\n")

    controls = tmp_path / "controls.csv"
    # Conflicting margins: almost all old + almost all F, but only one old,M row.
    controls.write_text(
        "margin,dimensions,age,sex,count\n"
        "age,age,young,,1\n"
        "age,age,old,,9999\n"
        "sex,sex,,M,5\n"
        "sex,sex,,F,9995\n"
    )
    out = tmp_path / "out.csv"

    with pytest.raises(ClickException):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed),
                "--controls",
                str(controls),
                "--out",
                str(out),
                "--max-iterations",
                "2",
                "--tolerance",
                "1e-100",
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — inspect OSError (line 97)
# ---------------------------------------------------------------------------


def test_microdata_inspect_oserror_raises_click_exception(tmp_path) -> None:
    """Line 97: OSError from read_statcan_2016_hierarchical_seed_sample raises ClickException."""
    missing = tmp_path / "no_such_file.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "inspect",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — check-seed OSError (line 147)
# ---------------------------------------------------------------------------


def test_microdata_check_seed_oserror_raises_click_exception(tmp_path) -> None:
    """Line 147: OSError from read_statcan_2016_hierarchical_seed_sample raises ClickException."""
    missing = tmp_path / "no_such_file.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "check-seed",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "household",
                "--columns",
                "HHSIZE",
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — suggest-tree-columns OSError (line 184)
# ---------------------------------------------------------------------------


def test_microdata_suggest_tree_columns_oserror_raises_click_exception(
    tmp_path,
) -> None:
    """Line 184: OSError from read_statcan_2016_hierarchical_seed_sample raises ClickException."""
    missing = tmp_path / "no_such_file.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "suggest-tree-columns",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — inspect-geography OSError (line 301)
# ---------------------------------------------------------------------------


def test_microdata_inspect_geography_oserror_raises_click_exception(
    tmp_path,
) -> None:
    """Line 301: OSError from read_statcan_2016_hierarchical_seed_sample raises ClickException."""
    missing = tmp_path / "no_such_file.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "tree-geography-feasibility",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
                "--geo-column",
                "PR",
                "--household-block",
                "HHSIZE",
                "--person-block",
                "AGEGRP",
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — export-seed OSError on read (line 390)
# ---------------------------------------------------------------------------


def test_microdata_export_seed_oserror_on_missing_file_raises_click_exception(
    tmp_path,
) -> None:
    """Line 390: OSError when input file is missing raises ClickException."""
    missing = tmp_path / "no_such_file.csv"
    out = tmp_path / "seed_out.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "export-seed",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "HHSIZE",
                "--out",
                str(out),
            ]
        )


# ---------------------------------------------------------------------------
# cli_microdata.py — export-training OSError on read (line 462)
# ---------------------------------------------------------------------------


def test_microdata_export_training_oserror_on_missing_file_raises_click_exception(
    tmp_path,
) -> None:
    """Line 462: OSError when input file is missing raises ClickException."""
    missing = tmp_path / "no_such_file.csv"
    out = tmp_path / "training_out.csv"

    with pytest.raises(ClickException):
        main(
            [
                "microdata",
                "export-training",
                str(missing),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP",
                "--conditioning-columns",
                "HHSIZE",
                "--out",
                str(out),
            ]
        )
