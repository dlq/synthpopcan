"""Observed 2021 CMA/CT controls for the explicit hierarchical-PUMF workflow."""

from __future__ import annotations

import csv
import io
import itertools
import json
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

from synthpopcan.control_packs import load_compatibility_registry, load_control_pack

AGE_CONTROL = "statcan.2021.private-age-gender.v1"
PROFILE = "statcan-hierarchical-2021"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def workflow_controls(geography_level="ct"):
    pack = load_control_pack(f"statcan-2021-broad-{geography_level}-v1")
    definitions = {c.identifier: c for c in load_compatibility_registry().controls}
    return pack, definitions


@contextmanager
def _profile_reader(path: Path):
    if path.suffix.lower() != ".zip":
        with path.open(encoding="latin-1", newline="") as handle:
            yield csv.reader(handle)
        return
    with ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.endswith("English_CSV_data.csv")]
        if len(members) != 1:
            raise ValueError(
                "Profile ZIP must contain exactly one English_CSV_data.csv member."
            )
        with (
            archive.open(members[0]) as raw,
            io.TextIOWrapper(raw, encoding="latin-1", newline="") as handle,
        ):
            yield csv.reader(handle)


def _needed_characteristics() -> set[str]:
    pack, definitions = workflow_controls()
    needed = {"1", "4", "5", "8", "50", "56"}
    for margin in pack.margins:
        control = definitions[margin.control_identifier]
        needed.add(control.source.root_characteristic_id)
        if control.universe.companion_characteristic_id:
            needed.add(control.universe.companion_characteristic_id)
        for axis in control.source_axes:
            for category in axis.categories:
                needed.update(category.source_characteristic_ids)
    return needed


def select_profile(
    path: Path, cma: str, destination: Path
) -> dict[str, dict[str, dict[str, str]]]:
    """Preserve selected raw source rows and reject duplicate or wrong-vintage rows."""
    needed = _needed_characteristics()
    cells: dict[str, dict[str, dict[str, str]]] = {}
    required = {
        "CENSUS_YEAR",
        "ALT_GEO_CODE",
        "GEO_LEVEL",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "C2_COUNT_MEN+",
        "C3_COUNT_WOMEN+",
    }
    with (
        _profile_reader(path) as reader,
        destination.open("w", encoding="latin-1", newline="") as output,
    ):
        columns = next(reader, [])
        missing = required - set(columns)
        if missing:
            raise ValueError(
                "2021 Profile is missing columns: " + ", ".join(sorted(missing))
            )
        # DictReader resolves repeated headers to their final occurrence.
        positions = {name: index for index, name in enumerate(columns)}
        geo_index = positions["ALT_GEO_CODE"]
        member_index = positions["CHARACTERISTIC_ID"]
        level_index = positions["GEO_LEVEL"]
        width = len(columns)
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for values in reader:
            if not values:  # DictReader skips empty CSV records.
                continue
            if len(values) < width:
                values = cast(list[Any], values)
                values.extend([None] * (width - len(values)))
            geo, member = values[geo_index].strip(), values[member_index].strip()
            selected = geo == cma or (
                geo.startswith(cma) and values[level_index].strip() == "Census tract"
            )
            if selected and member in needed:
                # Materialize only retained records, preserving DictReader's
                # missing/extra-field behavior and DictWriter's canonical output.
                row: dict[Any, Any] = dict(zip(columns, values, strict=False))
                if len(values) > width:
                    row[None] = values[width:]
                _store_profile_row(cells, row, geo, member)
                writer.writerow(row)
    if cma not in cells or not any(geo != cma for geo in cells):
        raise ValueError(
            f"Profile must contain CMA {cma} and its Census tracts; "
            "supply the complete 2021 CT Profile ZIP/CSV."
        )
    return cells


def _store_profile_row(cells, row, geo, member) -> None:
    if row["CENSUS_YEAR"].strip() != "2021":
        raise ValueError(f"Profile geography {geo} is not Census 2021.")
    if member in cells.setdefault(geo, {}):
        raise ValueError(
            f"Duplicate Profile cell: geography {geo}, characteristic {member}."
        )
    cells[geo][member] = row


