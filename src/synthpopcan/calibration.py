"""Advisory helpers for choosing IPF calibration controls."""

from __future__ import annotations

from typing import Any

__all__ = ["build_control_suggestion_report"]

from collections.abc import Iterable, Sequence

_HOUSEHOLD_CONTROL_CATALOG = (
    {
        "canonical": "household_size",
        "aliases": ("household_size", "hhsize", "hhsz", "hh_size"),
        "search": "household size",
        "role": "household structure",
        "reason": (
            "Useful for calibrating generated household counts and person linkage."
        ),
    },
    {
        "canonical": "tenure",
        "aliases": ("tenure", "TENUR"),
        "search": "tenure",
        "role": "housing",
        "reason": (
            "Common household/dwelling control and often present in census outputs."
        ),
    },
    {
        "canonical": "dwelling_type",
        "aliases": ("dwelling_type", "DTYPE", "structural_type"),
        "search": "dwelling type",
        "role": "housing",
        "reason": "Useful when the model output includes dwelling structure.",
    },
    {
        "canonical": "rooms",
        "aliases": ("rooms", "ROOMS"),
        "search": "rooms",
        "role": "housing",
        "reason": (
            "Candidate housing-quality control; review category definitions first."
        ),
    },
)

_PERSON_CONTROL_CATALOG = (
    {
        "canonical": "age_group",
        "aliases": ("age_group", "AGEGRP", "age", "agegrp"),
        "search": "age sex",
        "role": "demographics",
        "reason": "Age is a core person-level calibration dimension.",
    },
    {
        "canonical": "sex",
        "aliases": ("sex", "SEX"),
        "search": "age sex",
        "role": "demographics",
        "reason": "Sex is a core person-level calibration dimension.",
    },
    {
        "canonical": "marital_status",
        "aliases": ("marital_status", "MARSTH", "marital"),
        "search": "marital status",
        "role": "demographics",
        "reason": "Useful if the generated person rows include compatible categories.",
    },
    {
        "canonical": "immigration_status",
        "aliases": ("immigration_status", "IMMSTAT", "immigrant_status"),
        "search": "immigration status",
        "role": "demographics",
        "reason": "Useful when present, but often needs careful category review.",
    },
)

_GEOGRAPHY_ALIASES = ("geo", "GEO", "PR", "CMA", "CD", "CSD", "CT")


def build_control_suggestion_report(
    rows: Sequence[dict[str, str]], *, unit: str = "auto", seed_path: str | None = None
) -> dict[str, Any]:
    """Suggest calibration-control directions from seed/generated columns."""
    if not rows:
        raise ValueError("control suggestions require at least one seed row")
    available_columns = list(rows[0].keys())
    selected_unit = _infer_unit(available_columns) if unit == "auto" else unit
    if selected_unit not in {"household", "person"}:
        raise ValueError("unit must be household, person, or auto")

    catalog = (
        _HOUSEHOLD_CONTROL_CATALOG
        if selected_unit == "household"
        else _PERSON_CONTROL_CATALOG
    )
    usable_controls, enrichment_candidates = _classify_controls(
        available_columns, catalog
    )
    geography_columns = [
        column for column in available_columns if column in _GEOGRAPHY_ALIASES
    ]
    first_search = _first_search_query(usable_controls, selected_unit)
    next_commands = [
        f"synthpopcan statcan wds search {first_search}",
        "synthpopcan statcan wds explain PRODUCT_ID",
        (
            "synthpopcan ipf check-inputs --seed "
            f"{seed_path or 'seed.csv'} --controls controls.csv"
        ),
    ]

    return {
        "schema_version": "synthpopcan-ipf-control-suggestions-v1",
        "unit": selected_unit,
        "seed_path": seed_path,
        "seed_records": len(rows),
        "available_columns": available_columns,
        "geography_columns": geography_columns,
        "usable_controls": usable_controls,
        "enrichment_candidates": enrichment_candidates,
        "review_notes": _build_review_notes(
            selected_unit, usable_controls, geography_columns
        ),
        "next_commands": next_commands,
    }


def _classify_controls(
    columns: Sequence[str], catalog: Iterable[dict[str, Any]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    usable: list[dict[str, str]] = []
    enrichment: list[dict[str, str]] = []
    for item in catalog:
        match = _matching_column(columns, item["aliases"])  # type: ignore[arg-type]
        suggestion = {
            "column": match or str(item["canonical"]),
            "canonical": str(item["canonical"]),
            "role": str(item["role"]),
            "statcan_search": str(item["search"]),
            "reason": str(item["reason"]),
        }
        if match:
            suggestion["status"] = "usable_if_categories_match"
            usable.append(suggestion)
        else:
            suggestion["status"] = "needs_enrichment_or_modeling"
            enrichment.append(suggestion)
    return usable, enrichment


def _matching_column(columns: Sequence[str], aliases: object) -> str | None:
    if not isinstance(aliases, tuple):
        return None
    lower_lookup = {column.lower(): column for column in columns}
    for alias in aliases:
        alias_text = str(alias)
        if alias_text in columns:
            return alias_text
        match = lower_lookup.get(alias_text.lower())
        if match:
            return match
    return None


def _infer_unit(columns: Sequence[str]) -> str:
    lower_columns = {column.lower() for column in columns}
    if (
        "synthetic_person_id" in lower_columns
        or {"age_group", "agegrp", "sex"} & lower_columns
    ):
        return "person"
    return "household"


def _first_search_query(usable_controls: list[dict[str, str]], unit: str) -> str:
    if usable_controls:
        return usable_controls[0]["statcan_search"]
    return f"{unit} totals"


def _build_review_notes(
    unit: str,
    usable_controls: list[dict[str, str]],
    geography_columns: list[str],
) -> list[str]:
    notes = [
        "Use only controls whose categories can be mapped cleanly to generated rows.",
        "Prefer a small set of important controls before adding detailed cross-tabs.",
    ]
    if not geography_columns:
        notes.append(
            "No obvious geography column was found; check that controls match "
            "the model scope."
        )
    if unit == "household":
        notes.append("Use household or dwelling margins for household rows.")
    else:
        notes.append("Use person margins for person rows; preserve household linkage.")
    if not usable_controls:
        notes.append(
            "No common calibration columns were found; add attributes before IPF."
        )
    return notes
