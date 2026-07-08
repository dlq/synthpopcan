"""Small shared helpers for tabular string data.

These utilities are dependency-free so any core, API, or CLI module can import
them without creating an import cycle.
"""

from __future__ import annotations

__all__ = ["format_csv_number", "validate_columns"]


def format_csv_number(value: float) -> str:
    """Format a number for CSV output as a whole number when it is integral.

    Values within a small tolerance of an integer are written without a decimal
    point; other values use compact general formatting. Using a tolerance rather
    than :meth:`float.is_integer` keeps floating-point noise from
    integerization and IPF (for example ``2.9999999998``) from leaking decimals
    into otherwise-integer output.
    """

    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(rounded)
    return f"{value:.12g}"


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    """Raise ``ValueError`` if any *required* column is missing from *columns*."""

    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
