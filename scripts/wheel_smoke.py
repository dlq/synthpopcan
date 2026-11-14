"""Smoke-test an installed wheel from outside the source checkout."""

from __future__ import annotations

import csv
import json
import os
from importlib.metadata import version as distribution_version
from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path

from click.testing import CliRunner

import synthpopcan
from synthpopcan._interface import validate_installed_public_interface
from synthpopcan.cli import cli
from synthpopcan.control_packs import (
    list_builtin_control_packs,
    load_control_pack,
    plan_control_pack,
)
from synthpopcan.controls import ControlTable
from synthpopcan.enrichment import SourceProfile, register_resource
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.ipf import IPFMargin, fit_ipf

package_path = Path(synthpopcan.__file__).resolve()
source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
expected_version = os.environ["SYNTHPOPCAN_EXPECTED_VERSION"]
if source_root in package_path.parents:
    raise RuntimeError(f"wheel smoke imported from the checkout: {package_path}")
assert "site-packages" in package_path.parts
assert distribution_version("synthpopcan") == expected_version
assert synthpopcan.__version__ == expected_version
for optional_dependency in ("numba", "polars", "scipy"):
    assert find_spec(optional_dependency) is None, (
        f"base distribution unexpectedly installed {optional_dependency}"
    )

result = fit_ipf(
    [{"age": "young"}, {"age": "old"}],
    [IPFMargin(("age",), {("young",): 6.0, ("old",): 4.0})],
)
assert result.converged
assert result.weights == [6.0, 4.0]
assert files("synthpopcan").joinpath("web/index.html").is_file()
assert files("synthpopcan").joinpath("contracts/public-interface-v1.json").is_file()
assert (
    files("synthpopcan")
    .joinpath("contracts/public-interface-v1-baseline.json")
    .is_file()
)
assert (
    files("synthpopcan")
    .joinpath("contracts/prepared-model-licensing-v1-examples.json")
    .is_file()
)
assert files("synthpopcan").joinpath("archive_correction_evidence_v1.json").is_file()
validate_installed_public_interface()

packs = list_builtin_control_packs()
assert len(packs) == 24
assert sum("-broad-" in str(pack["identifier"]) for pack in packs) == 8
broad_pack = load_control_pack("statcan-2021-broad-da-v1")
assert len(broad_pack.margins) == 14
empty_controls = ControlTable(margins=(), dimensions=())
failed_plan = plan_control_pack(
    broad_pack,
    [],
    [],
    empty_controls,
    empty_controls,
)
assert failed_plan["passed"] is False
assert "missing_control_pack_evidence" in {
    issue["kind"] for issue in failed_plan["issues"]
}

geography = statcan_geography_universe(2021, "da", "DAUID")
population = synthpopcan.write_linked_population(
    synthpopcan.LinkedPopulation(
        households=[
            {"synthetic_household_id": "h1", "DAUID": "24660001"},
            {"synthetic_household_id": "h2", "DAUID": "24660002"},
        ],
        persons=[
            {"synthetic_person_id": "p1", "synthetic_household_id": "h1"},
            {"synthetic_person_id": "p2", "synthetic_household_id": "h2"},
        ],
    ),
    "population",
    geography_column="DAUID",
)
source = SourceProfile(
    source_id="example.wheel-smoke.v1",
    publisher_id="example.publisher",
    titles={"en": "Wheel smoke fixture", "fr": "Exemple de paquet"},
    descriptions={"en": "Synthetic fixture.", "fr": "Exemple synthétique."},
    canonical_url="https://example.invalid/wheel-smoke.csv",
    acquisition_mode="public-download",
    authority="Synthetic fixture created by the project.",
    licence_id="CC0-1.0",
    source_version="1",
    publication_date="2026-07-31",
    observation_period={"start": "2026-07-31", "end": "2026-07-31"},
    unit_of_observation="2021 dissemination area",
    access_classification="public",
    redistribution_status="Synthetic fixture may be redistributed.",
    geography=geography,
    translation_provenance={"en": "project", "fr": "project"},
    known_limitations=("Packaging smoke test only.",),
)
resource_path = Path("source.csv")
resource_path.write_text("source\nfixture\n")
resource = register_resource(
    resource_path,
    source,
    acquired_at="2026-07-31T00:00:00Z",
    media_type="text/csv",
    public_locator=source.canonical_url,
)
layer_path = Path("normalized-layer.csv")
layer_path.write_text("DAUID,context\n24660001,A\n24660002,B\n")
enrichment = synthpopcan.enrich_population(
    population,
    layer_path,
    source_profile=source,
    resource_record=resource,
    layer_id="example.wheel-smoke.normalized.v1",
    layer_class="area-attributes",
    key_columns=["DAUID"],
    variables=["context"],
    base_geography=geography,
    output_dir="enrichment",
    limitations=["Packaging smoke test only."],
)
assert enrichment.validation["passed"] is True
assert population.manifest is not None and population.manifest.is_file()
assert enrichment.manifest.is_file()

