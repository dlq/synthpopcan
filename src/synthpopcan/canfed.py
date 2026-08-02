"""Maintained adapter for the public general-use Can-FED v2 archive."""

from __future__ import annotations

__all__ = [
    "CANFED_V2_ARCHIVE_SHA256",
    "CANFED_V2_ARCHIVE_URL",
    "CanFedAdapter",
    "can_fed_source_profile",
    "normalize_can_fed_archive",
]

import csv
import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from synthpopcan.enrichment import SourceProfile
from synthpopcan.geography import statcan_geography_universe

CanFedBuffer = Literal["1km", "3km", "both"]

CANFED_V2_ARCHIVE_URL = (
    "https://www150.statcan.gc.ca/n1/pub/13-20-0001/2025001/zip/canfed_2024.zip"
)
CANFED_V2_ARCHIVE_SHA256 = (
    "fad07b23513eb2c170694f989a9d1ea51c081c44590cc91dfcd5e88fb67768a2"
)
_DATA_PAGE = "https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012025001-eng.htm"
_RAW_COLUMNS = (
    "cls_02_grocery_stores",
    "cls_03_superstores",
    "cls_04_convenience_stores",
    "cls_07_fruit_vegetable_markets",
    "cls_12_restaurants",
    "cls_13_limited_service_fast_food",
    "cls_mRFEI",
    "cls_Rmix",
)
_OUTPUT_NAMES = {
    "cls_02_grocery_stores": "grocery_store_class",
    "cls_03_superstores": "superstore_class",
    "cls_04_convenience_stores": "convenience_store_class",
    "cls_07_fruit_vegetable_markets": "fruit_vegetable_market_class",
    "cls_12_restaurants": "restaurant_class",
    "cls_13_limited_service_fast_food": "limited_service_fast_food_class",
    "cls_mRFEI": "modified_retail_food_environment_index_class",
    "cls_Rmix": "restaurant_mix_class",
}
_RATIO_COLUMNS = frozenset({"cls_mRFEI", "cls_Rmix"})
_DAUID = re.compile(r"^[0-9]{8}$")
_MAX_EXPANDED_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CanFedAdapter:
    """Reviewed source contract and normalizer for one Can-FED buffer choice."""

    buffer: CanFedBuffer = "both"
    expected_sha256: str = CANFED_V2_ARCHIVE_SHA256

    dataset_id = "statcan.canfed.v2.general-use"
    resource_url = CANFED_V2_ARCHIVE_URL
    layer_class = "area-attributes"
    key_columns = ("DAUID",)
    limitations = (
        "Can-FED describes historical area-level food-environment context, not "
        "a current establishment inventory or a person-level exposure.",
        "The public categorical product does not contain the detailed measures "
        "available under Research Data Centre controls.",
        "The publisher guide reports 28 excluded DAs, while the reviewed public "
        "archive contains 57,936 unique DA rows in each buffer product.",
    )
    requires_base_geography = True
    max_download_bytes = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.buffer not in {"1km", "3km", "both"}:
            raise ValueError("Can-FED buffer must be 1km, 3km, or both")

    @property
    def layer_id(self) -> str:
        """Return a stable layer identifier including the selected buffers."""

        return f"statcan.canfed.v2.general-use.{self.buffer}"

    @property
    def layer_filename(self) -> str:
        """Return the deterministic normalized sidecar filename."""

        return f"canfed-v2-{self.buffer}.csv"

    @property
    def variables(self) -> tuple[str, ...]:
        """Return normalized categorical columns for the selected buffers."""

        return _variables_for(self.buffer)

    def describe(self) -> SourceProfile:
        """Return the reviewed Statistics Canada source profile."""

        return can_fed_source_profile()

    def normalize_archive(
        self,
        archive_path: Path,
        output_path: Path,
    ) -> Mapping[str, object]:
        """Normalize the pinned public archive into one DA-keyed CSV."""

        return normalize_can_fed_archive(
            archive_path,
            output_path,
            buffer=self.buffer,
        )

    def reproduction_parameters(self) -> Mapping[str, object]:
        """Record the chosen public buffer product or combined product."""

        return {"buffer": self.buffer}


def can_fed_source_profile() -> SourceProfile:
    """Describe the reviewed Can-FED v2 public general-use source revision."""

    return SourceProfile(
        source_id="statcan.canfed.v2.general-use",
        publisher_id="statistics-canada",
        titles={
            "en": "Canadian Food Environment Dataset, version 2",
            "fr": (
                "Ensemble de données sur l'environnement alimentaire canadien, "
                "version 2"
            ),
        },
        descriptions={
            "en": (
                "Public categorical food-environment classes for 1 km and 3 km "
                "road-network buffers around 2021 dissemination areas."
            ),
            "fr": (
                "Classes publiques de l'environnement alimentaire pour des zones "
                "tampons de réseau routier de 1 km et de 3 km autour des aires de "
                "diffusion de 2021."
            ),
        },
        canonical_url=_DATA_PAGE,
        acquisition_mode="public-download",
        authority="Statistics Canada",
        licence_id="Statistics Canada Open Licence",
        source_version="2.0-public-general-use-2024",
        publication_date="2025-12-19",
        observation_period={
            "food_environment": "2024-08",
            "business_register": "2024",
            "road_network": "2024",
            "census_geography": "2021",
        },
        unit_of_observation="2021 Census dissemination area",
        access_classification="public",
        redistribution_status="permitted with Statistics Canada attribution",
        geography=statcan_geography_universe(2021, "da", "DAUID"),
        translation_provenance={
            "en": "Official title; project-written source summary.",
            "fr": "Official title; project translation of the source summary.",
        },
        known_limitations=CanFedAdapter.limitations,
    )


