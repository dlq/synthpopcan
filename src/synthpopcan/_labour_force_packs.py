"""Reviewed labour-force status targets for Statistics Canada Census tracts."""

from synthpopcan._conditional_profile import prepare_profile_targets

PACKS = {f"statcan-{year}-labour-force-status-ct-v1": year for year in (2016, 2021)}
CROSSWALK = {
    **dict.fromkeys(map(str, range(1, 3)), "employed"),
    **dict.fromkeys(map(str, range(3, 11)), "unemployed"),
    **dict.fromkeys(map(str, range(11, 15)), "not_in_labour_force"),
}
_ROWS = {
    2016: (1135, 1865, (672, 1683), ((1867,), (1868,), (1869,))),
    2021: (1522, 2223, (126, 1998), ((2225,), (2226,), (2227,))),
}
SOURCE_FIELDS = {2016: "LFTAG", 2021: "LFACT"}


def prepare_pack_targets(pack, path, geography, identifiers):
    year = PACKS[pack]
    return prepare_profile_targets(
        pack,
        path,
        geography,
        identifiers,
        year,
        "labour-force status",
        _ROWS[year],
        CROSSWALK,
        16,
    )
