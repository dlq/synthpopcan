"""Bounded public evidence preparation for the Québec 2021 DA workflow."""

from __future__ import annotations

__all__ = [
    "finalize_quebec_da_proof",
    "prepare_quebec_da_proof",
    "select_quebec_da_relationships",
]

import csv
import hashlib
import json
import time
from collections.abc import Mapping
from pathlib import Path

from synthpopcan.geography import (
    GeographyRelationship,
    statcan_geography_identity,
    statcan_geography_universe,
)
from synthpopcan.map_render import filter_boundaries_geojson
from synthpopcan.small_area_controls import (
    extract_controls_from_profile,
    scale_and_validate_controls,
    write_controls_csv,
)
from synthpopcan.tree import validate_linked_population_files

_DGRF_PRODUCT = "Statistics Canada 2021 DGRF, catalogue 98-26-0004"
_DGRF_FINAL_RELEASE = "2022-02-09"
_QUEBEC_PR_DGUID = "2021A000224"
_DEFAULT_METRO_CSD = "2466023"  # Montréal
_DEFAULT_RURAL_CSD = "2479088"  # bounded non-CMA/CA comparison with full controls


def select_quebec_da_relationships(
    relationship_path: Path,
    *,
    per_area: int = 4,
    metro_csd: str = _DEFAULT_METRO_CSD,
    rural_csd: str = _DEFAULT_RURAL_CSD,
) -> dict[str, object]:
    """Select deterministic metro and non-CMA/CA DAs from the final 2021 DGRF."""

    if per_area < 1:
        raise ValueError("per_area must be at least 1")
    resource_sha256 = _sha256(relationship_path)
    by_da: dict[str, tuple[str, str, str]] = {}
    conflicting: set[str] = set()
    with relationship_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "PRDGUID_PRIDUGD",
            "CSDDGUID_SDRIDUGD",
            "DADGUID_ADIDUGD",
            "CMADGUID_RMRIDUGD",
        }
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ValueError("DGRF is missing required columns: " + ", ".join(missing))
        for row in reader:
            if row["PRDGUID_PRIDUGD"] != _QUEBEC_PR_DGUID:
                continue
            da_dguid = row["DADGUID_ADIDUGD"].strip()
            csd_dguid = row["CSDDGUID_SDRIDUGD"].strip()
            if not da_dguid or not csd_dguid:
                continue
            da_id = _short_id(da_dguid, 8, "DA")
            relationship = (
                _short_id(csd_dguid, 7, "CSD"),
                csd_dguid,
                row["CMADGUID_RMRIDUGD"].strip(),
            )
            previous = by_da.setdefault(da_id, relationship)
            if previous != relationship:
                conflicting.add(da_id)
    if conflicting:
        raise ValueError(
            "DGRF contains conflicting DA relationships: "
            + ", ".join(sorted(conflicting)[:10])
        )

    metro_ids = sorted(
        da_id
        for da_id, (csd_id, _csd_dguid, cma_dguid) in by_da.items()
        if csd_id == metro_csd and cma_dguid
    )[:per_area]
    rural_ids = sorted(
        da_id
        for da_id, (csd_id, _csd_dguid, cma_dguid) in by_da.items()
        if csd_id == rural_csd and not cma_dguid
    )[:per_area]
    if len(metro_ids) != per_area:
        raise ValueError(f"metro CSD {metro_csd} has too few eligible DAs")
    if len(rural_ids) != per_area:
        raise ValueError(f"rural CSD {rural_csd} has too few eligible DAs")

    relationships: list[dict[str, object]] = []
    for study_area, identifiers in (
        ("metropolitan", metro_ids),
        ("rural-non-cma-ca", rural_ids),
    ):
        for da_id in identifiers:
            csd_id, csd_dguid, _ = by_da[da_id]
            relationships.append(
                {
                    "study_area": study_area,
                    "relationship": GeographyRelationship(
                        child=statcan_geography_identity(
                            2021,
                            "da",
                            da_id,
                            dguid=f"2021S0512{da_id}",
                        ),
                        parent=statcan_geography_identity(
                            2021,
                            "csd",
                            csd_id,
                            dguid=csd_dguid,
                        ),
                        authoritative_product=_DGRF_PRODUCT,
                        release_date=_DGRF_FINAL_RELEASE,
                        resource_sha256=resource_sha256,
                    ).as_dict(),
                }
            )
    return {
        "schema_version": "synthpopcan-quebec-da-selection-v1",
        "census_vintage": 2021,
        "province_dguid": _QUEBEC_PR_DGUID,
        "metropolitan_parent_csd": metro_csd,
        "rural_parent_csd": rural_csd,
        "per_area": per_area,
        "relationships": relationships,
    }


