"""Smoke-test an installed wheel from outside the source checkout."""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

from click.testing import CliRunner

import synthpopcan
from synthpopcan.cli import cli
from synthpopcan.enrichment import SourceProfile, register_resource
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.ipf import IPFMargin, fit_ipf

package_path = Path(synthpopcan.__file__).resolve()
source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
if source_root in package_path.parents:
    raise RuntimeError(f"wheel smoke imported from the checkout: {package_path}")
assert "site-packages" in package_path.parts

result = fit_ipf(
    [{"age": "young"}, {"age": "old"}],
    [IPFMargin(("age",), {("young",): 6.0, ("old",): 4.0})],
)
assert result.converged
assert result.weights == [6.0, 4.0]
assert files("synthpopcan").joinpath("web/index.html").is_file()

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

print(f"Installed wheel smoke passed: {package_path}")