def observed_count(cells, geo: str, member: str, column: str = "C1_COUNT_TOTAL") -> int:
    try:
        text = cells[geo][member][column].strip().replace(",", "")
        # Decimal text is accepted only when its value is an integer.
        value = Decimal(text)
        if not value.is_finite() or value < 0 or value != value.to_integral_value():
            raise ValueError
        return int(value)
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise ValueError(
            f"Missing, suppressed or invalid Profile count: geography {geo}, "
            f"characteristic {member}, {column}. Supply observed counts; "
            "this workflow does not impute them."
        ) from exc


def allocate_observed(values: list[int], target: int) -> list[int]:
    """Largest remainder with exact integers, stable ties, and observed zeros."""
    total = sum(values)
    if total == 0:
        if target == 0:
            return [0] * len(values)
        raise ValueError(
            "An all-zero observed vector cannot be normalized to a positive target."
        )
    allocated = [value * target // total for value in values]
    order = sorted(range(len(values)), key=lambda i: (-(values[i] * target % total), i))
    for i in order[: target - sum(allocated)]:
        allocated[i] += 1
    return allocated


def _source_vector(cells, geo, control):
    axes = control.source_axes
    categories, counts = [], []
    for combination in itertools.product(*(axis.categories for axis in axes)):
        labels = tuple(category.target_category for category in combination)
        column = "C1_COUNT_TOTAL"
        if control.identifier == AGE_CONTROL:
            column = combination[1].source_count_columns[0]
            # The source columns are authoritative. Frozen v1 target labels use
            # a different codebook; do not mutate that compatibility contract.
            gender = {"C2_COUNT_MEN+": "2", "C3_COUNT_WOMEN+": "1"}[column]
            labels = (labels[0], gender)
        values = [
            observed_count(cells, geo, member, column)
            for member in combination[0].source_characteristic_ids
        ]
        categories.append(labels)
        counts.append(sum(values))
    return categories, counts


def _write_batch(
    cells,
    geos,
    household_totals,
    folder: Path,
    include_age: bool,
    geography_level="ct",
):
    pack, definitions = workflow_controls(geography_level)
    folder.mkdir(parents=True)
    rows: dict[str, list[dict[str, Any]]] = {"household": [], "person": []}
    dimensions: dict[str, list[str]] = {"household": [], "person": []}
    audit = []
    for margin in pack.margins:
        if margin.control_identifier == AGE_CONTROL and not include_age:
            continue
        control = definitions[margin.control_identifier]
        entity, dims = margin.entity_level, margin.dimensions[1:]
        dimensions[entity].extend(d for d in dims if d not in dimensions[entity])
        for geo in geos:
            target = (
                household_totals[geo]
                if entity == "household"
                else observed_count(cells, geo, "56")
            )
            categories, values = _source_vector(cells, geo, control)
            normalized = allocate_observed(values, target)
            audit.append(
                {
                    geography_level: geo,
                    "control": control.identifier,
                    "source_root": observed_count(
                        cells, geo, control.source.root_characteristic_id
                    ),
                    "source_categories": dict(
                        zip(("|".join(c) for c in categories), values, strict=True)
                    ),
                    "target_total": target,
                    "normalized_categories": dict(
                        zip(("|".join(c) for c in categories), normalized, strict=True)
                    ),
                }
            )
            for category, count in zip(categories, normalized, strict=True):
                rows[entity].append(
                    {
                        "margin": geography_level + " " + " ".join(dims),
                        "dimensions": ",".join([geography_level, *dims]),
                        geography_level: geo,
                        **dict(zip(dims, category, strict=True)),
                        "count": count,
                    }
                )
    for entity, records in rows.items():
        with (folder / f"{entity}-controls.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "margin",
                    "dimensions",
                    geography_level,
                    *dimensions[entity],
                    "count",
                ],
            )
            writer.writeheader()
            writer.writerows(records)
    write_json(folder / "normalization.json", audit)
    return {
        "name": folder.name,
        "tracts" if geography_level == "ct" else "geographies": list(geos),
        "include_age_gender": include_age,
        "target_households": sum(household_totals[g] for g in geos),
        "target_persons": sum(observed_count(cells, g, "56") for g in geos),
    }


