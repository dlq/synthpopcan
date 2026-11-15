"""The browser receives reviewed guidance, never raw validation failures."""

import pytest

from synthpopcan._web_error_messages import (
    _RESTART_MESSAGES,
    conditional_message,
    restart_message,
)


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        (
            "requires its matching Statistics Canada CT geography",
            "matching Statistics Canada CT geography",
        ),
        ("requires broad pack", "matching built-in broad pack"),
        ("requires its matching source upload", "matching source upload"),
        (
            "require person controls and an explicit Census geography",
            "person controls and an explicit Census geography",
        ),
        (
            "Expected the 2021 Census Profile tract CSV or ZIP",
            "Census Profile tract CSV or ZIP",
        ),
        (
            "incompatible private-household denominators",
            "incompatible private-household denominators",
        ),
        ("exceed the rounding envelope", "rounding envelope"),
        ("suppressed", "suppressed or unavailable"),
        ("duplicate Profile row", "duplicate rows or cells"),
        ("missing Profile rows", "source rows or fields are missing"),
        ("unavailable or invalid Profile row", "unavailable or invalid"),
        ("Profile row is not base-five", "rounded to base five"),
        ("Unknown education pack", "pack is not recognized"),
        ("conditional and person geographies differ", "geographies differ"),
        ("under-15 target", "under-15 conditional target"),
        ("eligible category targets must sum", "age-15+ denominator"),
        ("unsupported eligible category", "unsupported eligible category"),
        ("unknown age eligibility", "unknown age category"),
        ("unrecognized error", "Conditional controls could not be validated"),
    ],
)
def test_conditional_message_uses_reviewed_guidance(detail: str, expected: str) -> None:
    result = conditional_message(ValueError(f"/private/secret.csv: {detail}"))
    assert expected in result
    assert "/private/secret.csv" not in result


@pytest.mark.parametrize("message", _RESTART_MESSAGES)
def test_restart_message_preserves_reviewed_guidance(message: str) -> None:
    assert restart_message(ValueError(message)) == message


def test_restart_message_rejects_unreviewed_text() -> None:
    result = restart_message(ValueError("/private/secret.csv: Only interrupted"))
    assert "Check its state and input integrity" in result
    assert "/private/secret.csv" not in result
