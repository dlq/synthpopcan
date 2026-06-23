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
        check_directory(
            "Raw data directory",
            raw_root,
            missing_tip="Create data/raw or pass --data-root PATH.",
        ),
        check_variable_metadata(
            "2016 hierarchical metadata",
            metadata_path(data_root, "statcan-2016-hierarchical-pumf"),
        ),
        check_variable_metadata(
            "2016 individual metadata",
            metadata_path(data_root, "statcan-2016-individual-pumf"),
        ),
        check_file(
            "2016 Census Profile tract metadata",
            data_root
            / "raw"
            / "statscan"
            / "2016-census"
            / "Census Tract Summaries 2016"
            / "98-401-X2016043_eng_CSV"
            / "98-401-X2016043_English_meta.txt",
            missing_tip="Download or copy the 2016 Census Profile metadata file.",
        ),
    ]
    return checks


def metadata_path(data_root: Path, package_name: str) -> Path:
    return (
        data_root
        / "raw"
        / "statscan"
        / "2016-census"
        / "metadata"
        / package_name
        / "variable-labels.json"
    )


def check_directory(name: str, path: Path, *, missing_tip: str = "") -> DataLayoutCheck:
    if path.is_dir():
        return DataLayoutCheck(name, "found", "ready", path)
    return DataLayoutCheck(name, "missing", "not found", path, missing_tip)


def check_file(name: str, path: Path, *, missing_tip: str = "") -> DataLayoutCheck:
    if path.is_file():
        return DataLayoutCheck(name, "found", "available", path)
    return DataLayoutCheck(name, "missing", "not found", path, missing_tip)


def check_variable_metadata(name: str, path: Path) -> DataLayoutCheck:
    tip = (
        "Expected variable-labels.json here. Download the 2016 PUMF metadata "
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
