from datetime import UTC, datetime
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from synthpopcan._http import open_with_rate_limit_retry, retry_after


@pytest.fixture
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 1, 12, 0, 0, 250000, tzinfo=UTC)

    monkeypatch.setattr("synthpopcan._http.datetime", Clock)


def throttled(value=None, *, headers=None, body=None):
    fields = dict(headers or {})
    if value is not None:
        fields["Retry-After"] = value
    return HTTPError("https://example.test/api", 429, "Too Many Requests", fields, body)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("0", 0), (" 120 ", 120), ("999999999999999999999", 999999999999999999999)],
)
def test_retry_after_accepts_nonnegative_seconds_without_capping(value, seconds):
    assert retry_after(throttled(value)).seconds == seconds


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "-1",
        "+1",
        "1.5",
        "nan",
        "inf",
        "private garbage",
        "9" * 129,
        "Fri, 31 Dec 9999 23:59:59 -2359",
    ],
)
def test_unusable_retry_after_does_not_invent_a_retry_time(value):
    assert retry_after(throttled(value)) is None


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("Sun, 01 Nov 2026 12:00:02 GMT", 2),
        ("Sun, 01 Nov 2026 11:59:00 GMT", 0),
        ("Sun, 01 Nov 2026 14:00:02 +0200", 2),
    ],
)
def test_http_date_waits_round_up_and_use_utc(value, seconds, fixed_clock):
    delay = retry_after(throttled(value))
    assert delay.seconds == seconds
    assert delay.deadline.tzinfo == UTC


def test_server_date_prevents_early_retry_when_local_clock_is_ahead(fixed_clock):
    delay = retry_after(
        throttled(
            "Sun, 01 Nov 2026 12:00:02 GMT",
            headers={"Date": "Sun, 01 Nov 2026 11:59:02 GMT"},
        )
    )
    assert delay.seconds == 60


def test_invalid_server_date_falls_back_to_local_clock(fixed_clock):
    error = throttled("Sun, 01 Nov 2026 12:00:02 GMT", headers={"Date": "invalid"})
    assert retry_after(error).seconds == 2


def test_header_names_are_case_insensitive():
    assert retry_after(throttled(headers={"retry-after": "3"})).seconds == 3
    assert (
        retry_after(HTTPError("https://example.test", 429, "busy", None, None)) is None
    )


@pytest.mark.parametrize(
    "http_request",
    ["https://example.test/api", Request("https://example.test/api", method="HEAD")],
)
def test_safe_request_retries_once_after_the_entire_short_wait(
    http_request, monkeypatch
):
    events = []
    body = BytesIO(b"private error body")
    error = throttled("5", body=body)
    response = BytesIO(b"success")

    def opener(actual, *, timeout):
        assert actual is http_request
        assert timeout == 37
        events.append("open")
        if len(events) == 1:
            raise error
        return response

    def sleep(seconds):
        assert body.closed
        events.append(("sleep", seconds))

    monkeypatch.setattr("synthpopcan._http.time.sleep", sleep)
    assert open_with_rate_limit_retry(opener, http_request, timeout=37) is response
    assert events == ["open", ("sleep", 5), "open"]


@pytest.mark.parametrize("value", [None, "invalid", "6", "3600"])
def test_unknown_or_long_delays_stop_without_sleeping_or_retrying(value, monkeypatch):
    error = throttled(value)
    calls = []
    monkeypatch.setattr(
        "synthpopcan._http.time.sleep", lambda _: pytest.fail("must not sleep")
    )

    def opener(*args, **kwargs):
        calls.append(args)
        raise error

    with pytest.raises(HTTPError) as caught:
        open_with_rate_limit_retry(opener, "https://example.test/api", timeout=60)
    assert caught.value is error
    assert len(calls) == 1


def test_second_429_is_returned_with_its_own_retry_after_without_a_third_attempt(
    monkeypatch,
):
    errors = [throttled("0"), throttled("120")]
    events = []

    def opener(*args, **kwargs):
        events.append("open")
        raise errors.pop(0)

    monkeypatch.setattr(
        "synthpopcan._http.time.sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )
    with pytest.raises(HTTPError) as caught:
        open_with_rate_limit_retry(opener, "https://example.test/api", timeout=60)
    assert caught.value.headers["Retry-After"] == "120"
    assert events == ["open", ("sleep", 0), "open"]


@pytest.mark.parametrize(
    "error",
    [
        HTTPError("https://example.test", 503, "unavailable", {}, None),
        URLError("connection failed"),
    ],
)
def test_other_network_failures_are_not_retried(error, monkeypatch):
    calls = []

    def opener(*args, **kwargs):
        calls.append(args)
        raise error

    with pytest.raises(type(error)) as caught:
        open_with_rate_limit_retry(opener, "https://example.test/api", timeout=60)
    assert caught.value is error
    assert len(calls) == 1


def test_arbitrary_post_is_not_replayed():
    calls = []

    def opener(*args, **kwargs):
        calls.append(args)
        raise throttled("0")

    with pytest.raises(HTTPError):
        open_with_rate_limit_retry(
            opener, Request("https://example.test", data=b"write"), timeout=60
        )
    assert len(calls) == 1
