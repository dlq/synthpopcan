from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import shlex
from pathlib import Path

import click

import synthpopcan
from synthpopcan.cli import cli


def test_citation_metadata_matches_release() -> None:
    """Keep CITATION.cff in step with the package version and changelog date.

    GitHub's citation widget reads this file, so drift here misstates how to
    cite the release. Note that Zenodo ignores CITATION.cff whenever
    .zenodo.json is present, which is the case here.
    """

    citation = Path("CITATION.cff").read_text()
    versions = re.findall(r'^\s*version:\s*"([^"]+)"', citation, re.MULTILINE)
    dates = re.findall(r"^\s*date-released:\s*(\S+)", citation, re.MULTILINE)

    assert versions, "CITATION.cff should declare a version"
    for version in versions:
        assert version == synthpopcan.__version__, (
            f"CITATION.cff version {version} does not match package version "
            f"{synthpopcan.__version__}"
        )

    assert len(set(dates)) == 1, f"CITATION.cff release dates disagree: {dates}"

    changelog = Path("CHANGELOG.md").read_text()
    entry = re.search(
        rf"^## {re.escape(synthpopcan.__version__)} - (\S+)",
        changelog,
        re.MULTILINE,
    )
    assert entry, f"CHANGELOG.md has no entry for {synthpopcan.__version__}"
    assert dates[0] == entry.group(1), (
        f"CITATION.cff date-released {dates[0]} does not match the CHANGELOG "
        f"date {entry.group(1)} for {synthpopcan.__version__}"
    )

    version_identifier = re.search(
        rf"value:\s*(\S+)\n\s+description: Version DOI for the archived "
        rf"{re.escape(synthpopcan.__version__)} release\.",
        citation,
    )
    primary_dois = re.findall(r"^\s*doi:\s*(\S+)", citation, re.MULTILINE)
    if version_identifier is None:
        assert not primary_dois, (
            "a release awaiting its Zenodo archive must not retain an older version DOI"
        )
    else:
        assert primary_dois == [version_identifier.group(1)] * 2, (
            "the versioned software and preferred citation should use the version DOI"
        )


def test_zenodo_metadata_is_valid_and_drift_free() -> None:
    """Guard the archive record metadata Zenodo actually uses.

    Because .zenodo.json is present, Zenodo ignores CITATION.cff entirely and
    builds the archived record from this file. It deliberately omits a version
    field so the GitHub release tag remains the single source of the version;
    if one is ever added it must track the package.
    """

    zenodo = json.loads(Path(".zenodo.json").read_text())

    assert zenodo["upload_type"] == "software"
    assert zenodo["title"]
    assert zenodo["license"]
    assert zenodo["creators"], ".zenodo.json must credit at least one creator"
    for creator in zenodo["creators"]:
        assert creator.get("name"), "each creator needs a name"
        # Never infer an ORCID; only record one supplied by its owner.
        assert set(creator) <= {"name", "affiliation", "orcid"}

    assert "version" not in zenodo or zenodo["version"] == synthpopcan.__version__

    description = zenodo["description"]
    assert "not affiliated with or endorsed by Statistics Canada" in description
    assert "synthetic artifacts" in description


def test_helper_modules_declare_public_exports() -> None:
    for module_name in (
        "synthpopcan.cli_ipf",
        "synthpopcan.cli_output",
        "synthpopcan.console",
        "synthpopcan.controls",
        "synthpopcan.localdata",
        "synthpopcan.sources",
    ):
        module = importlib.import_module(module_name)
        exports = getattr(module, "__all__", None)

        assert exports, f"{module_name} should declare public exports"
        for name in exports:
            assert not name.startswith("_"), f"{module_name} exports private {name}"
            assert hasattr(module, name), f"{module_name}.{name} is missing"


