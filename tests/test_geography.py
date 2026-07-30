from __future__ import annotations

import pytest

from synthpopcan.geography import (
    GEOGRAPHY_IDENTITY_SCHEMA_VERSION,
    GeographyIdentity,
    GeographyRelationship,
    GeographyUniverse,
    ensure_geography_compatible,
    statcan_geography_identity,
    statcan_geography_universe,
    validate_geography_identifiers,
)


def test_statcan_identity_round_trips_with_explicit_context() -> None:
    identity = statcan_geography_identity(
        2021,
        "da",
        "24660244",
        dguid="2021S051224660244",
    )

    assert identity.canonical_key == (
        2021,
        "da",
        "statcan:census:2021:da",
        "24660244",
    )
    assert identity.as_dict()["schema_version"] == GEOGRAPHY_IDENTITY_SCHEMA_VERSION
    assert GeographyIdentity.from_dict(identity.as_dict()) == identity


def test_geography_universe_builds_contextualized_row_identities() -> None:
    universe = statcan_geography_universe(
        2021,
        "da",
        "DAUID",
        dguid_column="DGUID",
    )

    assert GeographyUniverse.from_dict(universe.as_dict()) == universe
    assert universe.identity(
        "24660244",
        dguid="2021S051224660244",
    ) == statcan_geography_identity(
        2021,
        "da",
        "24660244",
        dguid="2021S051224660244",
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"census_vintage": 21}, "four-digit year"),
        ({"geography_level": "postal-code"}, "unsupported geography_level"),
        ({"identifier_namespace": "StatCan DA"}, "lowercase stable"),
        ({"identifier": " 24660244"}, "trimmed"),
        ({"dguid": ""}, "DGUID"),
    ],
)
def test_identity_rejects_ambiguous_or_malformed_context(
    kwargs: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "census_vintage": 2021,
        "geography_level": "da",
        "identifier_namespace": "statcan:census:2021:da",
        "identifier": "24660244",
        "dguid": None,
    }
    values.update(kwargs)

    with pytest.raises((TypeError, ValueError), match=message):
        GeographyIdentity(**values)  # type: ignore[arg-type]


def test_compatibility_rejects_cross_vintage_and_namespace_guessing() -> None:
    current = statcan_geography_identity(2021, "da", "24660244")

    with pytest.raises(ValueError, match="Census vintage mismatch"):
        ensure_geography_compatible(
            current,
            statcan_geography_identity(2016, "da", "24660244"),
        )
    with pytest.raises(ValueError, match="identifier namespace mismatch"):
        ensure_geography_compatible(
            current,
            GeographyIdentity(
                2021,
                "da",
                "researcher:custom-da",
                "24660244",
            ),
        )
    with pytest.raises(ValueError, match="geography identifier mismatch"):
        ensure_geography_compatible(
            current,
            statcan_geography_identity(2021, "da", "24660245"),
            require_same_identifier=True,
        )


def test_universe_validation_reports_duplicates_and_mixed_context() -> None:
    identities = [
        statcan_geography_identity(2021, "da", "001"),
        statcan_geography_identity(2021, "da", "001"),
        statcan_geography_identity(2016, "da", "002"),
    ]

    report = validate_geography_identifiers(identities)

    assert report["passed"] is False
    assert {issue["code"] for issue in report["issues"]} == {
        "duplicate-geography-identifier",
        "incompatible-geography-universe",
    }


def test_relationship_requires_authoritative_same_vintage_lineage() -> None:
    child = statcan_geography_identity(2021, "da", "24660244")
    parent = statcan_geography_identity(2021, "csd", "2466023")
    relationship = GeographyRelationship(
        child=child,
        parent=parent,
        authoritative_product="2021 Dissemination Geographies Relationship File",
        release_date="2022-11-30",
        resource_sha256="a" * 64,
    )

    assert GeographyRelationship.from_dict(relationship.as_dict()) == relationship

    with pytest.raises(ValueError, match="cannot cross Census vintages"):
        GeographyRelationship(
            child=child,
            parent=statcan_geography_identity(2016, "csd", "2466023"),
            authoritative_product="relationship file",
            release_date="2022-11-30",
            resource_sha256="a" * 64,
        )


def test_geography_contract_defensive_validation_paths() -> None:
    universe = statcan_geography_universe(2021, "da", "DAUID")
    identity = statcan_geography_identity(2021, "da", "001", dguid="d1")
    other_dguid = statcan_geography_identity(2021, "da", "001", dguid="d2")

    assert identity.in_universe(identifier_column="DAUID") == universe
    assert validate_geography_identifiers([], expected=identity)["universe"] == [
        2021,
        "da",
        "statcan:census:2021:da",
    ]
    with pytest.raises(ValueError, match="DGUID mismatch"):
        ensure_geography_compatible(
            identity,
            other_dguid,
            require_same_identifier=True,
        )
    with pytest.raises(ValueError, match="must differ"):
        GeographyUniverse(2021, "da", "statcan:census:2021:da", "DAUID", "DAUID")
    with pytest.raises(ValueError, match="unsupported geography universe"):
        GeographyUniverse.from_dict({})
    with pytest.raises(ValueError, match="must be an integer"):
        GeographyUniverse.from_dict({**universe.as_dict(), "census_vintage": True})
    with pytest.raises(ValueError, match="unsupported geography identity"):
        GeographyIdentity.from_dict({})
    with pytest.raises(ValueError, match="must be an integer"):
        GeographyIdentity.from_dict({**identity.as_dict(), "census_vintage": "2021"})
    with pytest.raises(ValueError, match="must be a string"):
        GeographyIdentity.from_dict({**identity.as_dict(), "identifier": 1})
    with pytest.raises(ValueError, match="string or null"):
        GeographyIdentity.from_dict({**identity.as_dict(), "dguid": 1})


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"resource_sha256": "bad"}, "SHA-256"),
        ({"selection_method": "guess"}, "unsupported"),
    ],
)
def test_relationship_rejects_invalid_integrity_metadata(
    updates: dict[str, str],
    message: str,
) -> None:
    values = {
        "child": statcan_geography_identity(2021, "da", "001"),
        "parent": statcan_geography_identity(2021, "csd", "0000001"),
        "authoritative_product": "DGRF",
        "release_date": "2022-02-09",
        "resource_sha256": "a" * 64,
        "selection_method": "authoritative-relationship",
    }
    values.update(updates)
    with pytest.raises(ValueError, match=message):
        GeographyRelationship(**values)  # type: ignore[arg-type]


def test_relationship_payload_rejects_invalid_shape() -> None:
    relationship = GeographyRelationship(
        child=statcan_geography_identity(2021, "da", "001"),
        parent=statcan_geography_identity(2021, "csd", "0000001"),
        authoritative_product="DGRF",
        release_date="2022-02-09",
        resource_sha256="a" * 64,
    )
    with pytest.raises(ValueError, match="unsupported geography relationship"):
        GeographyRelationship.from_dict({})
    with pytest.raises(ValueError, match="child must be an object"):
        GeographyRelationship.from_dict({**relationship.as_dict(), "child": []})
    with pytest.raises(ValueError, match="must differ"):
        GeographyRelationship(
            child=relationship.child,
            parent=relationship.child,
            authoritative_product="DGRF",
            release_date="2022-02-09",
            resource_sha256="a" * 64,
        )
