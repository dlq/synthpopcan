"""Human-readable failures at the command-line boundary."""

from __future__ import annotations

import csv
import errno
import gzip
import json
import os
import socket
import ssl
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from zipfile import BadZipFile

import click
from pydantic import ValidationError

from synthpopcan._http import retry_after
from synthpopcan._version import __version__

__all__ = [
    "FriendlyCommand",
    "FriendlyGroup",
    "click_file_access_error",
    "click_value_error",
    "format_file_access_error",
]


class _PresentedError(click.ClickException):
    """An error already presented by the innermost command."""


class FriendlyCommand(click.Command):
    """Present callback failures while preserving Click's parsing and exit rules."""

    def invoke(self, ctx: click.Context) -> Any:
        return _invoke(ctx, super().invoke)


class FriendlyGroup(click.Group):
    """Apply the same boundary to every nested group and command."""

    command_class = FriendlyCommand
    group_class = type

    def invoke(self, ctx: click.Context) -> Any:
        return _invoke(ctx, super().invoke)


def _invoke(ctx: click.Context, invoke: Callable[[click.Context], Any]) -> Any:
    try:
        return invoke(ctx)
    except (
        _PresentedError,
        click.UsageError,
        click.Abort,
        click.exceptions.Exit,
        BrokenPipeError,
    ):
        raise
    except Exception as exc:
        cause = exc.__cause__ if isinstance(exc, click.ClickException) else exc
        cause = cause or exc
        expected = isinstance(
            cause,
            (
                OSError,
                ValueError,
                csv.Error,
                EOFError,
                BadZipFile,
                ImportError,
                MemoryError,
            ),
        ) or isinstance(exc, click.ClickException)
        if not expected and os.environ.get("SYNTHPOPCAN_DEBUG") == "1":
            raise
        message = _format_error(exc, cause, ctx)
        presented = _PresentedError(message)
        raise presented from exc


def _format_error(exc: Exception, cause: BaseException, ctx: click.Context) -> str:
    network = _network_error(cause)
    if network is not None:
        return network
    if isinstance(cause, gzip.BadGzipFile):
        return (
            "The input is not a valid gzip file. Provide a complete .gz file, "
            "or decompress the input and use the matching input format."
        )
    if isinstance(cause, BadZipFile):
        return (
            "The input is not a valid ZIP archive. Download or recreate the "
            "complete archive before trying again."
        )
    if isinstance(cause, EOFError):
        return (
            "The input ended unexpectedly and may be incomplete. Restore or "
            "re-download the complete file before trying again."
        )
    if isinstance(cause, ImportError):
        if isinstance(exc, click.ClickException):
            return _with_help(exc.message, ctx)
        if cause.name and cause.name.split(".")[0] == "sklearn":
            return (
                "CART training needs the optional model-build dependencies. "
                "Install them in this Python environment with: "
                "python -m pip install 'synthpopcan[model-build]'"
            )
        return (
            f"A required Python dependency could not be imported: {cause}. Reinstall "
            "or repair dependencies in the Python environment running this command. "
            "Use 'python -m pip check' to identify missing or incompatible packages."
        )
    if isinstance(cause, MemoryError):
        return (
            "There is not enough memory to complete this command. Reduce the "
            "population or input size, use smaller batches, or free memory and retry."
        )
    if isinstance(cause, csv.Error):
        return (
            f"Could not parse CSV input: {cause}. "
            "Check the delimiter, quoting, and row structure of the input file."
        )
    if isinstance(cause, ValueError):
        original = exc.message if isinstance(exc, click.ClickException) else str(cause)
        return _with_help(_value_error(cause, original), ctx)
    if isinstance(cause, OSError):
        if isinstance(exc, click.ClickException):
            return _with_help(exc.message, ctx)
        return format_file_access_error(
            cause.filename or "the input or output path", "access", cause
        )
    if isinstance(cause, RuntimeError) and "changed while" in str(cause):
        return (
            f"Processing stopped because {cause}. "
            "Stop other processes changing these inputs, then retry with stable files."
        )
    if (
        isinstance(cause, RuntimeError)
        and ctx.info_name == "run"
        and ctx.parent is not None
        and ctx.parent.info_name in {"national-da", "national-ada"}
    ):
        return (
            f"A national-run batch failed: {cause}. "
            "Review the failed batch's error and status in the plan directory, "
            "correct its inputs or restore the unavailable source, then retry the plan."
        )
    if isinstance(exc, click.ClickException):
        return _with_help(exc.message, ctx)
    return (
        f"Unexpected SynthPopCan error ({type(cause).__name__}). "
        "Set SYNTHPOPCAN_DEBUG=1 when running the command to see technical details. "
        "Report the failure at https://github.com/dlq/synthpopcan/issues, "
        f"including the command and SynthPopCan version {__version__}."
    )


