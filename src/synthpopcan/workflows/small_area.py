"""File-backed small-area synthesis workflow shared by local adapters."""

from __future__ import annotations

__all__ = ["SmallAreaRequest", "SmallAreaWorkflowResult", "synthesize_small_area_files"]

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from synthpopcan.geography import GeographyUniverse
from synthpopcan.linked_schema import (
    read_linked_population_contract,
    write_linked_population_contract,
)
from synthpopcan.map_render import render_synthesis_map
from synthpopcan.model_licensing import validate_prepared_model_licensing
from synthpopcan.small_area_controls import write_recoded_candidates
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
from synthpopcan.tree import validate_linked_population_files
from synthpopcan.workflows.models import (
    PreparedModelRequest,
    generate_prepared_model_files,
)
from synthpopcan.workflows.types import (
    ProgressReporter,
    ReproductionCommand,
    WorkflowProgress,
    WorkflowReproduction,
)


@dataclass(frozen=True)
class SmallAreaRequest:
    """One linked generation and small-area calibration request."""

    package_path: Path | None
    controls_path: Path
    candidates_dir: Path
    output_dir: Path
    candidate_households: int
    geography_dimension: str
    geography_column: str
    conditions: dict[str, str]
    geography_universe: GeographyUniverse | None = None
    person_controls_path: Path | None = None
    control_pack: str | Path | None = None
    control_pack_evidence_path: Path | None = None
    package_reference: str | None = None
    random_seed: int | None = None
    pool_size: int | None = None
    subsample_seed: int = 42
    max_household_size: int | None = None
    household_size_group_column: str = "household_size_group"
    include_weights: bool = False
    chunk_size: int = 1000
    max_iterations: int = 100
    tolerance: float = 1e-6
    candidate_households_path: Path | None = None
    candidate_persons_path: Path | None = None
    boundaries_path: Path | None = None
    map_path: Path | None = None
    geography_id_field: str = "geo_id"
    map_title: str = "Synthetic Population"
    max_candidate_households: int | None = None
    max_candidate_persons: int | None = None
    controls_reference: str | None = None
    person_controls_reference: str | None = None
    control_pack_reference: str | None = None
    control_pack_evidence_reference: str | None = None
    candidate_households_reference: str | None = None
    candidate_persons_reference: str | None = None
    boundaries_reference: str | None = None
    output_dir_reference: str | None = None

    def __post_init__(self) -> None:
        if (
            self.geography_universe is not None
            and self.geography_universe.identifier_column != self.geography_column
        ):
            raise ValueError(
                "geography universe identifier column must match geography_column"
            )
        if bool(self.control_pack) != bool(self.control_pack_evidence_path):
            raise ValueError("control pack and control-pack evidence are both required")
        if self.control_pack is not None and self.person_controls_path is None:
            raise ValueError("control packs require person controls")

    def reproduction(self) -> WorkflowReproduction:
        controls_reference = self.controls_reference or str(self.controls_path)
        person_controls_reference = self.person_controls_reference or (
            str(self.person_controls_path)
            if self.person_controls_path is not None
            else None
        )
        control_pack_reference = self.control_pack_reference or (
            str(self.control_pack) if self.control_pack is not None else None
        )
        control_pack_evidence_reference = self.control_pack_evidence_reference or (
            str(self.control_pack_evidence_path)
            if self.control_pack_evidence_path is not None
            else None
        )
        candidate_households_reference = self.candidate_households_reference or (
            str(self.candidate_households_path)
            if self.candidate_households_path is not None
            else None
        )
        candidate_persons_reference = self.candidate_persons_reference or (
            str(self.candidate_persons_path)
            if self.candidate_persons_path is not None
            else None
        )
        boundaries_reference = self.boundaries_reference or (
            str(self.boundaries_path) if self.boundaries_path is not None else None
        )
        output_dir_reference = self.output_dir_reference or str(self.output_dir)
        map_reference = (
            str(Path(output_dir_reference) / self.map_path.name)
            if self.map_path is not None
            else None
        )
        reference = self.package_reference or (
            str(self.package_path) if self.package_path is not None else None
        )
        if reference is not None:
            arguments = [
                "geo",
                "synthesize",
                reference,
                "--households",
                str(self.candidate_households),
            ]
        else:
            if candidate_households_reference is None:
                raise ValueError("candidate household path is required")
            arguments = [
                "geo",
                "calibrate",
                candidate_households_reference,
            ]
            if candidate_persons_reference is None:
                raise ValueError("candidate person path is required")
            arguments.extend(("--persons", candidate_persons_reference))
        arguments.extend(
            (
                "--controls",
                controls_reference,
                "--geo-dimension",
                self.geography_dimension,
                "--geo-column",
                self.geography_column,
                "--out",
                output_dir_reference,
                "--subsample-seed",
                str(self.subsample_seed),
            )
        )
        if person_controls_reference is not None:
            arguments.extend(("--person-controls", person_controls_reference))
        if control_pack_reference is not None:
            assert control_pack_evidence_reference is not None
            arguments.extend(("--control-pack", control_pack_reference))
            arguments.extend(
                ("--control-pack-evidence", control_pack_evidence_reference)
            )
        for column, value in sorted(self.conditions.items()):
            if reference is not None:
                arguments.extend(("--condition", f"{column}={value}"))
        if reference is not None and self.random_seed is not None:
            arguments.extend(("--random-seed", str(self.random_seed)))
        if self.pool_size is not None:
            arguments.extend(("--pool-size", str(self.pool_size)))
        if reference is not None and self.max_household_size is not None:
            arguments.extend(("--max-household-size", str(self.max_household_size)))
            arguments.extend(
                ("--household-size-group-column", self.household_size_group_column)
            )
        if self.include_weights:
            arguments.append("--include-weights")
        if self.max_iterations != 100:
            arguments.extend(("--max-iterations", str(self.max_iterations)))
        if self.tolerance != 1e-6:
            arguments.extend(("--tolerance", str(self.tolerance)))
        if self.geography_universe is not None:
            arguments.extend(
                (
                    "--census-vintage",
                    str(self.geography_universe.census_vintage),
                    "--geo-level",
                    self.geography_universe.geography_level,
                    "--geo-namespace",
                    self.geography_universe.identifier_namespace,
                )
            )
            if self.geography_universe.dguid_column is not None:
                arguments.extend(
                    ("--geo-dguid-column", self.geography_universe.dguid_column)
                )
        commands = [ReproductionCommand("synthpopcan", tuple(arguments))]
        if boundaries_reference is not None and map_reference is not None:
            commands.append(
                ReproductionCommand(
                    "synthpopcan",
                    (
                        "geo",
                        "map",
                        output_dir_reference,
                        "--boundaries",
                        boundaries_reference,
                        "--geo-column",
                        self.geography_column,
                        "--geo-id-field",
                        self.geography_id_field,
                        "--out",
                        map_reference,
                        "--title",
                        self.map_title,
                    ),
                )
            )
        return WorkflowReproduction(
            request={
                "workflow": "small_area",
                "inputs": {
                    "package": reference,
                    "candidate_households": (candidate_households_reference),
                    "candidate_persons": candidate_persons_reference,
                    "controls": controls_reference,
                    "person_controls": person_controls_reference,
                    "control_pack": control_pack_reference,
                    "control_pack_evidence": control_pack_evidence_reference,
                },
                "options": {
                    "candidate_households": self.candidate_households,
                    "geography_dimension": self.geography_dimension,
                    "geography_column": self.geography_column,
                    "conditions": self.conditions,
                    "random_seed": self.random_seed,
                    "pool_size": self.pool_size,
                    "subsample_seed": self.subsample_seed,
                    "max_household_size": self.max_household_size,
                    "household_size_group_column": self.household_size_group_column,
                    "include_weights": self.include_weights,
                    "chunk_size": self.chunk_size,
                    "max_iterations": self.max_iterations,
                    "tolerance": self.tolerance,
                },
                "outputs": {
                    "directory": output_dir_reference,
                    "map": map_reference,
                },
                "map": {
                    "boundaries": boundaries_reference,
                    "geography_id_field": self.geography_id_field,
                    "title": self.map_title,
                },
                "geography_universe": (
                    self.geography_universe.as_dict()
                    if self.geography_universe is not None
                    else None
                ),
            },
            command=commands[0],
            commands=tuple(commands),
        )


