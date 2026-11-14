"""Inventory completeness checked against independent repository interfaces."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
from support.readiness import audit

from synthpopcan._interface import load_public_interface_contract
from synthpopcan.webapi import create_web_app
from synthpopcan.webapp import get_webapp_root

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def inventory():
    return audit.localization_inventory()


def repository_files() -> set[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "src/synthpopcan",
            "docs",
            "adr",
            "plans",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return set(result.stdout.rstrip("\0").split("\0"))


def test_cli_inventory_contains_every_contract_path_once(inventory):
    expected = {
        item["path"] for item in load_public_interface_contract()["cli"]["commands"]
    }
    actual = [item["path"] for item in inventory["commands"]]
    assert set(actual) == expected
    assert len(actual) == len(expected), (
        "aliases must have distinct paths, without duplicates"
    )


def test_route_inventory_matches_the_registered_application(inventory, tmp_path):
    app = create_web_app(static_root=get_webapp_root(), workspace=tmp_path)
    try:
        expected = {
            (route.path, method)
            for route in app.routes
            for method in (getattr(route, "methods", None) or ())
        }
    finally:
        app.state.job_manager.shutdown()
    actual = [
        (route["path"], method)
        for route in inventory["routes"]
        for method in route["method"].split(",")
    ]
    assert set(actual) == expected
    assert len(actual) == len(expected)


def test_every_repository_owned_localization_file_is_classified(inventory):
    extensions = {".py", ".js", ".mjs", ".html", ".css", ".md", ".rst", ".json"}
    expected = {path for path in repository_files() if Path(path).suffix in extensions}
    assert set(inventory["files"]) == expected


@pytest.mark.parametrize(
    "path,classification",
    [
        pytest.param(
            "src/synthpopcan/cli_errors.py", "mixed-presentation", id="cli-errors"
        ),
        pytest.param(
            "docs/records/zenodo-2026-10-07.md",
            "historical-or-maintainer",
            id="historical-evidence",
        ),
        pytest.param(
            "src/synthpopcan/contracts/public-interface-v1.json",
            "machine-contract-or-source",
            id="machine-contract",
        ),
        pytest.param("docs/command-line.md", "user-documentation", id="user-guide"),
        pytest.param(
            "src/synthpopcan/controls.py", "domain-or-workflow", id="domain-messages"
        ),
    ],
)
def test_file_classification_respects_translation_boundaries(
    inventory, path, classification
):
    assert inventory["files"][path].split(":", 1)[0] == classification


def test_python_literal_inventory_covers_all_package_sources_with_valid_hashes(
    inventory,
):
    expected = {
        path
        for path in repository_files()
        if path.startswith("src/synthpopcan/") and path.endswith(".py")
    }
    assert set(inventory["python_literals"]) == expected
    for filename, entry in inventory["python_literals"].items():
        source = (ROOT / filename).read_bytes()
        assert entry["source_sha256"] == hashlib.sha256(source).hexdigest(), filename
        line_count = len(source.splitlines())
        for locations in entry["roles"].values():
            assert locations == sorted(set(locations)), filename
            assert all(1 <= line <= line_count for line in locations), filename


def test_literal_roles_and_hashes_follow_a_known_source_fixture(tmp_path, monkeypatch):
    package = tmp_path / "src/synthpopcan"
    package.mkdir(parents=True)
    path = package / "sample.py"
    source = (
        '"""Maintainer documentation."""\n'
        'VALUES = {"schema_key": "Human prose."}\n'
        "def example(name):\n"
        '    """Command help."""\n'
        '    raise ValueError(f"Missing {name}.")\n'
    )
    path.write_text(source)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    result = audit._python_literal_inventory()["src/synthpopcan/sample.py"]
    assert result == {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "roles": {
            "docstring-review-cli-help-or-maintainer": [1, 4],
            "machine-key-retain": [2],
            "human-or-source-review": [2, 5],
        },
    }
    updated = source + '\nMESSAGE = "New human message."\n'
    path.write_text(updated)
    result = audit._python_literal_inventory()["src/synthpopcan/sample.py"]
    assert result["source_sha256"] == hashlib.sha256(updated.encode()).hexdigest()
    assert result["roles"]["human-or-source-review"] == [2, 5, 7]


def test_inventory_declares_canonical_locales_without_claiming_translation(inventory):
    assert inventory["canonical_locales"] == ["en-CA", "fr-CA"]
    assert inventory["default_locale"] == "en-CA"
    assert "inventory only" in inventory["translation_status"]


def test_web_html_inventory_records_human_text_and_accessibility(tmp_path, monkeypatch):
    web = tmp_path / "src/synthpopcan/web"
    web.mkdir(parents=True)
    source = (
        '<button aria-label="Open menu" title="Options">Open &amp; close</button>\n'
        '<input placeholder="Choose a file" data-help="Select a CSV"><img alt="Logo">\n'
        '<script>const internal = "not visible";</script>'
    )
    (web / "index.html").write_text(source)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    result = audit._web_html_inventory()["src/synthpopcan/web/index.html"]
    assert result["source_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert {(item["role"], item["text"]) for item in result["entries"]} == {
        ("attribute:aria-label", "Open menu"),
        ("attribute:title", "Options"),
        ("visible-text", "Open & close"),
        ("attribute:placeholder", "Choose a file"),
        ("attribute:data-help", "Select a CSV"),
        ("attribute:alt", "Logo"),
    }


def test_real_web_help_attributes_are_in_the_inventory(inventory):
    path = "src/synthpopcan/web/index.html"
    source = (ROOT / path).read_text()
    expected = re.findall(r'data-help="([^"]+)"', source)
    actual = [
        entry["text"]
        for entry in inventory["web_html_text"][path]["entries"]
        if entry["role"] == "attribute:data-help"
    ]
    assert expected
    assert actual == expected


def test_javascript_inventory_uses_parser_byte_ranges(tmp_path, monkeypatch):
    script = ROOT / "scripts/audit_web_literals.py"
    spec = importlib.util.spec_from_file_location("audit_web_literals", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = 'const label = "Québec";\nconst text = `Hello ${label}`;\n'.encode()
    path = tmp_path / "example.mjs"
    path.write_bytes(source)
    first = '"Québec"'.encode()
    second = b"`Hello ${label}`"
    first_start, second_start = source.index(first), source.index(second)
    parser_output = (
        f"JS_STRING_LITERAL_EXPRESSION@{first_start}..{first_start + len(first)}\n"
        f"JS_TEMPLATE_EXPRESSION@{second_start}..{second_start + len(second)}\n"
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, parser_output),
    )
    result = module.inventory_file(path, tmp_path / "biome")
    assert result["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert [
        (e["line"], e["kind"], e["source"], e["role"]) for e in result["entries"]
    ] == [
        (1, "string", '"Québec"', "review-required"),
        (2, "template", "`Hello ${label}`", "review-required"),
    ]


def test_javascript_roles_classify_only_direct_sinks():
    script = ROOT / "scripts/audit_web_literals.py"
    spec = importlib.util.spec_from_file_location("audit_web_literals_roles", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for prefix, expected in (
        ("label.textContent = ", "direct-presentation-candidate"),
        ("label.className = ", "dom-identifier-or-structure-preserve"),
        ("document.createElement(", "dom-identifier-or-structure-preserve"),
        ("payload.message = ", "review-required"),
        ("const heading = ", "review-required"),
    ):
        source = (prefix + '"value"').encode()
        assert module.expression_role(source, len(prefix.encode())) == expected


def test_javascript_module_reviews_are_bound_to_exact_source_hashes():
    script = ROOT / "scripts/audit_web_literals.py"
    spec = importlib.util.spec_from_file_location("audit_web_review", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = ROOT / "src/synthpopcan/web/csv.mjs"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        module.reviewed_module_role(path.name, digest, 82)
        == "web-error-message-candidate"
    )
    assert (
        module.reviewed_module_role(path.name, digest, 31)
        == "machine-data-or-protocol-preserve"
    )
    assert module.reviewed_module_role(path.name, "0" * 64, 82) is None
    run_list = ROOT / "src/synthpopcan/web/run-list.mjs"
    run_digest = hashlib.sha256(run_list.read_bytes()).hexdigest()
    assert module.reviewed_module_role(run_list.name, run_digest, 32, '"model"') == (
        "machine-data-or-protocol-preserve"
    )
    assert module.reviewed_module_role(run_list.name, run_digest, 32, '"Model"') == (
        "web-presentation-candidate"
    )
    model = ROOT / "src/synthpopcan/web/run-workbench-model.mjs"
    model_digest = hashlib.sha256(model.read_bytes()).hexdigest()
    assert module.reviewed_module_role(model.name, model_digest, 176, '"model"') == (
        "machine-data-or-protocol-preserve"
    )
    assert (
        module.reviewed_module_role(
            model.name, model_digest, 176, '"Generate from a prepared model"'
        )
        == "web-presentation-candidate"
    )
    workbench = ROOT / "src/synthpopcan/web/runs-workbench.mjs"
    workbench_digest = hashlib.sha256(workbench.read_bytes()).hexdigest()
    assert (
        module.reviewed_module_role(
            workbench.name, workbench_digest, 220, '"uploading"'
        )
        == "machine-data-or-protocol-preserve"
    )
    assert (
        module.reviewed_module_role(workbench.name, workbench_digest, 207, '"success"')
        == "machine-data-or-protocol-preserve"
    )
    assert (
        module.reviewed_module_role(
            workbench.name, workbench_digest, 207, '"Demo files are ready to upload."'
        )
        == "web-presentation-candidate"
    )
    assert (
        module.reviewed_module_role(
            workbench.name,
            workbench_digest,
            301,
            '"Checking package provenance, privacy, and output scale…"',
        )
        == "web-presentation-candidate"
    )
    assert module.reviewed_module_role(workbench.name, workbench_digest, 302, '""') == (
        "machine-data-or-protocol-preserve"
    )


def test_reviewed_javascript_snapshot_covers_current_web_modules():
    snapshot = json.loads(
        (ROOT / "docs/records/localization-web-js-2026-11-14.json").read_text()
    )["files"]
    paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "src/synthpopcan/web").glob("*.mjs")
    }
    assert set(snapshot) == paths
    for name, record in snapshot.items():
        assert (
            record["source_sha256"]
            == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        )
        assert all(entry["role"] != "review-required" for entry in record["entries"])


def test_python_roles_keep_output_and_errors_machine_safe(tmp_path):
    script = ROOT / "scripts/audit_localization_roles.py"
    spec = importlib.util.spec_from_file_location("audit_localization_roles", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (
        '"""API documentation."""\n'
        'schema = {"key": "value"}\n'
        'click.echo("message")\n'
        '_emit(progress, "stage", "status")\n'
        'raise ValueError("invalid")\n'
        'ambiguous = "other"\n'
    )
    path = tmp_path / "example.py"
    path.write_text(source)
    result = module.inventory_file(path)
    by_line = {}
    for entry in result["literals"]:
        by_line.setdefault(entry["line"], set()).add(entry["role"])
    assert by_line == {
        1: {"docstring-mixed-help-api-or-maintainer"},
        2: {"mapping-key-preserve", "structured-value-mixed-preserve"},
        3: {"console-mixed-human-and-machine-preserve"},
        4: {"durable-or-callback-progress-preserve"},
        5: {"exception-mixed-api-cli-web-preserve"},
        6: {"unresolved-preserve-until-reviewed"},
    }
    assert [(item["call"], item["role"]) for item in result["output_sinks"]] == [
        ("click.echo", "console-mixed-human-and-machine-preserve"),
        ("_emit", "durable-or-callback-progress-preserve"),
    ]


def test_python_role_inventory_covers_durable_events_and_worker_logs():
    script = ROOT / "scripts/audit_localization_roles.py"
    spec = importlib.util.spec_from_file_location("audit_localization_sinks", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runs = module.inventory_file(ROOT / "src/synthpopcan/runs.py")
    assert any(
        sink["call"].endswith(".append_event")
        and sink["role"] == "durable-or-callback-progress-preserve"
        for sink in runs["output_sinks"]
    )
    worker = module.inventory_file(ROOT / "src/synthpopcan/workflows/ipf.py")
    assert any(sink["call"] == "_emit" for sink in worker["output_sinks"])
    terminal = module.inventory_file(ROOT / "src/synthpopcan/cli_output.py")
    assert any(
        sink["role"] == "console-mixed-human-and-machine-preserve"
        for sink in terminal["output_sinks"]
    )
    webapi = module.inventory_file(ROOT / "src/synthpopcan/webapi.py")
    assert any(
        sink["call"] == "_error_response"
        and sink["role"] == "http-json-response-preserve"
        for sink in webapi["output_sinks"]
    )


def test_click_inventory_separates_names_help_and_defaults(tmp_path):
    script = ROOT / "scripts/audit_localization_roles.py"
    spec = importlib.util.spec_from_file_location("audit_click_roles", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "cli.py"
    path.write_text(
        '@click.option("--output", default="result.json", help="Write output.")\n'
        "def command(output):\n"
        "    pass\n"
    )
    roles = [item["role"] for item in module.inventory_file(path)["literals"]]
    assert roles == [
        "click-parameter-machine-preserve",
        "click-parameter-machine-preserve",
        "click-help-or-prompt-candidate",
    ]
