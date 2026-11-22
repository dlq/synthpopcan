"""Bilingual Profile ingestion using bounded original Statistics Canada rows."""

import csv
from pathlib import Path
from zipfile import ZipFile

import pytest

from synthpopcan import _education_packs, _labour_force_packs, _work_activity_packs
from synthpopcan._profile_preparation import observed_count, select_profile
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.small_area_controls import extract_controls_from_profile

FIXTURES = Path(__file__).parent / "fixtures" / "census"
TRACT = "4210001.01"


@pytest.mark.parametrize("year", [2016, 2021])
@pytest.mark.parametrize(
    ("module", "family"),
    [
        (_education_packs, "education"),
        (_labour_force_packs, "labour-force-status"),
        (_work_activity_packs, "work-activity"),
    ],
)
@pytest.mark.parametrize("zipped", [False, True])
def test_actual_profile_conditional_targets_match_languages(
    tmp_path, year, module, family, zipped
):
    universe = statcan_geography_universe(year, "ct", "ct")
    targets = []
    for language in ("en", "fr"):
        source = FIXTURES / f"profile-{year}-{language}-quebec.csv"
        if zipped:
            archive = tmp_path / f"{language}.zip"
            member = "English" if language == "en" else "Francais"
            with ZipFile(archive, "w") as z:
                z.write(source, f"profile_{member}_CSV_data.csv")
            source = archive
        result, report = module.prepare_pack_targets(
            f"statcan-{year}-{family}-ct-v1", source, universe, {TRACT}
        )
        targets.append((result, report["geographies"]))
    assert targets[0] == targets[1]


@pytest.mark.parametrize("year", [2016, 2021])
def test_actual_profile_household_controls_match_languages(year):
    controls = [
        extract_controls_from_profile(
            FIXTURES / f"profile-{year}-{language}-quebec.csv", "ct", geo_ids={TRACT}
        )
        for language in ("en", "fr")
    ]
    assert controls[0] == controls[1]
    assert set(controls[0][TRACT]) == {"hhsize", "tenure"}


def test_french_broad_controls_match_and_preserve_positional_symbols(tmp_path):
    profiles = []
    for language in ("en", "fr"):
        selected = tmp_path / f"{language}.csv"
        cells = select_profile(
            FIXTURES / f"profile-2021-{language}-quebec.csv", "421", selected
        )
        profiles.append(cells)
        with selected.open(encoding="latin-1", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows[0].count("SYMBOL") == 6
        assert any("..." in row for row in rows[1:])
    for geo in ("421", TRACT):
        for member in profiles[0][geo]:
            for column in ("C1_COUNT_TOTAL", "C2_COUNT_MEN+", "C3_COUNT_WOMEN+"):
                assert (
                    profiles[0][geo][member][column] == profiles[1][geo][member][column]
                )


@pytest.mark.parametrize("symbol", ["x", "F", "..", "...", "r"])
def test_flagged_numeric_french_count_is_not_accepted(tmp_path, symbol):
    source = FIXTURES / "profile-2021-fr-quebec.csv"
    with source.open(encoding="latin-1", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    for row in rows[1:]:
        if row[2] == TRACT and row[8] == "50":
            row[12] = symbol
            break
    path = tmp_path / "flagged.csv"
    with path.open("w", encoding="latin-1", newline="") as f:
        csv.writer(f).writerows(rows)
    assert header[12] == "SYMBOLE"
    cells = select_profile(path, "421", tmp_path / "selected.csv")
    with pytest.raises(ValueError, match="suppressed or invalid"):
        observed_count(cells, TRACT, "50")


def test_mixed_language_zip_rejected(tmp_path):
    path = tmp_path / "mixed.zip"
    with ZipFile(path, "w") as z:
        for language, member in (("en", "English"), ("fr", "Francais")):
            z.write(
                FIXTURES / f"profile-2021-{language}-quebec.csv",
                f"profile_{member}_CSV_data.csv",
            )
    with pytest.raises(ValueError, match="exactly one"):
        select_profile(path, "421", tmp_path / "selected.csv")
