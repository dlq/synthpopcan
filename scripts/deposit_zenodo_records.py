"""Deposit prepared model packages to Zenodo as reviewable drafts.

Reads the metadata emitted by ``build_zenodo_depositions.py``, creates one
Zenodo deposition per model package, uploads the release asset, and records the
resulting deposition IDs and reserved DOIs.

Safety model, because publishing to Zenodo is irreversible:

* the sandbox is the default target; ``--production`` is required to touch the
  real archive;
* nothing is published unless ``--publish`` is passed, and even then each
  publish is confirmed;
* ``--dry-run`` reports the planned calls without contacting Zenodo at all.

Authentication uses a personal access token from ``ZENODO_TOKEN`` (or
``ZENODO_SANDBOX_TOKEN`` when targeting the sandbox); tokens are never accepted
on the command line, so they stay out of shell history.

Usage::

    uv run python scripts/deposit_zenodo_records.py --dry-run
    uv run python scripts/deposit_zenodo_records.py --only ontario-2021-all-fields
    uv run python scripts/deposit_zenodo_records.py --production --publish
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import click

ROOT = Path(__file__).resolve().parents[1]
DEPOSITIONS_DIR = ROOT / "data" / "derived" / "zenodo" / "depositions"
RESULTS_PATH = DEPOSITIONS_DIR / "deposited.json"

PRODUCTION_API = "https://zenodo.org/api"
SANDBOX_API = "https://sandbox.zenodo.org/api"


class ZenodoError(RuntimeError):
    """Raised when the Zenodo API rejects a request."""


def _request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
) -> dict[str, Any]:
    """Issue one authenticated Zenodo API call and return the parsed response."""

    headers = {"Authorization": f"Bearer {token}"}
    body: bytes | None = data
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = "application/octet-stream"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network failure
        detail = exc.read().decode(errors="replace")
        raise ZenodoError(f"{method} {url} failed: {exc.code} {detail}") from exc
    return json.loads(raw) if raw else {}


def _asset_bytes(deposition: dict[str, Any], *, token: str) -> bytes:
    """Fetch the release asset this deposition describes."""

    url = str(deposition["synthpopcan"]["asset_url"])
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def deposit_one(
    deposition: dict[str, Any],
    *,
    api: str,
    token: str,
    publish: bool,
) -> dict[str, Any]:
    """Create one Zenodo deposition, upload its asset, and set its metadata."""

    model_id = str(deposition["synthpopcan"]["model_id"])
    created = _request("POST", f"{api}/deposit/depositions", token=token, payload={})
    deposition_id = created["id"]

    bucket = created["links"]["bucket"]
    filename = f"{model_id}-package.json.gz"
    payload = _asset_bytes(deposition, token=token)
    _request("PUT", f"{bucket}/{filename}", token=token, data=payload)

    updated = _request(
        "PUT",
        f"{api}/deposit/depositions/{deposition_id}",
        token=token,
        payload={"metadata": deposition["metadata"]},
    )

    result = {
        "model_id": model_id,
        "deposition_id": deposition_id,
        "state": "draft",
        "doi": updated.get("metadata", {}).get("prereserve_doi", {}).get("doi"),
        "html_url": created["links"].get("html"),
        "uploaded_bytes": len(payload),
    }

    if publish:
        published = _request(
            "POST",
            f"{api}/deposit/depositions/{deposition_id}/actions/publish",
            token=token,
        )
        result["state"] = "published"
        result["doi"] = published.get("doi", result["doi"])
        result["concept_doi"] = published.get("conceptdoi")

    return result


def _load_depositions(only: tuple[str, ...]) -> list[dict[str, Any]]:
    """Load generated deposition metadata, optionally filtered to some models."""

    if not DEPOSITIONS_DIR.exists():
        raise click.UsageError(
            f"No deposition metadata in {DEPOSITIONS_DIR.relative_to(ROOT)}. "
            "Run scripts/build_zenodo_depositions.py first."
        )
    paths = sorted(
        path
        for path in DEPOSITIONS_DIR.glob("*.json")
        if path.name not in {"index.json", RESULTS_PATH.name}
    )
    depositions = [json.loads(path.read_text()) for path in paths]
    if only:
        wanted = set(only)
        depositions = [
            item for item in depositions if item["synthpopcan"]["model_id"] in wanted
        ]
        missing = wanted - {item["synthpopcan"]["model_id"] for item in depositions}
        if missing:
            raise click.UsageError(f"Unknown model IDs: {sorted(missing)}")
    if not depositions:
        raise click.UsageError("No depositions selected")
    return depositions


@click.command()
@click.option(
    "--production",
    is_flag=True,
    help="Target the real Zenodo archive instead of the sandbox.",
)
@click.option(
    "--publish",
    is_flag=True,
    help="Publish each deposition after upload. Irreversible; confirmed per record.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report the planned depositions without contacting Zenodo.",
)
@click.option(
    "--only",
    multiple=True,
    metavar="MODEL_ID",
    help="Deposit only these model IDs. Repeat as needed.",
)
def main(production: bool, publish: bool, dry_run: bool, only: tuple[str, ...]) -> None:
    """Deposit prepared model packages to Zenodo as reviewable drafts."""

    depositions = _load_depositions(only)
    api = PRODUCTION_API if production else SANDBOX_API
    target = "PRODUCTION" if production else "sandbox"

    if dry_run:
        click.echo(f"Dry run against {target} ({api}); no requests will be sent.\n")
        for item in depositions:
            spc = item["synthpopcan"]
            click.echo(
                f"  {spc['model_id']}: would upload {spc['size_bytes']:,} bytes "
                f"as {item['metadata']['title']!r}"
            )
        click.echo(f"\n{len(depositions)} deposition(s) planned.")
        return

    token_var = "ZENODO_TOKEN" if production else "ZENODO_SANDBOX_TOKEN"
    token = os.environ.get(token_var)
    if not token:
        raise click.UsageError(
            f"Set {token_var} to a Zenodo personal access token with the "
            "deposit:write scope. Tokens are not accepted as arguments."
        )

    if production and not click.confirm(
        f"Deposit {len(depositions)} record(s) to PRODUCTION Zenodo?"
    ):
        raise click.Abort

    results: list[dict[str, Any]] = []
    for item in depositions:
        model_id = item["synthpopcan"]["model_id"]
        click.echo(f"Depositing {model_id} to {target} …")
        should_publish = publish and click.confirm(
            f"  Publish {model_id}? This cannot be undone", default=False
        )
        result = deposit_one(item, api=api, token=token, publish=should_publish)
        results.append(result)
        click.echo(f"  {result['state']} id={result['deposition_id']}")

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-deposit-results-v1",
                "target": target,
                "api": api,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    click.echo(f"\nWrote {RESULTS_PATH.relative_to(ROOT)}")
    click.echo(
        "Add a hasPart related identifier on the software record for each "
        "published model concept DOI."
    )


if __name__ == "__main__":
    main()
