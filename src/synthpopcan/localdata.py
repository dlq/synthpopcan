"""Local data layout checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DataLayoutCheck", "inspect_local_data_layout"]


@dataclass(frozen=True)
class DataLayoutCheck:
    """One local data-layout check returned by :func:`inspect_local_data_layout`.

    The object records a check name, status, human-readable detail, checked
    path, and optional tip for resolving missing or invalid local files.
    """

    name: str
    status: str
    detail: str
    path: Path
    tip: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "path": str(self.path),
            "tip": self.tip,
        }


def inspect_local_data_layout(data_root: Path) -> list[DataLayoutCheck]:
    """Inspect whether expected local data directories and metadata exist.

    The checks are intentionally non-destructive and do not read private source
    data. They are used by the ``data doctor`` command and by scripts that want
    to explain local setup problems before running a workflow.
    """

    raw_root = data_root / "raw"
    checks = [
        _check_directory(
            "Raw data directory",
            raw_root,
            missing_tip="Create data/raw or pass --data-root PATH.",
        ),
        _check_directory(
            "Derived data directory",
            data_root / "derived",
            missing_tip="Create data/derived before writing generated artifacts.",
        ),
        _check_directory(
            "Working data directory",
            data_root / "work",
            missing_tip="Create data/work for disposable builds and experiments.",
        ),
        _check_variable_metadata(
            "2016 hierarchical metadata",
            _metadata_path(data_root, "hierarchical"),
        ),
        _check_variable_metadata(
            "2016 individual metadata",
            _metadata_path(data_root, "individual"),
        ),
        _check_variable_metadata(
            "2021 hierarchical metadata",
            _metadata_path(
                data_root,
                "hierarchical",
                census_year=2021,
            ),
            census_year=2021,
        ),
        _check_variable_metadata(
            "2021 individual metadata",
            _metadata_path(
                data_root,
                "individual",
                census_year=2021,
            ),
            census_year=2021,
        ),
        _check_file(
            "2016 Census Profile tract metadata",
            data_root
            / "raw"
            / "statcan"
            / "census"
            / "2016"
            / "profiles"
            / "ct"
            / "2016-census-profile-ct.json",
            missing_tip="Fetch the canonical 2016 CT Census Profile and manifest.",
        ),
    ]
    return checks


def _metadata_path(
    data_root: Path,
    pumf_kind: str,
    *,
    census_year: int = 2016,
) -> Path:
    return (
        data_root
        / "raw"
        / "statcan"
        / "census"
        / str(census_year)
        / "metadata"
        / "pumf"
        / pumf_kind
        / "variable-labels.json"
    )


def _check_directory(
    name: str, path: Path, *, missing_tip: str = ""
) -> DataLayoutCheck:
    if path.is_dir():
        return DataLayoutCheck(name, "found", "ready", path)
    return DataLayoutCheck(name, "missing", "not found", path, missing_tip)


def _check_file(name: str, path: Path, *, missing_tip: str = "") -> DataLayoutCheck:
    if path.is_file():
        return DataLayoutCheck(name, "found", "available", path)
    return DataLayoutCheck(name, "missing", "not found", path, missing_tip)


def _check_variable_metadata(
    name: str,
    path: Path,
    *,
    census_year: int = 2016,
) -> DataLayoutCheck:
    tip = (
        f"Expected variable-labels.json here. Download the {census_year} PUMF metadata "
        "package or pass --data-root PATH."
    )
    if not path.is_file():
        return DataLayoutCheck(name, "missing", "not found", path, tip)
    try:
        payload: dict[str, Any] = json.loads(path.read_text())
    except json.JSONDecodeError:
        return DataLayoutCheck(name, "problem", "invalid JSON", path, tip)
    count = payload.get("variable_count")
    if isinstance(count, int):
        return DataLayoutCheck(name, "found", f"{count:,} variable labels", path)
    variables = payload.get("variables")
    if isinstance(variables, dict):
        return DataLayoutCheck(
            name, "found", f"{len(variables):,} variable labels", path
        )
    return DataLayoutCheck(name, "problem", "missing variable labels", path, tip)
