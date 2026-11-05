"""Whole-household screening and optional support selection for linked candidates."""

from __future__ import annotations

import csv
import json
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from synthpopcan._profile_preparation import AGE_CONTROL, workflow_controls, write_json
from synthpopcan.control_packs import _derive_candidate_value
from synthpopcan.controls import read_control_table
from synthpopcan.linked_schema import (
    build_linked_population_contract,
    validate_linked_population_contract,
)
from synthpopcan.small_area_synthesis import (
    _LinkedCalibrationIndex,
    controls_by_geography,
)
from synthpopcan.tree import validate_linked_population_files


def read_records(path: Path):
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_records(path: Path, fields: list[str], rows) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _derive_records(rows, controls, entity, rejected, reasons):
    for row in rows:
        for control in controls:
            for derivation, axis in zip(
                control.candidate_derivations, control.source_axes, strict=True
            ):
                try:
                    value = _derive_candidate_value(
                        derivation, row.get(derivation.source_field, "")
                    )
                    if value not in {
                        category.target_category for category in axis.categories
                    }:
                        raise ValueError("missing or inapplicable category")
                    row[derivation.output_field] = value
                except ValueError:
                    rejected.add(row["synthetic_household_id"])
                    reasons[f"{entity}.{derivation.source_field}"] += 1


def _derive_person_indicators(persons, require_gender, rejected, reasons):
    for row in persons:
        try:
            age = int(row.get("AGEGRP", ""))
            if not 1 <= age <= 13:
                raise ValueError
            row["age_group_3"] = (
                "0_14" if age <= 2 else "15_64" if age <= 11 else "65_plus"
            )
            row["age_under_20"] = str(int(age <= 3))
            row["age_65_plus"] = str(int(age >= 12))
        except ValueError:
            rejected.add(row["synthetic_household_id"])
            reasons["person.AGEGRP"] += 1
        if require_gender and row.get("GENDER") not in {"1", "2"}:
            rejected.add(row["synthetic_household_id"])
            reasons["person.GENDER"] += 1
        row["visible_minority"] = str(
            int(row.get("visible_minority_group") == "visible_minority")
        )


def screen_candidates(source: Path, require_gender: bool):
    hh_fields, households = read_records(source / "households.csv")
    pp_fields, persons = read_records(source / "persons.csv")
    pack, definitions = workflow_controls()
    base = [
        definitions[m.control_identifier]
        for m in pack.margins
        if m.control_identifier != AGE_CONTROL
    ]
    for entity, fields in [("household", hh_fields), ("person", pp_fields)]:
        required = {
            d.source_field
            for c in base
            if c.entity_level == entity
            for d in c.candidate_derivations
        }
        if entity == "person":
            required.update({"AGEGRP", *(["GENDER"] if require_gender else [])})
        if missing := required - set(fields):
            raise ValueError(
                f"Candidate {entity} CSV is missing fields: "
                f"{', '.join(sorted(missing))}. Generate candidates with an "
                "all-fields hierarchical 2021 model."
            )
    rejected: set[str] = set()
    reasons: Counter[str] = Counter()
    for entity, records in [("household", households), ("person", persons)]:
        _derive_records(
            records,
            [c for c in base if c.entity_level == entity],
            entity,
            rejected,
            reasons,
        )
    _derive_person_indicators(persons, require_gender, rejected, reasons)
    kept_hh = [r for r in households if r["synthetic_household_id"] not in rejected]
    kept_pp = [r for r in persons if r["synthetic_household_id"] not in rejected]
    if not kept_hh or not kept_pp:
        raise ValueError(
            "Complete-case screening retained no linked "
            "households. Generate more compatible candidates or "
            "review the source fields; unknown values are not "
            "imputed."
        )
    summary = {
        "input_households": len(households),
        "input_persons": len(persons),
        "kept_households": len(kept_hh),
        "kept_persons": len(kept_pp),
        "excluded_households": len(rejected),
        "excluded_persons": len(persons) - len(kept_pp),
        "reasons": dict(reasons),
        "require_gender": require_gender,
        "policy": (
            "Whole-household complete cases for all nine "
            "household and four private-person controls; known "
            "source age required. Screening can change the "
            "candidate distribution; exclusion counts retained."
        ),
    }
    hh_fields = list(dict.fromkeys([*hh_fields, *kept_hh[0]]))
    pp_fields = list(dict.fromkeys([*pp_fields, *kept_pp[0]]))
    return hh_fields, pp_fields, kept_hh, kept_pp, summary