def _with_help(message: str, ctx: click.Context) -> str:
    message = message.strip() or "The command could not complete. Check the inputs."
    if "unknown model package" in message.lower():
        return f"{message}\nRun 'synthpopcan models list' to see available model IDs."
    if "unknown control pack" in message.lower():
        return (
            f"{message}\nRun 'synthpopcan geo control-packs list' "
            "to see available control-pack IDs."
        )
    if message.startswith("Statistics Canada WDS") and "try again later" in message:
        return message
    parts: list[str] = []
    current: click.Context | None = ctx
    while current is not None and current.parent is not None:
        if current.info_name:
            parts.append(current.info_name)
        current = current.parent
    command = " ".join(["synthpopcan", *reversed(parts)])
    return (
        f"{message}\nFor command options and input requirements, run: {command} --help"
    )


def _value_error(exc: ValueError, message: str) -> str:
    if isinstance(exc, UnicodeDecodeError):
        return (
            "Could not read the input as UTF-8 text. Save the text file as UTF-8 "
            "and check that compressed or binary data uses the correct input format."
        )
    if isinstance(exc, json.JSONDecodeError):
        context = f"{message}. " if "not valid JSON" in message else ""
        return (
            f"{context}Invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}. "
            "Check JSON syntax, including quotes and commas, and supply a JSON file."
        )
    if isinstance(exc, ValidationError):
        errors = exc.errors(include_input=False, include_url=False)
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'input'}: {error['msg']}"
            for error in errors[:5]
        )
        more = f"; {len(errors) - 5} more errors" if len(errors) > 5 else ""
        return f"Invalid input fields: {details}{more}. Correct these fields and retry."
    if message.startswith(
        ("invalid literal for int()", "could not convert string to float")
    ):
        return (
            "The input contains a value that could not be read as a number. "
            "Check numeric columns and option values for text or empty values."
        )
    if "not valid JSON" in message and "Check JSON syntax" not in message:
        location = ""
        if isinstance(exc.__cause__, json.JSONDecodeError):
            location = f" (line {exc.__cause__.lineno}, column {exc.__cause__.colno})"
        return f"{message}{location}. Check JSON syntax, including quotes and commas."
    return message or "Input validation failed. Check the input values and file format."


def _network_error(exc: BaseException) -> str | None:
    if isinstance(exc, HTTPError):
        try:
            host = urlsplit(exc.url).hostname or "remote service"
        except ValueError:
            host = "remote service"
        prefix = f"Could not fetch data from {host} (HTTP {exc.code})."
        if exc.code == 429:
            return _rate_limit_error(exc, prefix)
        if exc.code in {408, 425} or exc.code >= 500:
            return (
                f"{prefix} The service may be temporarily unavailable. Try again later."
            )
        if exc.code == 404:
            return (
                f"{prefix} Check the source URL or product/model ID; "
                "the requested resource was not found."
            )
        if exc.code in {401, 403}:
            return (
                f"{prefix} The service refused access. Check the source's access "
                "requirements and your network or proxy settings."
            )
        return f"{prefix} Check the source URL and the service's availability."
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, ssl.SSLError):
        return (
            "Could not establish a trusted HTTPS connection. Check the system clock, "
            "trusted CA certificates, and any HTTPS proxy configuration. "
            "Keep certificate verification enabled."
        )
    if isinstance(reason, TimeoutError):
        return (
            "The connection to the remote service timed out. Check your internet "
            "connection and try again later."
        )
    if isinstance(reason, socket.gaierror):
        return (
            "Could not resolve the remote service's hostname. Check your internet "
            "connection, DNS, and proxy settings, then try again."
        )
    if isinstance(exc, URLError | ConnectionError) or (
        isinstance(reason, OSError)
        and reason.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}
    ):
        return (
            "Could not connect to the remote service. Check your internet connection "
            "and proxy settings; the service may also be temporarily unavailable. "
            "Try again later."
        )
    return None