def test_api_reference_members_exist_and_have_docstrings() -> None:
    members_by_module = parse_api_reference_members(Path("docs/api.rst"))

    assert members_by_module
    for module_name, member_names in members_by_module.items():
        module = importlib.import_module(module_name)
        for member_name in member_names:
            assert hasattr(module, member_name), (
                f"{module_name}.{member_name} is missing"
            )
            docstring = inspect.getdoc(getattr(module, member_name))
            assert docstring, f"{module_name}.{member_name} has no docstring"
            assert len(docstring.split()) >= 8, (
                f"{module_name}.{member_name} docstring is too thin"
            )


def parse_api_reference_members(path: Path) -> dict[str, list[str]]:
    """Return explicit autodoc members declared in ``docs/api.rst``."""

    members_by_module: dict[str, list[str]] = {}
    current_module: str | None = None
    collecting_members = False
    for line in path.read_text().splitlines():
        module_match = re.match(r"^\.\. automodule::\s+(\S+)", line)
        if module_match:
            current_module = module_match.group(1)
            collecting_members = False
            continue
        if current_module is None:
            continue
        stripped = line.strip()
        if stripped.startswith(":members:"):
            collecting_members = True
            members_by_module.setdefault(current_module, []).extend(
                split_members(stripped.removeprefix(":members:"))
            )
            continue
        if collecting_members and line.startswith("             "):
            members_by_module.setdefault(current_module, []).extend(
                split_members(stripped)
            )
            continue
        if stripped.startswith(":") or not stripped:
            continue
        collecting_members = False
    return {
        module_name: member_names
        for module_name, member_names in members_by_module.items()
        if member_names
    }


def split_members(raw_members: str) -> list[str]:
    return [member.strip() for member in raw_members.split(",") if member.strip()]


def test_scenario_inventory_matches_automated_test_references() -> None:
    scenario_text = Path("tests/SCENARIOS.md").read_text()
    scenario_ids = re.findall(r"^## (SCN-[A-Z]+-\d{3})$", scenario_text, re.MULTILINE)
    test_text = "\n".join(
        (
            Path("tests/test_workflows.py").read_text(),
            Path("tests/web/scenarios.spec.mjs").read_text(),
        )
    )
    referenced_ids = set(re.findall(r"SCN-[A-Z]+-\d{3}", test_text))

    assert len(scenario_ids) == len(set(scenario_ids))
    assert set(scenario_ids) == referenced_ids


def test_correctness_assurance_is_public_and_names_each_evidence_family() -> None:
    correctness_text = Path("CORRECTNESS.md").read_text()
    readme_text = Path("README.md").read_text()
    docs_index_text = Path("docs/index.rst").read_text()

    assert "CORRECTNESS.md" in readme_text
    assert "correctness.yml/badge.svg" in readme_text
    assert re.search(r"^\s+correctness$", docs_index_text, re.MULTILINE)
    for evidence_path in (
        "tests/test_ipf_correctness.py",
        "tests/test_model_correctness.py",
        "tests/test_small_area_correctness.py",
        "tests/test_reference_correctness.py",
        "tests/test_webapi.py",
        "scripts/check-wheel.sh",
    ):
        assert evidence_path in correctness_text


def test_command_line_navigation_follows_workflow_dependencies() -> None:
    docs_index_text = Path("docs/index.rst").read_text()
    command_line_section = docs_index_text.split(":caption: Command Line", 1)[1]
    command_line_section = command_line_section.split(":caption: Library", 1)[0]
    expected_pages = (
        "command-line",
        "data",
        "statcan",
        "controls",
        "ipf",
        "tree-generate",
        "small-area",
        "validate",
        "microdata",
        "tree",
        "web-app",
    )

    positions = [command_line_section.index(f"   {page}\n") for page in expected_pages]
    assert positions == sorted(positions)


