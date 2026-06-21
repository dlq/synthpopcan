"""Shared terminal rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table


def print_summary_table(
    payload: dict[str, object], *, title: str | None = None
) -> None:
    table = Table(title=title)
    table.add_column("Field")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(format_field_label(key), format_display_value(value))
    Console().print(table)


def print_table(table: Table) -> None:
    Console().print(table)


def print_checks_table(rows: list[dict[str, str]], *, title: str) -> None:
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
    Console(stderr=True, soft_wrap=True).print(message, style="green")


def print_wrote(path: Path) -> None:
    print_success(f"Wrote {path}")


def format_display_value(value: object) -> str:
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
    return value.replace("_", " ").capitalize()


def format_status(value: str) -> str:
    if value == "found":
        return "Found"
    if value == "missing":
        return "Missing"
    if value == "problem":
        return "Problem"
    return format_field_label(value)
