from __future__ import annotations

import csv
import errno
import gzip
import json
import socket
import ssl
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from zipfile import BadZipFile

import click
import pytest
from click.testing import CliRunner
from pydantic import BaseModel, RootModel, create_model

from synthpopcan.cli import cli
from synthpopcan.cli_errors import format_file_access_error
from synthpopcan.cli_output import click_value_error, read_json_object
from synthpopcan.statcan import fetch_json, post_json

WDS_COMMANDS = [
    ["statcan", "wds", "search", "population dwelling"],
    ["statcan", "wds", "metadata", "98100001"],
    ["statcan", "wds", "explain", "98100001"],
    ["statcan", "wds", "fetch", "98100001", "--out-dir", "output"],
]


@pytest.mark.parametrize("command", WDS_COMMANDS)
@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<!-- outage --><html>PRIVATE RESPONSE</html>", "returned HTML"),
        (b"", "empty response"),
        (b"not-json PRIVATE RESPONSE", "invalid JSON"),
        (b"\xff", "not valid UTF-8"),
    ],
)
def test_wds_invalid_responses_are_actionable_and_do_not_write_files(
    command, body, message, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synthpopcan.statcan.urlopen", lambda *_a, **_kw: BytesIO(body))
    result = CliRunner().invoke(cli, command)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Statistics Canada WDS" in result.stderr
    assert message in result.stderr
    assert "try again later" in result.stderr.lower()
    assert "Expecting value" not in result.stderr
    assert "PRIVATE RESPONSE" not in result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_wds_helpers_keep_valid_json_and_request_body(monkeypatch) -> None:
    requests = []

    def open_response(request, **kwargs):
        requests.append(request)
        return BytesIO(b'\xef\xbb\xbf{"status":"SUCCESS"}')

    monkeypatch.setattr("synthpopcan.statcan.urlopen", open_response)
    assert fetch_json("https://example.test/api") == {"status": "SUCCESS"}
    assert post_json("https://example.test/api", [{"productId": "98100001"}]) == {
        "status": "SUCCESS"
    }
    assert requests[1].method == "POST"
    assert json.loads(requests[1].data) == [{"productId": "98100001"}]


@pytest.mark.parametrize("command", WDS_COMMANDS)
def test_remote_failure_is_not_reported_as_file_permissions(command, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise HTTPError(
            "https://user:SECRET@example.test/api?token=PRIVATE", 503, "busy", {}, None
        )

    monkeypatch.setattr("synthpopcan.statcan.urlopen", unavailable)
    result = CliRunner().invoke(cli, command)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "example.test (HTTP 503)" in result.stderr
    assert "Try again later" in result.stderr
    assert "permission" not in result.stderr
    assert "SECRET" not in result.stderr
    assert "PRIVATE" not in result.stderr


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            HTTPError("https://example.test", 404, "missing", {}, None),
            "product/model ID",
        ),
        (HTTPError("https://example.test", 401, "denied", {}, None), "refused access"),
        (HTTPError("https://example.test", 403, "denied", {}, None), "refused access"),
        (
            HTTPError("https://example.test", 429, "slow down", {}, None),
            "rate-limiting",
        ),
        (
            HTTPError("https://example.test", 408, "timeout", {}, None),
            "Try again later",
        ),
        (HTTPError("/api", 418, "unknown", {}, None), "source URL"),
        (HTTPError("http://[bad", 500, "bad host", {}, None), "remote service"),
        (
            URLError(ssl.SSLCertVerificationError("untrusted")),
            "trusted CA certificates",
        ),
        (ssl.SSLError("handshake"), "Keep certificate verification enabled"),
        (URLError(TimeoutError()), "timed out"),
        (TimeoutError(), "timed out"),
        (URLError(socket.gaierror("DNS")), "hostname"),
        (socket.gaierror("DNS"), "hostname"),
        (URLError("connection failed"), "proxy settings"),
        (ConnectionRefusedError(), "connect to the remote service"),
        (OSError(errno.ENETUNREACH, "unreachable"), "internet connection"),
        (csv.Error("unterminated field"), "delimiter, quoting"),
        (
            UnicodeDecodeError("utf8", b"\xff", 0, 1, "bad"),
            "Save the text file as UTF-8",
        ),
        (json.JSONDecodeError("bad syntax", "PRIVATE INPUT", 2), "line 1, column 3"),
        (
            ValueError("invalid literal for int() with base 10: 'private'"),
            "numeric columns",
        ),
        (ValueError("could not convert string to float: 'private'"), "numeric columns"),
        (ValueError("input.json is not valid JSON"), "Check JSON syntax"),
        (ValueError(""), "Input validation failed"),
        (BadZipFile("PRIVATE BYTES"), "complete archive"),
        (gzip.BadGzipFile("PRIVATE BYTES"), "valid gzip"),
        (EOFError(), "incomplete"),
        (ImportError("missing", name="sklearn.tree"), "synthpopcan[model-build]"),
        (ImportError("missing", name="other_module"), "python -m pip check"),
        (ImportError("missing"), "python -m pip check"),
        (MemoryError(), "smaller batches"),
        (
            RuntimeError("base population changed while publishing"),
            "Stop other processes",
        ),
        (TypeError("PRIVATE BUG DETAILS"), "SYNTHPOPCAN_DEBUG=1"),
        (KeyError("PRIVATE BUG DETAILS"), "github.com/dlq/synthpopcan/issues"),
        (RuntimeError("PRIVATE BUG DETAILS"), "Unexpected SynthPopCan error"),
    ],
)
def test_runtime_failures_have_recovery_guidance(error, expected, monkeypatch):
    def fail():
        raise error

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert expected in result.stderr
    assert "PRIVATE" not in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stderr.count("Error:") == 1


