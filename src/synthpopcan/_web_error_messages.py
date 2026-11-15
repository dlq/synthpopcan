"""Render reviewed web diagnostics without returning exception text.

Matching selects only fixed messages; it never includes the exception, file paths,
source values, or traceback in the HTTP response. Unrecognized errors fail closed.
"""

from __future__ import annotations

_RESTART_MESSAGES = (
    "Only interrupted small-area runs can be restarted.",
    "The run used a different SynthPopCan version; create a new run.",
    "Run evidence or inputs have changed; create a new run.",
    "Restart inputs changed during preflight; create a new run.",
    "The prior model path is invalid; create a new run.",
    "The prior model cannot be verified; create a new run.",
    "The model has changed since the interrupted run; create a new run.",
    "The run input directory is invalid; create a new run.",
    "Run input path is invalid; create a new run.",
    "Run has duplicate input identifiers.",
    "Run inputs have changed; create a new run.",
    "Saved inputs no longer pass preflight; create a new run and "
    "check the controls and candidate support.",
    "Not enough workspace capacity to restart this run.",
)


def restart_message(error: Exception) -> str:
    """Return an explicitly reviewed recovery message or a safe fallback."""
    detail = str(error)
    for message in _RESTART_MESSAGES:
        if detail == message:
            return message
    return (
        "Could not restart this run. Check its state and input integrity, "
        "or create a new run."
    )


def conditional_message(error: Exception) -> str:
    """Identify common control failures using fixed, actionable messages."""
    detail = str(error)
    rules = (
        (
            "matching Statistics Canada CT geography",
            "The selected conditional pack requires its matching Statistics Canada "
            "CT geography. Select the same Census vintage and geography as the pack.",
        ),
        (
            "requires broad pack",
            "The selected conditional pack requires its matching built-in broad "
            "pack. Choose compatible packs for the same Census vintage and geography.",
        ),
        (
            "requires its matching source upload",
            "Each conditional pack requires its matching source upload. "
            "Upload the source for every selected pack.",
        ),
        (
            "require person controls and an explicit Census geography",
            "Conditional controls require person controls and an explicit Census "
            "geography. Supply both before continuing.",
        ),
        (
            "Census Profile tract CSV or ZIP",
            "The selected source is not the expected Census Profile tract CSV or "
            "ZIP. Upload the source for the selected Census vintage and pack.",
        ),
        (
            "private-household denominators",
            "Conditional and person controls have incompatible private-household "
            "denominators. Check their source, geography, and Census vintage.",
        ),
        (
            "rounding envelope",
            "Conditional source counts exceed the permitted Census rounding "
            "envelope. Check the source counts and selected geography.",
        ),
        (
            "suppressed",
            "A required conditional source count is suppressed or unavailable. "
            "Choose an area with published controls or omit the affected pack.",
        ),
        (
            "duplicate",
            "The conditional source contains duplicate rows or cells. Check "
            "the uploaded source for the selected geography.",
        ),
        (
            "missing",
            "Required conditional source rows or fields are missing. Check the "
            "uploaded source and selected geography.",
        ),
        (
            "unavailable or invalid",
            "A required Census Profile row is unavailable or invalid. Check the "
            "source counts and choose an area with published controls.",
        ),
        (
            "not base-five",
            "A Census Profile count is not rounded to base five. Check that the "
            "uploaded source contains the expected published counts.",
        ),
        (
            "Unknown ",
            "The selected conditional pack is not recognized. Choose a listed "
            "pack for the desired Census vintage and geography.",
        ),
        (
            "conditional and person geographies differ",
            "Conditional and person control geographies differ. Supply controls "
            "covering the same geographies.",
        ),
        (
            "under-15",
            "The under-15 conditional target is incompatible with the person "
            "controls. Check their age totals and source evidence.",
        ),
        (
            "eligible category targets must sum",
            "Eligible category targets must sum to the age-15+ denominator. "
            "Check the conditional control counts and source evidence.",
        ),
        (
            "unsupported eligible",
            "Candidate people contain an unsupported eligible category. "
            "Check the candidate fields and the pack crosswalk.",
        ),
        (
            "unknown age eligibility",
            "Candidate people contain an unknown age category. Check the age "
            "field and the pack crosswalk.",
        ),
    )
    for marker, message in rules:
        if marker in detail:
            return message
    return (
        "Conditional controls could not be validated. Check the selected packs, "
        "source data, geography, and candidate support; use the CLI for detailed "
        "diagnostics."
    )