exchange = synthpopcan.create_exchange_bundle(
    population,
    "exchange",
    geography_universe=geography,
    reproduction={
        "interface": "python",
        "operation": "installed-wheel-smoke",
    },
    access_classification="public",
    redistribution_status="permitted",
    limitations=("Fictional packaging smoke fixture only.",),
)
assert exchange.report["passed"] is True
assert synthpopcan.validate_exchange_bundle(exchange.directory)["passed"] is True

help_result = CliRunner().invoke(cli, ["--help"])
assert help_result.exit_code == 0
assert "SynthPopCan" in help_result.output

show_pack_result = CliRunner().invoke(
    cli,
    ["geo", "control-packs", "show", "statcan-2021-broad-da-v1"],
)
assert show_pack_result.exit_code == 0
assert "statcan-2021-broad-da-v1" in show_pack_result.output


def check_conditional_packs(year: int) -> None:
    """Exercise all four installed packs with fictional, linked tract inputs."""
    tract = "4620053.00"
    folder = Path(f"conditional-{year}")
    folder.mkdir()
    households, persons, controls, person_controls, profile, marital = (
        folder / name
        for name in (
            "hh.csv",
            "pp.csv",
            "hc.csv",
            "pc.csv",
            "profile.csv",
            "marital.csv",
        )
    )
    households.write_text("synthetic_household_id,household_size\na,1\nb,1\nc,2\n")
    labour = "LFTAG" if year == 2016 else "LFACT"
    marital_field = "MarStH" if year == 2016 else "MARSTH"
    persons.write_text(
        f"synthetic_person_id,synthetic_household_id,AGEGRP,HDGREE,{labour},WRKACT,{marital_field},group\n"
        "p1,a,3,1,1,2,1,all\np2,b,12,8,8,11,2,all\n"
        "p3,c,3,1,1,2,1,all\np4,c,2,99,99,99,8,all\n"
    )
    controls.write_text(
        f'margin,dimensions,ct,household_size,count\nsize,"ct,household_size",{tract},1,10\n'
        f'size,"ct,household_size",{tract},2,5\n'
    )
    person_controls.write_text(
        f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all,20\n'
    )
    if year == 2016:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "GEO_CODE (POR)",
            "Member ID: Profile of Census Tracts (2247)",
            "Dim: Sex (3): Member ID: [1]: Total - Sex",
        ]
        prefix = [year, 2, tract]
        members = [
            1135,
            1683,
            672,
            1684,
            1685,
            1688,
            1689,
            1690,
            1691,
            1693,
            1694,
            1695,
            1696,
            1697,
        ]
        extra = {
            1865: 15,
            1867: 5,
            1868: 5,
            1869: 0,
            1873: 15,
            1874: 5,
            1876: 5,
            1877: 0,
        }
    else:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "ALT_GEO_CODE",
            "DGUID",
            "CHARACTERISTIC_ID",
            "C1_COUNT_TOTAL",
            "SYMBOL",
        ]
        prefix = [year, "Census tract", tract, f"2021S0507{tract}"]
        members = [
            1522,
            1998,
            126,
            1999,
            2000,
            2004,
            2005,
            2006,
            2007,
            2009,
            2010,
            2011,
            2012,
            2013,
        ]
        extra = {
            2223: 15,
            2225: 5,
            2226: 5,
            2227: 0,
            2231: 15,
            2232: 5,
            2234: 5,
            2235: 0,
        }
    with profile.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        values = [20, 15, 15, 5, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0]
        for member, value in [*zip(members, values, strict=True), *extra.items()]:
            writer.writerow([*prefix, member, value, *([""] if year == 2021 else [])])
    with marital.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ct", "marital_status", "age_20", "value"])
        observed = {(1, 1): 20, (1, 2): 5, (1, 3): 15, (3, 3): 5, (6, 3): 5}
        for status in (1, 3, 4, 6, 7, 8, 9):
            ages = (1, 2, 3, *range(6, 16)) if status == 1 else (3, *range(6, 16))
            for age in ages:
                writer.writerow([tract, status, age, observed.get((status, age), 0)])
    names = {
        "marital_status": f"statcan-{year}-marital-status-ct-v1",
        "education": f"statcan-{year}-education-ct-v1",
        "labour_force": f"statcan-{year}-labour-force-status-ct-v1",
        "work_activity": f"statcan-{year}-work-activity-ct-v1",
    }
    for identifier in names.values():
        result = CliRunner().invoke(cli, ["geo", "control-packs", "show", identifier])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["census_vintage"] == year
    args = [
        "geo",
        "calibrate",
        str(households),
        "--persons",
        str(persons),
        "--controls",
        str(controls),
        "--person-controls",
        str(person_controls),
        "--geo-dimension",
        "ct",
        "--census-vintage",
        str(year),
        "--geo-level",
        "ct",
        "--geo-namespace",
        f"statcan:census:{year}:ct",
        "--integerization",
        "swap",
        "--out",
        str(folder / "cli"),
    ]
    for family, identifier in names.items():
        option = family.replace("_", "-")
        args += [
            f"--{option}-pack",
            identifier,
            f"--{option}-{'controls' if family == 'marital_status' else 'profile'}",
            str(marital if family == "marital_status" else profile),
        ]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    cli_report = json.loads((folder / "cli" / "report.json").read_text())
    assert cli_report["summary"]["converged_count"] == 1
    result = synthpopcan.calibrate_small_area(
        synthpopcan.LinkedPopulationFiles(households=households, persons=persons),
        controls,
        person_controls=person_controls,
        geography_dimension="ct",
        output_dir=folder / "python",
        geography_universe=statcan_geography_universe(year, "ct", "ct"),
        marital_status_pack=names["marital_status"],
        marital_status_controls_path=marital,
        education_pack=names["education"],
        education_profile_path=profile,
        labour_force_pack=names["labour_force"],
        labour_force_profile_path=profile,
        work_activity_pack=names["work_activity"],
        work_activity_profile_path=profile,
        integerization="swap",
    )
    python_report = json.loads(result.report_path.read_text())
    for family in (
        "marital_status",
        "education",
        "labour_force_status",
        "work_activity",
    ):
        assert python_report[f"{family}_controls"] == cli_report[f"{family}_controls"]
    wrong = args.copy()
    wrong[wrong.index("--education-pack") + 1] = (
        f"statcan-{2021 if year == 2016 else 2016}-education-ct-v1"
    )
    wrong[wrong.index("--out") + 1] = str(folder / "wrong")
    rejected = CliRunner().invoke(cli, wrong)
    assert rejected.exit_code != 0
    assert "matching Statistics Canada CT geography" in rejected.output
    assert not (folder / "wrong" / "persons.csv").exists()


for vintage in (2016, 2021):
    check_conditional_packs(vintage)

print(f"Installed wheel smoke passed: {package_path}")
