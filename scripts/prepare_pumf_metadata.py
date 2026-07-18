"""Extract public-safe variable metadata from a StatCan PUMF SPSS program."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path


def parse_spss_metadata(text: str) -> dict[str, dict[str, object]]:
    """Parse fixed-width positions and labels without reading microdata rows."""

    widths = _parse_fixed_widths(text)
    labels = _parse_variable_labels(text)
    names = tuple(dict.fromkeys((*widths, *labels)))
    return {
        name: {
            **({"fixed_width": widths[name]} if name in widths else {}),
            **({"label": labels[name]} if name in labels else {}),
        }
        for name in names
    }


def _parse_fixed_widths(text: str) -> dict[str, dict[str, int]]:
    section = _section(text, "DATA LIST FILE=DATA/", "FORMATS")
    output: dict[str, dict[str, int]] = {}
    for name, start_text, end_text in re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s+(\d+)(?:-(\d+))?",
        section,
    ):
        start = int(start_text)
        end = int(end_text or start_text)
        output[name] = {"start": start, "end": end, "width": end - start + 1}
    return output


def _parse_variable_labels(text: str) -> dict[str, str]:
    section = _section(text, "VARIABLE LABELS", "VALUE LABELS")
    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in section.splitlines():
        match = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s+('.*)", line)
        if match:
            current = match.group(1)
            entries[current] = [match.group(2)]
        elif current is not None and re.match(r"\s+'", line):
            entries[current].append(line.strip())
    output: dict[str, str] = {}
    for name, fragments in entries.items():
        quoted = re.findall(r"'((?:[^']|'')*)'", " ".join(fragments))
        output[name] = "".join(part.replace("''", "'") for part in quoted)
    return output


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise ValueError(f"SPSS metadata is missing {start_marker!r}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise ValueError(f"SPSS metadata is missing {end_marker!r}")
    return text[start + len(start_marker) : end]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-format", required=True)
    parser.add_argument("--census-year", required=True, type=int)
    args = parser.parse_args()

    variables = parse_spss_metadata(
        args.source.read_text(encoding="utf-8-sig", errors="replace")
    )
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_file": str(args.source),
        "source_format": args.source_format,
        "census_year": args.census_year,
        "variable_count": len(variables),
        "variables": variables,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
