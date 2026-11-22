"""Catalogue gate rejects changed coverage and unsafe presentation literals."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from synthpopcan._web_error_messages import (
    _RESTART_MESSAGES,
    conditional_message,
    restart_message,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "check_web_localization", ROOT / "scripts/check_web_localization.py"
)
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


@pytest.fixture
def catalogues():
    web = ROOT / "src/synthpopcan/web"
    return {
        locale: json.loads((web / f"messages.{locale}.json").read_text())
        for locale in ("en-CA", "fr-CA")
    }


def test_small_area_fixed_server_errors_have_exact_presentation_mappings():
    adapter = (ROOT / "src/synthpopcan/web/localization-ui.mjs").read_text()
    markers = (
        "matching Statistics Canada CT geography",
        "requires broad pack",
        "requires its matching source upload",
        "require person controls and an explicit Census geography",
        "Census Profile tract CSV or ZIP",
        "private-household denominators",
        "rounding envelope",
        "suppressed",
        "duplicate",
        "missing",
        "unavailable or invalid",
        "not base-five",
        "Unknown ",
        "conditional and person geographies differ",
        "under-15",
        "eligible category targets must sum",
        "unsupported eligible",
        "unknown age eligibility",
        "unrecognized internal problem",
    )
    conditional = {conditional_message(ValueError(marker)) for marker in markers}
    for message in conditional:
        # Preflight, durable-run creation and restart use distinct endpoint keys.
        assert adapter.count(json.dumps(message, ensure_ascii=False)) == 3
    for message in (*_RESTART_MESSAGES, restart_message(ValueError("unknown"))):
        assert json.dumps(message, ensure_ascii=False) in adapter


def test_preview_is_valid_but_cannot_claim_unreviewed_coverage(catalogues):
    check.validate_catalogues(catalogues, [])
    with pytest.raises(ValueError, match="unreviewed covered"):
        check.validate_catalogues(catalogues, ["web.language.label"])


def test_shared_shell_bindings_have_matching_catalogue_entries(catalogues):
    class Bindings(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = []

        def handle_starttag(self, tag, attrs):
            del tag
            self.ids.extend(
                value
                for key, value in attrs
                if key in {"data-i18n", "data-i18n-aria-label"}
            )

    parser = Bindings()
    parser.feed((ROOT / "src/synthpopcan/web/index.html").read_text())
    assert parser.ids
    for catalogue in catalogues.values():
        assert set(parser.ids) <= catalogue["messages"].keys()


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        json.loads('{"messages":{"x":1,"x":2}}', object_pairs_hook=check.unique_object)


def test_placeholder_parity_and_braces_are_enforced(catalogues):
    changed = copy.deepcopy(catalogues)
    changed["fr-CA"]["messages"]["web.language.label"]["value"] = "Bonjour {name}"
    with pytest.raises(ValueError, match="invalid template"):
        check.validate_catalogues(changed, [])
    assert check.placeholders("{{{name}}}") == {"name"}
    with pytest.raises(ValueError, match="unbalanced"):
        check.placeholders("value }")


def test_plural_categories_and_review_provenance_are_required(catalogues):
    msg = {
        "kind": "plural",
        "count_parameter": "count",
        "parameters": {"count": "number"},
        "provenance": {"kind": "project", "source_id": "web.count", "review": "draft"},
    }
    catalogues["en-CA"]["messages"]["web.count"] = {
        **msg,
        "forms": {"one": "{count} item", "other": "{count} items"},
    }
    catalogues["fr-CA"]["messages"]["web.count"] = {
        **msg,
        "forms": {"one": "{count} article", "other": "{count} articles"},
    }
    with pytest.raises(ValueError, match="missing plural"):
        check.validate_catalogues(catalogues, [])
    catalogues["fr-CA"]["messages"]["web.count"]["forms"]["many"] = "{count} articles"
    check.validate_catalogues(catalogues, [])


def test_literal_guard_rejects_additions_and_omissions():
    approved = {'"#selector"': 1}
    check.guard_literals([{"source": '"#selector"'}], approved)
    with pytest.raises(ValueError, match="literals changed"):
        check.guard_literals(
            [{"source": '"#selector"'}, {"source": '"New hard-coded message"'}],
            approved,
        )
    with pytest.raises(ValueError, match="literals changed"):
        check.guard_literals([], approved)