def test_documented_commands_use_the_current_cli_surface() -> None:
    documented_paths = (
        Path("README.md"),
        Path("CORRECTNESS.md"),
        Path("CONTRIBUTING.md"),
        Path("NOTES.md"),
        Path("RELEASING.md"),
        *Path("docs").glob("*.md"),
    )
    checked_commands = 0
    errors: list[str] = []

    for path in documented_paths:
        bash_blocks = re.findall(
            r"^[ \t]*```bash[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
            path.read_text(),
            re.MULTILINE | re.DOTALL,
        )
        for block_number, block in enumerate(bash_blocks, start=1):
            for line in block.replace("\\\n", " ").splitlines():
                tokens = shlex.split(line.strip())
                args = documented_synthpopcan_args(tokens)
                if args is None:
                    continue
                checked_commands += 1
                errors.extend(documented_command_errors(path, block_number, args))

    assert checked_commands >= 150
    assert not errors, "\n".join(errors)


def documented_synthpopcan_args(tokens: list[str]) -> list[str] | None:
    """Return CLI arguments from a documented invocation, when present."""

    for prefix in (
        ["synthpopcan"],
        ["uvx", "synthpopcan"],
        ["uv", "run", "synthpopcan"],
    ):
        if tokens[: len(prefix)] == prefix:
            return tokens[len(prefix) :]
    return None


def documented_command_errors(
    path: Path,
    block_number: int,
    args: list[str],
) -> list[str]:
    """Check one documented command path and its displayed option names."""

    command: click.Command = cli
    command_path: list[str] = []
    index = 0
    while isinstance(command, click.Group) and index < len(args):
        token = args[index]
        if token.startswith("-") or token in {"COMMAND", "SUBCOMMAND"}:
            break
        child = command.commands.get(token)
        if child is None:
            return [
                f"{path}: bash block {block_number}: unknown command "
                f"{' '.join([*command_path, token])}"
            ]
        command = child
        command_path.append(token)
        index += 1

    if not command_path:
        return []
    valid_options = {"-h", "--help"}
    for parameter in command.params:
        valid_options.update(getattr(parameter, "opts", ()))
        valid_options.update(getattr(parameter, "secondary_opts", ()))
    shown_options = {
        token.split("=", 1)[0] for token in args[index:] if token.startswith("-")
    }
    unknown_options = sorted(shown_options - valid_options)
    if not unknown_options:
        return []
    return [
        f"{path}: bash block {block_number}: "
        f"{' '.join(command_path)} uses unknown options "
        f"{', '.join(unknown_options)}"
    ]


def test_library_examples_and_companion_notebook_are_parseable() -> None:
    for path in (
        Path("docs/library-getting-started.md"),
        Path("docs/library.md"),
    ):
        python_blocks = re.findall(
            r"^```python\n(.*?)^```$",
            path.read_text(),
            re.MULTILINE | re.DOTALL,
        )
        assert python_blocks, f"{path} should contain Python examples"
        for index, block in enumerate(python_blocks, start=1):
            ast.parse(block, filename=f"{path}:python-block-{index}")

    notebook_path = Path("docs/_static/library-getting-started.ipynb")
    notebook = json.loads(notebook_path.read_text())
    notebook_text = "\n".join("".join(cell["source"]) for cell in notebook["cells"])
    for workflow_name in (
        "fit_ipf",
        "generate_from_model",
        "calibrate_small_area",
        "render_small_area_map",
    ):
        assert workflow_name in notebook_text

    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]), filename=f"{notebook_path}:{cell['id']}")


def test_beginner_notebook_code_cells_execute(tmp_path: Path, monkeypatch) -> None:
    notebook_path = Path("docs/_static/library-getting-started.ipynb").resolve()
    notebook = json.loads(notebook_path.read_text())
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        code = compile(source, f"{notebook_path}:{cell['id']}", "exec")
        exec(code, namespace)

    assert Path("synthetic-weights.csv").is_file()
    assert Path("expanded-population.csv").is_file()
    assert Path("synthetic-linked-population/households.csv").is_file()
    assert Path("synthetic-linked-population/persons.csv").is_file()
