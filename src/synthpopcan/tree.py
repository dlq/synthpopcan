"""Tree-based synthetic population generator contracts."""

from __future__ import annotations

import csv
import json
import random
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from sklearn.tree import DecisionTreeClassifier

TreeLevel = Literal["household", "person"]

__all__ = [
    "CartTreeModel",
    "FrequencyGroup",
    "FrequencyOutcome",
    "FrequencyTreeModel",
    "TreeGenerationRequest",
    "TreeLevel",
    "TreeModel",
    "TreeModelSpec",
    "TreeTrainingSample",
    "audit_tree_model",
    "generate_linked_population_to_csv",
    "generate_linked_population",
    "generate_tree_rows",
    "read_cart_model",
    "read_frequency_model",
    "read_tree_model",
    "read_tree_training_sample",
    "train_cart_model",
    "train_frequency_model",
    "validate_linked_population",
    "write_generated_rows",
    "write_tree_model",
]


@dataclass(frozen=True)
class TreeTrainingSample:
    """Training rows and column roles for a tree-based generator.

    Parameters
    ----------
    level:
        Whether the rows describe households or people.
    source_format:
        Name of the adapter or file format that produced the training rows.
    records:
        Training rows as dictionaries of strings.
    columns:
        Column names available in the training rows.
    target_columns:
        Columns the model should generate.
    conditioning_columns:
        Columns used to select or predict target outcomes.
    geography_column:
        Optional column used to describe geographic scope.
    weight_column:
        Optional column containing training weights.
    metadata:
        Additional source-specific notes for reports or manifests.
    """

    level: TreeLevel
    source_format: str
    records: tuple[dict[str, str], ...]
    columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    conditioning_columns: tuple[str, ...]
    geography_column: str | None = None
    weight_column: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def as_summary(self) -> dict[str, object]:
        """Return a compact, JSON-serializable summary of this sample."""

        summary = {
            "level": self.level,
            "source_format": self.source_format,
            "records": len(self.records),
            "columns": list(self.columns),
            "target_columns": list(self.target_columns),
            "conditioning_columns": list(self.conditioning_columns),
            "geography_column": self.geography_column,
            "weight_column": self.weight_column,
        }
        summary.update(self.metadata)
        return summary


