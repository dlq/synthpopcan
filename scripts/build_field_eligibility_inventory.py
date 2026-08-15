"""Build the reviewed pre-1.0 hierarchical PUMF field inventory.

The inventory is deliberately evidence, not a new model profile.  It joins
locally acquired public-use CSV headers and Statistics Canada metadata to the
column roles that SynthPopCan currently exposes, then records an explicit
decision for every 2016 and 2021 hierarchical PUMF field.

Run from the repository root::

    uv run python scripts/build_field_eligibility_inventory.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from synthpopcan.microdata import SeedSample, resolve_tree_column_block_pair

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/_static/hierarchical-pumf-field-eligibility-v1.json"
REVIEW_DATE = "2026-08-15"
REVIEWER = "SynthPopCan maintainers"
RARE_THRESHOLD = 50


@dataclass(frozen=True)
class SourceSpec:
    """One locally acquired hierarchical PUMF source and its public metadata."""

    vintage: int
    source_format: str
    csv_path: Path
    metadata_path: Path
    spss_path: Path
    spss_encoding: str


SOURCES = (
    SourceSpec(
        vintage=2016,
        source_format="statcan-2016-hierarchical",
        csv_path=ROOT
        / "data/raw/statcan/census/2016/pumf/hierarchical"
        / "data_donnees_2016_hier.csv",
        metadata_path=ROOT
        / "data/raw/statcan/census/2016/metadata/pumf/hierarchical"
        / "variable-labels.json",
        spss_path=ROOT
        / "data/raw/statcan/census/2016/metadata/pumf/hierarchical"
        / "2016 Hierarchical PUMF SPSS EN.sps",
        spss_encoding="cp1252",
    ),
    SourceSpec(
        vintage=2021,
        source_format="statcan-2021-hierarchical",
        csv_path=ROOT
        / "data/raw/statcan/census/2021/pumf/hierarchical"
        / "data_donnees_2021_hier_v2.csv",
        metadata_path=ROOT
        / "data/raw/statcan/census/2021/metadata/pumf/hierarchical"
        / "variable-labels.json",
        spss_path=ROOT
        / "data/raw/statcan/census/2021/metadata/pumf/hierarchical"
        / "PUMF2021_Hierarchical_spss_en.sps",
        spss_encoding="utf-8-sig",
    ),
)

EntityLevel = Literal[
    "household",
    "economic_family",
    "census_family",
    "person",
    "geography",
    "identifier",
    "weight",
]

IDENTIFIERS = frozenset({"HH_ID", "EF_ID", "CF_ID", "PP_ID"})
GEOGRAPHIES = frozenset({"PR", "CMA"})
HOUSEHOLD_FIELDS = frozenset(
    {
        "BEDRM",
        "BUILT",
        "CONDO",
        "DTYPE",
        "FCOND",
        "HCORENEED_IND",
        "NOS",
        "PRESMORTG",
        "REPAIR",
        "ROOM",
        "SHELCO",
        "STIR_GRP",
        "SUBSIDY",
        "TENUR",
        "VALUE",
    }
)
ECONOMIC_FAMILY_FIELDS = frozenset(
    {
        "EFCOVID_ERB",
        "EFDECILE",
        "EFDIMBM",
        "EFDIMBM_2018",
        "LOLICOA",
        "LOLICOB",
        "LOLIMA",
        "LOLIMB",
        "LOMBM",
        "LOMBM_2018",
    }
)
CENSUS_FAMILY_FIELDS = frozenset({"CFSTRUCT"})
QUANTITATIVE_FIELDS = frozenset(
    {
        "EFCOVID_ERB",
        "EFDIMBM",
        "EFDIMBM_2018",
        "EMPIN",
        "FCOND",
        "GTRFS",
        "INCTAX",
        "MRKINC",
        "SHELCO",
        "TOTINC",
        "TOTINC_AT",
        "VALUE",
    }
)
ORDERED_BAND_FIELDS = frozenset(
    {
        "AGEGRP",
        "AGEIMM",
        "BEDRM",
        "BUILT",
        "DIST",
        "DUR",
        "EFDECILE",
        "HRSWRK",
        "LEAVE",
        "PWDUR",
        "PWLEAVE",
        "ROOM",
        "STIR_GRP",
        "WKSWRK",
        "YRIM",
        "YRIMM",
    }
)
COMPONENT_INDICATOR_FIELDS = frozenset(
    {
        "HLAEN",
        "HLAFR",
        "HLBEN",
        "HLBFR",
        "HLMOSTEN",
        "HLMOSTFR",
        "HLREGEN",
        "HLREGFR",
        "LWAEN",
        "LWAFR",
        "LWBEN",
        "LWBFR",
        "LWMOSTEN",
        "LWMOSTFR",
        "LWREGEN",
        "LWREGFR",
        "MTNEN",
        "MTNFR",
    }
)

# Statistics Canada documents these quantitative special values separately
# from the SPSS VALUE LABELS section.  Codes are field-specific: for example,
# disposable MBM income is defined for all persons and has no not-applicable
# code, while individual income variables use one for people under age 15.
QUANTITATIVE_SPECIAL_CODES: dict[str, dict[str, list[str]]] = {
    "EFCOVID_ERB": {
        "missing": ["88888888"],
        "not_applicable": ["99999999"],
    },
    "EFDIMBM": {"missing": ["88888888"], "not_applicable": []},
    "EFDIMBM_2018": {"missing": ["88888888"], "not_applicable": []},
    "EMPIN": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "FCOND": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "GTRFS": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "INCTAX": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "MRKINC": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "SHELCO": {"missing": [], "not_applicable": []},
    "TOTINC": {"missing": ["88888888"], "not_applicable": ["99999999"]},
    "TOTINC_AT": {
        "missing": ["88888888"],
        "not_applicable": ["99999999"],
    },
    "VALUE": {"missing": ["88888888"], "not_applicable": ["99999999"]},
}
SENSITIVE_FIELDS = frozenset(
    {
        "ABOID",
        "BFNMEMB",
        "ETHDER",
        "REGIND",
        "RELIG",
        "VISMIN",
    }
)
FAMILY_RELATION_FIELDS = frozenset({"CF_RP", "EF_RP"})

# Cross-vintage concepts that are not simple case-normalized names.  Keeping an
# explicit relationship prevents a renamed or reclassified variable from being
# represented as definitionally identical.
CROSS_VINTAGE: dict[tuple[int, str], tuple[str, str]] = {
    (2016, "SEX"): ("GENDER", "definition_changed"),
    (2021, "GENDER"): ("SEX", "definition_changed"),
    (2016, "CIP2011"): ("CIP2021", "classification_changed"),
    (2021, "CIP2021"): ("CIP2011", "classification_changed"),
    (2016, "NOCS"): ("NOC21", "classification_changed"),
    (2021, "NOC21"): ("NOCS", "classification_changed"),
    (2016, "YRIMM"): ("YRIM", "renamed"),
    (2021, "YRIM"): ("YRIMM", "renamed"),
    (2016, "EFDIMBM"): ("EFDIMBM_2018", "reference_year_changed"),
    (2021, "EFDIMBM_2018"): ("EFDIMBM", "reference_year_changed"),
    (2016, "LOMBM"): ("LOMBM_2018", "reference_year_changed"),
    (2021, "LOMBM_2018"): ("LOMBM", "reference_year_changed"),
    (2016, "LEAVE"): ("PWLEAVE", "renamed"),
    (2021, "PWLEAVE"): ("LEAVE", "renamed"),
    (2016, "OCC"): ("PWOCC", "renamed"),
    (2021, "PWOCC"): ("OCC", "renamed"),
    (2016, "POBF"): ("POBPAR1", "parent_definition_changed"),
    (2016, "POBM"): ("POBPAR2", "parent_definition_changed"),
    (2021, "POBPAR1"): ("POBF", "parent_definition_changed"),
    (2021, "POBPAR2"): ("POBM", "parent_definition_changed"),
    (2016, "DUR"): ("PWDUR", "renamed"),
    (2021, "PWDUR"): ("DUR", "renamed"),
    (2016, "HLAEN"): ("HLMOSTEN", "question_and_derivation_changed"),
    (2021, "HLMOSTEN"): ("HLAEN", "question_and_derivation_changed"),
    (2016, "HLAFR"): ("HLMOSTFR", "question_and_derivation_changed"),
    (2021, "HLMOSTFR"): ("HLAFR", "question_and_derivation_changed"),
    (2016, "HLANO"): ("HLMOSTNO", "question_and_derivation_changed"),
    (2021, "HLMOSTNO"): ("HLANO", "question_and_derivation_changed"),
    (2016, "HLBEN"): ("HLREGEN", "question_and_derivation_changed"),
    (2021, "HLREGEN"): ("HLBEN", "question_and_derivation_changed"),
    (2016, "HLBFR"): ("HLREGFR", "question_and_derivation_changed"),
    (2021, "HLREGFR"): ("HLBFR", "question_and_derivation_changed"),
    (2016, "HLBNO"): ("HLREGNO", "question_and_derivation_changed"),
    (2021, "HLREGNO"): ("HLBNO", "question_and_derivation_changed"),
    (2016, "LFTAG"): ("LFACT", "classification_changed"),
    (2021, "LFACT"): ("LFTAG", "classification_changed"),
    (2016, "LOLICOA"): ("LICO_AT", "renamed"),
    (2021, "LICO_AT"): ("LOLICOA", "renamed"),
    (2016, "LOLICOB"): ("LICO_BT", "renamed"),
    (2021, "LICO_BT"): ("LOLICOB", "renamed"),
    (2016, "LWAEN"): ("LWMOSTEN", "question_and_derivation_changed"),
    (2021, "LWMOSTEN"): ("LWAEN", "question_and_derivation_changed"),
    (2016, "LWAFR"): ("LWMOSTFR", "question_and_derivation_changed"),
    (2021, "LWMOSTFR"): ("LWAFR", "question_and_derivation_changed"),
    (2016, "LWANO"): ("LWMOSTNO", "question_and_derivation_changed"),
    (2021, "LWMOSTNO"): ("LWANO", "question_and_derivation_changed"),
    (2016, "LWBEN"): ("LWREGEN", "question_and_derivation_changed"),
    (2021, "LWREGEN"): ("LWBEN", "question_and_derivation_changed"),
    (2016, "LWBFR"): ("LWREGFR", "question_and_derivation_changed"),
    (2021, "LWREGFR"): ("LWBFR", "question_and_derivation_changed"),
    (2016, "LWBNO"): ("LWREGNO", "question_and_derivation_changed"),
    (2021, "LWREGNO"): ("LWBNO", "question_and_derivation_changed"),
}


@dataclass
class FieldStats:
    """Bounded sufficient statistics for one source field."""

    observations: int = 0
    missing: int = 0
    not_applicable: int = 0
    weighted_applicable: float = 0.0
    values: Counter[str] = field(default_factory=Counter)
    constant_checks: int = 0
    constant_failures: int = 0
    applicable_constant_checks: int = 0
    applicable_constant_failures: int = 0


def build_inventory() -> dict[str, Any]:
    """Return the complete, deterministic field-eligibility inventory."""

    source_payloads: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    headers_by_vintage: dict[int, tuple[str, ...]] = {}
    targets_by_vintage: dict[int, set[str]] = {}

    for source in SOURCES:
        header = read_header(source.csv_path)
        headers_by_vintage[source.vintage] = header
        metadata = load_metadata(source)
        targets = current_source_targets(source, header)
        targets_by_vintage[source.vintage] = targets
        entities = {name: entity_level(name) for name in header}
        missing_codes = {
            name: classified_missing_codes(name, metadata.get(name, {}))
            for name in header
        }
        stats = scan_source(source.csv_path, header, entities, missing_codes)
        for name in header:
            records.append(
                field_record(
                    source,
                    name,
                    metadata.get(name, {}),
                    stats[name],
                    targets,
                    missing_codes[name],
                )
            )
        source_payloads.append(
            {
                "census_vintage": source.vintage,
                "source_format": source.source_format,
                "ordered_header": list(header),
                "csv_header_sha256": header_sha256(header),
                "source_data_sha256": file_sha256(source.csv_path),
                "metadata_sha256": file_sha256(source.metadata_path),
                "spss_metadata_sha256": file_sha256(source.spss_path),
                "field_count": len(header),
                "metadata_path": repo_path(source.metadata_path),
                "spss_metadata_path": repo_path(source.spss_path),
                "source_data_path": repo_path(source.csv_path),
                "source_data_redistributed": False,
            }
        )

    records.sort(key=lambda item: (item["census_vintage"], item["source_name"]))
    return {
        "schema_version": "synthpopcan-hierarchical-pumf-field-eligibility-v1",
        "review": {
            "status": "reviewed_pre_1_0_baseline",
            "reviewed_on": REVIEW_DATE,
            "reviewer": REVIEWER,
            "scope": (
                "Every source column is classified; deferred fields require a "
                "separate modelling, interpretation, control, and privacy review."
            ),
        },
        "rare_category_threshold": RARE_THRESHOLD,
        "sources": source_payloads,
        "summary": {
            "field_records": len(records),
            "source_fields_by_vintage": {
                str(year): len(header) for year, header in headers_by_vintage.items()
            },
            "current_source_targets_by_vintage": {
                str(year): len(targets) for year, targets in targets_by_vintage.items()
            },
            "roles": dict(
                sorted(Counter(r["permitted_role"] for r in records).items())
            ),
            "review_statuses": dict(
                sorted(Counter(r["review"]["status"] for r in records).items())
            ),
        },
        "fields": records,
    }


def read_header(path: Path) -> tuple[str, ...]:
    """Read one CSV header while preserving the published source order."""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        return tuple(next(csv.reader(handle)))


def load_metadata(source: SourceSpec) -> dict[str, dict[str, Any]]:
    """Join checked-in variable labels with value labels from the SPSS source."""

    payload = json.loads(source.metadata_path.read_text(encoding="utf-8"))
    variables = payload["variables"]
    if not isinstance(variables, dict):
        raise ValueError(f"invalid variables mapping in {source.metadata_path}")
    value_labels = parse_spss_value_labels(
        source.spss_path.read_text(encoding=source.spss_encoding)
    )
    result: dict[str, dict[str, Any]] = {}
    for name, value in variables.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValueError(f"invalid variable metadata in {source.metadata_path}")
        result[name] = {**value}
        if name in value_labels and "values" not in result[name]:
            result[name]["values"] = value_labels[name]
    for header_name in read_header(source.csv_path):
        match = next(
            (
                value
                for name, value in result.items()
                if name.casefold() == header_name.casefold()
            ),
            None,
        )
        if match is not None:
            result[header_name] = match
    return result


def parse_spss_value_labels(text: str) -> dict[str, dict[str, str]]:
    """Parse StatCan's simple slash-delimited SPSS VALUE LABELS section."""

    marker = text.find("VALUE LABELS")
    if marker < 0:
        raise ValueError("SPSS metadata is missing 'VALUE LABELS'")
    result: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in text[marker + len("VALUE LABELS") :].splitlines():
        stripped = line.strip()
        if stripped == "/":
            current = None
            continue
        if stripped == "." or stripped.startswith("SAVE OUTFILE"):
            break
        entry = re.fullmatch(r'(-?\d+(?:\.\d+)?)\s+"(.*)"', stripped)
        if entry and current is not None:
            result[current][entry.group(1)] = entry.group(2).replace('""', '"')
            continue
        name = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped)
        if name:
            current = name.group(0)
            result.setdefault(current, {})
    return result


