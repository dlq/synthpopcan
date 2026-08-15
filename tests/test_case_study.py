from __future__ import annotations

import importlib.util
import re
import shlex
from pathlib import Path

from synthpopcan.models import model_registry_entry

_ROOT = Path(__file__).parents[1]
_DOCUMENT = _ROOT / "docs" / "case-study-quebec-2021.md"
_SCRIPT = _ROOT / "scripts" / "case_study_wheel_smoke.py"
_MODEL_ID = "quebec-2021-all-fields"


def _load_smoke_commands() -> tuple[tuple[str, ...], ...]:
    spec = importlib.util.spec_from_file_location("case_study_wheel_smoke", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMMANDS


def _load_offline_commands() -> tuple[tuple[str, ...], ...]:
    spec = importlib.util.spec_from_file_location("case_study_wheel_smoke", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SMOKE_COMMANDS


def _documented_commands() -> tuple[tuple[str, ...], ...]:
    text = _DOCUMENT.read_text()
    block = re.search(r"```bash\n(.*?)```", text, re.DOTALL)
    assert block is not None
    commands = block.group(1).replace("\\\n", " ").splitlines()
    parsed: list[tuple[str, ...]] = []
    for line in commands:
        if not line.strip():
            continue
        tokens = shlex.split(line)
        assert tokens.pop(0) == "synthpopcan"
        if ">" in tokens:
            tokens = tokens[: tokens.index(">")]
        parsed.append(tuple(tokens))
    return tuple(parsed)


def test_case_study_pins_registry_identity_and_integrity() -> None:
    metadata = model_registry_entry(_MODEL_ID)
    text = _DOCUMENT.read_text()

    for expected in (
        _MODEL_ID,
        metadata["release_version"],
        metadata["doi"],
        metadata["sha256"],
        metadata["uncompressed_sha256"],
        "98M0001X2021002",
        "20210921",
        "> quebec-2021-case-study/validation.json",
    ):
        assert str(expected) in text


def test_installed_wheel_smoke_matches_published_commands() -> None:
    assert _load_smoke_commands() == _documented_commands()


def test_installed_wheel_smoke_never_relabels_demo_bytes_as_quebec() -> None:
    offline = _load_offline_commands()
    real_model_commands = [command for command in offline if _MODEL_ID in command]

    assert real_model_commands == [("models", "show", _MODEL_ID, "--format", "json")]
    assert any(
        command[:2] == ("models", "generate")
        and "demo-linked-household-person" in command
        for command in offline
    )


def test_case_study_is_bilingual_and_states_claim_boundaries() -> None:
    text = _DOCUMENT.read_text()
    docs_index = (_ROOT / "docs" / "index.rst").read_text()

    for expected in (
        "## English interpretation and limits",
        "## Interprétation et limites en français",
        "not a simulation",
        "no causal claim",
        "not a fitness-for-use claim",
        "not a non-disclosure guarantee",
        "n'est pas une simulation",
        "aucune affirmation causale",
        "aucune garantie d'aptitude à l'usage",
        "ni une garantie de non-divulgation",
    ):
        assert expected in text
    assert re.search(r"^\s+case-study-quebec-2021$", docs_index, re.MULTILINE)
