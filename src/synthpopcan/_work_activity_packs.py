"""Reviewed annual work-activity targets for Statistics Canada Census tracts."""

from synthpopcan._conditional_profile import prepare_profile_targets

PACKS = {f"statcan-{year}-work-activity-ct-v1": year for year in (2016, 2021)}
CROSSWALK = {
    "1": "did_not_work",
    "2": "did_not_work",
    "11": "full_year_full_time",
    **dict.fromkeys((*map(str, range(3, 11)), "12"), "part_year_or_part_time"),
}
PROFILE_ROWS = {
    2016: (1135, 1873, (672, 1683, 1865), ((1874,), (1876,), (1877,))),
    2021: (1522, 2231, (126, 1998, 2223), ((2232,), (2234,), (2235,))),
}
SOURCE_FIELDS = dict.fromkeys((2016, 2021), "WRKACT")


ROUNDING_LIMIT = 16


def prepare_pack_targets(pack, path, geography, identifiers):
    year = PACKS[pack]
    return prepare_profile_targets(
        pack,
        path,
        geography,
        identifiers,
        year,
        "work activity",
        PROFILE_ROWS[year],
        CROSSWALK,
        ROUNDING_LIMIT,
    )