@dataclass(frozen=True)
class SmallAreaWorkflowResult:
    """Small-area artifacts and calibration diagnostics."""

    households_path: Path
    persons_path: Path
    manifest_path: Path
    report_path: Path
    weights_path: Path | None
    map_path: Path | None
    details: dict[str, Any]
    reproduction: WorkflowReproduction


def synthesize_small_area_files(
    request: SmallAreaRequest,
    *,
    progress: ProgressReporter | None = None,
) -> SmallAreaWorkflowResult:
    """Generate candidates, calibrate them, and write linked output artifacts."""
    request.candidates_dir.mkdir(parents=True, exist_ok=True)
    request.output_dir.mkdir(parents=True, exist_ok=True)
    if request.package_path is not None:
        generated = generate_prepared_model_files(
            PreparedModelRequest(
                package_path=request.package_path,
                households_path=request.candidates_dir / "households.csv",
                persons_path=request.candidates_dir / "persons.csv",
                report_path=request.candidates_dir / "generation-report.json",
                households=request.candidate_households,
                conditions=request.conditions,
                random_seed=request.random_seed,
                package_reference=request.package_reference,
                chunk_size=request.chunk_size,
                max_households=request.max_candidate_households,
                max_persons=request.max_candidate_persons,
            ),
            progress=progress,
        )
        candidate_households = generated.households_path
        candidate_persons = generated.persons_path
        household_size_column = str(generated.report["household_size_column"])
        generated_contract = _object(generated.report.get("linked_population"))
        input_licensing = validate_prepared_model_licensing(
            generated_contract.get("licensing")
        )
    elif (
        request.candidate_households_path is not None
        and request.candidate_persons_path is not None
    ):
        _emit(progress, "validating", "Validating uploaded linked candidates")
        validation = validate_linked_population_files(
            request.candidate_households_path,
            request.candidate_persons_path,
        )
        if not validation["passed"]:
            raise ValueError("uploaded linked candidates failed validation")
        candidate_households = request.candidate_households_path
        candidate_persons = request.candidate_persons_path
        household_size_column = "household_size"
        input_licensing = _candidate_licensing(
            candidate_households,
            candidate_persons,
        )
    else:
        raise ValueError("provide a package or linked candidate household/person CSVs")
    if request.max_household_size is not None:
        _emit(progress, "recoding", "Grouping candidate household sizes")
        source_households = candidate_households
        candidate_households = request.candidates_dir / "households-recoded.csv"
        write_recoded_candidates(
            source_households,
            candidate_households,
            hhsize_col=household_size_column,
            group_col=request.household_size_group_column,
            cap=request.max_household_size,
        )

    households_path = request.output_dir / "households.csv"
    persons_path = request.output_dir / "persons.csv"
    manifest_path = request.output_dir / "manifest.json"
    report_path = request.output_dir / "report.json"
    weights_path = (
        request.output_dir / "weights.csv" if request.include_weights else None
    )
    _emit(progress, "calibrating", "Fitting candidates to small-area controls")
    details = calibrate_linked_household_csvs(
        households_path=candidate_households,
        persons_path=candidate_persons,
        controls_path=request.controls_path,
        person_controls_path=request.person_controls_path,
        control_pack=request.control_pack,
        control_pack_evidence=request.control_pack_evidence_path,
        geography_dimension=request.geography_dimension,
        geography_column=request.geography_column,
        geography_universe=request.geography_universe,
        households_out=households_path,
        persons_out=persons_path,
        report_out=report_path,
        weights_out=weights_path,
        pool_size=request.pool_size,
        subsample_seed=request.subsample_seed,
        max_iterations=request.max_iterations,
        tolerance=request.tolerance,
    )
    write_linked_population_contract(
        manifest_path,
        households_path,
        persons_path,
        geography_column=request.geography_column,
        licensing=input_licensing,
    )
    map_path = None
    if request.boundaries_path is not None and request.map_path is not None:
        _emit(progress, "mapping", "Rendering the standalone small-area map")
        map_path = render_synthesis_map(
            households_path=households_path,
            persons_path=persons_path,
            boundaries_path=request.boundaries_path,
            geography_column=request.geography_column,
            geography_id_field=request.geography_id_field,
            out_path=request.map_path,
            title=request.map_title,
        )
    _emit(progress, "completed", "Small-area synthesis completed")
    return SmallAreaWorkflowResult(
        households_path=households_path,
        persons_path=persons_path,
        manifest_path=manifest_path,
        report_path=report_path,
        weights_path=weights_path,
        map_path=map_path,
        details=details,
        reproduction=request.reproduction(),
    )


def _candidate_licensing(
    households_path: Path,
    persons_path: Path,
) -> dict[str, Any] | None:
    if households_path.parent.resolve() != persons_path.parent.resolve():
        return None
    manifest_path = households_path.parent / "manifest.json"
    if not manifest_path.is_file():
        return None
    contract = read_linked_population_contract(manifest_path)
    tables = _object(contract.get("tables"))
    households = _object(tables.get("households"))
    persons = _object(tables.get("persons"))
    if (
        households.get("path") != households_path.name
        or persons.get("path") != persons_path.name
    ):
        return None
    licensing = contract.get("licensing")
    return (
        validate_prepared_model_licensing(licensing) if licensing is not None else None
    )


def _object(value: object) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _emit(progress: ProgressReporter | None, stage: str, message: str) -> None:
    if progress is not None:
        progress(WorkflowProgress(stage, message))