def normalize_can_fed_archive(
    archive_path: Path,
    output_path: Path,
    *,
    buffer: CanFedBuffer = "both",
) -> dict[str, object]:
    """Normalize reviewed Can-FED CSV members and validate their source schema.

    The public archive is header-driven because its live member names differ
    from the user guide. DA identifiers remain text. Published ``..`` values
    for ratio denominators are represented explicitly as ``not_applicable``.
    """

    if buffer not in {"1km", "3km", "both"}:
        raise ValueError("Can-FED buffer must be 1km, 3km, or both")
    requested = ("1km", "3km") if buffer == "both" else (buffer,)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            _validate_archive_size(archive)
            products = {
                distance: _read_product(archive, distance) for distance in requested
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("Can-FED resource is not a valid ZIP archive") from exc

    identifiers = sorted(set().union(*(set(product) for product in products.values())))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["DAUID", *_variables_for(buffer)],
            lineterminator="\n",
        )
        writer.writeheader()
        for dauid in identifiers:
            output: dict[str, str] = {"DAUID": dauid}
            for distance in requested:
                raw = products[distance].get(dauid)
                for index, column in enumerate(_RAW_COLUMNS):
                    normalized_name = f"{_OUTPUT_NAMES[column]}_{distance}"
                    output[normalized_name] = raw[index] if raw is not None else ""
            writer.writerow(output)

    one_km = set(products.get("1km", {}))
    three_km = set(products.get("3km", {}))
    only_one = sorted(one_km - three_km) if buffer == "both" else []
    only_three = sorted(three_km - one_km) if buffer == "both" else []
    return {
        "schema_version": "synthpopcan-canfed-validation-v1",
        "passed": True,
        "buffer_products": list(requested),
        "product_rows": {distance: len(products[distance]) for distance in requested},
        "normalized_rows": len(identifiers),
        "duplicate_dauid_count": 0,
        "malformed_dauid_count": 0,
        "only_1km_dauids": only_one,
        "only_3km_dauids": only_three,
        "coverage_accounting": {
            "union_rows": len(identifiers),
            "intersection_rows": (
                len(one_km & three_km) if buffer == "both" else len(identifiers)
            ),
            "only_1km_rows": len(only_one),
            "only_3km_rows": len(only_three),
        },
        "missing_code": {
            "source": "..",
            "normalized": "not_applicable",
            "meaning": "ratio denominator equals zero",
        },
        "warnings": [
            "The user guide says 28 of 57,936 DAs were excluded, but the "
            "reviewed archive contains 57,936 unique rows in both products."
        ],
        "issues": [],
    }


def _read_product(
    archive: zipfile.ZipFile,
    distance: str,
) -> dict[str, tuple[str, ...]]:
    member = _member_by_basename(archive, f"dens_thresholds_{distance}.csv")
    with archive.open(member) as raw_handle:
        reader = csv.DictReader(
            io.TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
        )
        expected = ["DAuid", *_RAW_COLUMNS]
        if reader.fieldnames != expected:
            raise ValueError(
                f"Can-FED {distance} columns do not match the reviewed schema"
            )
        rows: dict[str, tuple[str, ...]] = {}
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(
                    f"Can-FED {distance} row {row_number} does not match the "
                    "reviewed column count"
                )
            dauid = str(row.get("DAuid", "")).strip()
            if not _DAUID.fullmatch(dauid):
                raise ValueError(
                    f"Can-FED {distance} row {row_number} has malformed DAuid"
                )
            if dauid in rows:
                raise ValueError(f"Can-FED {distance} has duplicate DAuid {dauid}")
            rows[dauid] = tuple(
                _normalize_category(
                    str(row.get(column, "")).strip(),
                    column=column,
                    distance=distance,
                    row_number=row_number,
                )
                for column in _RAW_COLUMNS
            )
    if not rows:
        raise ValueError(f"Can-FED {distance} product is empty")
    return rows


def _normalize_category(
    value: str,
    *,
    column: str,
    distance: str,
    row_number: int,
) -> str:
    if value in {"0", "1", "2", "3", "4"}:
        return value
    if value == ".." and column in _RATIO_COLUMNS:
        return "not_applicable"
    raise ValueError(
        f"Can-FED {distance} row {row_number} has unsupported {column} value {value!r}"
    )


def _member_by_basename(archive: zipfile.ZipFile, basename: str) -> str:
    matches = [
        member.filename
        for member in archive.infolist()
        if not member.is_dir() and Path(member.filename).name == basename
    ]
    if len(matches) != 1:
        raise ValueError(f"Can-FED archive must contain exactly one {basename} member")
    return matches[0]


def _validate_archive_size(archive: zipfile.ZipFile) -> None:
    expanded = sum(member.file_size for member in archive.infolist())
    if expanded > _MAX_EXPANDED_BYTES:
        raise ValueError("Can-FED archive expands beyond the reviewed size limit")


def _variables_for(buffer: CanFedBuffer) -> tuple[str, ...]:
    distances = ("1km", "3km") if buffer == "both" else (buffer,)
    return tuple(
        f"{_OUTPUT_NAMES[column]}_{distance}"
        for distance in distances
        for column in _RAW_COLUMNS
    )