def _support_modules():
    try:
        from scipy.optimize import OptimizeWarning, linprog
        from scipy.sparse import csr_matrix
    except ImportError as exc:
        raise ValueError(
            "Linear-feasibility support requires scipy. Install "
            "synthpopcan[performance], or omit "
            "--augment-support to skip feasibility augmentation."
        ) from exc
    return OptimizeWarning, linprog, csr_matrix


def select_support(
    households,
    persons,
    controls_path,
    person_controls_path,
    pool_size,
    seed,
    *,
    geography_dimension="ct",
):
    warning_type, linprog, csr_matrix = _support_modules()
    hc = controls_by_geography(
        read_control_table(controls_path), geography_dimension=geography_dimension
    )
    pc = controls_by_geography(
        read_control_table(person_controls_path),
        geography_dimension=geography_dimension,
    )
    if not hc or set(hc) != set(pc):
        raise ValueError(
            "Support selection requires matching nonempty "
            "household and person control geographies."
        )
    index = _LinkedCalibrationIndex.build(
        households,
        persons,
        hc[min(hc)],
        pc[min(pc)],
        household_id_column="synthetic_household_id",
    )
    matrix = csr_matrix(index.contributions)
    selected = set(
        int(i)
        for i in np.random.default_rng(seed).choice(
            len(households), size=min(pool_size, len(households)), replace=False
        )
    )

    def fit(geo):
        targets = index.targets(hc[geo], pc[geo])
        result = linprog(
            np.zeros(len(households)),
            A_eq=matrix,
            b_eq=targets,
            bounds=(0, None),
            method="highs",
            options={"threads": 1, "presolve": False},
        )
        presolve = False
        if result.status not in {0, 2}:
            # Numerical difficulty or an incomplete solve is not infeasibility.
            # Retry with the solver's conservative default preprocessing.
            result = linprog(
                np.zeros(len(households)),
                A_eq=matrix,
                b_eq=targets,
                bounds=(0, None),
                method="highs",
                options={"threads": 1, "presolve": True},
            )
            presolve = True
        support = np.flatnonzero(result.x > 1e-8).tolist() if result.success else []
        return (
            geo,
            support,
            bool(result.success),
            result.message,
            result.status,
            presolve,
        )

    with warnings.catch_warnings(), ThreadPoolExecutor(max_workers=4) as executor:
        warnings.simplefilter("ignore", warning_type)
        results = list(executor.map(fit, sorted(hc)))
    reports = []
    for geo, support, feasible, message, status, presolve in results:
        selected.update(support)
        reports.append(
            {
                geography_dimension: geo,
                "feasible": feasible,
                "support_households": len(support),
                "message": message,
                "solver_status": int(status),
                "presolve": presolve,
            }
        )
    return selected, reports


def _matching_columns(columns, dimensions, categories, count):
    matches = np.ones(count, dtype=bool)
    for dimension, category in zip(dimensions, categories, strict=True):
        matches &= columns[dimension] == category
    return matches