def current_source_targets(source: SourceSpec, header: tuple[str, ...]) -> set[str]:
    """Resolve the actual current full profile and omit its derived size field."""

    sample = SeedSample(
        level="person",
        source_format=source.source_format,
        records=(),
        columns=header,
        weight_column="WEIGHT",
        geography_columns=("PR", "CMA"),
        id_columns=("HH_ID", "EF_ID", "CF_ID", "PP_ID"),
    )
    household, _, person, _, _ = resolve_tree_column_block_pair(
        sample,
        household_block="all",
        person_block="all",
    )
    return (set(household) | set(person)) & set(header)


def entity_level(name: str) -> EntityLevel:
    """Return the entity to which the published source column belongs."""

    if name in IDENTIFIERS:
        return "identifier"
    if name == "WEIGHT" or re.fullmatch(r"WT\d+", name):
        return "weight"
    if name in GEOGRAPHIES:
        return "geography"
    if name in HOUSEHOLD_FIELDS:
        return "household"
    if name in ECONOMIC_FAMILY_FIELDS:
        return "economic_family"
    if name in CENSUS_FAMILY_FIELDS:
        return "census_family"
    return "person"


def classified_missing_codes(
    name: str, metadata: dict[str, Any]
) -> dict[str, list[str]]:
    """Separate unavailable/missing codes from explicit not-applicable codes."""

    values = metadata.get("values", {})
    if not isinstance(values, dict):
        values = {}
    missing: list[str] = []
    not_applicable: list[str] = []
    for code, label_value in values.items():
        label = str(label_value).casefold()
        if "not applicable" in label:
            not_applicable.append(str(code))
        elif any(
            phrase in label
            for phrase in ("not available", "missing", "no response", "invalid")
        ):
            missing.append(str(code))
    quantitative_codes = QUANTITATIVE_SPECIAL_CODES.get(name)
    if quantitative_codes is not None:
        missing.extend(quantitative_codes["missing"])
        not_applicable.extend(quantitative_codes["not_applicable"])
    return {
        "missing": sorted(set(missing), key=code_sort),
        "not_applicable": sorted(set(not_applicable), key=code_sort),
    }


