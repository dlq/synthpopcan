"""Compatibility imports for the generalized national small-area workflow."""

from synthpopcan.national_small_area import (
    CANADA_DA_JURISDICTIONS,
    NationalDAJurisdiction,
    estimate_national_da_storage,
    execute_canada_da_plan,
    load_2021_da_jurisdictions,
    prepare_canada_da_plan,
    regional_2021_da_profile_paths,
    required_2021_da_profile_keys,
)

__all__ = [
    "CANADA_DA_JURISDICTIONS",
    "NationalDAJurisdiction",
    "estimate_national_da_storage",
    "execute_canada_da_plan",
    "load_2021_da_jurisdictions",
    "prepare_canada_da_plan",
    "regional_2021_da_profile_paths",
    "required_2021_da_profile_keys",
]