def _rate_limit_error(exc: HTTPError, prefix: str) -> str:
    delay = retry_after(exc)
    if delay is None:
        guidance = (
            "The service did not provide a usable Retry-After time. "
            "Wait a few minutes before rerunning this command."
        )
    elif delay.seconds == 0:
        guidance = (
            "The service's Retry-After time has passed, but the request is still "
            "rate-limited. Wait a few minutes before rerunning this command."
        )
    else:
        deadline = (
            f" (not before {delay.deadline:%Y-%m-%d %H:%M:%S} UTC)"
            if delay.deadline is not None
            else ""
        )
        guidance = (
            f"Retry-After asks you to wait at least {delay.seconds} seconds{deadline} "
            "before rerunning this command."
        )
    return (
        f"{prefix} The service is rate-limiting requests. {guidance} "
        "Pause other requests to this service and avoid repeated retries. "
        "If this persists after waiting, check the provider's service status "
        "or contact its support."
    )


def format_file_access_error(path: object, action: str, exc: OSError) -> str:
    """Name the failing path and distinguish filesystem and network recovery."""

    network = _network_error(exc)
    if network is not None:
        return network
    if exc.errno == errno.EADDRINUSE:
        return (
            "The local server address is already in use. Stop the other server "
            "or choose a different --port for 'synthpopcan serve'."
        )
    if exc.errno == errno.EADDRNOTAVAIL:
        return (
            "The requested local server address is not available on this computer. "
            "Use an available loopback address, such as --host 127.0.0.1."
        )
    if isinstance(exc, FileNotFoundError):
        tip = (
            "Create the output's parent directory or choose an existing "
            "writable directory."
            if action in {"write", "write to"}
            else (
                "Check that the path is correct, including the filename; "
                "make sure the required input exists "
                "or the output's parent directory exists."
            )
        )
    elif isinstance(exc, PermissionError):
        tip = (
            "Choose an accessible path or ask the file owner to grant "
            "the required access."
        )
    elif isinstance(exc, IsADirectoryError):
        tip = "Pass the path to a file rather than a directory."
    elif isinstance(exc, NotADirectoryError):
        tip = (
            "Check that each parent component is a directory and use the correct path."
        )
    elif isinstance(exc, FileExistsError):
        tip = (
            "Choose a new output path or inspect the existing files before "
            "replacing them."
        )
    elif exc.errno == errno.ENOSPC:
        tip = "Free disk space or choose an output directory on another volume."
    elif exc.errno == errno.EROFS:
        tip = "Choose an output directory on a writable filesystem."
    else:
        tip = (
            "Check that the path is correct and that SynthPopCan has permission "
            "to access it."
        )
    reason = exc.strerror or str(exc) or "operating system error"
    return f"Could not {action} {exc.filename or path}: {reason}. {tip}"


def click_file_access_error(
    path: object, action: str, exc: OSError
) -> click.ClickException:
    return click.ClickException(format_file_access_error(path, action, exc))


def click_value_error(
    exc: ValueError, formatter: Callable[[ValueError], str] = str
) -> click.ClickException:
    return click.ClickException(_value_error(exc, formatter(exc)))
