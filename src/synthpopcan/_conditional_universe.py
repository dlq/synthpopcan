"""Internal v1 contract for reviewed age-15+ private-household targets.

This contract validates reconciled targets only. It neither derives Census
counts nor admits a new control family to existing packs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from synthpopcan.geography import GeographyIdentity

_SCHEMA = "synthpopcan-conditional-person-universe-v1"


@dataclass(frozen=True)
class ConditionalPersonUniverse:
    """One independently evidenced age universe at one Census geography.

    Counts must already be reconciled by a reviewed, family-specific source
    preparer. Missing/suppressed counts and raw rounded vectors cannot be
    repaired here. Source evidence identifies the pinned rows, revision,
    suppression decisions, and any reconciliation applied upstream.
    """

    geography: GeographyIdentity
    all_private_household_persons: float
    age_15_plus_persons: float
    under_15_persons: float
    source_evidence: str
    population: Literal["private-household-persons"] = "private-household-persons"
    minimum_age: Literal[15] = 15
    schema_version: str = _SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA:
            raise ValueError("unsupported conditional-person universe schema")
        if self.population != "private-household-persons" or self.minimum_age != 15:
            raise ValueError(
                "conditional-person universe requires private-household persons "
                "aged 15+"
            )
        _require_identity(self.geography)
        if self.geography.census_vintage not in {2016, 2021}:
            raise ValueError(
                "conditional-person universe requires reviewed 2016/2021 evidence"
            )
        _require_evidence(self.source_evidence)
        for count in (
            self.all_private_household_persons,
            self.age_15_plus_persons,
            self.under_15_persons,
        ):
            _observed_count(count)
        if not math.isclose(
            self.age_15_plus_persons + self.under_15_persons,
            self.all_private_household_persons,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "age-15+ and under-15 targets must reconcile to the "
                "private-household total before fitting; raw rounding differences "
                "require reviewed source reconciliation"
            )

    def validate_targets(
        self,
        geography: GeographyIdentity,
        eligible_counts: tuple[float, ...],
        *,
        under_15_not_applicable: float,
    ) -> None:
        """Reject mismatched geography, denominators, and implicit under-15 states.

        Eligible counts describe an exhaustive, mutually exclusive family over
        age-15+ persons. Under-15 persons remain an explicit separate state.
        An explicitly conditional fitting implementation may omit that state
        from its fitting vector only after preserving this evidence boundary.
        """
        if geography != self.geography:
            raise ValueError(
                "conditional-person targets must match Census vintage, namespace, "
                "level and geography identity"
            )
        if not eligible_counts:
            raise ValueError(
                "conditional-person targets require an exhaustive eligible "
                "category vector"
            )
        for count in (*eligible_counts, under_15_not_applicable):
            _observed_count(count)
        if not math.isclose(
            _eligible_total(eligible_counts),
            self.age_15_plus_persons,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "eligible category targets must sum to the age-15+ denominator, "
                "not the all-person total"
            )
        if not math.isclose(
            under_15_not_applicable, self.under_15_persons, rel_tol=0, abs_tol=1e-9
        ):
            raise ValueError(
                "under-15 not-applicable target must match independently "
                "evidenced under-15 persons"
            )


def _observed_count(value: object) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(
            "counts must be observed, finite and non-negative; "
            "suppressed/missing counts are not zero"
        )


def _require_identity(value: object) -> None:
    if not isinstance(value, GeographyIdentity):
        raise ValueError("conditional-person universe requires a geography identity")


def _require_evidence(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("conditional-person universe requires source evidence")


def _eligible_total(counts: tuple[float, ...]) -> float:
    try:
        return math.fsum(counts)
    except OverflowError as exc:
        raise ValueError("eligible target total must be finite") from exc
