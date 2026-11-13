"""Prepare reviewed conditional education targets from Census Profile tracts."""

from __future__ import annotations

from synthpopcan._conditional_controls import ConditionalPersonTargets
from synthpopcan._conditional_universe import ConditionalPersonUniverse
from synthpopcan._profile_preparation import _profile_reader, allocate_observed
from synthpopcan.geography import GeographyUniverse
from synthpopcan.statcan import file_integrity

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
_ROWS = {
    2016: (
        1135,
        1683,
        672,
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
        126,
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


def _read_profile(path, year, identifiers, required):
    cells = {ct: {} for ct in identifiers}
    required_text = {str(member) for member in required}
    with _profile_reader(path) as reader:
        header = next(reader, [])
        header = [column.removeprefix("ï»¿").strip('"') for column in header]
        if year == 2016:
            geo, member, count = (
                "GEO_CODE (POR)",
                "Member ID: Profile of Census Tracts (2247)",
                "Dim: Sex (3): Member ID: [1]: Total - Sex",
            )
            tract_level = "2"
        else:
            geo, member, count = "ALT_GEO_CODE", "CHARACTERISTIC_ID", "C1_COUNT_TOTAL"
            tract_level = "Census tract"
        try:
            g, m, c, level, vintage = (
                header.index(key)
                for key in (geo, member, count, "GEO_LEVEL", "CENSUS_YEAR")
            )
            identity = header.index("DGUID") if year == 2021 else g
            if year == 2021 and header[c + 1 : c + 2] != ["SYMBOL"]:
                raise ValueError("Expected a SYMBOL column after C1_COUNT_TOTAL")
            width = max(g, m, c + (year == 2021), level, vintage, identity) + 1
        except ValueError as exc:
            raise ValueError(
                f"Expected the {year} Census Profile tract CSV or ZIP"
            ) from exc
        for row in reader:
            if len(row) <= g or row[g] not in cells:
                continue
            if len(row) < width:
                raise ValueError(f"{row[g]}: incomplete education Profile CSV row")
            if row[level] != tract_level:
                continue
            if row[vintage] != str(year) or (
                year == 2021 and row[identity] != f"2021S0507{row[g]}"
            ):
                raise ValueError(f"{row[g]}: incompatible education Profile geography")
            if row[m] not in required_text:
                continue
            _store_count(cells[row[g]], row, year, g, m, c)
    return cells


def _store_count(cells, row, year, geo_index, member_index, count_index):
    ct, member = row[geo_index], int(row[member_index])
    if member in cells:
        raise ValueError(f"{ct}: duplicate education Profile row {member}")
    value = row[count_index].strip()
    if (
        not value.isascii()
        or not value.isdecimal()
        or (year == 2021 and row[count_index + 1].strip())
    ):
        raise ValueError(f"{ct}: unavailable or invalid education Profile row {member}")
    if int(value) % 5:
        raise ValueError(f"{ct}: education Profile row {member} is not base-five")
    cells[member] = int(value)


def prepare_pack_targets(pack, path, geography: GeographyUniverse, identifiers):
    year = PACKS[pack]
    if geography.canonical_key != (year, "ct", f"statcan:census:{year}:ct"):
        raise ValueError(f"{pack} requires its matching Statistics Canada CT geography")
    all_row, adult_row, check_row, groups = _ROWS[year]
    required = {
        all_row,
        adult_row,
        check_row,
        *[row for group in groups for row in group],
    }
    fingerprint = file_integrity(path)
    cells = _read_profile(path, year, identifiers, required)
    if file_integrity(path) != fingerprint:
        raise ValueError("Education Profile changed while being read")
    source = f"Statistics Canada Census Profile {year}, tract table"
    targets, adjustments = {}, {}
    for ct, counts in sorted(cells.items()):
        if counts.keys() != required:
            raise ValueError(
                f"{ct}: missing education Profile rows "
                f"{sorted(required - counts.keys())}"
            )
        total, adult, companion = (
            counts[row] for row in (all_row, adult_row, check_row)
        )
        if not 0 < adult <= total or abs(adult - companion) > 5:
            raise ValueError(
                f"{ct}: incompatible education private-household denominators"
            )
        raw = [sum(counts[row] for row in group) for group in groups]
        if not sum(raw) or abs(sum(raw) - adult) > 48:
            raise ValueError(
                f"{ct}: education categories exceed the rounding envelope "
                "or have no support"
            )
        child = total - adult
        normalized = dict(
            zip(CROSSWALK.values(), allocate_observed(raw, adult), strict=True)
        )
        universe = ConditionalPersonUniverse(
            geography.identity(ct), total, adult, child, source
        )
        targets[ct] = ConditionalPersonTargets(universe, normalized, child)
        adjustments[ct] = {
            "profile_rows": counts,
            "source_all_ages": total,
            "source_age_15_plus": adult,
            "companion_age_15_plus": companion,
            "source_categories": dict(zip(CROSSWALK.values(), raw, strict=True)),
            "under_15_target": child,
            "eligible_targets": normalized,
        }
    return targets, {
        "pack": pack,
        "source": source,
        "input": {"path": str(path), **fingerprint},
        "geographies": adjustments,
    }
