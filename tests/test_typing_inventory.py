"""Check diagnostic aggregation independently of Pyright's implementation."""

from pathlib import Path

from support.readiness import audit


def test_typing_audit_separates_package_and_script_findings(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    fixture = {
        "version": "fixture-version",
        "summary": {"filesAnalyzed": 3, "errorCount": 3},
        "generalDiagnostics": [
            {
                "file": str(root / "src/synthpopcan/example.py"),
                "rule": "unknown-type",
                "severity": "error",
            },
            {
                "file": str(root / "src/synthpopcan/example.py"),
                "rule": "unknown-type",
                "severity": "error",
            },
            {
                "file": str(root / "scripts/example.py"),
                "rule": "missing-annotation",
                "severity": "error",
            },
        ],
    }
    commands = []

    def tool_response(arguments):
        commands.append(arguments)
        return fixture

    monkeypatch.setattr(audit, "_run_json", tool_response)
    report = audit.typing_inventory()
    assert commands == [
        ["pyright", "--project", "pyrightconfig.strict.json", "--outputjson"]
    ]
    assert report["files_analyzed"] == 3
    assert report["errors"] == 3
    assert report["files_with_diagnostics_by_scope"] == {"src": 1, "scripts": 1}
    assert report["diagnostics_by_rule"] == {"unknown-type": 2, "missing-annotation": 1}
    assert report["diagnostics_by_file"] == {
        "src/synthpopcan/example.py": {"unknown-type": 2},
        "scripts/example.py": {"missing-annotation": 1},
    }
