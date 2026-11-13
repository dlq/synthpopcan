"""Prepare reviewed conditional education targets from Census Profile tracts."""

from __future__ import annotations

from synthpopcan._conditional_profile import prepare_profile_targets
from synthpopcan.geography import GeographyUniverse

SOURCE_FIELDS = dict.fromkeys((2016, 2021), "HDGREE")
PACKS = {f"statcan-{year}-education-ct-v1": year for year in (2016, 2021)}
CROSSWALK = {
    "1": "no_credential",
    "2": "secondary",
    "3": "other_trades",
    "4": "apprenticeship",
    "5": "college",
    "6": "university_below_bachelor",
    "7": "bachelor",
    "8": "university_above_bachelor",
}
PROFILE_ROWS = {
    2016: (
        1135,
        1683,
        (672,),
        (
            (1684,),
            (1685,),
            (1688,),
            (1689,),
            (1690,),
            (1691,),
            (1693,),
            (1694, 1695, 1696, 1697),
        ),
    ),
    2021: (
        1522,
        1998,
        (126,),
        (
            (1999,),
            (2000,),
            (2004,),
            (2005,),
            (2006,),
            (2007,),
            (2009,),
            (2010, 2011, 2012, 2013),
        ),
    ),
}


ROUNDING_LIMIT = 48


def prepare_pack_targets(pack, path, geography: GeographyUniverse, identifiers):
    year = PACKS[pack]
    return prepare_profile_targets(
        pack,
        path,
        geography,
        identifiers,
        year,
        "education",
        PROFILE_ROWS[year],
        CROSSWALK,
        ROUNDING_LIMIT,
    )