def _structural_presence(households, persons, specs):
    """Record whether each whole household contributes to a control cell."""
    presence = np.zeros((len(specs), len(households)), dtype=bool)
    household_indexes = {
        row["synthetic_household_id"]: i for i, row in enumerate(households)
    }
    person_indexes = np.fromiter(
        (
            household_indexes.get(row.get("synthetic_household_id", ""), -1)
            for row in persons
        ),
        dtype=np.int64,
        count=len(persons),
    )
    for unit, records in (("household", households), ("person", persons)):
        fields = {d for spec in specs if spec.unit == unit for d in spec.dimensions}
        columns = {
            field: np.fromiter(
                (row.get(field, "") for row in records),
                dtype=object,
                count=len(records),
            )
            for field in fields
        }
        _fill_structural_presence(
            presence, specs, unit, columns, len(records), person_indexes
        )
    return presence


def _fill_structural_presence(presence, specs, unit, columns, count, person_indexes):
    for i, spec in enumerate(specs):
        if spec.unit != unit:
            continue
        matches = _matching_columns(columns, spec.dimensions, spec.categories, count)
        if unit == "household":
            presence[i] = matches
        else:
            presence[i, person_indexes[matches & (person_indexes >= 0)]] = True


def _append_structural_witnesses(presence, targets, selected):
    allowed = ~np.any(presence[targets == 0], axis=0)
    supported = np.any(presence[:, allowed & selected], axis=1)
    added, unsupported = [], []
    for row in np.flatnonzero((targets > 0) & ~supported):
        if supported[row]:
            continue
        candidates = np.flatnonzero(allowed & presence[row])
        if not len(candidates):
            unsupported.append(int(row))
            candidates = _observed_only_candidates(presence, row, selected)
            if not len(candidates):
                continue
        witness = int(candidates[0])
        violations = np.flatnonzero((targets == 0) & presence[:, witness]).tolist()
        selected[witness] = True
        if not violations:
            supported |= presence[:, witness]
        added.append((witness, violations))
    return added, unsupported


def _observed_only_candidates(presence, row, selected):
    if np.any(presence[row, selected]):
        return np.empty(0, dtype=np.int64)
    return np.flatnonzero(presence[row])


def _unsupported_control(spec, target):
    return {
        "unit": spec.unit,
        "margin": spec.margin,
        "categories": dict(zip(spec.dimensions, spec.categories, strict=True)),
        "target": float(target),
    }


def _witness_diagnostic(witness, households, layout, targets):
    index, violations = witness
    return {
        "household_id": households[index]["synthetic_household_id"],
        "kind": "observed-only" if violations else "structural-compatible",
        "violated_zero_controls": [
            _unsupported_control(layout.specs[i], targets[i]) for i in violations
        ],
    }


def select_structural_support(
    households,
    persons,
    controls_path,
    person_controls_path,
    pool_size,
    seed,
    *,
    geography_dimension="ct",
):
    """Retain seeded candidates and witnesses, without claiming LP feasibility.

    Prefer witnesses that do not contribute to any zero-target cell. If none
    exists and a positive category is missing from the entire selected pool,
    retain an observed-only donor and report its zero-cell conflicts. This
    strategy is intended for the explicitly requested observed-zero policy.
    Independent cell support never certifies simultaneous linear feasibility.
    """
    hc = controls_by_geography(
        read_control_table(controls_path), geography_dimension=geography_dimension
    )
    pc = controls_by_geography(
        read_control_table(person_controls_path),
        geography_dimension=geography_dimension,
    )
    if not hc or set(hc) != set(pc):
        raise ValueError(
            "Support selection requires matching nonempty "
            "household and person control geographies."
        )
    layout = _LinkedCalibrationIndex.build(
        [], [], hc[min(hc)], pc[min(pc)], household_id_column="synthetic_household_id"
    )
    presence = _structural_presence(households, persons, layout.specs)
    selected = np.zeros(len(households), dtype=bool)
    selected[
        np.random.default_rng(seed).choice(
            len(households), size=min(pool_size, len(households)), replace=False
        )
    ] = True
    reports = []
    for geo in sorted(hc):
        targets = layout.targets(hc[geo], pc[geo])
        added, unsupported = _append_structural_witnesses(presence, targets, selected)
        reports.append(
            {
                geography_dimension: geo,
                "strategy": "structural-witness",
                "support_households": len(added),
                "added_household_ids": [
                    households[i]["synthetic_household_id"] for i, _ in added
                ],
                "witnesses": [
                    _witness_diagnostic(witness, households, layout, targets)
                    for witness in added
                ],
                "structural_support_complete": not unsupported,
                "unsupported_positive_controls": [
                    _unsupported_control(layout.specs[i], targets[i])
                    for i in unsupported
                ],
                "message": (
                    "Prefer individual positive-cell support after structural zeros; "
                    "observed-only donors retain missing categories and disclose "
                    "zero-cell conflicts; "
                    "simultaneous linear feasibility has not been tested. "
                    "Source targets are unchanged."
                ),
            }
        )
    return set(np.flatnonzero(selected).tolist()), reports