def _eligible_tracts(cells, cma, incomplete_geographies):
    geos, excluded = [], []
    pack, definitions = workflow_controls()
    for geo in sorted(g for g in cells if g != cma):
        try:
            households = observed_count(cells, geo, "50")
            if households == 0:
                excluded.append(
                    {"ct": geo, "reason": "zero published private households"}
                )
                continue
            total, private = (
                observed_count(cells, geo, "8"),
                observed_count(cells, geo, "56"),
            )
            if private <= 0:
                raise ValueError(
                    f"Invalid private-person universe totals for tract {geo}."
                )
            for margin in pack.margins:
                control = definitions[margin.control_identifier]
                if control.identifier == AGE_CONTROL and total != private:
                    continue
                observed_count(cells, geo, control.source.root_characteristic_id)
                _source_vector(cells, geo, control)
            geos.append(geo)
        except ValueError as exc:
            if incomplete_geographies != "exclude":
                raise
            excluded.append({"ct": geo, "reason": str(exc)})
    return geos, excluded


def _prepare_cma_profile_controls(
    source: Path, cma: str, output: Path, incomplete_geographies: str = "error"
) -> dict[str, Any]:
    """Prepare observed proportional controls with explicit universe partitioning."""
    output.mkdir(parents=True, exist_ok=True)
    cells = select_profile(source, cma, output / "selected-profile.csv")
    geos, excluded = _eligible_tracts(cells, cma, incomplete_geographies)
    if not geos:
        raise ValueError("No positive-household Census tracts were selected.")
    household_target = observed_count(cells, cma, "5")
    totals = dict(
        zip(
            geos,
            allocate_observed(
                [observed_count(cells, g, "50") for g in geos], household_target
            ),
            strict=True,
        )
    )
    age_geos = {
        g
        for g in geos
        if observed_count(cells, g, "8") == observed_count(cells, g, "56")
    }
    batches = []
    for name, selected, age in [
        ("private-households", [g for g in geos if g not in age_geos], False),
        ("zero-collective", [g for g in geos if g in age_geos], True),
    ]:
        if selected:
            batches.append(_write_batch(cells, selected, totals, output / name, age))
    summary = {
        "source_profile": PROFILE,
        "incomplete_geographies": incomplete_geographies,
        "excluded_tracts": excluded,
        "cma": cma,
        "target_households": household_target,
        "target_persons": sum(observed_count(cells, g, "56") for g in geos),
        "tracts": geos,
        "batches": batches,
        "normalization": (
            "Complete observed vectors proportionally normalized "
            "by largest remainder; source rows and observed zeros "
            "retained; suppressed/missing counts rejected."
        ),
        "age_gender_policy": (
            "Only tracts with equal all-person and "
            "private-household-person roots; hierarchical 2021 "
            "AGEGRP 1–13 and GENDER 1=Women+, 2=Men+. Frozen v1 "
            "pack is not modified."
        ),
    }
    write_json(output / "plan.json", summary)
    return summary


def prepare_profile_controls(
    source: Path,
    cma: str | None,
    output: Path,
    incomplete_geographies: str = "error",
    *,
    province: str | None = None,
    geo_level: str = "ct",
    province_profile: Path | None = None,
    canada: bool = False,
) -> dict[str, Any]:
    """Prepare observed controls for a CMA's CTs or a province's complete ADAs."""
    if canada:
        if cma is not None or province is not None or geo_level != "ada":
            raise ValueError("Choose Canada, one province, or one CMA.")
        summary = _prepare_province_profile_controls(
            source, "01", output, incomplete_geographies, province_profile
        )
        summary.pop("province")
        summary["country"] = "01"
        for suffix in ("households", "private_persons", "total_persons"):
            summary[f"country_{suffix}"] = summary.pop(f"province_{suffix}")
        coverage = summary["coverage"]
        coverage["official_country_households"] = coverage.pop(
            "official_province_households"
        )
        write_json(output / "plan.json", summary)
        return summary
    if province is None:
        if cma is None:
            raise ValueError("Supply --cma for CTs or --province for ADAs.")
        if geo_level != "ct" or province_profile is not None:
            raise ValueError(
                "ADA controls require --province; --cma selects Census tracts."
            )
        return _prepare_cma_profile_controls(
            source, cma, output, incomplete_geographies
        )
    if cma is not None or geo_level != "ada":
        raise ValueError("Choose --cma for Census tracts or --province for ADAs.")
    if len(province) != 2 or not province.isascii() or not province.isdigit():
        raise ValueError("--province must be a two-digit Census 2021 province code.")
    return _prepare_province_profile_controls(
        source, province, output, incomplete_geographies, province_profile
    )


