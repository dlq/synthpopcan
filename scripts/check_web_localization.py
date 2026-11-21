"""Validate the draft web catalogues and guard the pilot presentation module."""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
from pathlib import Path

from audit_web_literals import ROOT, inventory_file

WEB = ROOT / "src/synthpopcan/web"
POLICY = ROOT / "scripts/web_localization_policy.json"
REPORT = ROOT / "docs/records/web-localization-coverage.json"
ID = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys at every level instead of silently overwriting."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def placeholders(value: str) -> set[str]:
    """Read the contract's named placeholders and doubled literal braces."""
    names: set[str] = set()
    index = 0
    while index < len(value):
        if value[index : index + 2] in ("{{", "}}"):
            index += 2
        elif value[index] == "{":
            end = value.find("}", index + 1)
            name = value[index + 1 : end]
            if end < 0 or not NAME.fullmatch(name):
                raise ValueError("invalid placeholder")
            names.add(name)
            index = end + 1
        elif value[index] == "}":
            raise ValueError("unbalanced brace")
        else:
            index += 1
    return names


def _validate_provenance(msgid: str, entry: dict, covered: list[str]) -> None:
    provenance = entry.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("kind") != "project"
        or provenance.get("source_id") != msgid
        or provenance.get("review") not in ("draft", "reviewed")
    ):
        raise ValueError(f"invalid provenance: {msgid}")
    if msgid not in covered:
        return
    reviewer = provenance.get("reviewer")
    if (
        provenance.get("review") != "reviewed"
        or not isinstance(reviewer, str)
        or not reviewer.strip()
    ):
        raise ValueError(f"unreviewed covered message: {msgid}")
    try:
        datetime.date.fromisoformat(provenance["reviewed_on"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid review date: {msgid}") from exc


def _validate_entry(
    msgid: str, entry: dict, source: dict, locale: str, covered: list[str]
) -> None:
    if not ID.fullmatch(msgid) or not isinstance(entry, dict):
        raise ValueError(f"invalid message: {msgid}")
    params = entry.get("parameters")
    if not isinstance(params, dict) or any(
        not NAME.fullmatch(name) or kind not in ("text", "number", "date")
        for name, kind in params.items()
    ):
        raise ValueError(f"invalid parameters: {msgid}")
    kind = entry.get("kind")
    if kind == "text":
        forms = {"text": entry.get("value")}
    elif kind == "plural" and params.get(entry.get("count_parameter")) == "number":
        forms = entry.get("forms")
        required = {"one", "other"} | ({"many"} if locale == "fr-CA" else set())
        if not isinstance(forms, dict) or not required <= forms.keys():
            raise ValueError(f"missing plural form: {msgid}")
    else:
        raise ValueError(f"invalid message kind: {msgid}")
    if any(
        not isinstance(value, str)
        or not value.strip()
        or placeholders(value) != set(params)
        for value in forms.values()
    ):
        raise ValueError(f"invalid template: {msgid}")
    if not source or any(
        entry.get(key) != source.get(key)
        for key in ("kind", "parameters", "count_parameter")
    ):
        raise ValueError(f"catalogue parity mismatch: {msgid}")
    _validate_provenance(msgid, entry, covered)


def validate_catalogues(catalogues: dict, covered: list[str]) -> None:
    """Fail on malformed or inconsistent entries, including declared coverage."""
    if len(covered) != len(set(covered)):
        raise ValueError("duplicate covered ID")
    english = catalogues["en-CA"]
    for locale in ("en-CA", "fr-CA"):
        cat = catalogues[locale]
        if (
            (cat.get("schema_version"), cat.get("locale"))
            != ("synthpopcan-web-messages-v1", locale)
            or not isinstance(cat.get("revision"), str)
            or not cat["revision"]
        ):
            raise ValueError(f"invalid catalogue header: {locale}")
        if cat["revision"] != english["revision"] or not isinstance(
            cat.get("messages"), dict
        ):
            raise ValueError(f"revision or messages mismatch: {locale}")
        for msgid, entry in cat["messages"].items():
            _validate_entry(
                msgid, entry, english["messages"].get(msgid), locale, covered
            )
        for msgid in covered:
            if msgid not in cat["messages"]:
                raise ValueError(f"missing covered message: {msgid}")


def guard_literals(entries: list[dict], approved: dict[str, int]) -> None:
    """Require review of every changed string expression in the covered adapter."""
    current = collections.Counter(entry["source"] for entry in entries)
    if current != collections.Counter(approved):
        raise ValueError(
            f"presentation adapter literals changed: {dict(current - collections.Counter(approved))}; update the catalogue or review the allowlist"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    def load(path: Path) -> dict:
        return json.loads(path.read_text(), object_pairs_hook=unique_object)

    policy = load(POLICY)
    catalogues = {loc: load(WEB / f"messages.{loc}.json") for loc in ("en-CA", "fr-CA")}
    validate_catalogues(catalogues, policy["covered_ids"])
    path = WEB / "localization-ui.mjs"
    guard_literals(
        inventory_file(path, ROOT / "node_modules/.bin/biome")["entries"],
        policy["approved_adapter_literals"],
    )
    ids = sorted(catalogues["en-CA"]["messages"])
    report = {
        "revision": catalogues["en-CA"]["revision"],
        "guarded_literal_module": "src/synthpopcan/web/localization-ui.mjs",
        "covered_ids": sorted(policy["covered_ids"]),
        "draft_ids": sorted(set(ids) - set(policy["covered_ids"])),
        "counts": {
            "covered_messages": len(policy["covered_ids"]),
            "draft_messages": len(set(ids) - set(policy["covered_ids"])),
            "untranslated_surface_groups": 4,
        },
        "untranslated_surfaces": [
            "web HTML outside the shared shell and language selector",
            "web workflows outside the shared run list",
            "unknown and parameterized server messages",
            "generated reports and maps",
        ],
        "note": "Draft translations are a preview and are not reviewed coverage.",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write_report:
        REPORT.write_text(text)
    elif not REPORT.is_file() or REPORT.read_text() != text:
        raise SystemExit(
            "Web localization coverage report is stale; rerun with --write-report."
        )
    print("Web localization catalogue and scoped literal guard passed.")


if __name__ == "__main__":
    main()