@pytest.mark.parametrize(
    ("error", "action", "tip"),
    [
        (
            FileNotFoundError(errno.ENOENT, "missing", "input.csv"),
            "read",
            "input exists",
        ),
        (
            FileNotFoundError(errno.ENOENT, "missing", "out.csv"),
            "write",
            "parent directory",
        ),
        (PermissionError(errno.EACCES, "denied", "in.csv"), "read", "file owner"),
        (
            IsADirectoryError(errno.EISDIR, "directory", "folder"),
            "read",
            "path to a file",
        ),
        (NotADirectoryError(errno.ENOTDIR, "not directory", "a/b"), "write", "parent"),
        (
            FileExistsError(errno.EEXIST, "exists", "out.csv"),
            "write",
            "new output path",
        ),
        (OSError(errno.ENOSPC, "full", "out.csv"), "write", "Free disk space"),
        (OSError(errno.EROFS, "read only", "out.csv"), "write", "writable filesystem"),
        (OSError(errno.EADDRINUSE, "busy"), "access", "different --port"),
        (OSError(errno.EADDRNOTAVAIL, "bad address"), "access", "--host 127.0.0.1"),
        (OSError("other error"), "access", "permission"),
        (OSError(), "access", "operating system error"),
        (URLError("down"), "write", "remote service"),
    ],
)
def test_filesystem_recovery_is_specific_to_the_failure(
    error, action, tip, monkeypatch
):
    message = format_file_access_error("fallback", action, error)
    assert tip in message

    def fail():
        raise error

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert tip in result.stderr
    if error.filename and not isinstance(error, URLError):
        assert str(error.filename) in result.stderr


def _leaf_commands(group, path=()):
    for name, command in group.commands.items():
        current = (*path, name)
        if isinstance(command, click.Group):
            yield from _leaf_commands(command, current)
        else:
            yield current, command


@pytest.mark.parametrize(("path", "command"), list(_leaf_commands(cli)))
def test_every_cli_command_presents_uncaught_failures(path, command, monkeypatch):
    def fail(**kwargs):
        raise ValueError("required input column is missing")

    monkeypatch.setattr(command, "callback", fail)
    parent = click.Context(cli, info_name="synthpopcan")
    for name in path:
        parent = click.Context(command, info_name=name, parent=parent)
    with pytest.raises(click.ClickException) as error:
        command.invoke(parent)
    assert "required input column" in str(error.value)
    assert f"synthpopcan {' '.join(path)} --help" in str(error.value)


