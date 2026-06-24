"""Census microdata seed sample contracts and adapters."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SeedLevel = Literal["household", "person"]

__all__ = [
    "SeedLevel",
    "SeedSample",
    "TreeColumnBlockSpec",
    "TreeColumnSuggestionProfile",
    "build_tree_geography_feasibility_report",
    "check_statcan_2016_household_seed_columns",
    "derive_statcan_2016_household_seed_sample",
    "export_seed_rows",
    "export_statcan_2016_household_training_rows",
    "export_statcan_2016_person_training_rows",
    "export_training_rows",
    "read_fixture_seed_sample",
    "read_statcan_2016_hierarchical_seed_sample",
    "resolve_tree_column_block_pair",
    "suggest_tree_column_blocks",
]


@dataclass(frozen=True)
class SeedSample:
    """A loaded seed microdata sample with normalized metadata.

    Seed samples keep raw CSV rows plus the column roles needed by IPF and tree
    workflows, such as identifier, geography, and weight columns.

    Parameters
    ----------
    level:
        Whether records describe households or people.
    source_format:
        Adapter name identifying how the source file was interpreted.
    records:
        Source rows represented as dictionaries of strings.
    columns:
        Column names available in ``records``.
    weight_column:
        Optional column containing source weights.
    geography_columns:
        Columns that locate records geographically.
    id_columns:
        Columns that identify source records within the sample.
    metadata:
        Additional source-specific summary values.
    """

    level: SeedLevel
    source_format: str
    records: tuple[dict[str, str], ...]
    columns: tuple[str, ...]
    weight_column: str | None
    geography_columns: tuple[str, ...]
    id_columns: tuple[str, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    def as_summary(self) -> dict[str, object]:
        """Return a compact, JSON-serializable summary of the sample."""

        summary = {
            "level": self.level,
            "source_format": self.source_format,
            "records": len(self.records),
            "columns": list(self.columns),
            "weight_column": self.weight_column,
            "geography_columns": list(self.geography_columns),
            "id_columns": list(self.id_columns),
        }
        summary.update(self.metadata)
        return summary


@dataclass(frozen=True)
class TreeColumnBlockSpec:
    """A named set of target and conditioning columns for tree workflows.

    Blocks are teaching and workflow aids: they group plausible target and
    conditioning columns for supported source formats without hiding the final
    modelling decision from the caller.
    """

    name: str
    level: SeedLevel
    target_columns: tuple[str, ...]
    conditioning_columns: tuple[str, ...]


@dataclass(frozen=True)
class TreeColumnSuggestionProfile:
    """Column-role suggestions for a known source microdata format.

    A profile records known geography, identifier, weight, replicate-weight,
    derived, and block columns for a source adapter. It is used to produce
    reviewable suggestions rather than silently choosing a model design.
    """

    source_format: str
    geography_columns: tuple[str, ...]
    identifier_columns: tuple[str, ...]
    weight_columns: tuple[str, ...]
    replicate_weight_prefixes: tuple[str, ...]
    derived_columns: tuple[str, ...]
    blocks: tuple[TreeColumnBlockSpec, ...]


_STATCAN_2016_HIERARCHICAL_TREE_PROFILE = TreeColumnSuggestionProfile(
    source_format="statcan-2016-hierarchical",
    geography_columns=("PR", "CMA"),
    identifier_columns=("HH_ID", "EF_ID", "CF_ID", "PP_ID"),
    weight_columns=("WEIGHT",),
    replicate_weight_prefixes=("WT",),
    derived_columns=("household_size",),
    blocks=(
        TreeColumnBlockSpec(
            name="household_core",
            level="household",
            target_columns=(
                "household_size",
                "TENUR",
                "DTYPE",
                "ROOM",
                "BEDRM",
                "CONDO",
                "PRESMORTG",
                "VALUE",
                "SHELCO",
                "SUBSIDY",
                "REPAIR",
                "BUILT",
            ),
            conditioning_columns=("PR",),
        ),
        TreeColumnBlockSpec(
            name="person_demographics",
            level="person",
            target_columns=("AGEGRP", "SEX", "MarStH", "IMMSTAT"),
            conditioning_columns=("PR", "household_size", "TENUR"),
        ),
        TreeColumnBlockSpec(
            name="person_identity_language",
            level="person",
            target_columns=(
                "CITIZEN",
                "GENSTAT",
                "POB",
                "VISMIN",
                "MTNEn",
                "MTNFr",
                "MTNNO",
                "HLBEN",
                "HLBFR",
                "HLBNO",
            ),
            conditioning_columns=("PR", "household_size", "TENUR", "AGEGRP", "SEX"),
        ),
        TreeColumnBlockSpec(
            name="person_education_work_income",
            level="person",
            target_columns=(
                "HDGREE",
                "LFTAG",
                "EMPIN",
                "FPTWK",
                "HRSWRK",
                "WKSWRK",
                "WRKACT",
                "TOTINC",
            ),
            conditioning_columns=("PR", "household_size", "TENUR", "AGEGRP", "SEX"),
        ),
    ),
)

_TREE_COLUMN_SUGGESTION_PROFILES = {
    _STATCAN_2016_HIERARCHICAL_TREE_PROFILE.source_format: (
        _STATCAN_2016_HIERARCHICAL_TREE_PROFILE
    )
}


def read_fixture_seed_sample(
    path: Path,
    *,
    level: SeedLevel,
    weight_column: str | None,
    geography_columns: tuple[str, ...],
    id_columns: tuple[str, ...],
) -> SeedSample:
    """Read a small fixture CSV as a seed sample.

    This adapter is mainly for examples, tests, and teaching workflows where
    column roles are supplied directly by the caller. It performs only column
    validation; it does not infer census-specific roles.
    """

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_columns(
        columns,
        required=tuple(
            column
            for column in (*geography_columns, *id_columns, weight_column)
            if column
        ),
    )
    return SeedSample(
        level=level,
        source_format="fixture-v1",
        records=records,
        columns=columns,
        weight_column=weight_column,
        geography_columns=geography_columns,
        id_columns=id_columns,
    )


def read_statcan_2016_hierarchical_seed_sample(path: Path) -> SeedSample:
    """Read a Statistics Canada 2016 hierarchical microdata extract.

    The returned sample is person-level and records known identifier columns,
    the ``WEIGHT`` column, household counts, person counts, and a basic
    duplicate-person-ID check in its metadata.
    """

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_columns(columns, required=("HH_ID", "EF_ID", "CF_ID", "PP_ID", "WEIGHT"))
    household_ids = [record["HH_ID"] for record in records if record.get("HH_ID")]
    person_ids = [record["PP_ID"] for record in records if record.get("PP_ID")]
    household_count = len(set(household_ids))
    person_count = len(records)
    duplicate_person_ids = sum(
        count - 1 for count in Counter(person_ids).values() if count > 1
    )
    average_household_size = (
        round(person_count / household_count, 4) if household_count else 0
    )

    return SeedSample(
        level="person",
        source_format="statcan-2016-hierarchical",
        records=records,
        columns=columns,
        weight_column="WEIGHT",
        geography_columns=(),
        id_columns=("PP_ID",),
        metadata={
            "household_id_column": "HH_ID",
            "economic_family_id_column": "EF_ID",
            "census_family_id_column": "CF_ID",
            "person_id_column": "PP_ID",
            "households": household_count,
            "people": person_count,
            "average_household_size": average_household_size,
            "duplicate_person_ids": duplicate_person_ids,
        },
    )


def export_seed_rows(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Select seed columns for IPF or simple synthetic-population examples.

    The returned tuple contains output rows and a JSON-serializable manifest.
    Identifier, geography, derived household-size, and weight columns are kept
    when they are known on the input sample.
    """

    if not columns:
        raise ValueError("at least one seed column is required")
    validate_columns(sample.columns, required=columns)

    derived_columns = ("household_size",) if "household_size" in sample.columns else ()
    output_columns = unique_columns(
        (
            *sample.id_columns,
            *sample.geography_columns,
            *columns,
            *derived_columns,
            sample.weight_column,
        )
    )
    rows = [
        {column: record.get(column, "") for column in output_columns}
        for record in sample.records
    ]
    return rows, {
        "source_format": sample.source_format,
        "level": sample.level,
        "rows_read": len(sample.records),
        "rows_written": len(rows),
        "columns": list(output_columns),
        "selected_columns": list(columns),
        "id_columns": list(sample.id_columns),
        "geography_columns": list(sample.geography_columns),
        "weight_column": sample.weight_column,
    }


