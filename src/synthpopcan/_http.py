"""Bounded rate-limit handling shared by HTTP clients and error presentation."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

_MAX_RETRY_WAIT_SECONDS = 5


@dataclass(frozen=True)
class RetryAfter:
    """A minimum delay, optionally accompanied by the server's UTC deadline."""

    seconds: int
    deadline: datetime | None = None


def _http_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return (
            parsed.replace(tzinfo=UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    except (TypeError, ValueError, OverflowError):
        return None


def _header(error: HTTPError, name: str) -> str | None:
    if error.headers is None:
        return None
    value = error.headers.get(name) or error.headers.get(name.lower())
    return value.strip() if isinstance(value, str) else None


def retry_after(error: HTTPError) -> RetryAfter | None:
    """Interpret Retry-After without truncating a valid server-requested delay.

    HTTP dates use the larger of the local-clock and server-Date delays, so a
    clock skew cannot cause a premature retry. Unusable headers fail closed.
    """

    value = _header(error, "Retry-After")
    if not value or len(value) > 128:
        return None
    if re.fullmatch(r"[0-9]+", value):
        return RetryAfter(int(value))
    deadline = _http_date(value)
    if deadline is None:
        return None
    now = datetime.now(UTC)
    reference = _http_date(_header(error, "Date")) or now
    seconds = math.ceil(
        max(0, (deadline - now).total_seconds(), (deadline - reference).total_seconds())
    )
    return RetryAfter(seconds, deadline)


def open_with_rate_limit_retry(
    opener: Callable[..., Any],
    request: str | Request,
    *,
    timeout: int,
    read_only_post: bool = False,
) -> Any:
    """Retry opening a safe request once, only for an explicit short 429 wait.

    Longer or unknown waits propagate the original HTTPError for callers to
    report. Bodies are not replayed after reading begins. POST replay must be
    explicitly admitted by a caller that knows the operation is read-only.
    """

    try:
        return opener(request, timeout=timeout)
    except HTTPError as error:
        method = request.get_method() if isinstance(request, Request) else "GET"
        safe = method in {"GET", "HEAD"} or (method == "POST" and read_only_post)
        if error.code != 429 or not safe:
            raise
        delay = retry_after(error)
        if delay is None or delay.seconds > _MAX_RETRY_WAIT_SECONDS:
            raise
        error.close()
        time.sleep(delay.seconds)
    return opener(request, timeout=timeout)