def _province_profile_positions(columns):
    required = {
        "CENSUS_YEAR",
        "ALT_GEO_CODE",
        "GEO_LEVEL",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "C2_COUNT_MEN+",
        "C3_COUNT_WOMEN+",
    }
    if missing := required - set(columns):
        raise ValueError(
            "2021 Profile is missing columns: " + ", ".join(sorted(missing))
        )
    return {name: index for index, name in enumerate(columns)}


def _province_row_selected(geo, level, province, include_areas):
    if geo == province:
        return True
    return bool(
        include_areas
        and (province == "01" or geo.startswith(province))
        and level == "Aggregate dissemination area"
    )


def _validate_province_identity(row, geo, province):
    if geo == province:
        levels = (
            {"Country"}
            if province == "01"
            else {
                "Province",
                "Territory",
                "Province / territory",
                "Province or territory",
            }
        )
        if row["GEO_LEVEL"].strip() not in levels:
            kind = "country" if province == "01" else "province"
            raise ValueError(f"Profile root {province} must identify a {kind}.")
        expected = "2021A000011124" if province == "01" else f"2021A0002{province}"
    else:
        if len(geo) != 8 or not geo.isascii() or not geo.isdigit():
            raise ValueError(f"Invalid Census 2021 ADA identifier: {geo}.")
        expected = f"2021S0516{geo}"
    if row.get("DGUID") and row["DGUID"].strip() != expected:
        raise ValueError(f"Profile DGUID does not match Census 2021 geography {geo}.")


def _store_province_rows(reader, columns, province, cells, writer, include_areas):
    positions = _province_profile_positions(columns)
    needed = _needed_characteristics()
    width = len(columns)
    for values in reader:
        if not values:
            continue
        if len(values) < width:
            values = cast(list[Any], values)
            values.extend([None] * (width - len(values)))
        geo = (values[positions["ALT_GEO_CODE"]] or "").strip()
        member = (values[positions["CHARACTERISTIC_ID"]] or "").strip()
        level = (values[positions["GEO_LEVEL"]] or "").strip()
        if member not in needed or not _province_row_selected(
            geo, level, province, include_areas
        ):
            continue
        if len(values) > width:
            raise ValueError(
                f"Selected Profile row has extra fields: geography {geo}, "
                f"characteristic {member}."
            )
        row: dict[Any, Any] = dict(zip(columns, values, strict=True))
        _validate_province_identity(row, geo, province)
        _store_profile_row(cells, row, geo, member)
        # Repeated SYMBOL headers describe different count columns. Preserve
        # every positional source cell rather than repeat the final SYMBOL.
        writer.writerow(values)


def select_province_profile(source, province, destination, province_profile=None):
    """Preserve ADA rows and an authoritative provincial root, never infer it."""
    cells = {}
    with (
        _profile_reader(source) as reader,
        destination.open("w", encoding="latin-1", newline="") as output,
    ):
        columns = next(reader, [])
        _province_profile_positions(columns)
        writer = csv.writer(output)
        writer.writerow(columns)
        _store_province_rows(reader, columns, province, cells, writer, True)
        if province_profile is not None:
            with _profile_reader(province_profile) as parent_reader:
                parent_columns = next(parent_reader, [])
                if parent_columns != columns:
                    raise ValueError("ADA and province Profile CSV headers must match.")
                _store_province_rows(
                    parent_reader, columns, province, cells, writer, False
                )
    if province not in cells:
        raise ValueError(
            f"Profile has no observed Census 2021 province {province} root. "
            "Supply --province-profile with the official provincial Profile; "
            "rounded ADA totals cannot replace it."
        )
    if not any(geo != province for geo in cells):
        raise ValueError(
            f"Profile contains no Census 2021 ADAs for province {province}."
        )
    return cells


def _check_province_area(cells, geo, households, pack, definitions):
    total, private = observed_count(cells, geo, "8"), observed_count(cells, geo, "56")
    if private <= 0:
        raise ValueError(f"Invalid private-person universe totals for ADA {geo}.")
    for margin in pack.margins:
        control = definitions[margin.control_identifier]
        if control.identifier == AGE_CONTROL and total != private:
            continue
        observed_count(cells, geo, control.source.root_characteristic_id)
        _categories, values = _source_vector(cells, geo, control)
        target = households if margin.entity_level == "household" else private
        allocate_observed(values, target)