def scan_source(
    path: Path,
    header: tuple[str, ...],
    entities: dict[str, EntityLevel],
    missing_codes: dict[str, dict[str, list[str]]],
) -> dict[str, FieldStats]:
    """Compute aggregate support and within-entity constancy evidence."""

    stats = {name: FieldStats() for name in header}
    fields_by_level = {
        level: tuple(name for name in header if entities[name] == level)
        for level in (
            "household",
            "economic_family",
            "census_family",
            "person",
        )
    }
    row_fields = tuple(
        name
        for name in header
        if entities[name]
        not in {"household", "economic_family", "census_family", "person"}
    )
    entity_levels: tuple[EntityLevel, ...] = (
        "household",
        "economic_family",
        "census_family",
        "person",
    )
    previous_keys: dict[EntityLevel, tuple[str, ...] | None] = {
        level: None for level in entity_levels
    }
    entity_weights: dict[EntityLevel, float] = {level: 0.0 for level in entity_levels}
    raw_entity_values: dict[tuple[EntityLevel, str], str] = {}
    applicable_entity_values: dict[tuple[EntityLevel, str], str | None] = {}
    support_entity_values: dict[tuple[EntityLevel, str], str] = {}

    def flush(level: EntityLevel) -> None:
        if previous_keys[level] is None:
            return
        for field_name in fields_by_level[level]:
            update_support(
                stats[field_name],
                support_entity_values[(level, field_name)],
                entity_weights[level],
                missing_codes[field_name],
            )

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != header:
            raise ValueError(f"header changed while scanning {path}")
        for row in reader:
            keys = {
                "household": (row["HH_ID"],),
                "economic_family": (
                    (row["HH_ID"], row["EF_ID"])
                    if row["EF_RP"] in {"1", "2"}
                    else (row["HH_ID"], "unattached-person", row["PP_ID"])
                ),
                "census_family": (
                    (row["HH_ID"], row["CF_ID"])
                    if row["CF_RP"] in {"1", "2"}
                    else (row["HH_ID"], "non-family-person", row["PP_ID"])
                ),
                "person": (row["HH_ID"], row["PP_ID"]),
            }
            weight = float(row.get("WEIGHT", "0") or 0)
            for level in entity_levels:
                key = keys[level]
                first = previous_keys[level] != key
                if first:
                    flush(level)
                    previous_keys[level] = key
                    entity_weights[level] = weight
                for name in fields_by_level[level]:
                    value = row[name].strip()
                    state = stats[name]
                    value_key = (level, name)
                    if first:
                        raw_entity_values[value_key] = value
                        applicable_entity_values[value_key] = (
                            value if is_applicable(value, missing_codes[name]) else None
                        )
                        support_entity_values[value_key] = value
                    else:
                        state.constant_checks += 1
                        if raw_entity_values[value_key] != value:
                            state.constant_failures += 1
                        if is_applicable(value, missing_codes[name]):
                            applicable = applicable_entity_values[value_key]
                            if applicable is None:
                                applicable_entity_values[value_key] = value
                            else:
                                state.applicable_constant_checks += 1
                                if applicable != value:
                                    state.applicable_constant_failures += 1
                        selected = support_entity_values[value_key]
                        if support_rank(value, missing_codes[name]) > support_rank(
                            selected, missing_codes[name]
                        ):
                            support_entity_values[value_key] = value
            for name in row_fields:
                update_support(
                    stats[name], row[name].strip(), weight, missing_codes[name]
                )
    for level in entity_levels:
        flush(level)
    return stats


