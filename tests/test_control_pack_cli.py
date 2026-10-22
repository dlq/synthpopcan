"""Control pack cli behaviour and regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.control_pack_fixtures import (
    _GEOGRAPHY_IDS,
    _population,
    _tables,
    _write_rows,
)

from synthpopcan.cli import main
from synthpopcan.controls import (
    write_control_table,
)


def test_control_pack_cli_builds_evidence_and_plans_without_fitting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    geography = _GEOGRAPHY_IDS["da"]
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack_id,
        households,
        persons,
        geographies=(geography,),
    )
    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    controls_path = tmp_path / "controls.csv"
    person_controls_path = tmp_path / "person-controls.csv"
    universe_path = tmp_path / "universe.json"
    evidence_path = tmp_path / "evidence.json"
    _write_rows(households_path, households)
    _write_rows(persons_path, persons)
    write_control_table(controls_path, controls)
    write_control_table(person_controls_path, person_controls)
    universe_path.write_text(
        json.dumps(
            {
                geography: {
                    "total_population": 15,
                    "persons_in_private_households": 15,
                }
            }
        )
    )

    assert (
        main(
            [
                "geo",
                "control-packs",
                "evidence",
                pack_id,
                "--controls",
                str(controls_path),
                "--person-controls",
                str(person_controls_path),
                "--universe-evidence",
                str(universe_path),
                "--out",
                str(evidence_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert evidence_path.is_file()
    assert (
        main(
            [
                "geo",
                "control-packs",
                "plan",
                pack_id,
                str(households_path),
                "--persons",
                str(persons_path),
                "--controls",
                str(controls_path),
                "--person-controls",
                str(person_controls_path),
                "--evidence",
                str(evidence_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    plan = json.loads(capsys.readouterr().out)
    assert plan["passed"] is True
    assert plan["geographies"]["identifiers"] == [geography]
