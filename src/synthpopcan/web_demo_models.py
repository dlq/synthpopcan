"""Safe demo model payloads for the local web app."""

from __future__ import annotations


def demo_model_catalogue() -> list[dict[str, object]]:
    """Return safe demo models served by the local app."""
    return [
        {
            "id": "demo-linked-household-person",
            "name": "Safe demo household/person package",
            "description": (
                "Tiny linked model trained from synthetic toy rows; not derived "
                "from Census microdata."
            ),
            "kind": "linked_household_person",
            "geography": "Demo regions",
            "safe_demo": True,
        }
    ]


def demo_model_payload(model_id: str) -> dict[str, object]:
    """Return a prepared demo model package.

    The package is intentionally trained from toy synthetic rows so it can be
    bundled and served without disclosure risk.
    """
    if model_id != "demo-linked-household-person":
        raise KeyError(model_id)
    return {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "name": "Safe demo household/person package",
        "description": (
            "Demonstration package trained from synthetic toy rows. It exercises "
            "linked household/person generation without using restricted data."
        ),
        "household_size_column": "household_size",
        "privacy": {
            "publishable_candidate": True,
            "safe_demo": True,
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "source": "synthetic toy rows only",
        },
        "provenance": {
            "source": "SynthPopCan bundled demo",
            "training_data": "hand-authored synthetic toy distribution",
            "contains_real_microdata": False,
        },
        "models": {
            "household": demo_household_model(),
            "person": demo_person_model(),
        },
    }


def demo_household_model() -> dict[str, object]:
    return {
        "schema_version": "synthpopcan-tree-model-v1",
        "model_type": "conditional-frequency",
        "release_class": "publishable_candidate",
        "spec": {
            "level": "household",
            "model_family": "tree-based",
            "target_columns": ["household_size", "tenure"],
            "conditioning_columns": ["geo"],
            "geography_column": "geo",
            "weight_column": None,
            "random_seed": 101,
        },
        "source_format": "synthetic-demo-v1",
        "records_trained": 96,
        "groups": [
            {
                "conditions": {"geo": "Demo North"},
                "support": 48,
                "outcomes": [
                    {
                        "values": {"household_size": "1", "tenure": "renter"},
                        "weight": 10,
                    },
                    {
                        "values": {"household_size": "2", "tenure": "owner"},
                        "weight": 24,
                    },
                    {
                        "values": {"household_size": "3", "tenure": "owner"},
                        "weight": 14,
                    },
                ],
            },
            {
                "conditions": {"geo": "Demo South"},
                "support": 48,
                "outcomes": [
                    {
                        "values": {"household_size": "1", "tenure": "renter"},
                        "weight": 18,
                    },
                    {
                        "values": {"household_size": "2", "tenure": "renter"},
                        "weight": 16,
                    },
                    {
                        "values": {"household_size": "4", "tenure": "owner"},
                        "weight": 14,
                    },
                ],
            },
        ],
        "global_outcomes": [
            {"values": {"household_size": "1", "tenure": "renter"}, "weight": 28},
            {"values": {"household_size": "2", "tenure": "owner"}, "weight": 24},
            {"values": {"household_size": "3", "tenure": "owner"}, "weight": 14},
            {"values": {"household_size": "2", "tenure": "renter"}, "weight": 16},
            {"values": {"household_size": "4", "tenure": "owner"}, "weight": 14},
        ],
        "privacy": {
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "minimum_support": 48,
            "min_support_threshold": 5,
            "groups_below_threshold": 0,
            "publishable": True,
            "safe_demo": True,
        },
    }


def demo_person_model() -> dict[str, object]:
    person_outcomes = [
        {"values": {"age_group": "child", "sex": "F"}, "weight": 1},
        {"values": {"age_group": "adult", "sex": "F"}, "weight": 2},
        {"values": {"age_group": "adult", "sex": "M"}, "weight": 2},
        {"values": {"age_group": "older", "sex": "F"}, "weight": 1},
    ]
    groups = []
    for geo in ("Demo North", "Demo South"):
        for household_size in ("1", "2", "3", "4"):
            for tenure in ("owner", "renter"):
                groups.append(
                    {
                        "conditions": {
                            "geo": geo,
                            "household_size": household_size,
                            "tenure": tenure,
                        },
                        "support": 12,
                        "outcomes": person_outcomes,
                    }
                )
    return {
        "schema_version": "synthpopcan-tree-model-v1",
        "model_type": "conditional-frequency",
        "release_class": "publishable_candidate",
        "spec": {
            "level": "person",
            "model_family": "tree-based",
            "target_columns": ["age_group", "sex"],
            "conditioning_columns": ["geo", "household_size", "tenure"],
            "geography_column": "geo",
            "weight_column": None,
            "random_seed": 202,
        },
        "source_format": "synthetic-demo-v1",
        "records_trained": 192,
        "groups": groups,
        "global_outcomes": person_outcomes,
        "privacy": {
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "minimum_support": 12,
            "min_support_threshold": 5,
            "groups_below_threshold": 0,
            "publishable": True,
            "safe_demo": True,
        },
    }