def test_unexpected_failure_keeps_traceback_available_in_debug_mode(monkeypatch):
    def fail():
        raise TypeError("original diagnostic detail")

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"], env={"SYNTHPOPCAN_DEBUG": "1"})
    assert isinstance(result.exception, TypeError)
    assert str(result.exception) == "original diagnostic detail"
    assert result.exc_info is not None
    assert result.stderr == ""


def test_click_usage_cancellation_and_explicit_exits_are_preserved(monkeypatch):
    assert CliRunner().invoke(cli, ["--unknown-option"]).exit_code == 2
    assert CliRunner().invoke(cli, ["models", "show"]).exit_code == 2
    for error in (click.Abort(), KeyboardInterrupt(), click.exceptions.Exit(7)):

        def fail(error=error):
            raise error

        monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
        result = CliRunner().invoke(cli, ["models", "list"])
        assert result.exit_code == (
            7 if isinstance(error, click.exceptions.Exit) else 1
        )
        assert "Unexpected" not in result.output


def test_field_validation_has_locations_but_no_raw_input(monkeypatch):
    class Inputs(BaseModel):
        households: int

    def fail():
        Inputs.model_validate({"households": "PRIVATE VALUE"})

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert "households" in result.stderr
    assert "Correct these fields" in result.stderr
    assert "PRIVATE VALUE" not in result.stderr


def test_unknown_model_suggests_the_catalogue():
    result = CliRunner().invoke(cli, ["models", "show", "missing-model"])
    assert result.exit_code == 1
    assert "synthpopcan models list" in result.stderr


def test_missing_file_uses_the_leaf_command_help(tmp_path: Path):
    result = CliRunner().invoke(cli, ["data", "schema", str(tmp_path / "absent.csv")])
    assert result.exit_code == 1
    assert "absent.csv" in result.stderr
    assert "input exists" in result.stderr
    assert "synthpopcan data schema --help" in result.stderr


def test_named_json_errors_keep_the_location_and_do_not_duplicate_advice(
    tmp_path, monkeypatch
):
    path = tmp_path / "settings.json"
    path.write_text('{"broken":}')

    def fail():
        try:
            read_json_object(path, "settings")
        except ValueError as exc:
            raise click_value_error(exc) from exc

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert str(path) in result.stderr
    assert "line 1, column 11" in result.stderr
    assert result.stderr.count("Check JSON syntax") == 1


@pytest.mark.parametrize("root", [True, False])
def test_field_error_details_are_bounded_and_handle_root_values(root, monkeypatch):
    model = (
        RootModel[int]
        if root
        else create_model("ManyInputs", **{f"field{i}": (int, ...) for i in range(6)})
    )

    def fail():
        model.model_validate(
            "PRIVATE" if root else {f"field{i}": "PRIVATE" for i in range(6)}
        )

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert "PRIVATE" not in result.stderr
    assert "input:" in result.stderr if root else "1 more errors" in result.stderr


def test_failed_national_batch_points_to_preserved_status(monkeypatch):
    command = cli.commands["geo"].commands["national-da"].commands["run"]

    def fail(**_kwargs):
        raise RuntimeError("batch 24 failed: missing controls")

    monkeypatch.setattr(command, "callback", fail)
    result = CliRunner().invoke(
        cli, ["geo", "national-da", "run", "demo-model", "--plan", "plan.json"]
    )
    assert result.exit_code == 1
    assert "missing controls" in result.stderr
    assert "status in the plan directory" in result.stderr
    assert "retry the plan" in result.stderr


def test_broken_pipe_retains_click_behavior(monkeypatch):
    def fail():
        raise BrokenPipeError(errno.EPIPE, "closed output pipe")

    monkeypatch.setattr("synthpopcan.cli.model_catalogue", fail)
    result = CliRunner().invoke(cli, ["models", "list"])
    assert result.exit_code == 1
    assert "Unexpected" not in result.output
