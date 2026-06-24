"""Shared terminal rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

__all__ = [
    "format_display_value",
    "format_field_label",
    "format_status",
    "print_checks_table",
    "print_success",
    "print_summary_table",
    "print_table",
    "print_wrote",
]


def print_summary_table(
    payload: dict[str, object], *, title: str | None = None
) -> None:
    """Render a two-column Rich table for compact dictionary summaries."""

    table = Table(title=title)
    table.add_column("Field")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(format_field_label(key), format_display_value(value))
    Console().print(table)


def print_table(table: Table) -> None:
    """Print a prebuilt Rich table with the project console defaults."""

    Console().print(table)


def print_checks_table(rows: list[dict[str, str]], *, title: str) -> None:
    """Render data-doctor style checks with status, detail, and tip columns."""

    table = Table(title=title)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Tip")
    for row in rows:
        table.add_row(
            row.get("name", ""),
            format_status(row.get("status", "")),
            row.get("detail", ""),
            row.get("tip", ""),
        )
    Console().print(table)


def print_success(message: str) -> None:
    """Print a short success/status line to stderr in green."""

    Console(stderr=True, soft_wrap=True).print(message, style="green")


def print_wrote(path: Path) -> None:
    """Print the standard message used after writing a file."""

    print_success(f"Wrote {path}")


def format_display_value(value: object) -> str:
    """Format scalar and JSON-like values for terminal summary tables."""

    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if value is None:
        return ""
    return str(value)


def format_field_label(value: str) -> str:
    """Convert an internal snake_case field name to a readable table label."""

    acronyms = {
        "csv": "CSV",
        "id": "ID",
        "ipf": "IPF",
        "json": "JSON",
        "pumf": "PUMF",
        "url": "URL",
        "wds": "WDS",
    }
    labels: list[str] = []
    for index, word in enumerate(value.split("_")):
        lower_word = word.lower()
        if lower_word in acronyms:
            labels.append(acronyms[lower_word])
        elif index == 0:
            labels.append(word.capitalize())
        else:
            labels.append(lower_word)
    return " ".join(labels)


def format_status(value: str) -> str:
    """Normalize machine-readable check statuses for terminal display."""

    if value == "found":
        return "Found"
    if value == "missing":
        return "Missing"
    if value == "problem":
        return "Problem"
    return format_field_label(value)
