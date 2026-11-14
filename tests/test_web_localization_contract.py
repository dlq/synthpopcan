"""Catalogue gate rejects changed coverage and unsafe presentation literals."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

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


def test_preview_is_valid_but_cannot_claim_unreviewed_coverage(catalogues):
    check.validate_catalogues(catalogues, [])
    with pytest.raises(ValueError, match="unreviewed covered"):
        check.validate_catalogues(catalogues, ["web.language.label"])


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