def is_applicable(value: str, codes: dict[str, list[str]]) -> bool:
    """Return whether a raw value is substantive rather than a special code."""

    return (
        bool(value)
        and value not in codes["missing"]
        and value not in codes["not_applicable"]
    )


def support_rank(value: str, codes: dict[str, list[str]]) -> int:
    """Prefer substantive, then missing, then not-applicable group evidence."""

    if is_applicable(value, codes):
        return 2
    if not value or value in codes["missing"]:
        return 1
    return 0


def update_support(
    stats: FieldStats,
    value: str,
    weight: float,
    codes: dict[str, list[str]],
) -> None:
    """Add one entity observation to a field's sufficient statistics."""

    stats.observations += 1
    if not value or value in codes["missing"]:
        stats.missing += 1
        return
    if value in codes["not_applicable"]:
        stats.not_applicable += 1
        return
    stats.values[value] += 1
    stats.weighted_applicable += weight


def field_record(
    source: SourceSpec,
    name: str,
    metadata: dict[str, Any],
    stats: FieldStats,
    current_targets: set[str],
    missing_codes: dict[str, list[str]],
) -> dict[str, Any]:
    """Build one reviewed field record."""

    level = entity_level(name)
    role = permitted_role(name, current_targets)
    categories = field_categories(metadata)
    counterpart, relationship = cross_vintage(source.vintage, name)
    controlled = control_compatibility(name, source.vintage)
    missing_fraction = stats.missing / stats.observations if stats.observations else 0
    not_applicable_fraction = (
        stats.not_applicable / stats.observations if stats.observations else 0
    )
    applicable_observations = stats.observations - stats.missing - stats.not_applicable
    category_counts = stats.values
    rare_count = (
        sum(0 < count < RARE_THRESHOLD for count in category_counts.values())
        if name not in QUANTITATIVE_FIELDS
        and level not in {"identifier", "weight"}
        and len(category_counts) <= 1_000
        else None
    )
    return {
        "field_id": f"{source.vintage}:{name}",
        "census_vintage": source.vintage,
        "source_name": name,
        "label": metadata.get("label", ""),
        "categories": categories,
        "source_universe": source_universe(level, name),
        "concept_id": concept_id(name),
        "cross_vintage": {
            "counterpart": counterpart,
            "relationship": relationship,
        },
        "entity_level": level,
        "within_entity_constancy": constancy_evidence(level, stats),
        "missing_codes": missing_codes["missing"],
        "not_applicable_codes": missing_codes["not_applicable"],
        "observed": {
            "entity_observations": stats.observations,
            "applicable_observations": applicable_observations,
            "cardinality": len(category_counts),
            "weighted_applicable_support": round(stats.weighted_applicable, 6),
            "missing_observations": stats.missing,
            "missing_fraction": round(missing_fraction, 8),
            "not_applicable_observations": stats.not_applicable,
            "not_applicable_fraction": round(not_applicable_fraction, 8),
            "rare_category_count": rare_count,
            "rare_category_threshold": RARE_THRESHOLD,
        },
        "permitted_role": role,
        "recommended_representation": representation(name, role),
        "dependencies": dependencies(name),
        "consistency_invariants": invariants(name),
        "control_compatibility": controlled,
        "disclosure_and_interpretation_concerns": concerns(name, level),
        "review": review_decision(name, role, controlled),
    }


