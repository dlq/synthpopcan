"""File-backed small-area synthesis workflow shared by local adapters."""

from __future__ import annotations

__all__ = ["SmallAreaRequest", "SmallAreaWorkflowResult", "synthesize_small_area_files"]

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.map_render import render_synthesis_map
from synthpopcan.small_area_controls import write_recoded_candidates
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
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

    package_path: Path
    controls_path: Path
    candidates_dir: Path
    output_dir: Path
    candidate_households: int
    geography_dimension: str
    geography_column: str
    conditions: dict[str, str]
    person_controls_path: Path | None = None
    package_reference: str | None = None
    random_seed: int | None = None
    pool_size: int | None = None
    subsample_seed: int = 42
    max_household_size: int | None = None
    household_size_group_column: str = "household_size_group"
    include_weights: bool = False
    chunk_size: int = 1000
    boundaries_path: Path | None = None
    map_path: Path | None = None
    geography_id_field: str = "geo_id"
    map_title: str = "Synthetic Population"

    def reproduction(self) -> WorkflowReproduction:
        reference = self.package_reference or str(self.package_path)
        arguments = [
            "geo",
            "synthesize",
            reference,
            "--households",
            str(self.candidate_households),
            "--controls",
            str(self.controls_path),
            "--geo-dimension",
            self.geography_dimension,
            "--geo-column",
            self.geography_column,
            "--out",
            str(self.output_dir),
            "--subsample-seed",
            str(self.subsample_seed),
        ]
        if self.person_controls_path is not None:
            arguments.extend(("--person-controls", str(self.person_controls_path)))
        if self.random_seed is not None:
            arguments.extend(("--random-seed", str(self.random_seed)))
        if self.pool_size is not None:
            arguments.extend(("--pool-size", str(self.pool_size)))
        if self.max_household_size is not None:
            arguments.extend(("--max-household-size", str(self.max_household_size)))
            arguments.extend(
                ("--household-size-group-column", self.household_size_group_column)
            )
        if self.include_weights:
            arguments.append("--include-weights")
        return WorkflowReproduction(
            request={
                "workflow": "small_area",
                "inputs": {
                    "package": reference,
                    "controls": str(self.controls_path),
                    "person_controls": (
                        str(self.person_controls_path)
                        if self.person_controls_path is not None
                        else None
                    ),
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
                },
            },
            command=ReproductionCommand("synthpopcan", tuple(arguments)),
        )


@dataclass(frozen=True)
class SmallAreaWorkflowResult:
    """Small-area artifacts and calibration diagnostics."""

    households_path: Path
    persons_path: Path
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
        ),
        progress=progress,
    )
    candidate_households = generated.households_path
    if request.max_household_size is not None:
        _emit(progress, "recoding", "Grouping candidate household sizes")
        candidate_households = request.candidates_dir / "households-recoded.csv"
        write_recoded_candidates(
            generated.households_path,
            candidate_households,
            hhsize_col=str(generated.report["household_size_column"]),
            group_col=request.household_size_group_column,
            cap=request.max_household_size,
        )

    households_path = request.output_dir / "households.csv"
    persons_path = request.output_dir / "persons.csv"
    report_path = request.output_dir / "report.json"
    weights_path = (
        request.output_dir / "weights.csv" if request.include_weights else None
    )
    _emit(progress, "calibrating", "Fitting candidates to small-area controls")
    details = calibrate_linked_household_csvs(
        households_path=candidate_households,
        persons_path=generated.persons_path,
        controls_path=request.controls_path,
        person_controls_path=request.person_controls_path,
        geography_dimension=request.geography_dimension,
        geography_column=request.geography_column,
        households_out=households_path,
        persons_out=persons_path,
        report_out=report_path,
        weights_out=weights_path,
        pool_size=request.pool_size,
        subsample_seed=request.subsample_seed,
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
        report_path=report_path,
        weights_path=weights_path,
        map_path=map_path,
        details=details,
        reproduction=request.reproduction(),
    )


def _emit(progress: ProgressReporter | None, stage: str, message: str) -> None:
    if progress is not None:
        progress(WorkflowProgress(stage, message))