def export_training_rows(
    sample: SeedSample,
    *,
    level: SeedLevel,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Export a tree-training view from a supported seed sample.

    This dispatches to the supported source-specific household or person export
    routine. It returns rows plus a manifest describing source format, level,
    selected columns, identifiers, and weight column.
    """

    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("training export requires statcan-2016-hierarchical")
    if not target_columns:
        raise ValueError("at least one target column is required")
    if not conditioning_columns:
        raise ValueError("at least one conditioning column is required")
    if level == "person":
        return export_statcan_2016_person_training_rows(
            sample,
            target_columns=target_columns,
            conditioning_columns=conditioning_columns,
        )
    return export_statcan_2016_household_training_rows(
        sample,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
    )


def export_statcan_2016_person_training_rows(
    sample: SeedSample,
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Export person-level training rows from 2016 hierarchical microdata.

    ``household_size`` may be requested even though it is not a source column;
    it is derived from the number of persons sharing each ``HH_ID``.
    """

    validate_columns(sample.columns, required=("PP_ID", "HH_ID", "WEIGHT"))
    source_columns = tuple(
        column
        for column in (*conditioning_columns, *target_columns)
        if column != "household_size"
    )
    validate_columns(sample.columns, required=source_columns)

    household_sizes = household_size_lookup(sample.records)
    output_columns = unique_columns(
        ("PP_ID", "HH_ID", *conditioning_columns, *target_columns, "WEIGHT")
    )
    rows = [
        {
            column: training_value(
                record,
                column,
                household_sizes=household_sizes,
            )
            for column in output_columns
        }
        for record in sample.records
    ]
    return rows, training_export_summary(
        sample,
        level="person",
        rows_written=len(rows),
        output_columns=output_columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        id_columns=("PP_ID", "HH_ID"),
    )


def export_statcan_2016_household_training_rows(
    sample: SeedSample,
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Export one household-level training row per household ID.

    Household-level source columns must be constant within each household. Use
    :func:`check_statcan_2016_household_seed_columns` before exporting when
    preparing a model design interactively.
    """

    selected_columns = unique_columns((*conditioning_columns, *target_columns))
    household_sample = derive_statcan_2016_household_seed_sample(
        sample,
        columns=tuple(
            column for column in selected_columns if column != "household_size"
        ),
    )
    output_columns = unique_columns(
        ("HH_ID", *conditioning_columns, *target_columns, "WEIGHT")
    )
    rows = [
        {column: record[column] for column in output_columns}
        for record in household_sample.records
    ]
    return rows, training_export_summary(
        sample,
        level="household",
        rows_written=len(rows),
        output_columns=output_columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        id_columns=("HH_ID",),
    )


def training_export_summary(
    sample: SeedSample,
    *,
    level: SeedLevel,
    rows_written: int,
    output_columns: tuple[str, ...],
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    id_columns: tuple[str, ...],
) -> dict[str, object]:
    return {
        "source_format": sample.source_format,
        "level": level,
        "rows_read": len(sample.records),
        "rows_written": rows_written,
        "columns": list(output_columns),
        "target_columns": list(target_columns),
        "conditioning_columns": list(conditioning_columns),
        "id_columns": list(id_columns),
        "weight_column": "WEIGHT",
    }


def derive_statcan_2016_household_seed_sample(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> SeedSample:
    """Derive household seed records from person-level hierarchical rows.

    One output record is produced per ``HH_ID``. Selected household columns and
    ``WEIGHT`` must be constant within the household; ``household_size`` is
    derived from the number of person rows.
    """

    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("household derivation requires statcan-2016-hierarchical")
    if not columns:
        raise ValueError("at least one household column is required")
    validate_columns(sample.columns, required=("HH_ID", "WEIGHT", *columns))

    records_by_household = group_records_by_household(sample.records)

    household_records: list[dict[str, str]] = []
    for household_id, records in records_by_household.items():
        household_record = {"HH_ID": household_id}
        for column in columns:
            household_record[column] = unique_household_value(
                records,
                column,
                household_id,
                "household column",
            )
        household_record["household_size"] = str(len(records))
        household_record["WEIGHT"] = unique_household_value(
            records,
            "WEIGHT",
            household_id,
            "household weight",
        )
        household_records.append(household_record)

    return SeedSample(
        level="household",
        source_format=sample.source_format,
        records=tuple(household_records),
        columns=("HH_ID", *columns, "household_size", "WEIGHT"),
        weight_column="WEIGHT",
        geography_columns=(),
        id_columns=("HH_ID",),
        metadata={
            "households": len(household_records),
            "people": len(sample.records),
            "derivation": "one row per HH_ID with constant selected household columns",
        },
    )


def check_statcan_2016_household_seed_columns(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> dict[str, object]:
    """Check whether selected columns are constant within each household.

    The report is JSON-serializable and includes one check per requested column,
    plus checks for ``WEIGHT`` and derived ``household_size``.
    """

    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("household seed checks require statcan-2016-hierarchical")
    if not columns:
        raise ValueError("at least one household column is required")
    validate_columns(sample.columns, required=("HH_ID", "WEIGHT", *columns))

    records_by_household = group_records_by_household(sample.records)
    checks = [
        household_column_check(records_by_household, column) for column in columns
    ]
    checks.append(household_column_check(records_by_household, "WEIGHT", role="weight"))
    checks.append(
        {
            "column": "household_size",
            "role": "derived",
            "status": "ok",
            "detail": "derived from row count per HH_ID",
            "problem_households": 0,
        }
    )

    return {
        "source_format": sample.source_format,
        "level": "household",
        "households": len(records_by_household),
        "people": len(sample.records),
        "passed": all(check["status"] == "ok" for check in checks),
        "checks": checks,
    }


def suggest_tree_column_blocks(sample: SeedSample) -> dict[str, object]:
    """Suggest tree-model column blocks for a known source format.

    Suggestions are source-aware but not authoritative. They are intended to
    start a model-design review by naming available blocks, missing columns, and
    excluded identifiers or replicate weights.
    """

    profile = _TREE_COLUMN_SUGGESTION_PROFILES.get(sample.source_format)
    if profile is None:
        raise ValueError(
            f"tree column suggestions are not available for {sample.source_format}"
        )

    columns = set(sample.columns)
    available = columns | set(profile.derived_columns)

    return {
        "source_format": sample.source_format,
        "profile": profile.source_format,
        "geography_columns": available_columns(profile.geography_columns, columns),
        "excluded_columns": excluded_tree_columns(sample.columns, profile),
        "blocks": [
            tree_column_block(
                block,
                available,
            )
            for block in profile.blocks
        ],
    }


def resolve_tree_column_block_pair(
    sample: SeedSample,
    *,
    household_block: str,
    person_block: str,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    dict[str, object],
]:
    """Resolve named household and person column blocks into column tuples.

    Returns household targets, household conditioning columns, person targets,
    person conditioning columns, and a design report. The report highlights
    feasibility issues that should be reviewed before training linked models.
    """

    suggestion = suggest_tree_column_blocks(sample)
    suggested_household_block = find_suggested_tree_column_block(
        suggestion,
        name=household_block,
        level="household",
    )
    suggested_person_block = find_suggested_tree_column_block(
        suggestion,
        name=person_block,
        level="person",
    )
    return (
        require_suggested_tree_columns(suggested_household_block, "target_columns"),
        require_suggested_tree_columns(
            suggested_household_block,
            "conditioning_columns",
        ),
        require_suggested_tree_columns(suggested_person_block, "target_columns"),
        require_suggested_tree_columns(suggested_person_block, "conditioning_columns"),
        {
            "mode": "profile",
            "profile": suggestion["profile"],
            "household_block": household_block,
            "person_block": person_block,
        },
    )


def build_tree_geography_feasibility_report(
    sample: SeedSample,
    *,
    geography_column: str,
    household_block: str = "household_core",
    person_block: str = "person_demographics",
    likely_person_rows: int = 10_000,
    likely_household_rows: int = 4_000,
    borderline_person_rows: int = 2_500,
    borderline_household_rows: int = 1_000,
    min_support: float = 50,
    max_purity: float = 0.95,
) -> dict[str, object]:
    """Assess which geographies have enough support for tree modelling.

    The report compares person and household row counts, condition-group
    support, and dominant-outcome purity so users can avoid modelling very
    sparse or identifying subsets.
    """

    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError(
            "tree geography feasibility requires statcan-2016-hierarchical"
        )
    validate_columns(sample.columns, required=(geography_column,))
    (
        household_target_columns,
        household_conditioning_columns,
        person_target_columns,
        person_conditioning_columns,
        column_source,
    ) = resolve_tree_column_block_pair(
        sample,
        household_block=household_block,
        person_block=person_block,
    )

    household_sizes = household_size_lookup(sample.records)
    household_records = household_records_for_feasibility(
        sample,
        geography_column=geography_column,
        household_sizes=household_sizes,
        columns=unique_columns(
            (
                geography_column,
                *household_conditioning_columns,
                *household_target_columns,
            )
        ),
    )
    person_records = person_records_for_feasibility(
        sample,
        geography_column=geography_column,
        household_sizes=household_sizes,
        columns=unique_columns(
            (
                geography_column,
                *person_conditioning_columns,
                *person_target_columns,
            )
        ),
    )

    regions = sorted(
        (
            geography_feasibility_region(
                geography,
                household_records=[
                    row
                    for row in household_records
                    if row.get(geography_column, "") == geography
                ],
                person_records=[
                    row
                    for row in person_records
                    if row.get(geography_column, "") == geography
                ],
                geography_column=geography_column,
                household_conditioning_columns=household_conditioning_columns,
                household_target_columns=household_target_columns,
                person_conditioning_columns=person_conditioning_columns,
                person_target_columns=person_target_columns,
                likely_person_rows=likely_person_rows,
                likely_household_rows=likely_household_rows,
                borderline_person_rows=borderline_person_rows,
                borderline_household_rows=borderline_household_rows,
                min_support=min_support,
                max_purity=max_purity,
            )
            for geography in sorted(
                {
                    row.get(geography_column, "")
                    for row in sample.records
                    if row.get(geography_column, "")
                }
            )
        ),
        key=lambda region: (-int(region["person_rows"]), str(region["geography"])),
    )

    return {
        "source_format": sample.source_format,
        "geography_column": geography_column,
        "column_source": column_source,
        "thresholds": {
            "likely_person_rows": likely_person_rows,
            "likely_household_rows": likely_household_rows,
            "borderline_person_rows": borderline_person_rows,
            "borderline_household_rows": borderline_household_rows,
            "min_support": min_support,
            "max_purity": max_purity,
        },
        "regions": regions,
    }


def household_records_for_feasibility(
    sample: SeedSample,
    *,
    geography_column: str,
    household_sizes: dict[str, str],
    columns: tuple[str, ...],
) -> list[dict[str, str]]:
    records_by_household = group_records_by_household(sample.records)
    output: list[dict[str, str]] = []
    for household_id, records in records_by_household.items():
        row = {
            "HH_ID": household_id,
            "WEIGHT": unique_household_value(
                records,
                "WEIGHT",
                household_id,
                "household weight",
            ),
        }
        for column in columns:
            if column == "household_size":
                row[column] = household_sizes[household_id]
            else:
                row[column] = unique_household_value(
                    records,
                    column,
                    household_id,
                    "household feasibility column",
                )
        if row.get(geography_column, ""):
            output.append(row)
    return output


def person_records_for_feasibility(
    sample: SeedSample,
    *,
    geography_column: str,
    household_sizes: dict[str, str],
    columns: tuple[str, ...],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for record in sample.records:
        if not record.get(geography_column, ""):
            continue
        row = {
            "PP_ID": record["PP_ID"],
            "HH_ID": record["HH_ID"],
            "WEIGHT": record["WEIGHT"],
        }
        for column in columns:
            row[column] = training_value(
                record,
                column,
                household_sizes=household_sizes,
            )
        output.append(row)
    return output


def geography_feasibility_region(
    geography: str,
    *,
    household_records: list[dict[str, str]],
    person_records: list[dict[str, str]],
    geography_column: str,
    household_conditioning_columns: tuple[str, ...],
    household_target_columns: tuple[str, ...],
    person_conditioning_columns: tuple[str, ...],
    person_target_columns: tuple[str, ...],
    likely_person_rows: int,
    likely_household_rows: int,
    borderline_person_rows: int,
    borderline_household_rows: int,
    min_support: float,
    max_purity: float,
) -> dict[str, object]:
    household_risk = support_and_purity_summary(
        household_records,
        conditioning_columns=columns_except(
            household_conditioning_columns,
            geography_column,
        ),
        target_columns=household_target_columns,
    )
    person_risk = support_and_purity_summary(
        person_records,
        conditioning_columns=columns_except(
            person_conditioning_columns,
            geography_column,
        ),
        target_columns=person_target_columns,
    )
    reasons = feasibility_reasons(
        person_rows=len(person_records),
        household_rows=len(household_records),
        household_risk=household_risk,
        person_risk=person_risk,
        likely_person_rows=likely_person_rows,
        likely_household_rows=likely_household_rows,
        borderline_person_rows=borderline_person_rows,
        borderline_household_rows=borderline_household_rows,
        min_support=min_support,
        max_purity=max_purity,
    )
    tier = feasibility_tier(
        reasons,
        person_rows=len(person_records),
        household_rows=len(household_records),
        likely_person_rows=likely_person_rows,
        likely_household_rows=likely_household_rows,
    )
    return {
        "geography": geography,
        "person_rows": len(person_records),
        "household_rows": len(household_records),
        "weighted_persons": round(weighted_total(person_records), 4),
        "weighted_households": round(weighted_total(household_records), 4),
        "household_condition_groups": household_risk["groups"],
        "person_condition_groups": person_risk["groups"],
        "household_min_support": household_risk["minimum_support"],
        "person_min_support": person_risk["minimum_support"],
        "household_max_purity": household_risk["maximum_purity"],
        "person_max_purity": person_risk["maximum_purity"],
        "tier": tier,
        "reasons": reasons,
        "suggested_action": suggested_feasibility_action(tier),
        "model_design": model_design_advice(
            tier=tier,
            geography=geography,
            geography_column=geography_column,
            reasons=reasons,
            household_records=household_records,
            person_records=person_records,
            household_target_columns=household_target_columns,
            person_target_columns=person_target_columns,
            household_conditioning_columns=household_conditioning_columns,
            person_conditioning_columns=person_conditioning_columns,
        ),
    }


def support_and_purity_summary(
    rows: list[dict[str, str]],
    *,
    conditioning_columns: tuple[str, ...],
    target_columns: tuple[str, ...],
) -> dict[str, object]:
    if not rows:
        return {"groups": 0, "minimum_support": 0.0, "maximum_purity": 0.0}
    grouped: dict[tuple[str, ...], dict[tuple[str, ...], float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for row in rows:
        condition_key = tuple(row[column] for column in conditioning_columns)
        target_key = tuple(row[column] for column in target_columns)
        grouped[condition_key][target_key] += float(row.get("WEIGHT", "1") or 1)
    supports = [sum(outcomes.values()) for outcomes in grouped.values()]
    purities = [
        max(outcomes.values()) / sum(outcomes.values())
        for outcomes in grouped.values()
        if sum(outcomes.values()) > 0
    ]
    return {
        "groups": len(grouped),
        "minimum_support": round(min(supports), 4),
        "maximum_purity": round(max(purities, default=0.0), 4),
    }


def feasibility_reasons(
    *,
    person_rows: int,
    household_rows: int,
    household_risk: dict[str, object],
    person_risk: dict[str, object],
    likely_person_rows: int,
    likely_household_rows: int,
    borderline_person_rows: int,
    borderline_household_rows: int,
    min_support: float,
    max_purity: float,
) -> list[str]:
    reasons: list[str] = []
    if person_rows < borderline_person_rows:
        reasons.append("too few person rows")
    elif person_rows < likely_person_rows:
        reasons.append("limited person rows")
    if household_rows < borderline_household_rows:
        reasons.append("too few household rows")
    elif household_rows < likely_household_rows:
        reasons.append("limited household rows")
    if float(household_risk["minimum_support"]) < min_support:
        reasons.append("household conditioning support below threshold")
    if float(person_risk["minimum_support"]) < min_support:
        reasons.append("person conditioning support below threshold")
    if float(household_risk["maximum_purity"]) > max_purity:
        reasons.append("household outcome purity above threshold")
    if float(person_risk["maximum_purity"]) > max_purity:
        reasons.append("person outcome purity above threshold")
    return reasons


def feasibility_tier(
    reasons: list[str],
    *,
    person_rows: int,
    household_rows: int,
    likely_person_rows: int,
    likely_household_rows: int,
) -> str:
    if any(reason.startswith("too few") for reason in reasons):
        return "unlikely"
    if any("threshold" in reason for reason in reasons):
        return "unlikely"
    if any("purity" in reason for reason in reasons):
        return "unlikely"
    if person_rows >= likely_person_rows and household_rows >= likely_household_rows:
        return "likely"
    return "borderline"


def suggested_feasibility_action(tier: str) -> str:
    if tier == "likely":
        return "candidate for full block review"
    if tier == "borderline":
        return "coarsen targets or review before training"
    return "aggregate geography or use a simpler model"


def model_design_advice(
    *,
    tier: str,
    geography: str,
    geography_column: str,
    reasons: list[str],
    household_records: list[dict[str, str]],
    person_records: list[dict[str, str]],
    household_target_columns: tuple[str, ...],
    person_target_columns: tuple[str, ...],
    household_conditioning_columns: tuple[str, ...],
    person_conditioning_columns: tuple[str, ...],
) -> dict[str, object]:
    household_review = columns_to_review(
        household_records,
        household_target_columns,
        preferred_review_columns=(
            "VALUE",
            "SHELCO",
            "ROOM",
            "BEDRM",
            "PRESMORTG",
            "SUBSIDY",
        ),
    )
    person_review = columns_to_review(
        person_records,
        person_target_columns,
        preferred_review_columns=("IMMSTAT", "MarStH"),
    )
    if tier == "likely":
        return {
            "scope": "separate_geography_model",
            "block_strategy": "use_requested_blocks",
            "household_targets": list(household_target_columns),
            "person_targets": list(person_target_columns),
            "conditioning_columns": sorted(
                set(household_conditioning_columns) | set(person_conditioning_columns)
            ),
            "columns_to_review_first": household_review + person_review,
            "aggregation_hint": "",
            "next_steps": [
                "Train and audit this geography separately.",
                "Run release audit before packaging or sharing.",
                "Compare generated distributions against census controls.",
            ],
        }
    if tier == "borderline":
        return {
            "scope": "separate_geography_model_with_coarsening",
            "block_strategy": "start_with_reduced_blocks",
            "household_targets": reduced_household_targets(household_target_columns),
            "person_targets": reduced_person_targets(person_target_columns),
            "conditioning_columns": reduced_conditioning_columns(
                household_conditioning_columns,
                person_conditioning_columns,
                geography_column=geography_column,
            ),
            "columns_to_review_first": household_review + person_review,
            "aggregation_hint": canadian_aggregation_hint(geography_column, geography),
            "next_steps": [
                "Try a reduced target set before training the full block.",
                (
                    "Coarsen household size and dwelling/economic categories "
                    "if audit fails."
                ),
                "Aggregate with a neighbouring region if support remains low.",
            ],
        }
    return {
        "scope": "aggregate_geography_model",
        "block_strategy": "minimal_or_aggregate",
        "household_targets": minimal_household_targets(household_target_columns),
        "person_targets": minimal_person_targets(person_target_columns),
        "conditioning_columns": reduced_conditioning_columns(
            household_conditioning_columns,
            person_conditioning_columns,
            geography_column=geography_column,
        ),
        "columns_to_review_first": household_review + person_review,
        "aggregation_hint": canadian_aggregation_hint(geography_column, geography),
        "next_steps": [
            "Do not publish a rich separate model without manual review.",
            "Prefer an aggregate geography model or a much simpler target set.",
            "Use external census margins to calibrate outputs after generation.",
        ],
    }


def columns_to_review(
    rows: list[dict[str, str]],
    target_columns: tuple[str, ...],
    *,
    preferred_review_columns: tuple[str, ...],
) -> list[str]:
    if not rows:
        return list(preferred_review_columns)
    review: list[str] = [
        column for column in preferred_review_columns if column in target_columns
    ]
    for column in target_columns:
        distinct_values = {row.get(column, "") for row in rows}
        if len(distinct_values) > max(3, len(rows) // 4) and column not in review:
            review.append(column)
    return review


def reduced_household_targets(target_columns: tuple[str, ...]) -> list[str]:
    preferred = ("household_size", "TENUR", "DTYPE", "ROOM", "BEDRM")
    return [column for column in preferred if column in target_columns]


def reduced_person_targets(target_columns: tuple[str, ...]) -> list[str]:
    preferred = ("AGEGRP", "SEX", "MarStH")
    return [column for column in preferred if column in target_columns]


def minimal_household_targets(target_columns: tuple[str, ...]) -> list[str]:
    preferred = ("household_size", "TENUR")
    return [column for column in preferred if column in target_columns]


def minimal_person_targets(target_columns: tuple[str, ...]) -> list[str]:
    preferred = ("AGEGRP", "SEX")
    return [column for column in preferred if column in target_columns]


def reduced_conditioning_columns(
    household_conditioning_columns: tuple[str, ...],
    person_conditioning_columns: tuple[str, ...],
    *,
    geography_column: str,
) -> list[str]:
    preferred = (geography_column, "household_size", "TENUR")
    available = set(household_conditioning_columns) | set(person_conditioning_columns)
    return [column for column in preferred if column in available]


def canadian_aggregation_hint(geography_column: str, geography: str) -> str:
    if geography_column == "PR":
        if geography == "11":
            return "Use an Atlantic aggregate or national/province-family model."
        if geography == "70":
            return "Use a territories or northern aggregate model."
        if geography in {"10", "12", "13"}:
            return "Review as an Atlantic province; aggregate if audit fails."
    if geography_column == "CMA":
        if geography == "999":
            return "Treat as non-CMA/rest-of-region, not a single agglomeration."
        return "Use only for the large CMA codes exposed by the PUMF."
    return "Aggregate with a larger census geography if audit support is weak."


def columns_except(columns: tuple[str, ...], excluded: str) -> tuple[str, ...]:
    return tuple(column for column in columns if column != excluded)


def weighted_total(rows: list[dict[str, str]]) -> float:
    return sum(float(row.get("WEIGHT", "0") or 0) for row in rows)


def find_suggested_tree_column_block(
    suggestion: dict[str, object],
    *,
    name: str,
    level: str,
) -> dict[str, object]:
    blocks = suggestion["blocks"]
    if not isinstance(blocks, list):
        raise ValueError("tree column suggestion blocks must be a list")
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("name") == name:
            if block.get("level") != level:
                raise ValueError(f"suggested block {name!r} is not a {level} block")
            return block
    raise ValueError(f"suggested {level} block {name!r} was not found")


def require_suggested_tree_columns(
    block: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    value = block[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"suggested block {block.get('name')!r} has invalid {key}")
    if not value:
        raise ValueError(f"suggested block {block.get('name')!r} has no {key}")
    return tuple(value)


def tree_column_block(
    block: TreeColumnBlockSpec,
    available: set[str],
) -> dict[str, object]:
    available_targets = [
        column for column in block.target_columns if column in available
    ]
    missing_targets = [
        column for column in block.target_columns if column not in available
    ]
    return {
        "name": block.name,
        "level": block.level,
        "target_columns": available_targets,
        "conditioning_columns": available_columns(
            block.conditioning_columns,
            available,
        ),
        "available_target_columns": available_targets,
        "missing_target_columns": missing_targets,
    }


def available_columns(candidates: tuple[str, ...], columns: set[str]) -> list[str]:
    return [column for column in candidates if column in columns]


def excluded_tree_columns(
    columns: tuple[str, ...],
    profile: TreeColumnSuggestionProfile,
) -> list[dict[str, str]]:
    excluded: list[dict[str, str]] = []
    for column in columns:
        if column in profile.identifier_columns:
            excluded.append({"column": column, "reason": "identifier"})
        elif column in profile.weight_columns:
            excluded.append({"column": column, "reason": "weight"})
        elif is_replicate_weight_column(column, profile):
            excluded.append({"column": column, "reason": "replicate_weight"})
    return excluded


def is_replicate_weight_column(
    column: str,
    profile: TreeColumnSuggestionProfile,
) -> bool:
    return any(
        column.startswith(prefix) and column.removeprefix(prefix).isdigit()
        for prefix in profile.replicate_weight_prefixes
    )


def group_records_by_household(
    records: tuple[dict[str, str], ...],
) -> dict[str, list[dict[str, str]]]:
    records_by_household: dict[str, list[dict[str, str]]] = {}
    for record in records:
        household_id = record.get("HH_ID", "")
        if not household_id:
            raise ValueError("household derivation requires non-empty HH_ID values")
        records_by_household.setdefault(household_id, []).append(record)
    return records_by_household


def household_size_lookup(records: tuple[dict[str, str], ...]) -> dict[str, str]:
    return {
        household_id: str(len(household_records))
        for household_id, household_records in group_records_by_household(
            records
        ).items()
    }


def training_value(
    record: dict[str, str],
    column: str,
    *,
    household_sizes: dict[str, str],
) -> str:
    if column == "household_size":
        return household_sizes[record["HH_ID"]]
    return record[column]


def household_column_check(
    records_by_household: dict[str, list[dict[str, str]]],
    column: str,
    *,
    role: str = "selected household column",
) -> dict[str, object]:
    problem_households = sum(
        1
        for records in records_by_household.values()
        if len({record.get(column, "") for record in records}) != 1
    )
    status = "problem" if problem_households else "ok"
    if problem_households:
        detail = f"varies within {problem_households:,} "
        detail += "household" if problem_households == 1 else "households"
    else:
        detail = "constant within each HH_ID"
    return {
        "column": column,
        "role": role,
        "status": status,
        "detail": detail,
        "problem_households": problem_households,
    }


def unique_household_value(
    records: list[dict[str, str]],
    column: str,
    household_id: str,
    label: str,
) -> str:
    values = {record.get(column, "") for record in records}
    if len(values) != 1:
        raise ValueError(f"conflicting {label} {column!r} for HH_ID {household_id!r}")
    return next(iter(values))


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def unique_columns(columns: tuple[str | None, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for column in columns:
        if column and column not in output:
            output.append(column)
    return tuple(output)