@dataclass(frozen=True)
class TreeModelSpec:
    """Column roles and generation settings shared by tree model types.

    A model spec is the compact description of what a tree model learned: which
    level it operates at, which columns it generates, which columns it
    conditions on, and what random seed should be used by default.
    """

    level: TreeLevel
    target_columns: tuple[str, ...]
    conditioning_columns: tuple[str, ...]
    geography_column: str | None = None
    weight_column: str | None = None
    random_seed: int = 0
    model_family: str = "tree-based"

    def __post_init__(self) -> None:
        """Validate target and conditioning column roles."""

        validate_tree_roles(
            target_columns=self.target_columns,
            conditioning_columns=self.conditioning_columns,
        )

    def as_summary(self) -> dict[str, object]:
        """Return a JSON-serializable summary of the model specification."""

        return {
            "level": self.level,
            "model_family": self.model_family,
            "target_columns": list(self.target_columns),
            "conditioning_columns": list(self.conditioning_columns),
            "geography_column": self.geography_column,
            "weight_column": self.weight_column,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class TreeGenerationRequest:
    """Request parameters for generating rows from a tree model.

    This dataclass is mainly a reusable contract for callers that want to pass
    generation requests around before calling :func:`generate_tree_rows`.
    """

    model_spec: TreeModelSpec
    rows: int
    geography_values: tuple[str, ...] = ()
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if self.rows <= 0:
            raise ValueError("rows must be greater than zero")


@dataclass(frozen=True)
class FrequencyOutcome:
    """One possible target outcome and its training weight.

    ``values`` maps target column names to generated category values. ``weight``
    is the observed weighted support for that outcome within a conditioning
    group or globally.
    """

    values: dict[str, str]
    weight: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {"values": self.values, "weight": self.weight}


@dataclass(frozen=True)
class FrequencyGroup:
    """Observed outcomes for one set of conditioning values.

    A frequency group is the transparent equivalent of a tree leaf: it records
    the conditions, total support, and possible target outcomes observed in the
    training view.
    """

    conditions: dict[str, str]
    support: float
    outcomes: tuple[FrequencyOutcome, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "conditions": self.conditions,
            "support": self.support,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


@dataclass(frozen=True)
class _FrequencySelection:
    groups: tuple[FrequencyGroup, ...]
    group_cumulative_weights: tuple[float, ...]
    outcome_cumulative_weights_by_group: dict[int, tuple[float, ...]]


@dataclass(frozen=True)
class FrequencyTreeModel:
    """Conditional-frequency tree model used for transparent generation.

    This model stores aggregate outcome counts by conditioning group rather than
    source rows, which makes it easier to audit before sharing. Generation
    chooses a conditioning group and samples among its weighted outcomes.

    The model is still a model artifact and should be audited before release:
    small groups and highly pure groups can reveal too much about the source
    data even when raw rows are not present.
    """

    spec: TreeModelSpec
    groups: tuple[FrequencyGroup, ...]
    global_outcomes: tuple[FrequencyOutcome, ...]
    source_format: str
    records_trained: int
    release_class: str = "private_working"
    min_support_threshold: int = 5
    model_type: str = "conditional-frequency"

    def to_dict(self) -> dict[str, object]:
        """Serialize the model to a JSON-compatible dictionary."""

        minimum_support = min((group.support for group in self.groups), default=0.0)
        groups_below_threshold = sum(
            1 for group in self.groups if group.support < self.min_support_threshold
        )
        return {
            "schema_version": "synthpopcan-tree-model-v1",
            "model_type": self.model_type,
            "release_class": self.release_class,
            "spec": self.spec.as_summary(),
            "source_format": self.source_format,
            "records_trained": self.records_trained,
            "groups": [group.to_dict() for group in self.groups],
            "global_outcomes": [outcome.to_dict() for outcome in self.global_outcomes],
            "privacy": {
                "contains_raw_rows": False,
                "contains_source_identifiers": False,
                "minimum_support": minimum_support,
                "min_support_threshold": self.min_support_threshold,
                "groups_below_threshold": groups_below_threshold,
                "publishable": self.release_class == "publishable_candidate",
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FrequencyTreeModel:
        """Deserialize a conditional-frequency model payload."""

        if payload.get("schema_version") != "synthpopcan-tree-model-v1":
            raise ValueError("unsupported tree model schema")
        if payload.get("model_type") != "conditional-frequency":
            raise ValueError("unsupported tree model type")
        spec_payload = payload["spec"]
        if not isinstance(spec_payload, dict):
            raise ValueError("tree model spec must be an object")
        spec = TreeModelSpec(
            level=spec_payload["level"],  # type: ignore[arg-type]
            target_columns=tuple(spec_payload["target_columns"]),  # type: ignore[arg-type]
            conditioning_columns=tuple(spec_payload["conditioning_columns"]),  # type: ignore[arg-type]
            geography_column=spec_payload.get("geography_column"),  # type: ignore[arg-type]
            weight_column=spec_payload.get("weight_column"),  # type: ignore[arg-type]
            random_seed=int(spec_payload.get("random_seed", 0)),
            model_family=str(spec_payload.get("model_family", "tree-based")),
        )
        return cls(
            spec=spec,
            groups=tuple(
                FrequencyGroup(
                    conditions=dict(group["conditions"]),  # type: ignore[index]
                    support=float(group["support"]),  # type: ignore[index]
                    outcomes=tuple(
                        FrequencyOutcome(
                            values=dict(outcome["values"]),  # type: ignore[index]
                            weight=float(outcome["weight"]),  # type: ignore[index]
                        )
                        for outcome in group["outcomes"]  # type: ignore[index]
                    ),
                )
                for group in payload["groups"]  # type: ignore[index]
            ),
            global_outcomes=tuple(
                FrequencyOutcome(
                    values=dict(outcome["values"]),  # type: ignore[index]
                    weight=float(outcome["weight"]),  # type: ignore[index]
                )
                for outcome in payload["global_outcomes"]  # type: ignore[index]
            ),
            source_format=str(payload["source_format"]),
            records_trained=int(payload["records_trained"]),
            release_class=str(payload.get("release_class", "private_working")),
            min_support_threshold=int(
                payload.get("privacy", {}).get("min_support_threshold", 5)  # type: ignore[union-attr]
            ),
        )


@dataclass(frozen=True)
class CartTreeModel:
    """Serialized scikit-learn CART classifier for synthetic row generation.

    The object stores the tree structure and class counts needed for generation
    without storing a live scikit-learn estimator or raw training rows. CART
    models can be harder to explain than conditional-frequency models, so audit
    support and purity before treating them as shareable artifacts.
    """

    spec: TreeModelSpec
    feature_categories: dict[str, tuple[str, ...]]
    target_classes: tuple[dict[str, str], ...]
    children_left: tuple[int, ...]
    children_right: tuple[int, ...]
    feature: tuple[int, ...]
    threshold: tuple[float, ...]
    value: tuple[tuple[float, ...], ...]
    n_node_samples: tuple[int, ...]
    weighted_n_node_samples: tuple[float, ...]
    source_format: str
    records_trained: int
    min_samples_leaf: int
    max_depth: int | None
    release_class: str = "private_working"
    model_type: str = "cart"

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Return one-hot encoded feature names in model order."""

        return tuple(
            f"{column}={category}"
            for column in self.spec.conditioning_columns
            for category in self.feature_categories[column]
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the CART model to a JSON-compatible dictionary."""

        leaf_supports = [
            support
            for left, right, support in zip(
                self.children_left,
                self.children_right,
                self.n_node_samples,
                strict=True,
            )
            if left == right
        ]
        minimum_leaf_support = min(leaf_supports, default=0)
        leaves_below_threshold = sum(
            1 for support in leaf_supports if support < self.min_samples_leaf
        )
        return {
            "schema_version": "synthpopcan-tree-model-v1",
            "model_type": self.model_type,
            "release_class": self.release_class,
            "spec": self.spec.as_summary(),
            "source_format": self.source_format,
            "records_trained": self.records_trained,
            "feature_categories": {
                column: list(categories)
                for column, categories in self.feature_categories.items()
            },
            "target_classes": list(self.target_classes),
            "cart": {
                "feature_names": list(self.feature_names),
                "children_left": list(self.children_left),
                "children_right": list(self.children_right),
                "feature": list(self.feature),
                "threshold": list(self.threshold),
                "value": [list(node_value) for node_value in self.value],
                "n_node_samples": list(self.n_node_samples),
                "weighted_n_node_samples": list(self.weighted_n_node_samples),
                "max_depth": self.max_depth,
            },
            "privacy": {
                "contains_raw_rows": False,
                "contains_source_identifiers": False,
                "min_samples_leaf": self.min_samples_leaf,
                "minimum_leaf_support": minimum_leaf_support,
                "leaves_below_threshold": leaves_below_threshold,
                "publishable": self.release_class == "publishable_candidate",
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CartTreeModel:
        """Deserialize a CART model payload."""

        if payload.get("schema_version") != "synthpopcan-tree-model-v1":
            raise ValueError("unsupported tree model schema")
        if payload.get("model_type") != "cart":
            raise ValueError("unsupported tree model type")
        spec_payload = payload["spec"]
        if not isinstance(spec_payload, dict):
            raise ValueError("tree model spec must be an object")
        cart_payload = payload["cart"]
        if not isinstance(cart_payload, dict):
            raise ValueError("cart model payload must be an object")
        privacy_payload = payload["privacy"]
        if not isinstance(privacy_payload, dict):
            raise ValueError("tree model privacy payload must be an object")
        spec = TreeModelSpec(
            level=spec_payload["level"],  # type: ignore[arg-type]
            target_columns=tuple(spec_payload["target_columns"]),  # type: ignore[arg-type]
            conditioning_columns=tuple(spec_payload["conditioning_columns"]),  # type: ignore[arg-type]
            geography_column=spec_payload.get("geography_column"),  # type: ignore[arg-type]
            weight_column=spec_payload.get("weight_column"),  # type: ignore[arg-type]
            random_seed=int(spec_payload.get("random_seed", 0)),
            model_family=str(spec_payload.get("model_family", "tree-based")),
        )
        feature_categories_payload = payload["feature_categories"]
        if not isinstance(feature_categories_payload, dict):
            raise ValueError("feature categories must be an object")
        return cls(
            spec=spec,
            feature_categories={
                str(column): tuple(categories)  # type: ignore[arg-type]
                for column, categories in feature_categories_payload.items()
            },
            target_classes=tuple(
                dict(target_class)
                for target_class in payload["target_classes"]  # type: ignore[index]
            ),
            children_left=tuple(int(value) for value in cart_payload["children_left"]),
            children_right=tuple(
                int(value) for value in cart_payload["children_right"]
            ),
            feature=tuple(int(value) for value in cart_payload["feature"]),
            threshold=tuple(float(value) for value in cart_payload["threshold"]),
            value=tuple(
                tuple(float(class_value) for class_value in node_value)
                for node_value in cart_payload["value"]
            ),
            n_node_samples=tuple(
                int(value) for value in cart_payload["n_node_samples"]
            ),
            weighted_n_node_samples=tuple(
                float(value) for value in cart_payload["weighted_n_node_samples"]
            ),
            source_format=str(payload["source_format"]),
            records_trained=int(payload["records_trained"]),
            min_samples_leaf=int(privacy_payload["min_samples_leaf"]),
            max_depth=cart_payload.get("max_depth"),  # type: ignore[arg-type]
            release_class=str(payload.get("release_class", "private_working")),
        )


TreeModel = FrequencyTreeModel | CartTreeModel


def read_tree_training_sample(
    path: Path,
    *,
    level: TreeLevel,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    geography_column: str | None = None,
    weight_column: str | None = None,
) -> TreeTrainingSample:
    """Read a CSV training view for tree-model fitting.

    The caller must provide explicit target and conditioning columns. The
    function validates that all requested columns exist and returns a
    :class:`TreeTrainingSample` suitable for :func:`train_frequency_model` or
    :func:`train_cart_model`.
    """

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_tree_roles(
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
    )
    validate_columns(
        columns,
        required=tuple(
            column
            for column in (
                *target_columns,
                *conditioning_columns,
                geography_column,
                weight_column,
            )
            if column
        ),
    )
    return TreeTrainingSample(
        level=level,
        source_format="csv-v1",
        records=records,
        columns=columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        geography_column=geography_column,
        weight_column=weight_column,
    )


def audit_tree_model(
    model: TreeModel,
    *,
    min_support: float = 50,
    max_purity: float = 0.95,
) -> dict[str, object]:
    """Check whether a tree model meets basic release-review thresholds.

    The report flags low-support groups or leaves, high-purity groups or
    leaves, source-row/privacy metadata, and release-class status. It is a
    screening tool for review, not a proof that a model is safe or
    substantively valid.
    """

    if min_support <= 0:
        raise ValueError("min_support must be greater than zero")
    if not 0 < max_purity <= 1:
        raise ValueError("max_purity must be between 0 and 1")

    units = audit_units(model)
    below_min_support = [unit for unit in units if unit["support"] < min_support]
    above_max_purity = [unit for unit in units if unit["purity"] > max_purity]
    payload = model.to_dict()
    privacy = payload.get("privacy", {})
    contains_raw_rows = bool(
        isinstance(privacy, dict) and privacy.get("contains_raw_rows", True)
    )
    contains_source_identifiers = bool(
        isinstance(privacy, dict) and privacy.get("contains_source_identifiers", True)
    )

    issues: list[dict[str, object]] = []
    if model.release_class != "publishable_candidate":
        issues.append(
            {
                "severity": "warning",
                "kind": "private_working_release_class",
                "message": (
                    "Model is not marked as a publishable candidate; keep it "
                    "private unless a packaging workflow changes its release class."
                ),
            }
        )
    if contains_raw_rows:
        issues.append(
            {
                "severity": "error",
                "kind": "contains_raw_rows",
                "message": "Model privacy metadata indicates raw rows may be present.",
            }
        )
    if contains_source_identifiers:
        issues.append(
            {
                "severity": "error",
                "kind": "contains_source_identifiers",
                "message": (
                    "Model privacy metadata indicates source identifiers may "
                    "be present."
                ),
            }
        )
    issues.extend(support_issue(unit, min_support) for unit in below_min_support[:10])
    issues.extend(purity_issue(unit, max_purity) for unit in above_max_purity[:10])

    return {
        "passed": not any(issue["severity"] == "error" for issue in issues),
        "publishable_candidate": (
            model.release_class == "publishable_candidate" and not issues
        ),
        "model_type": model.model_type,
        "release_class": model.release_class,
        "thresholds": {
            "min_support": min_support,
            "max_purity": max_purity,
        },
        "summary": {
            "records_trained": model.records_trained,
            "groups_or_leaves": len(units),
            "minimum_support": min((unit["support"] for unit in units), default=0.0),
            "below_min_support": len(below_min_support),
            "above_max_purity": len(above_max_purity),
            "contains_raw_rows": contains_raw_rows,
            "contains_source_identifiers": contains_source_identifiers,
        },
        "issues": issues,
    }


def audit_units(model: TreeModel) -> list[dict[str, object]]:
    if isinstance(model, FrequencyTreeModel):
        return [
            {
                "label": f"group {index}",
                "support": group.support,
                "purity": outcome_purity(
                    tuple(outcome.weight for outcome in group.outcomes)
                ),
                "dominant_outcome": dominant_frequency_outcome(group.outcomes),
                "conditions": group.conditions,
            }
            for index, group in enumerate(model.groups, start=1)
        ]
    return [
        {
            "label": f"leaf {node_id}",
            "support": float(support),
            "purity": outcome_purity(model.value[node_id]),
            "dominant_outcome": dominant_cart_outcome(model, node_id),
            "conditions": {},
        }
        for node_id, support in enumerate(model.n_node_samples)
        if model.children_left[node_id] == model.children_right[node_id]
    ]


def outcome_purity(weights: tuple[float, ...]) -> float:
    total = sum(weights)
    if total <= 0:
        return 0.0
    return max(weights) / total


def dominant_frequency_outcome(
    outcomes: tuple[FrequencyOutcome, ...],
) -> dict[str, str] | None:
    if not outcomes:
        return None
    return max(outcomes, key=lambda outcome: outcome.weight).values


def dominant_cart_outcome(
    model: CartTreeModel,
    node_id: int,
) -> dict[str, str] | None:
    values = model.value[node_id]
    if not values:
        return None
    dominant_index = max(range(len(values)), key=lambda index: values[index])
    return model.target_classes[dominant_index]


def support_issue(unit: dict[str, object], min_support: float) -> dict[str, object]:
    return {
        "severity": "error",
        "kind": "below_min_support",
        "message": (
            f"{unit['label']} has support {unit['support']}, below minimum "
            f"{min_support}."
        ),
        "label": unit["label"],
        "support": unit["support"],
        "threshold": min_support,
        "purity": unit["purity"],
        "dominant_outcome": unit["dominant_outcome"],
        "conditions": unit["conditions"],
    }


def purity_issue(unit: dict[str, object], max_purity: float) -> dict[str, object]:
    return {
        "severity": "warning",
        "kind": "above_max_purity",
        "message": (
            f"{unit['label']} has purity {unit['purity']}, above maximum {max_purity}."
        ),
        "label": unit["label"],
        "support": unit["support"],
        "purity": unit["purity"],
        "threshold": max_purity,
        "dominant_outcome": unit["dominant_outcome"],
        "conditions": unit["conditions"],
    }


def train_cart_model(
    sample: TreeTrainingSample,
    *,
    random_seed: int = 0,
    min_samples_leaf: int = 5,
    max_depth: int | None = None,
) -> CartTreeModel:
    """Train a CART model from a tree-training sample.

    Categorical conditioning columns are one-hot encoded in a deterministic
    order before fitting a scikit-learn ``DecisionTreeClassifier``. The returned
    model is serialized into plain Python data structures for JSON output.
    """

    if min_samples_leaf < 1:
        raise ValueError("min_samples_leaf must be greater than zero")
    feature_categories = {
        column: tuple(sorted({record[column] for record in sample.records}))
        for column in sample.conditioning_columns
    }
    target_keys = [
        tuple(record[column] for column in sample.target_columns)
        for record in sample.records
    ]
    target_classes = tuple(
        dict(zip(sample.target_columns, target_key, strict=True))
        for target_key in sorted(set(target_keys))
    )
    class_lookup = {
        tuple(target_class[column] for column in sample.target_columns): index
        for index, target_class in enumerate(target_classes)
    }
    x = np.asarray(
        [
            encode_conditions(record, sample.conditioning_columns, feature_categories)
            for record in sample.records
        ],
        dtype=float,
    )
    y = np.asarray([class_lookup[target_key] for target_key in target_keys], dtype=int)
    weights = np.asarray(
        [
            read_record_weight(record, sample.weight_column, row_number)
            for row_number, record in enumerate(sample.records, start=2)
        ],
        dtype=float,
    )
    classifier = DecisionTreeClassifier(
        random_state=random_seed,
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
    )
    classifier.fit(x, y, sample_weight=weights)
    tree = classifier.tree_
    values = tree.value
    if values.ndim == 3:
        values = values[:, 0, :]
    return CartTreeModel(
        spec=TreeModelSpec(
            level=sample.level,
            target_columns=sample.target_columns,
            conditioning_columns=sample.conditioning_columns,
            geography_column=sample.geography_column,
            weight_column=sample.weight_column,
            random_seed=random_seed,
        ),
        feature_categories=feature_categories,
        target_classes=target_classes,
        children_left=tuple(int(value) for value in tree.children_left.tolist()),
        children_right=tuple(int(value) for value in tree.children_right.tolist()),
        feature=tuple(int(value) for value in tree.feature.tolist()),
        threshold=tuple(float(value) for value in tree.threshold.tolist()),
        value=tuple(
            tuple(float(class_value) for class_value in node_value)
            for node_value in values.tolist()
        ),
        n_node_samples=tuple(int(value) for value in tree.n_node_samples.tolist()),
        weighted_n_node_samples=tuple(
            float(value) for value in tree.weighted_n_node_samples.tolist()
        ),
        source_format=sample.source_format,
        records_trained=len(sample.records),
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
    )


def train_frequency_model(
    sample: TreeTrainingSample,
    *,
    random_seed: int = 0,
    min_support: int = 5,
) -> FrequencyTreeModel:
    """Train a conditional-frequency model from a tree-training sample.

    The model groups training rows by conditioning values and stores weighted
    target-outcome counts for each group. This is often easier to inspect and
    teach than CART because the generated probabilities are direct aggregates.
    """

    grouped: dict[tuple[str, ...], dict[tuple[str, ...], float]] = defaultdict(
        lambda: defaultdict(float)
    )
    global_counts: dict[tuple[str, ...], float] = defaultdict(float)

    for row_number, record in enumerate(sample.records, start=2):
        weight = read_record_weight(record, sample.weight_column, row_number)
        condition_key = tuple(record[column] for column in sample.conditioning_columns)
        target_key = tuple(record[column] for column in sample.target_columns)
        grouped[condition_key][target_key] += weight
        global_counts[target_key] += weight

    groups = tuple(
        FrequencyGroup(
            conditions=dict(
                zip(sample.conditioning_columns, condition_key, strict=True)
            ),
            support=sum(outcome_counts.values()),
            outcomes=frequency_outcomes(sample.target_columns, outcome_counts),
        )
        for condition_key, outcome_counts in sorted(grouped.items())
    )
    return FrequencyTreeModel(
        spec=TreeModelSpec(
            level=sample.level,
            target_columns=sample.target_columns,
            conditioning_columns=sample.conditioning_columns,
            geography_column=sample.geography_column,
            weight_column=sample.weight_column,
            random_seed=random_seed,
        ),
        groups=groups,
        global_outcomes=frequency_outcomes(sample.target_columns, global_counts),
        source_format=sample.source_format,
        records_trained=len(sample.records),
        min_support_threshold=min_support,
    )


def generate_tree_rows(
    model: TreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
) -> list[dict[str, str]]:
    """Generate synthetic rows from either supported tree model type.

    ``conditions`` may provide values for some or all conditioning columns. For
    conditional-frequency models, unknown or partial conditions fall back toward
    broader/global outcomes; for CART models, omitted conditions are encoded as
    empty strings.
    """

    if isinstance(model, FrequencyTreeModel):
        return generate_frequency_rows(
            model,
            rows=rows,
            conditions=conditions,
            random_seed=random_seed,
        )
    return generate_cart_rows(
        model,
        rows=rows,
        conditions=conditions,
        random_seed=random_seed,
    )


def iter_tree_rows(
    model: TreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
):
    if isinstance(model, FrequencyTreeModel):
        yield from iter_frequency_rows(
            model,
            rows=rows,
            conditions=conditions,
            random_seed=random_seed,
        )
        return
    yield from iter_cart_rows(
        model,
        rows=rows,
        conditions=conditions,
        random_seed=random_seed,
    )


def generate_linked_population(
    household_model: TreeModel,
    person_model: TreeModel,
    *,
    households: int,
    household_conditions: dict[str, str] | None = None,
    household_size_column: str = "household_size",
    random_seed: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Generate linked household and person records.

    The household model first generates household attributes, including
    household size. The person model then generates the requested number of
    people for each household using any shared conditioning columns.

    Returns
    -------
    tuple[list[dict[str, str]], list[dict[str, str]]]
        Household rows and person rows. Both include synthetic household
        identifiers so the records can be joined.
    """

    if household_model.spec.level != "household":
        raise ValueError("household model must have level 'household'")
    if person_model.spec.level != "person":
        raise ValueError("person model must have level 'person'")
    if households <= 0:
        raise ValueError("households must be greater than zero")

    effective_random_seed = (
        household_model.spec.random_seed if random_seed is None else random_seed
    )
    seed_rng = random.Random(effective_random_seed)
    generated_households = generate_tree_rows(
        household_model,
        rows=households,
        conditions=household_conditions,
        random_seed=random_seed,
    )

    linked_households: list[dict[str, str]] = []
    linked_persons: list[dict[str, str]] = []
    person_selection_cache: dict[tuple[tuple[str, str], ...], _FrequencySelection] = {}
    next_person_id = 1
    for household_index, generated_household in enumerate(
        generated_households,
        start=1,
    ):
        household_id = str(household_index)
        household_row = {
            "synthetic_household_id": household_id,
            **strip_synthetic_id(generated_household),
        }
        linked_households.append(household_row)
        household_size = read_household_size(household_row, household_size_column)
        person_conditions = household_conditions_for_person_model(
            household_row,
            person_model,
        )
        generated_persons = generate_person_rows_for_household(
            person_model,
            rows=household_size,
            conditions=person_conditions,
            rng=seed_rng,
            selection_cache=person_selection_cache,
        )
        for generated_person in generated_persons:
            linked_persons.append(
                {
                    "synthetic_person_id": str(next_person_id),
                    "synthetic_household_id": household_id,
                    **strip_synthetic_id(generated_person),
                }
            )
            next_person_id += 1

    return linked_households, linked_persons


def generate_linked_population_to_csv(
    household_model: TreeModel,
    person_model: TreeModel,
    *,
    households: int,
    households_path: Path,
    persons_path: Path,
    household_conditions: dict[str, str] | None = None,
    household_size_column: str = "household_size",
    random_seed: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    progress_interval: int = 1000,
) -> tuple[int, int]:
    """Stream linked household and person records to CSV files.

    This has the same generation semantics as :func:`generate_linked_population`
    but keeps memory bounded for city-scale or national-scale outputs.
    ``progress_callback`` receives generated household and person counts for
    callers that want to render progress without coupling the library to a
    terminal UI.
    """

    if household_model.spec.level != "household":
        raise ValueError("household model must have level 'household'")
    if person_model.spec.level != "person":
        raise ValueError("person model must have level 'person'")
    if households <= 0:
        raise ValueError("households must be greater than zero")
    if progress_interval <= 0:
        raise ValueError("progress interval must be greater than zero")

    effective_random_seed = (
        household_model.spec.random_seed if random_seed is None else random_seed
    )
    seed_rng = random.Random(effective_random_seed)
    household_fieldnames = unique_fieldnames(
        (
            "synthetic_household_id",
            *household_model.spec.conditioning_columns,
            *household_model.spec.target_columns,
        )
    )
    person_fieldnames = unique_fieldnames(
        (
            "synthetic_person_id",
            "synthetic_household_id",
            *person_model.spec.conditioning_columns,
            *person_model.spec.target_columns,
        )
    )

    person_count = 0
    person_selection_cache: dict[tuple[tuple[str, str], ...], _FrequencySelection] = {}
    with households_path.open("w", newline="") as households_handle:
        with persons_path.open("w", newline="") as persons_handle:
            household_writer = csv.writer(households_handle)
            person_writer = csv.writer(persons_handle)
            household_writer.writerow(household_fieldnames)
            person_writer.writerow(person_fieldnames)

            household_rows = iter_tree_rows(
                household_model,
                rows=households,
                conditions=household_conditions,
                random_seed=random_seed,
            )
            for household_index, generated_household in enumerate(
                household_rows,
                start=1,
            ):
                household_id = str(household_index)
                generated_household.pop("synthetic_id", None)
                household_row = {
                    "synthetic_household_id": household_id,
                    **generated_household,
                }
                household_writer.writerow(
                    [
                        household_row.get(fieldname, "")
                        for fieldname in household_fieldnames
                    ]
                )
                household_size = read_household_size(
                    household_row,
                    household_size_column,
                )
                person_conditions = household_conditions_for_person_model(
                    household_row,
                    person_model,
                )
                generated_persons = iter_person_rows_for_household(
                    person_model,
                    rows=household_size,
                    conditions=person_conditions,
                    rng=seed_rng,
                    selection_cache=person_selection_cache,
                )
                for generated_person in generated_persons:
                    person_count += 1
                    generated_person.pop("synthetic_id", None)
                    person_row = {
                        "synthetic_person_id": str(person_count),
                        "synthetic_household_id": household_id,
                        **generated_person,
                    }
                    person_writer.writerow(
                        [
                            person_row.get(fieldname, "")
                            for fieldname in person_fieldnames
                        ]
                    )
                if progress_callback and (
                    household_index % progress_interval == 0
                    or household_index == households
                ):
                    progress_callback(household_index, person_count)

    return households, person_count


def generate_person_rows_for_household(
    person_model: TreeModel,
    *,
    rows: int,
    conditions: dict[str, str],
    rng: random.Random,
    selection_cache: dict[tuple[tuple[str, str], ...], _FrequencySelection],
) -> list[dict[str, str]]:
    return list(
        iter_person_rows_for_household(
            person_model,
            rows=rows,
            conditions=conditions,
            rng=rng,
            selection_cache=selection_cache,
        )
    )


def iter_person_rows_for_household(
    person_model: TreeModel,
    *,
    rows: int,
    conditions: dict[str, str],
    rng: random.Random,
    selection_cache: dict[tuple[tuple[str, str], ...], _FrequencySelection],
):
    if not isinstance(person_model, FrequencyTreeModel):
        yield from iter_tree_rows(
            person_model,
            rows=rows,
            conditions=conditions,
            random_seed=rng.randrange(1, 2**31),
        )
        return
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    cache_key = frequency_selection_cache_key(person_model, conditions)
    selection = selection_cache.get(cache_key)
    if selection is None:
        selection = prepare_frequency_selection(person_model, conditions)
        selection_cache[cache_key] = selection
    for index in range(1, rows + 1):
        group, outcome = choose_frequency_group_and_outcome(selection, rng)
        yield {
            "synthetic_id": str(index),
            **group.conditions,
            **outcome.values,
        }


def frequency_selection_cache_key(
    model: FrequencyTreeModel,
    conditions: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    validate_condition_columns(model.spec.conditioning_columns, conditions)
    return tuple(
        (column, conditions.get(column, ""))
        for column in model.spec.conditioning_columns
    )


def validate_linked_population(
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    household_id_column: str = "synthetic_household_id",
    person_household_id_column: str = "synthetic_household_id",
    household_size_column: str = "household_size",
) -> dict[str, object]:
    """Validate household-person links and household-size consistency.

    The report checks that person rows reference generated households and that
    each household has the number of persons stated in ``household_size_column``.
    """

    household_counts: dict[str, int] = defaultdict(int)
    household_ids = {
        household.get(household_id_column, "") for household in households
    } - {""}
    unknown_person_households = 0
    for person in persons:
        household_id = person.get(person_household_id_column, "")
        if household_id not in household_ids:
            unknown_person_households += 1
            continue
        household_counts[household_id] += 1

    issues: list[dict[str, object]] = []
    for household in households:
        household_id = household.get(household_id_column, "")
        try:
            expected_persons = read_household_size(household, household_size_column)
        except ValueError as exc:
            issues.append(
                {
                    "severity": "error",
                    "kind": "invalid_household_size",
                    "household_id": household_id,
                    "message": str(exc),
                }
            )
            continue
        actual_persons = household_counts.get(household_id, 0)
        if expected_persons != actual_persons:
            issues.append(
                {
                    "severity": "error",
                    "kind": "household_size_mismatch",
                    "household_id": household_id,
                    "expected_persons": expected_persons,
                    "actual_persons": actual_persons,
                    "message": (
                        f"household {household_id} expected {expected_persons} "
                        f"persons but has {actual_persons}."
                    ),
                }
            )

    if unknown_person_households:
        issues.append(
            {
                "severity": "error",
                "kind": "unknown_person_household",
                "persons": unknown_person_households,
                "message": (
                    f"{unknown_person_households} person rows reference unknown "
                    "households."
                ),
            }
        )

    size_mismatches = sum(
        1 for issue in issues if issue["kind"] == "household_size_mismatch"
    )
    return {
        "passed": not issues,
        "summary": {
            "households": len(households),
            "persons": len(persons),
            "households_with_size_mismatches": size_mismatches,
            "persons_with_unknown_households": unknown_person_households,
        },
        "household_id_column": household_id_column,
        "person_household_id_column": person_household_id_column,
        "household_size_column": household_size_column,
        "issues": issues,
    }


def strip_synthetic_id(row: dict[str, str]) -> dict[str, str]:
    return {column: value for column, value in row.items() if column != "synthetic_id"}


def read_household_size(row: dict[str, str], household_size_column: str) -> int:
    value = row.get(household_size_column)
    if value is None:
        raise ValueError(f"missing household size column: {household_size_column}")
    try:
        household_size = int(value)
    except ValueError as exc:
        raise ValueError(f"household size {value!r} is not a whole number") from exc
    if household_size <= 0:
        raise ValueError("household size must be greater than zero")
    return household_size


def household_conditions_for_person_model(
    household: dict[str, str],
    person_model: TreeModel,
) -> dict[str, str]:
    missing = [
        column
        for column in person_model.spec.conditioning_columns
        if column not in household
    ]
    if missing:
        raise ValueError(
            "household rows cannot condition the person model; missing columns: "
            + ", ".join(missing)
        )
    return {
        column: household[column] for column in person_model.spec.conditioning_columns
    }


def generate_cart_rows(
    model: CartTreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
) -> list[dict[str, str]]:
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    requested_conditions = conditions or {}
    validate_condition_columns(model.spec.conditioning_columns, requested_conditions)
    rng = random.Random(model.spec.random_seed if random_seed is None else random_seed)
    feature_row = {
        column: requested_conditions.get(column, "")
        for column in model.spec.conditioning_columns
    }
    encoded = encode_conditions(
        feature_row,
        model.spec.conditioning_columns,
        model.feature_categories,
    )
    leaf_id = cart_leaf_id(model, encoded)
    outcomes = tuple(
        FrequencyOutcome(values=target_class, weight=weight)
        for target_class, weight in zip(
            model.target_classes,
            model.value[leaf_id],
            strict=True,
        )
        if weight > 0
    )
    if not outcomes:
        raise ValueError("selected CART leaf has no positive target probabilities")
    generated_rows: list[dict[str, str]] = []
    for index in range(1, rows + 1):
        outcome = choose_outcome(outcomes, rng)
        generated_rows.append(
            {
                "synthetic_id": str(index),
                **feature_row,
                **outcome.values,
            }
        )
    return generated_rows


def iter_cart_rows(
    model: CartTreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
):
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    requested_conditions = conditions or {}
    validate_condition_columns(model.spec.conditioning_columns, requested_conditions)
    rng = random.Random(model.spec.random_seed if random_seed is None else random_seed)
    feature_row = {
        column: requested_conditions.get(column, "")
        for column in model.spec.conditioning_columns
    }
    encoded = encode_conditions(
        feature_row,
        model.spec.conditioning_columns,
        model.feature_categories,
    )
    leaf_id = cart_leaf_id(model, encoded)
    outcomes = tuple(
        FrequencyOutcome(values=target_class, weight=weight)
        for target_class, weight in zip(
            model.target_classes,
            model.value[leaf_id],
            strict=True,
        )
        if weight > 0
    )
    if not outcomes:
        raise ValueError("selected CART leaf has no positive target probabilities")
    for index in range(1, rows + 1):
        outcome = choose_outcome(outcomes, rng)
        yield {
            "synthetic_id": str(index),
            **feature_row,
            **outcome.values,
        }


def generate_frequency_rows(
    model: FrequencyTreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
) -> list[dict[str, str]]:
    return list(
        iter_frequency_rows(
            model,
            rows=rows,
            conditions=conditions,
            random_seed=random_seed,
        )
    )


def iter_frequency_rows(
    model: FrequencyTreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
):
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    rng = random.Random(model.spec.random_seed if random_seed is None else random_seed)
    selection = prepare_frequency_selection(model, conditions or {})
    for index in range(1, rows + 1):
        group, outcome = choose_frequency_group_and_outcome(selection, rng)
        yield {
            "synthetic_id": str(index),
            **group.conditions,
            **outcome.values,
        }


def write_frequency_model(path: Path, model: FrequencyTreeModel) -> None:
    path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n")


def write_tree_model(path: Path, model: TreeModel) -> None:
    """Write a tree model JSON file.

    The JSON schema is the portable artifact format used by the CLI and
    library. It stores model structure, metadata, and privacy/release metadata,
    but not raw training rows.
    """

    path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n")


def read_tree_model(path: Path) -> TreeModel:
    """Read a tree model JSON file and return the matching model class.

    The model type is read from the JSON payload and dispatched to either
    :class:`FrequencyTreeModel` or :class:`CartTreeModel`.
    """

    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if payload.get("model_type") == "conditional-frequency":
        return FrequencyTreeModel.from_dict(payload)
    if payload.get("model_type") == "cart":
        return CartTreeModel.from_dict(payload)
    raise ValueError("unsupported tree model type")


def read_frequency_model(path: Path) -> FrequencyTreeModel:
    """Read a conditional-frequency tree model JSON file.

    Raises ``ValueError`` if the JSON file contains a different supported model
    family.
    """

    payload = read_tree_model(path)
    if not isinstance(payload, FrequencyTreeModel):
        raise ValueError("tree model is not a conditional-frequency model")
    return payload


def read_cart_model(path: Path) -> CartTreeModel:
    """Read a CART tree model JSON file.

    Raises ``ValueError`` if the JSON file contains a different supported model
    family.
    """

    payload = read_tree_model(path)
    if not isinstance(payload, CartTreeModel):
        raise ValueError("tree model is not a CART model")
    return payload


def write_generated_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write generated rows to CSV using the first row's column order.

    This helper is intentionally simple and deterministic. It raises
    ``ValueError`` for empty output because there is no first row from which to
    infer CSV columns.
    """

    if not rows:
        raise ValueError("cannot write empty generated output")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def unique_fieldnames(fieldnames: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for fieldname in fieldnames:
        if fieldname not in output:
            output.append(fieldname)
    return tuple(output)


def parse_conditions(values: tuple[str, ...]) -> dict[str, str]:
    """Parse ``COLUMN=VALUE`` strings into a conditions dictionary."""

    conditions: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"condition {value!r} must use COLUMN=VALUE")
        column, condition_value = value.split("=", 1)
        if not column:
            raise ValueError(f"condition {value!r} must include a column name")
        conditions[column] = condition_value
    return conditions


def validate_tree_roles(
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> None:
    if not target_columns:
        raise ValueError("at least one target column is required")
    if not conditioning_columns:
        raise ValueError("at least one conditioning column is required")

    overlap = sorted(set(target_columns) & set(conditioning_columns))
    if overlap:
        raise ValueError(
            f"target and conditioning columns must not overlap: {', '.join(overlap)}"
        )


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def encode_conditions(
    record: dict[str, str],
    conditioning_columns: tuple[str, ...],
    feature_categories: dict[str, tuple[str, ...]],
) -> list[float]:
    encoded: list[float] = []
    for column in conditioning_columns:
        value = record.get(column, "")
        encoded.extend(
            1.0 if value == category else 0.0 for category in feature_categories[column]
        )
    return encoded


def validate_condition_columns(
    conditioning_columns: tuple[str, ...],
    conditions: dict[str, str],
) -> None:
    missing = [column for column in conditions if column not in conditioning_columns]
    if missing:
        raise ValueError(f"unknown conditioning columns: {', '.join(missing)}")


def cart_leaf_id(model: CartTreeModel, encoded: list[float]) -> int:
    node_id = 0
    while model.children_left[node_id] != model.children_right[node_id]:
        feature_index = model.feature[node_id]
        threshold = model.threshold[node_id]
        if encoded[feature_index] <= threshold:
            node_id = model.children_left[node_id]
        else:
            node_id = model.children_right[node_id]
    return node_id


def read_record_weight(
    record: dict[str, str], weight_column: str | None, row_number: int
) -> float:
    if weight_column is None:
        return 1.0
    try:
        return float(record[weight_column])
    except ValueError as exc:
        raise ValueError(f"row {row_number} has invalid weight") from exc


def frequency_outcomes(
    target_columns: tuple[str, ...],
    outcome_counts: dict[tuple[str, ...], float],
) -> tuple[FrequencyOutcome, ...]:
    return tuple(
        FrequencyOutcome(
            values=dict(zip(target_columns, target_key, strict=True)),
            weight=weight,
        )
        for target_key, weight in sorted(outcome_counts.items())
    )


def choose_group(
    model: FrequencyTreeModel,
    conditions: dict[str, str],
    rng: random.Random,
) -> FrequencyGroup:
    selection = prepare_frequency_selection(model, conditions)
    return weighted_choice_from_cumulative(
        selection.groups,
        selection.group_cumulative_weights,
        rng,
    )


def choose_outcome(
    outcomes: tuple[FrequencyOutcome, ...], rng: random.Random
) -> FrequencyOutcome:
    return weighted_choice(outcomes, tuple(outcome.weight for outcome in outcomes), rng)


def prepare_frequency_selection(
    model: FrequencyTreeModel,
    conditions: dict[str, str],
) -> _FrequencySelection:
    groups = matching_frequency_groups(model, conditions)
    return _FrequencySelection(
        groups=groups,
        group_cumulative_weights=cumulative_weights(group.support for group in groups),
        outcome_cumulative_weights_by_group={
            id(group): cumulative_weights(outcome.weight for outcome in group.outcomes)
            for group in groups
        },
    )


def matching_frequency_groups(
    model: FrequencyTreeModel,
    conditions: dict[str, str],
) -> tuple[FrequencyGroup, ...]:
    if not conditions:
        return model.groups
    missing = [
        column for column in conditions if column not in model.spec.conditioning_columns
    ]
    if missing:
        raise ValueError(f"unknown conditioning columns: {', '.join(missing)}")
    matches = tuple(
        group
        for group in model.groups
        if all(
            group.conditions.get(column) == value
            for column, value in conditions.items()
        )
    )
    if matches:
        return matches
    return (
        FrequencyGroup(
            conditions={
                column: conditions.get(column, "")
                for column in model.spec.conditioning_columns
            },
            support=sum(outcome.weight for outcome in model.global_outcomes),
            outcomes=model.global_outcomes,
        ),
    )


def choose_frequency_group_and_outcome(
    selection: _FrequencySelection,
    rng: random.Random,
) -> tuple[FrequencyGroup, FrequencyOutcome]:
    group = weighted_choice_from_cumulative(
        selection.groups,
        selection.group_cumulative_weights,
        rng,
    )
    outcome = weighted_choice_from_cumulative(
        group.outcomes,
        selection.outcome_cumulative_weights_by_group[id(group)],
        rng,
    )
    return group, outcome


def weighted_choice(items, weights: Sequence[float], rng: random.Random):
    return weighted_choice_from_cumulative(items, cumulative_weights(weights), rng)


def cumulative_weights(weights) -> tuple[float, ...]:
    cumulative: list[float] = []
    total = 0.0
    for weight in weights:
        total += weight
        cumulative.append(total)
    if total <= 0:
        raise ValueError("cannot sample from non-positive weights")
    return tuple(cumulative)


def weighted_choice_from_cumulative(
    items,
    cumulative_weights: tuple[float, ...],
    rng: random.Random,
):
    threshold = rng.uniform(0, cumulative_weights[-1])
    index = bisect_left(cumulative_weights, threshold)
    if index >= len(cumulative_weights):
        return items[-1]
    return items[index]
