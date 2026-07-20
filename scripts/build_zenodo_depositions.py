"""Build Zenodo deposition metadata for the prepared model catalogue.

Emits one deposition-metadata JSON per downloadable model package, plus an
``index.json`` summarising the set. The registry in ``synthpopcan.models`` is the
single source of truth: geography, census vintage, the Statistics Canada
attribution notice, the source licence, review status, limitations, file sizes,
and both checksums are copied straight out of it.

Zenodo and DataCite have no native "subordinate DOI". The hierarchy is expressed
through ``related_identifiers``:

* each model record declares ``isPartOf`` the software concept DOI and
  ``isDerivedFrom`` the Statistics Canada PUMF catalogue entry it was trained on;
* the software record declares ``hasPart`` for each model concept DOI.

Generation is deliberately separate from upload. Review the emitted metadata,
then deposit it with the Zenodo REST API.

Usage::

    uv run python scripts/build_zenodo_depositions.py
    uv run python scripts/build_zenodo_depositions.py --year 2021
    uv run python scripts/build_zenodo_depositions.py --concept-doi 10.5281/zenodo.1234567
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from synthpopcan.models import model_catalogue, model_registry_entry

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "derived" / "zenodo" / "depositions"

# Upstream product each vintage was trained from, for the isDerivedFrom link.
_PUMF_SOURCES = {
    "2016 Census": {
        "catalogue": "98M0002X2016001",
        "url": "https://www150.statcan.gc.ca/n1/en/catalogue/98M0002X2016001",
        "title": "2016 Census Hierarchical Public Use Microdata File",
    },
    "2021 Census": {
        "catalogue": "98M0001X2021002",
        "url": "https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X2021002",
        "title": "2021 Census Hierarchical Public Use Microdata File, version 2",
    },
}

# CC BY 4.0 describes the SynthPopCan-authored model package. It does not replace
# the continuing Statistics Canada Open Licence conditions on any incorporated
# source Information; the record carries both the required notice and that
# distinction. Revisit the controlled-vocabulary choice after informed review.
_LICENSE = "cc-by-4.0"

_SOFTWARE_REPOSITORY = "https://github.com/dlq/synthpopcan"

# Authorship for the archived model records, kept in step with CITATION.cff.
# ORCIDs are only ever added when supplied by their owner, never inferred.
_CREATORS = [{"name": "Quesnel, Darcy"}]


def _description(entry: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Build the human-readable record description carrying full provenance."""

    source = _PUMF_SOURCES[str(entry["census_vintage"])]
    conditions = ", ".join(str(value) for value in entry["conditions"])
    return "\n".join(
        [
            f"<p>{entry['description']}</p>",
            "<p><strong>Geography:</strong> "
            f"{entry['geography']}<br>"
            f"<strong>Census vintage:</strong> {entry['census_vintage']}<br>"
            f"<strong>Conditioning columns:</strong> {conditions}<br>"
            f"<strong>Package version:</strong> {entry['release_version']}</p>",
            f"<p><strong>Source attribution.</strong> {entry['provenance']}</p>",
            "<p><strong>Licences.</strong> SynthPopCan-authored model material "
            "is offered under the Creative Commons Attribution 4.0 licence. The "
            "licence does not replace conditions that continue to apply to any "
            "incorporated Statistics Canada Information. The "
            f'<a href="{source["url"]}">source file</a> is released under the '
            f'<a href="{entry["source_licence"]}">Statistics Canada Open '
            "Licence</a>; retain its required attribution above and comply with "
            "its accuracy, non-identification, non-misrepresentation, and "
            "no-endorsement conditions.</p>",
            "<p><strong>Disclosure review.</strong> "
            f"{entry['privacy']} Review status: "
            f"{entry['privacy_review_status']}. Passing SynthPopCan's "
            "disclosure-risk checks is a project-level screen, not legal "
            "anonymization or Statistics Canada endorsement.</p>",
            f"<p><strong>Known limitations.</strong> {entry['known_limitations']}</p>",
            "<p><strong>Generation guidance.</strong> "
            f"{entry['generation_limits']}</p>",
            "<p><strong>File integrity.</strong> "
            f"Compressed {metadata['size_bytes']:,} bytes, "
            f"SHA-256 <code>{metadata['sha256']}</code>. "
            f"Uncompressed {metadata['uncompressed_size_bytes']:,} bytes, "
            f"SHA-256 <code>{metadata['uncompressed_sha256']}</code>.</p>",
            "<p>Generated populations are synthetic artifacts. They are not "
            "real Census records and must not be presented as confidential "
            "Statistics Canada information.</p>",
        ]
    )


