import pytest

from synthpopcan.calibration import (
    _build_review_notes,
    _classify_controls,
    _first_search_query,
    _infer_unit,
    _matching_column,
    build_control_suggestion_report,
)


def test_build_control_suggestion_report_rejects_empty_or_invalid_units() -> None:
    with pytest.raises(ValueError, match="at least one seed row"):
        build_control_suggestion_report([])
    with pytest.raises(ValueError, match="unit must be household"):
        build_control_suggestion_report([{"age": "young"}], unit="dwelling")


def test_control_suggestion_report_handles_household_and_person_paths() -> None:
    household_report = build_control_suggestion_report(
        [{"GEO": "QC", "TENUR": "owned"}],
        unit="auto",
        seed_path="households.csv",
    )
    person_report = build_control_suggestion_report(
        [{"PR": "24", "AGEGRP": "25 to 34", "SEX": "F"}],
        unit="auto",
    )

    assert household_report["unit"] == "household"
    assert household_report["geography_columns"] == ["GEO"]
    assert household_report["usable_controls"][0]["column"] == "TENUR"
    assert household_report["next_commands"][2].endswith(
        "--seed households.csv --controls controls.csv"
    )
    assert person_report["unit"] == "person"
    assert [control["column"] for control in person_report["usable_controls"][:2]] == [
        "AGEGRP",
        "SEX",
    ]


def test_control_classification_and_review_helper_edges() -> None:
    catalog = [
        {
            "canonical": "age_group",
            "aliases": ("AGEGRP",),
            "search": "age sex",
            "role": "demographics",
            "reason": "Age is useful.",
        },
        {
            "canonical": "custom",
            "aliases": "not-a-tuple",
            "search": "custom",
            "role": "custom",
            "reason": "Custom control.",
        },
    ]

    usable, enrichment = _classify_controls(["agegrp"], catalog)

    assert _matching_column(["AgeGrp"], ("agegrp",)) == "AgeGrp"
    assert _matching_column(["AgeGrp"], "agegrp") is None
    assert usable[0]["column"] == "agegrp"
    assert enrichment[0]["status"] == "needs_enrichment_or_modeling"
    assert _infer_unit(["synthetic_person_id"]) == "person"
    assert _infer_unit(["HH_ID"]) == "household"
    assert _first_search_query([], "person") == "person totals"
    assert _build_review_notes("person", [], [])[-1] == (
        "No common calibration columns were found; add attributes before IPF."
    )
