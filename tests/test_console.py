from __future__ import annotations

from pathlib import Path

from synthpopcan.console import (
    format_display_value,
    format_field_label,
    format_status,
    print_success,
    print_wrote,
)


def test_console_display_formatters_cover_common_value_types() -> None:
    assert format_display_value(True) == "True"
    assert format_display_value(1200) == "1,200"
    assert format_display_value(1.25) == "1.25"
    assert format_display_value({"a": 1}) == '{"a": 1}'
    assert format_display_value([1, 2]) == "[1, 2]"
    assert format_display_value(None) == ""
    assert format_display_value("plain") == "plain"


def test_console_status_formatter_uses_readable_labels() -> None:
    assert format_status("found") == "Found"
    assert format_status("missing") == "Missing"
    assert format_status("problem") == "Problem"
    assert format_status("needs_review") == "Needs review"


def test_console_field_label_formatter_keeps_common_acronyms() -> None:
    assert format_field_label("csv_member") == "CSV member"
    assert format_field_label("product_id") == "Product ID"
    assert format_field_label("ipf_hint") == "IPF hint"


def test_console_success_helpers_write_to_stderr(capsys) -> None:
    print_success("Done")
    print_wrote(Path("output.csv"))

    captured = capsys.readouterr()
    assert "Done" in captured.err
    assert "Wrote output.csv" in captured.err