def _related_identifiers(
    entry: dict[str, Any], *, concept_doi: str | None
) -> list[dict[str, str]]:
    """Link the model record upward to the software and back to its source."""

    source = _PUMF_SOURCES[str(entry["census_vintage"])]
    related: list[dict[str, str]] = [
        {
            "relation": "isDerivedFrom",
            "identifier": source["url"],
            "resource_type": "dataset",
        },
        {
            "relation": "isCompiledBy",
            "identifier": _SOFTWARE_REPOSITORY,
            "resource_type": "software",
        },
    ]
    if concept_doi:
        related.insert(
            0,
            {
                "relation": "isPartOf",
                "identifier": concept_doi,
                "resource_type": "software",
            },
        )
    return related


def build_deposition(model_id: str, *, concept_doi: str | None) -> dict[str, Any]:
    """Build the Zenodo deposition metadata for one model package."""

    entry = next(item for item in model_catalogue() if item["id"] == model_id)
    metadata = model_registry_entry(model_id)
    source = _PUMF_SOURCES[str(entry["census_vintage"])]

    return {
        "metadata": {
            "upload_type": "dataset",
            "title": f"SynthPopCan prepared model: {entry['name']}",
            "creators": _CREATORS,
            "version": str(entry["release_version"]),
            "description": _description(entry, metadata),
            "license": _LICENSE,
            "access_right": "open",
            "language": "eng",
            "keywords": [
                "synthetic population",
                "census",
                "Statistics Canada",
                "microdata",
                str(entry["census_vintage"]),
                str(entry["geography"]),
            ],
            "related_identifiers": _related_identifiers(entry, concept_doi=concept_doi),
            "notes": (
                f"Package identifier: {model_id}. Fetch with "
                f"`synthpopcan models fetch {model_id}`. Trained from "
                f"{source['title']} ({source['catalogue']})."
            ),
        },
        "synthpopcan": {
            "model_id": model_id,
            "asset_url": str(metadata["url"]),
            "filename": str(metadata["filename"]),
            "compression": str(metadata["compression"]),
            "size_bytes": metadata["size_bytes"],
            "sha256": metadata["sha256"],
            "uncompressed_size_bytes": metadata["uncompressed_size_bytes"],
            "uncompressed_sha256": metadata["uncompressed_sha256"],
        },
    }


@click.command()
@click.option(
    "--year",
    type=click.Choice(["2016", "2021", "all"]),
    default="all",
    show_default=True,
    help="Census vintage to emit depositions for.",
)
@click.option(
    "--concept-doi",
    default=None,
    metavar="DOI",
    help="Software concept DOI to link each model record to with isPartOf.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Output directory (default: {OUTPUT_DIR.relative_to(ROOT)}).",
)
def main(year: str, concept_doi: str | None, out_dir: Path | None) -> None:
    """Emit Zenodo deposition metadata for the prepared model catalogue."""

    destination = out_dir or OUTPUT_DIR
    destination.mkdir(parents=True, exist_ok=True)

    wanted = [
        entry
        for entry in model_catalogue()
        if entry["distribution"] == "download"
        and (year == "all" or str(entry["census_vintage"]).startswith(year))
    ]
    if not wanted:
        raise click.UsageError(f"No downloadable models for year {year}")

    if not concept_doi:
        click.echo(
            "No --concept-doi supplied; records will omit the isPartOf link to "
            "the software record. Re-run with it once the software DOI exists.",
            err=True,
        )

    index: list[dict[str, Any]] = []
    for entry in wanted:
        model_id = str(entry["id"])
        deposition = build_deposition(model_id, concept_doi=concept_doi)
        path = destination / f"{model_id}.json"
        path.write_text(json.dumps(deposition, indent=2, sort_keys=True) + "\n")
        index.append(
            {
                "model_id": model_id,
                "title": deposition["metadata"]["title"],
                "version": deposition["metadata"]["version"],
                "census_vintage": str(entry["census_vintage"]),
                "deposition_metadata": path.name,
            }
        )
        click.echo(f"Wrote {path.relative_to(ROOT)}")

    index_path = destination / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-deposition-index-v1",
                "software_concept_doi": concept_doi,
                "license": _LICENSE,
                "depositions": index,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    click.echo(
        f"\n{len(index)} deposition(s) written to {destination.relative_to(ROOT)}"
    )
    click.echo(
        "Review the metadata, then deposit with the Zenodo REST API. "
        "Add hasPart relations on the software record for each model concept DOI."
    )


if __name__ == "__main__":
    main()