def prepare_quebec_da_proof(
    profile_path: Path,
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    *,
    target_households: int = 800,
    per_area: int = 4,
    metro_csd: str = _DEFAULT_METRO_CSD,
    rural_csd: str = _DEFAULT_RURAL_CSD,
) -> dict[str, object]:
    """Prepare bounded controls, boundaries, relationships, and review evidence.

    Every retained input and output is hashed for reproducibility.
    """

    started = time.perf_counter()
    selection = select_quebec_da_relationships(
        relationship_path,
        per_area=per_area,
        metro_csd=metro_csd,
        rural_csd=rural_csd,
    )
    identifiers = _selected_identifiers(selection)
    raw_controls = extract_controls_from_profile(
        profile_path,
        "da",
        geo_ids=identifiers,
    )
    scaled_controls, dropped = scale_and_validate_controls(
        raw_controls,
        target_households,
    )
    missing_controls = sorted(identifiers - set(raw_controls))
    if missing_controls or dropped:
        raise ValueError(
            "selected DAs lack complete profile controls: "
            + ", ".join(sorted(set(missing_controls) | set(dropped)))
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    controls_path = output_directory / "controls.csv"
    boundaries_path = output_directory / "boundaries.geojson"
    relationships_path = output_directory / "relationships.json"
    write_controls_csv(
        scaled_controls,
        controls_path,
        "da",
        household_size_column="household_size_group",
    )
    boundary_report = filter_boundaries_geojson(
        boundary_path,
        boundaries_path,
        identifiers,
    )
    if boundary_report["missing_identifiers"]:
        missing = boundary_report["missing_identifiers"]
        if not isinstance(missing, list):
            missing = []
        raise ValueError(
            "selected DAs are missing boundaries: "
            + ", ".join(str(value) for value in missing)
        )
    _write_json(relationships_path, selection)

    inputs = {
        "census_profile": _file_evidence(profile_path),
        "boundary_geojson": _file_evidence(boundary_path),
        "dgrf": _file_evidence(relationship_path),
    }
    outputs = {
        "controls": _file_evidence(controls_path, relative=True),
        "boundaries": _file_evidence(boundaries_path, relative=True),
        "relationships": _file_evidence(relationships_path, relative=True),
    }
    manifest: dict[str, object] = {
        "schema_version": "synthpopcan-quebec-da-proof-v1",
        "status": "prepared",
        "geography": statcan_geography_universe(
            2021,
            "da",
            "DAUID",
            dguid_column="DGUID",
        ).as_dict(),
        "selection": selection,
        "inputs": inputs,
        "outputs": outputs,
        "controls": {
            "target_households": target_households,
            "selected_geographies": len(identifiers),
            "dropped_geographies": dropped,
            "margins": ["household_size_group", "TENUR"],
        },
        "boundaries": boundary_report,
        "resource_evidence": {
            "preparation_seconds": time.perf_counter() - started,
            "full_boundary_bytes": boundary_path.stat().st_size,
            "bounded_boundary_bytes": boundaries_path.stat().st_size,
        },
        "next_step": (
            "Run `synthpopcan geo synthesize quebec-2021-all-fields` with "
            "controls.csv, geography dimension `da`, Census vintage 2021, "
            "level `da`, namespace `statcan:census:2021:da`, and a fixed seed."
        ),
        "limitations": [
            "This is a bounded metro/rural workflow proof, not a Québec-wide fit.",
            "DA-level Census controls may be suppressed, rounded, or sparse.",
            "A successful preparation is not evidence of synthesis correctness; "
            "the linked output, residuals, and map must still be validated.",
        ],
    }
    _write_json(output_directory / "proof-manifest.json", manifest)
    return manifest


def finalize_quebec_da_proof(
    output_directory: Path,
    *,
    population_directory: Path | None = None,
    synthesis_seconds: float | None = None,
) -> dict[str, object]:
    """Validate generated proof artifacts and promote the manifest to complete."""

    manifest_path = output_directory / "proof-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != "synthpopcan-quebec-da-proof-v1":
        raise ValueError("unsupported Québec DA proof manifest")
    population = population_directory or output_directory / "population"
    households_path = population / "households.csv"
    persons_path = population / "persons.csv"
    report_path = population / "report.json"
    map_path = population / "map.html"
    linked_validation = validate_linked_population_files(
        households_path,
        persons_path,
    )
    if not linked_validation["passed"]:
        raise ValueError("linked population validation failed")
    report = _read_json(report_path)
    selected = _selected_identifiers(_mapping_value(manifest, "selection"))
    observed = _csv_identifiers(households_path, "DAUID")
    if observed != selected:
        raise ValueError(
            "generated population geography identifiers do not match the proof "
            "selection"
        )
    geography = _mapping_value(report, "geography_universe")
    if (
        geography.get("census_vintage"),
        geography.get("geography_level"),
        geography.get("identifier_namespace"),
    ) != (2021, "da", "statcan:census:2021:da"):
        raise ValueError("generated report has incompatible geography identity")
    summary = _mapping_value(report, "summary")
    if summary.get("non_converged_count") != 0:
        raise ValueError("one or more proof geographies did not converge")
    if not map_path.is_file():
        raise ValueError("bounded proof map is missing")
    if '"identifier_namespace":"statcan:census:2021:da"' not in map_path.read_text():
        raise ValueError("bounded proof map is missing its geography identity")

    parent_summary = _parent_summary(
        _mapping_value(manifest, "selection"),
        _mapping_value(report, "geographies"),
    )
    evidence = {
        "linked_validation": linked_validation,
        "geography_identifiers": {
            "selected": len(selected),
            "observed": len(observed),
            "unknown": [],
            "missing": [],
        },
        "calibration": {
            "mode": report.get("calibration_mode"),
            "converged_geographies": summary.get("converged_count"),
            "non_converged_geographies": summary.get("non_converged_geographies"),
            "fractional_max_abs_error": summary.get("max_abs_error"),
            "realized_max_abs_error": summary.get("realized_max_abs_error"),
            "input_checks": report.get("input_checks"),
            "parent_summary": parent_summary,
        },
        "artifacts": {
            "households": _relative_file_evidence(households_path, output_directory),
            "persons": _relative_file_evidence(persons_path, output_directory),
            "report": _relative_file_evidence(report_path, output_directory),
            "map": _relative_file_evidence(map_path, output_directory),
        },
        "resource_evidence": {
            "synthesis_seconds": synthesis_seconds,
            "map_bytes": map_path.stat().st_size,
        },
    }
    manifest["status"] = "completed"
    manifest["synthesis_evidence"] = evidence
    manifest["next_step"] = (
        "Review the recorded realized residuals and limitations before using "
        "this bounded workflow as evidence for a research application."
    )
    _write_json(manifest_path, manifest)
    return manifest


def _selected_identifiers(selection: Mapping[str, object]) -> set[str]:
    values = selection.get("relationships")
    if not isinstance(values, list):
        raise ValueError("selection relationships must be a list")
    identifiers: set[str] = set()
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("selection relationship must be an object")
        relationship = value.get("relationship")
        if not isinstance(relationship, Mapping):
            raise ValueError("selection relationship record must be an object")
        child = relationship.get("child")
        if not isinstance(child, Mapping) or not isinstance(
            child.get("identifier"), str
        ):
            raise ValueError("selection relationship child is invalid")
        identifiers.add(child["identifier"])
    return identifiers


def _short_id(dguid: str, length: int, label: str) -> str:
    identifier = dguid[-length:]
    if len(identifier) != length or not identifier.isdigit():
        raise ValueError(f"invalid {label} DGUID: {dguid!r}")
    return identifier


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _file_evidence(path: Path, *, relative: bool = False) -> dict[str, object]:
    return {
        "path": path.name if relative else str(path),
        "sha256": _sha256(path),
        "byte_size": path.stat().st_size,
    }


def _relative_file_evidence(path: Path, root: Path) -> dict[str, object]:
    evidence = _file_evidence(path)
    evidence["path"] = str(path.relative_to(root))
    return evidence


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _mapping_value(
    payload: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _csv_identifiers(path: Path, column: str) -> set[str]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if column not in (reader.fieldnames or ()):
            raise ValueError(f"{path} is missing {column}")
        return {row[column] for row in reader if row.get(column)}


def _parent_summary(
    selection: Mapping[str, object],
    geographies: Mapping[str, object],
) -> list[dict[str, object]]:
    relationships = selection.get("relationships")
    if not isinstance(relationships, list):
        raise ValueError("selection relationships must be a list")
    parents: dict[tuple[str, str], list[str]] = {}
    for item in relationships:
        if not isinstance(item, Mapping):
            raise ValueError("selection relationship must be an object")
        study_area = item.get("study_area")
        relationship = item.get("relationship")
        if not isinstance(study_area, str) or not isinstance(relationship, Mapping):
            raise ValueError("selection relationship is invalid")
        parent = relationship.get("parent")
        child = relationship.get("child")
        if not isinstance(parent, Mapping) or not isinstance(child, Mapping):
            raise ValueError("selection relationship identities are invalid")
        parent_id = parent.get("identifier")
        child_id = child.get("identifier")
        if not isinstance(parent_id, str) or not isinstance(child_id, str):
            raise ValueError("selection relationship identifiers are invalid")
        parents.setdefault((study_area, parent_id), []).append(child_id)
    result: list[dict[str, object]] = []
    for (study_area, parent_id), child_ids in sorted(parents.items()):
        assigned = 0
        realized_max = 0.0
        for child_id in child_ids:
            geography = geographies.get(child_id)
            if not isinstance(geography, Mapping):
                raise ValueError(f"report is missing selected DA {child_id}")
            assigned_value = geography.get("assigned_households")
            if not isinstance(assigned_value, int):
                raise ValueError("assigned_households must be an integer")
            assigned += assigned_value
            summaries = geography.get("realized_margin_summaries")
            if not isinstance(summaries, list):
                raise ValueError("realized margin summaries must be a list")
            for margin in summaries:
                if isinstance(margin, Mapping) and isinstance(
                    margin.get("max_abs_error"), int | float
                ):
                    realized_max = max(
                        realized_max,
                        float(margin["max_abs_error"]),
                    )
        result.append(
            {
                "study_area": study_area,
                "parent_csd": parent_id,
                "dissemination_areas": len(child_ids),
                "assigned_households": assigned,
                "realized_max_abs_error": realized_max,
            }
        )
    return result


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
