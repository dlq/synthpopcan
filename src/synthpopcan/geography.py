"""Versioned Census geography identity and relationship contracts."""

from __future__ import annotations

__all__ = [
    "GEOGRAPHY_IDENTITY_SCHEMA_VERSION",
    "GEOGRAPHY_RELATIONSHIP_SCHEMA_VERSION",
    "GEOGRAPHY_UNIVERSE_SCHEMA_VERSION",
    "GeographyIdentity",
    "GeographyRelationship",
    "GeographyUniverse",
    "ensure_geography_compatible",
    "statcan_geography_identity",
    "statcan_geography_universe",
    "validate_geography_identifiers",
]

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

GEOGRAPHY_IDENTITY_SCHEMA_VERSION = "synthpopcan-geography-identity-v1"
GEOGRAPHY_RELATIONSHIP_SCHEMA_VERSION = "synthpopcan-geography-relationship-v1"
GEOGRAPHY_UNIVERSE_SCHEMA_VERSION = "synthpopcan-geography-universe-v1"

_KNOWN_LEVELS = frozenset(
    {
        "country",
        "pr",
        "cd",
        "csd",
        "cma-ca",
        "ct",
        "ada",
        "da",
        "db",
    }
)
_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class GeographyUniverse:
    """The Census context shared by every geography identifier in a resource.

    A short code such as a DAUID is not globally unique across Census vintages
    or identifier systems. This object records the vintage, geography level,
    namespace, and source columns needed to interpret all identifiers in one
    table or artifact. Use :func:`statcan_geography_universe` for the standard
    Statistics Canada namespace.
    """

    census_vintage: int
    geography_level: str
    identifier_namespace: str
    identifier_column: str
    dguid_column: str | None = None

    def __post_init__(self) -> None:
        _validate_vintage(self.census_vintage)
        _validate_level(self.geography_level)
        _validate_namespace(self.identifier_namespace)
        _validate_text(self.identifier_column, "identifier column")
        if self.dguid_column is not None:
            _validate_text(self.dguid_column, "DGUID column")
            if self.dguid_column == self.identifier_column:
                raise ValueError("DGUID and identifier columns must differ")

    @property
    def canonical_key(self) -> tuple[int, str, str]:
        """Return the vintage, level, and namespace defining the universe."""
        return (
            self.census_vintage,
            self.geography_level,
            self.identifier_namespace,
        )

    def identity(
        self, identifier: str, *, dguid: str | None = None
    ) -> GeographyIdentity:
        """Build one identifier in this universe."""
        return GeographyIdentity(
            census_vintage=self.census_vintage,
            geography_level=self.geography_level,
            identifier_namespace=self.identifier_namespace,
            identifier=identifier,
            dguid=dguid,
        )

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": GEOGRAPHY_UNIVERSE_SCHEMA_VERSION,
            "census_vintage": self.census_vintage,
            "geography_level": self.geography_level,
            "identifier_namespace": self.identifier_namespace,
            "identifier_column": self.identifier_column,
            "dguid_column": self.dguid_column,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> GeographyUniverse:
        """Parse and validate a versioned universe payload."""
        if payload.get("schema_version") != GEOGRAPHY_UNIVERSE_SCHEMA_VERSION:
            raise ValueError("unsupported geography universe schema")
        vintage = payload.get("census_vintage")
        if not isinstance(vintage, int) or isinstance(vintage, bool):
            raise ValueError("census_vintage must be an integer")
        return cls(
            census_vintage=vintage,
            geography_level=_required_text(payload, "geography_level"),
            identifier_namespace=_required_text(payload, "identifier_namespace"),
            identifier_column=_required_text(payload, "identifier_column"),
            dguid_column=_optional_text(payload, "dguid_column"),
        )