def _validate_support_strategy(strategy, augment_support):
    if strategy not in {"linear", "witness"}:
        raise ValueError("Candidate support strategy must be 'linear' or 'witness'.")
    if strategy == "witness" and not augment_support:
        raise ValueError("Witness support selection requires --augment-support.")


def prepare_candidates(
    source: Path,
    output: Path,
    *,
    require_gender=False,
    pool_size=None,
    seed=42,
    augment_support=False,
    controls_path=None,
    person_controls_path=None,
    geography_dimension="ct",
    support_strategy="linear",
) -> dict[str, Any]:
    _validate_support_strategy(support_strategy, augment_support)
    payload = json.loads((source / "manifest.json").read_text())
    if not isinstance(payload, dict):
        raise ValueError("Candidate manifest must be a JSON object.")
    if payload.get("schema_version") == "synthpopcan-tree-generation-manifest-v1":
        payload = payload.get("linked_population")
    if not isinstance(payload, dict):
        raise ValueError(
            "Candidate generation manifest has no linked population contract."
        )
    validate_linked_population_contract(payload)
    manifest = payload
    validation = validate_linked_population_files(
        source / "households.csv", source / "persons.csv"
    )
    if not validation["passed"]:
        raise ValueError(
            "Input candidates have invalid household/person "
            "linkage; run synthpopcan validate linked before "
            "preparation."
        )
    hh_fields, pp_fields, households, persons, summary = screen_candidates(
        source, require_gender
    )
    reports = []
    if augment_support:
        if pool_size is None or controls_path is None or person_controls_path is None:
            raise ValueError(
                "--augment-support requires --pool-size, --controls "
                "and --person-controls."
            )
        selector = (
            select_support
            if support_strategy == "linear"
            else select_structural_support
        )
        selected, reports = selector(
            households,
            persons,
            controls_path,
            person_controls_path,
            pool_size,
            seed,
            geography_dimension=geography_dimension,
        )
    elif pool_size is not None:
        selected = set(
            int(i)
            for i in np.random.default_rng(seed).choice(
                len(households), size=min(pool_size, len(households)), replace=False
            )
        )
    else:
        selected = set(range(len(households)))
    kept_hh = [row for i, row in enumerate(households) if i in selected]
    ids = {row["synthetic_household_id"] for row in kept_hh}
    kept_pp = [row for row in persons if row["synthetic_household_id"] in ids]
    output.mkdir(parents=True, exist_ok=True)
    write_records(output / "households.csv", hh_fields, kept_hh)
    write_records(output / "persons.csv", pp_fields, kept_pp)
    summary.update(
        selected_households=len(kept_hh),
        selected_persons=len(kept_pp),
        pool_size=pool_size,
        subsample_seed=seed,
        support_diagnostics=reports,
    )
    contract = build_linked_population_contract(
        output / "households.csv",
        output / "persons.csv",
        licensing=manifest.get("licensing"),
    )
    contract["candidate_preparation"] = summary
    contract["source_manifest"] = str((source / "manifest.json").resolve())
    write_json(output / "manifest.json", contract)
    write_json(output / "report.json", summary)
    return summary