def field_categories(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """Return published category metadata without observed code frequencies."""

    values = metadata.get("values")
    if isinstance(values, dict) and values:
        return [
            {
                "code": str(code),
                "label": str(label),
            }
            for code, label in sorted(
                values.items(), key=lambda item: code_sort(item[0])
            )
        ]
    return []


def code_sort(value: object) -> tuple[int, float | str]:
    """Sort numeric category codes numerically and all other codes lexically."""

    text = str(value)
    try:
        return (0, float(text))
    except ValueError:
        return (1, text)


def cross_vintage(vintage: int, name: str) -> tuple[str | None, str]:
    """Return an explicit counterpart and semantic relationship."""

    explicit = CROSS_VINTAGE.get((vintage, name))
    if explicit is not None:
        return explicit
    other = 2021 if vintage == 2016 else 2016
    candidates = headers_for_vintage(other)
    if name in candidates:
        return name, "same_source_name_reviewed_separately"
    upper_match = next(
        (candidate for candidate in candidates if candidate.upper() == name.upper()),
        None,
    )
    if upper_match is not None:
        return upper_match, "case_normalized"
    return None, "no_direct_counterpart"


@lru_cache(maxsize=2)
def headers_for_vintage(vintage: int) -> tuple[str, ...]:
    """Read the counterpart header for cross-vintage matching."""

    source = next(item for item in SOURCES if item.vintage == vintage)
    return read_header(source.csv_path)


def concept_id(name: str) -> str:
    """Return a stable cross-vintage concept key without hiding known changes."""

    pair = CROSS_VINTAGE.get((2016, name)) or CROSS_VINTAGE.get((2021, name))
    root = min((name, pair[0]), key=str.casefold) if pair is not None else name
    return re.sub(r"[^a-z0-9]+", "_", root.casefold()).strip("_")


def permitted_role(name: str, targets: set[str]) -> str:
    """Classify the only role currently permitted by the reviewed baseline."""

    if name in IDENTIFIERS:
        return "structural_key"
    if name in GEOGRAPHIES:
        return "condition"
    if name == "WEIGHT" or re.fullmatch(r"WT\d+", name):
        return "validation_only"
    if name in targets:
        return "target"
    if name in FAMILY_RELATION_FIELDS:
        return "defer"
    return "defer"


def representation(name: str, role: str) -> str:
    """Recommend a representation without adding a public profile."""

    if role == "structural_key":
        return "structural_identifier"
    if role == "validation_only" and (name == "WEIGHT" or name.startswith("WT")):
        return "numeric_source_weight"
    if name in QUANTITATIVE_FIELDS:
        return "conditional_numeric"
    if name in COMPONENT_INDICATOR_FIELDS:
        return "component_indicator"
    if name in ORDERED_BAND_FIELDS:
        return "ordered_band"
    if name in FAMILY_RELATION_FIELDS:
        return "categorical_role_with_family_entity"
    return "categorical"


def dependencies(name: str) -> list[str]:
    """Name prerequisites that must be retained in any future model block."""

    if name in {"AGEIMM", "YRIMM", "YRIM"}:
        return ["AGEGRP", "IMMSTAT"]
    if name in {
        "COW",
        "EMPIN",
        "FPTWK",
        "HRSWRK",
        "JOBPERM",
        "LFACT",
        "LFTAG",
        "LSTWRK",
        "NAICS",
        "NOCS",
        "NOC21",
        "WKSWRK",
        "WRKACT",
    }:
        return ["AGEGRP", "labour_force_status"]
    if name in {
        "DIST",
        "LEAVE",
        "MODE",
        "OCC",
        "POWST",
        "PWDUR",
        "PWLEAVE",
        "PWOCC",
        "PWPR",
    }:
        return ["AGEGRP", "POWST"]
    if name in FAMILY_RELATION_FIELDS or entity_level(name) in {
        "economic_family",
        "census_family",
    }:
        return ["HH_ID", "EF_ID", "CF_ID"]
    if entity_level(name) == "household":
        return ["HH_ID"]
    return []


def invariants(name: str) -> list[str]:
    """Record the principal consistency assertions for later implementations."""

    if name == "AGEIMM":
        return [
            "age_at_immigration_must_not_exceed_age",
            "not_applicable_unless_immigrant",
        ]
    if name in {"YRIMM", "YRIM"}:
        return [
            "immigration_year_must_not_postdate_census",
            "not_applicable_unless_immigrant",
        ]
    if name in FAMILY_RELATION_FIELDS:
        return ["role_must_resolve_within_declared_family_entity"]
    if name in HOUSEHOLD_FIELDS:
        return ["value_must_be_constant_within_household"]
    if name in ECONOMIC_FAMILY_FIELDS:
        return ["value_must_be_constant_within_economic_family"]
    if name in CENSUS_FAMILY_FIELDS:
        return ["value_must_be_constant_within_census_family"]
    return []


def control_compatibility(name: str, vintage: int) -> dict[str, Any]:
    """Record a reviewed control candidate or an explicit uncontrolled result."""

    families = {
        "AGEGRP": ("age", "persons_in_private_households"),
        "SEX": ("sex", "persons_in_private_households"),
        "GENDER": ("gender", "persons_in_private_households"),
        "TENUR": ("tenure", "private_households"),
        "DTYPE": ("structural_dwelling_type", "private_households"),
    }
    candidate = families.get(name)
    if candidate is None:
        return {
            "status": "uncontrolled",
            "candidate_family": None,
            "universe": None,
            "note": "No reviewed Census Profile crosswalk is assigned in the pre-1.0 inventory.",
        }
    family, universe = candidate
    return {
        "status": "candidate_requires_crosswalk",
        "candidate_family": f"statcan-{vintage}-{family}",
        "universe": universe,
        "note": "Candidate only; local control claims require a versioned pack and evidence.",
    }


def source_universe(level: EntityLevel, name: str) -> dict[str, str]:
    """State the defensible source universe at the current review depth."""

    if level == "household":
        return {
            "status": "entity_level_reviewed_applicability_pending",
            "description": (
                "private households represented by the hierarchical PUMF; "
                "field-specific applicability follows public source metadata"
            ),
        }
    if level == "economic_family":
        return {
            "status": "requires_field_specific_review",
            "description": (
                "economic families and persons not in an economic family; "
                "constancy is evaluated only within declared family membership"
            ),
        }
    if level == "census_family":
        return {
            "status": "requires_field_specific_review",
            "description": (
                "persons in private households; constancy is evaluated only "
                "within declared census-family membership"
            ),
        }
    if level == "person":
        return {
            "status": "requires_field_specific_review",
            "description": "persons in private households, subject to published applicability codes",
        }
    return {
        "status": "not_a_synthetic_attribute",
        "description": f"source {name.lower()} metadata",
    }


def constancy_evidence(level: EntityLevel, stats: FieldStats) -> dict[str, Any]:
    """Summarize observed within-entity constancy without overstating semantics."""

    keys = {
        "household": ["HH_ID"],
        "economic_family": ["HH_ID", "EF_ID"],
        "census_family": ["HH_ID", "CF_ID"],
        "person": ["HH_ID", "PP_ID"],
    }
    if level not in keys:
        return {"status": "not_applicable", "entity_key": []}
    if level == "person":
        return {"status": "one_source_row_per_person", "entity_key": keys[level]}
    return {
        "status": "verified_constant_among_applicable_values"
        if stats.applicable_constant_failures == 0
        else "observed_applicable_values_not_constant",
        "entity_key": keys[level],
        "applicable_comparisons": stats.applicable_constant_checks,
        "applicable_failures": stats.applicable_constant_failures,
        "raw_comparisons_including_special_codes": stats.constant_checks,
        "raw_differences_including_special_codes": stats.constant_failures,
        "note": (
            "Missing and not-applicable differences are retained as applicability "
            "evidence, not treated as proof that a substantive family or household "
            "measure varies."
        ),
    }


def concerns(name: str, level: EntityLevel) -> list[str]:
    """Return field-specific interpretation and disclosure cautions."""

    output: list[str] = []
    if name in IDENTIFIERS:
        output.append("source_identifier_must_never_be_generated_or_published")
    if name in GEOGRAPHIES:
        output.append("broad_pumf_context_is_not_a_synthetic_small_area_location")
    if name in SENSITIVE_FIELDS:
        output.extend(
            ["sensitive_identity_attribute", "requires_privacy_and_terminology_review"]
        )
    if level in {"economic_family", "census_family"} or name in FAMILY_RELATION_FIELDS:
        output.append("requires_explicit_family_entity_semantics")
    return output


def review_decision(name: str, role: str, control: dict[str, Any]) -> dict[str, str]:
    """Explain why the role is frozen or deferred."""

    if role == "target":
        status = "reviewed_current_profile"
        rationale = (
            "Reconciles to the existing full linked household/person target profile."
        )
    elif role in {"structural_key", "condition", "validation_only"}:
        status = "reviewed_non_target"
        rationale = "Required for source structure, conditioning, or validation; never a generated target."
    else:
        status = "provisional_defer"
        rationale = (
            "Present in the source but omitted intentionally until its entity, applicability, "
            "representation, controls, interpretation, and privacy evidence are reviewed."
        )
    if control["status"] == "candidate_requires_crosswalk" and role != "target":
        rationale += " A possible control family does not itself authorize modelling."
    return {
        "status": status,
        "rationale": rationale,
        "reviewer": REVIEWER,
        "reviewed_on": REVIEW_DATE,
    }


def header_sha256(header: tuple[str, ...]) -> str:
    """Hash the exact ordered header independently of source row data."""

    return hashlib.sha256((",".join(header) + "\n").encode()).hexdigest()


def file_sha256(path: Path) -> str:
    """Hash exact input bytes without loading a public-use source into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    """Return a stable repository-relative path."""

    return path.relative_to(ROOT).as_posix()


def main() -> None:
    """Regenerate the committed pre-1.0 inventory."""

    payload = build_inventory()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"wrote {OUTPUT.relative_to(ROOT)} with "
        f"{payload['summary']['field_records']} field records"
    )


if __name__ == "__main__":
    main()