def _eligible_province_areas(cells, province, incomplete_geographies):
    geos, excluded = [], []
    pack, definitions = workflow_controls("ada")
    for geo in sorted(g for g in cells if g != province):
        try:
            households = observed_count(cells, geo, "5")
            if households == 0:
                excluded.append(
                    {"ada": geo, "reason": "zero published private households"}
                )
                continue
            _check_province_area(cells, geo, households, pack, definitions)
            geos.append(geo)
        except ValueError as error:
            if incomplete_geographies != "exclude":
                raise
            excluded.append({"ada": geo, "reason": str(error)})
    return geos, excluded


def _province_coverage(cells, province, geos, excluded):
    official = observed_count(cells, province, "5")
    known, unavailable = {}, []
    for geo in sorted(g for g in cells if g != province):
        try:
            known[geo] = observed_count(cells, geo, "5")
        except ValueError:
            unavailable.append(geo)
    observed, covered = sum(known.values()), sum(known[g] for g in geos)
    if observed > official:
        raise ValueError(
            "Selected ADA occupied-household counts exceed the provincial total."
        )
    return {
        "selected_geographies": len(cells) - 1,
        "eligible_geographies": len(geos),
        "excluded_geographies": len(excluded),
        "official_province_households": official,
        "observed_area_households": None if unavailable else observed,
        "known_area_households": observed,
        "covered_households": covered,
        "known_excluded_households": observed - covered,
        "household_target_shortfall": official - covered,
        "unavailable_household_geographies": unavailable,
        "household_coverage_complete": not unavailable and covered == official,
    }


def _prepare_province_profile_controls(
    source, province, output, incomplete_geographies, province_profile
):
    output.mkdir(parents=True, exist_ok=True)
    cells = select_province_profile(
        source, province, output / "selected-profile.csv", province_profile
    )
    geos, excluded = _eligible_province_areas(cells, province, incomplete_geographies)
    if not geos:
        raise ValueError("No positive-household Census 2021 ADAs were selected.")
    coverage = _province_coverage(cells, province, geos, excluded)
    if (
        incomplete_geographies != "exclude"
        and not coverage["household_coverage_complete"]
    ):
        raise ValueError(
            "Selected ADAs do not cover the published province household total. "
            "Supply the complete Profile, or explicitly use --incomplete-geographies "
            "exclude to prepare a partial-coverage plan."
        )
    totals = {g: observed_count(cells, g, "5") for g in geos}
    age_geos = {
        g
        for g in geos
        if observed_count(cells, g, "8") == observed_count(cells, g, "56")
    }
    batches = []
    for name, selected, age in [
        ("private-households", [g for g in geos if g not in age_geos], False),
        ("zero-collective", [g for g in geos if g in age_geos], True),
    ]:
        if selected:
            batches.append(
                _write_batch(cells, selected, totals, output / name, age, "ada")
            )
    summary = {
        "source_profile": PROFILE,
        "incomplete_geographies": incomplete_geographies,
        "excluded_geographies": excluded,
        "province": province,
        "geography_level": "ada",
        "geography_dimension": "ada",
        "target_households": sum(totals.values()),
        "province_households": observed_count(cells, province, "5"),
        "province_private_persons": observed_count(cells, province, "56"),
        "province_total_persons": observed_count(cells, province, "1"),
        "target_persons": sum(observed_count(cells, g, "56") for g in geos),
        "geographies": geos,
        "batches": batches,
        "coverage": coverage,
        "normalization": (
            "Complete observed vectors proportionally normalized by largest remainder "
            "to each ADA's published occupied-private-dwelling count; source rows "
            "and observed zeros retained. Excluded households are not reassigned."
        ),
        "age_gender_policy": (
            "Only ADAs with equal all-person and private-household-person roots; "
            "hierarchical 2021 AGEGRP 1–13 and GENDER 1=Women+, 2=Men+. "
            "Frozen v1 pack is not modified."
        ),
    }
    write_json(output / "plan.json", summary)
    return summary