@dataclass(frozen=True)
class GeographyIdentity:
    """One geography identifier with enough context for safe comparison.

    The canonical key combines Census vintage, geography level, identifier
    namespace, and short identifier. An optional DGUID provides another
    publisher-issued identity check but does not replace the explicit universe.
    Use :func:`ensure_geography_compatible` before joining independently
    obtained identities.
    """

    census_vintage: int
    geography_level: str
    identifier_namespace: str
    identifier: str
    dguid: str | None = None

    def __post_init__(self) -> None:
        _validate_vintage(self.census_vintage)
        _validate_level(self.geography_level)
        _validate_namespace(self.identifier_namespace)
        _validate_text(self.identifier, "geography identifier")
        if self.dguid is not None:
            _validate_text(self.dguid, "DGUID")

    @property
    def canonical_key(self) -> tuple[int, str, str, str]:
        """Return the stable tuple used for comparison and keyed joins."""
        return (
            self.census_vintage,
            self.geography_level,
            self.identifier_namespace,
            self.identifier,
        )

    @property
    def universe_key(self) -> tuple[int, str, str]:
        """Return the vintage, level, and namespace shared by one universe."""
        return (
            self.census_vintage,
            self.geography_level,
            self.identifier_namespace,
        )

    def in_universe(
        self,
        *,
        identifier_column: str,
        dguid_column: str | None = None,
    ) -> GeographyUniverse:
        """Return the resource universe containing this identity."""
        return GeographyUniverse(
            census_vintage=self.census_vintage,
            geography_level=self.geography_level,
            identifier_namespace=self.identifier_namespace,
            identifier_column=identifier_column,
            dguid_column=dguid_column,
        )

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": GEOGRAPHY_IDENTITY_SCHEMA_VERSION,
            "census_vintage": self.census_vintage,
            "geography_level": self.geography_level,
            "identifier_namespace": self.identifier_namespace,
            "identifier": self.identifier,
            "dguid": self.dguid,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> GeographyIdentity:
        """Parse and validate a versioned identity payload."""
        if payload.get("schema_version") != GEOGRAPHY_IDENTITY_SCHEMA_VERSION:
            raise ValueError("unsupported geography identity schema")
        vintage = payload.get("census_vintage")
        if not isinstance(vintage, int) or isinstance(vintage, bool):
            raise ValueError("census_vintage must be an integer")
        return cls(
            census_vintage=vintage,
            geography_level=_required_text(payload, "geography_level"),
            identifier_namespace=_required_text(payload, "identifier_namespace"),
            identifier=_required_text(payload, "identifier"),
            dguid=_optional_text(payload, "dguid"),
        )


@dataclass(frozen=True)
class GeographyRelationship:
    """One publisher-backed parent/child relationship.

    Both sides carry explicit Census geography identities. The record also
    identifies the authoritative product, release date, exact source checksum,
    and selection method supporting the relationship. It rejects cross-vintage
    relationships rather than inferring that matching-looking identifiers are
    historically comparable.
    """

    child: GeographyIdentity
    parent: GeographyIdentity
    authoritative_product: str
    release_date: str
    resource_sha256: str
    selection_method: str = "authoritative-relationship"

    def __post_init__(self) -> None:
        if self.child.census_vintage != self.parent.census_vintage:
            raise ValueError("geography relationship cannot cross Census vintages")
        if self.child.canonical_key == self.parent.canonical_key:
            raise ValueError("geography relationship child and parent must differ")
        _validate_text(self.authoritative_product, "authoritative product")
        _validate_text(self.release_date, "release date")
        if not _SHA256.fullmatch(self.resource_sha256):
            raise ValueError("resource_sha256 must be a lowercase SHA-256 digest")
        if self.selection_method not in {
            "authoritative-relationship",
            "direct-identifier",
            "spatial-intersection",
        }:
            raise ValueError("unsupported geography relationship selection method")

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": GEOGRAPHY_RELATIONSHIP_SCHEMA_VERSION,
            "child": self.child.as_dict(),
            "parent": self.parent.as_dict(),
            "authoritative_product": self.authoritative_product,
            "release_date": self.release_date,
            "resource_sha256": self.resource_sha256,
            "selection_method": self.selection_method,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> GeographyRelationship:
        """Parse and validate a versioned relationship payload."""
        if payload.get("schema_version") != GEOGRAPHY_RELATIONSHIP_SCHEMA_VERSION:
            raise ValueError("unsupported geography relationship schema")
        child = _required_mapping(payload, "child")
        parent = _required_mapping(payload, "parent")
        return cls(
            child=GeographyIdentity.from_dict(child),
            parent=GeographyIdentity.from_dict(parent),
            authoritative_product=_required_text(payload, "authoritative_product"),
            release_date=_required_text(payload, "release_date"),
            resource_sha256=_required_text(payload, "resource_sha256"),
            selection_method=_required_text(payload, "selection_method"),
        )


