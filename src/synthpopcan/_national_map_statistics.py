"""Checksum-bound map statistics and caching for completed national plans."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

_NATIONAL_MAP_STATISTIC_FIELDS = (
    "n_households",
    "n_persons",
    "avg_hh_size",
    "median_hh_income",
    "median_shelter_cost",
    "pct_owner",
    "pct_detached",
    "pct_major_repairs",
    "pct_child",
    "pct_senior",
    "pct_immigrant",
    "pct_vismin",
)


def _resolve_plan_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.is_file():
        return path
    for parent in (root, *root.parents):
        candidate = parent / path
        if candidate.is_file():
            return candidate
    return root / path


def _prepare_national_map_statistics(
    *,
    compute_statistics,
    plan_path: Path,
    geography_column: str,
    out_path: Path | None = None,
    jurisdiction_pruids: frozenset[str] | None = None,
) -> dict[str, object]:
    """Aggregate and cache map statistics from national-plan batch artifacts.

    Every selected completed household/person pair is streamed once and tied to
    its recorded checksum. A complete plan is required unless
    ``jurisdiction_pruids`` explicitly selects completed subsets. The returned
    evidence identifies coverage, source artifacts, cache validity, and the
    standard household/person variables available to the map.
    """

    from synthpopcan.statcan import file_integrity

    plan = json.loads(plan_path.read_text())
    if not isinstance(plan, Mapping):
        raise ValueError("national small-area plan must be completed")
    if plan.get("status") != "completed" and jurisdiction_pruids is None:
        raise ValueError("national small-area plan must be completed")
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    root = plan_path.parent
    out_path = out_path or root / "national-map-statistics.csv"
    manifest_path = out_path.with_suffix(".json")
    sources: list[dict[str, object]] = []
    batches: list[tuple[str, str, Path, Path]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("national small-area batch record must be an object")
        if (
            jurisdiction_pruids is not None
            and record.get("jurisdiction_pruid") not in jurisdiction_pruids
        ):
            continue
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            raise ValueError("national small-area batch manifest is invalid")
        batch_path = _resolve_plan_path(root, manifest_value)
        batch = json.loads(batch_path.read_text())
        if not isinstance(batch, Mapping) or batch.get("status") != "completed":
            raise ValueError(
                f"national small-area batch is not completed: {batch_path}"
            )
        result = batch.get("result")
        artifacts = result.get("artifacts") if isinstance(result, Mapping) else None
        if not isinstance(artifacts, Mapping):
            raise ValueError(
                f"national small-area batch artifacts are invalid: {batch_path}"
            )
        paths: dict[str, Path] = {}
        evidence: dict[str, object] = {"batch_id": batch.get("batch_id")}
        for name in ("households", "persons"):
            artifact = artifacts.get(name)
            if not isinstance(artifact, Mapping):
                raise ValueError(
                    f"national batch {name} artifact is invalid: {batch_path}"
                )
            path_value = artifact.get("path")
            if not isinstance(path_value, str):
                raise ValueError(
                    f"national batch {name} artifact is invalid: {batch_path}"
                )
            paths[name] = _resolve_plan_path(root, path_value)
            evidence[name] = {
                key: artifact.get(key) for key in ("path", "byte_size", "sha256")
            }
        jurisdiction = batch.get("jurisdiction")
        abbreviation = (
            str(jurisdiction.get("abbreviation", ""))
            if isinstance(jurisdiction, Mapping)
            else ""
        )
        batch_id = str(batch.get("batch_id", ""))
        batches.append((batch_id, abbreviation, paths["households"], paths["persons"]))
        sources.append(evidence)
    source_digest = hashlib.sha256(
        json.dumps(sources, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    if out_path.is_file() and manifest_path.is_file():
        cached = json.loads(manifest_path.read_text())
        if (
            isinstance(cached, Mapping)
            and cached.get("schema_version") == "synthpopcan-national-map-statistics-v1"
            and cached.get("source_digest") == source_digest
            and cached.get("geography_column") == geography_column
        ):
            artifact = cached.get("artifact")
            integrity = file_integrity(out_path)
            if isinstance(artifact, Mapping) and all(
                artifact.get(key) == integrity[key] for key in ("byte_size", "sha256")
            ):
                return dict(cached)

    rows: dict[str, dict[str, object]] = {}
    for batch_id, jurisdiction, households_path, persons_path in batches:
        statistics_by_geography = compute_statistics(
            households_path,
            geography_column,
            persons_path,
        )
        for identifier, geography_statistics in statistics_by_geography.items():
            if identifier in rows:
                raise ValueError(
                    f"national map geography appears in multiple batches: {identifier}"
                )
            rows[identifier] = {
                geography_column: identifier,
                "jurisdiction": jurisdiction,
                "batch_id": batch_id,
                **geography_statistics,
            }
    if not rows:
        scope = (
            "selected national small-area batches"
            if jurisdiction_pruids
            else "national small-area batches"
        )
        raise ValueError(f"{scope} contain no map geographies")
    fieldnames = [
        geography_column,
        "jurisdiction",
        "batch_id",
        *_NATIONAL_MAP_STATISTIC_FIELDS,
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(f".{out_path.name}.tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for identifier in sorted(rows):
            writer.writerow(rows[identifier])
    temporary.replace(out_path)
    report: dict[str, object] = {
        "schema_version": "synthpopcan-national-map-statistics-v1",
        "source_digest": source_digest,
        "geography_column": geography_column,
        "jurisdiction_pruids": sorted(jurisdiction_pruids or ()),
        "geographies": len(rows),
        "batches": len(batches),
        "artifact": {
            "path": out_path.name,
            **file_integrity(out_path),
        },
    }
    manifest_temporary = manifest_path.with_name(f".{manifest_path.name}.tmp")
    manifest_temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    manifest_temporary.replace(manifest_path)
    return report
