"""Check the proposed web catalogue example and machine-output boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/web-localization-contract.md"


def test_catalogue_example_is_valid_and_has_consistent_parameters():
    text = CONTRACT.read_text()
    example = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    assert example is not None
    catalogue = json.loads(example.group(1))
    assert catalogue["schema_version"] == "synthpopcan-web-messages-v1"
    assert catalogue["locale"] == "en-CA"
    assert catalogue["revision"]
    for identifier, message in catalogue["messages"].items():
        assert re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+", identifier)
        assert message["provenance"]["source_id"] == identifier
        assert message["provenance"]["review"] == "reviewed"
        assert message["provenance"]["reviewer"]
        assert message["provenance"]["reviewed_on"]
        templates = (
            [message["value"]]
            if message["kind"] == "text"
            else list(message["forms"].values())
        )
        if message["kind"] == "plural":
            assert "other" in message["forms"]
            assert message["parameters"][message["count_parameter"]] == "number"
        for template in templates:
            assert set(re.findall(r"\{([a-z][a-z0-9_]*)\}", template)) == set(
                message["parameters"]
            )


def test_dynamic_message_contract_rejects_guessing_or_machine_output_changes():
    text = CONTRACT.read_text()
    assert 'Current `_error_response` returns `{"error": message}`' in text
    assert "complete original error text" in text
    assert "workflow, stage and complete original message text" in text
    assert "do not guess by" in text
    assert "without mutating or serializing translated data" in text
    assert "A future protocol may introduce independently versioned" in text