def statcan_geography_identity(
    census_vintage: int,
    geography_level: str,
    identifier: str,
    *,
    dguid: str | None = None,
) -> GeographyIdentity:
    """Build one identifier in the standard Statistics Canada Census namespace.

    The namespace is derived as ``statcan:census:{vintage}:{level}``. The
    function normalizes the level to lowercase but preserves the supplied
    identifier and optional DGUID exactly.
    """
    level = geography_level.lower()
    return GeographyIdentity(
        census_vintage=census_vintage,
        geography_level=level,
        identifier_namespace=f"statcan:census:{census_vintage}:{level}",
        identifier=identifier,
        dguid=dguid,
    )


def statcan_geography_universe(
    census_vintage: int,
    geography_level: str,
    identifier_column: str,
    *,
    dguid_column: str | None = None,
) -> GeographyUniverse:
    """Build a resource universe in the standard Statistics Canada namespace.

    Parameters identify the Census vintage and geography level as well as the
    table columns carrying the short identifier and optional DGUID. The
    resulting object can be serialized into controls, manifests, maps, and
    enrichment records.
    """
    level = geography_level.lower()
    return GeographyUniverse(
        census_vintage=census_vintage,
        geography_level=level,
        identifier_namespace=f"statcan:census:{census_vintage}:{level}",
        identifier_column=identifier_column,
        dguid_column=dguid_column,
    )


def ensure_geography_compatible(
    left: GeographyIdentity,
    right: GeographyIdentity,
    *,
    require_same_identifier: bool = False,
) -> None:
    """Reject a join across incompatible geography contexts.

    Vintage, level, and namespace must always match. When
    ``require_same_identifier`` is true, the short identifiers must also match,
    and two present DGUIDs must agree. The function returns ``None`` on success
    and raises :class:`ValueError` with the mismatched component otherwise.
    """
    labels = ("Census vintage", "geography level", "identifier namespace")
    for label, left_value, right_value in zip(
        labels,
        left.universe_key,
        right.universe_key,
        strict=True,
    ):
        if left_value != right_value:
            raise ValueError(
                f"{label} mismatch: {left_value!r} cannot be joined to {right_value!r}"
            )
    if require_same_identifier and left.identifier != right.identifier:
        raise ValueError(
            f"geography identifier mismatch: {left.identifier!r} cannot be joined "
            f"to {right.identifier!r}"
        )
    if (
        require_same_identifier
        and left.dguid is not None
        and right.dguid is not None
        and left.dguid != right.dguid
    ):
        raise ValueError(f"DGUID mismatch: {left.dguid!r} != {right.dguid!r}")


def validate_geography_identifiers(
    identities: Iterable[GeographyIdentity],
    *,
    expected: GeographyIdentity | None = None,
) -> dict[str, Any]:
    """Validate a collection of identities without silently repairing it.

    The report identifies rows from incompatible universes and duplicate
    canonical keys. If ``expected`` is supplied, its universe is the required
    context; otherwise the first identity establishes the expected universe.
    Empty input is valid and reports no inferred universe.
    """
    values = list(identities)
    issues: list[dict[str, object]] = []
    seen: set[tuple[int, str, str, str]] = set()
    universe: tuple[int, str, str] | None = (
        expected.universe_key if expected is not None else None
    )
    for index, identity in enumerate(values):
        if universe is None:
            universe = identity.universe_key
        elif identity.universe_key != universe:
            issues.append(
                {
                    "code": "incompatible-geography-universe",
                    "row": index,
                    "expected": list(universe),
                    "observed": list(identity.universe_key),
                }
            )
        if identity.canonical_key in seen:
            issues.append(
                {
                    "code": "duplicate-geography-identifier",
                    "row": index,
                    "identifier": identity.identifier,
                }
            )
        seen.add(identity.canonical_key)
    return {
        "schema_version": "synthpopcan-geography-validation-v1",
        "passed": not issues,
        "count": len(values),
        "universe": list(universe) if universe is not None else None,
        "issues": issues,
    }


def _validate_vintage(value: int) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1800 <= value <= 9999
    ):
        raise ValueError("census_vintage must be a four-digit year")


def _validate_level(value: str) -> None:
    if value not in _KNOWN_LEVELS:
        raise ValueError(
            "unsupported geography_level; expected one of "
            + ", ".join(sorted(_KNOWN_LEVELS))
        )


def _validate_namespace(value: str) -> None:
    if not _NAMESPACE.fullmatch(value):
        raise ValueError("identifier_namespace must be a lowercase stable identifier")


def _validate_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty trimmed string")


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    _validate_text(value, key)
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    _validate_text(value, key)
    return value


def _required_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value
