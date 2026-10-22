"""Compatibility checks for preferred names and existing extension hooks."""

from __future__ import annotations

import importlib
import json

import click
import pytest

from synthpopcan.benchmarks import PROVINCE_SCALE_SMALL_AREA_BUDGET
from synthpopcan.cli import cli
from synthpopcan.tree import (
    FrequencyGroup,
    FrequencyOutcome,
    TreeModelSpec,
    TreeTrainingSample,
    train_cart_model,
    train_frequency_model,
)


@pytest.mark.parametrize(
    ("module_name", "old_name", "preferred_name"),
    [
        ("controls", "WdsSelection", "WDSSelection"),
        ("tree", "CartTreeModel", "CARTTreeModel"),
        ("odef", "OdefAdapter", "ODEFAdapter"),
        ("cli", "run_statcan_wds_fetch", "statcan_wds_fetch_command"),
        ("cli_ipf", "_fit_ipf_command", "fit_ipf_command"),
        ("cli_geo", "small_area", "small_area_group"),
        ("cli_tree", "model_build", "model_build_group"),
    ],
)
def test_legacy_imports_resolve_to_preferred_objects(
    module_name, old_name, preferred_name
):
    module = importlib.import_module(f"synthpopcan.{module_name}")
    assert getattr(module, old_name) is getattr(module, preferred_name)


def test_control_advice_preserves_the_old_import_and_signature():
    from synthpopcan.calibration import build_control_suggestion_report as legacy
    from synthpopcan.control_suggestions import build_control_suggestion_report

    assert legacy is build_control_suggestion_report
    assert legacy([{"TENUR": "owned"}], unit="household")["unit"] == "household"


def test_registered_callbacks_use_consistent_names():
    def walk(command):
        if command is not cli:
            suffix = "_group" if isinstance(command, click.Group) else "_command"
            assert command.callback is not None
            assert command.callback.__name__.endswith(suffix), command.name
        if isinstance(command, click.Group):
            for child in command.commands.values():
                walk(child)

    walk(cli)


@pytest.fixture
def serialized_objects():
    outcome = FrequencyOutcome({"tenure": "owner"}, 1.0)
    sample = TreeTrainingSample(
        level="household",
        source_format="synthetic-naming-fixture",
        records=({"geo": "A", "tenure": "owner"}, {"geo": "B", "tenure": "renter"}),
        columns=("geo", "tenure"),
        target_columns=("tenure",),
        conditioning_columns=("geo",),
    )
    return {
        "spec": TreeModelSpec("household", ("tenure",), ("geo",)),
        "outcome": outcome,
        "group": FrequencyGroup({}, 1.0, (outcome,), 1),
        "frequency": train_frequency_model(sample),
        "cart": train_cart_model(sample, min_samples_leaf=1),
        "budget": PROVINCE_SCALE_SMALL_AREA_BUDGET,
    }


@pytest.mark.parametrize(
    "kind", ["spec", "outcome", "group", "frequency", "cart", "budget"]
)
def test_preferred_serialization_matches_legacy_payload(kind, serialized_objects):
    value = serialized_objects[kind]
    assert value.as_dict() == value.to_dict()
    assert json.loads(json.dumps(value.as_dict())) == value.to_dict()
    if kind in {"frequency", "cart"}:
        restored = type(value).from_dict(value.as_dict())
        assert restored.as_dict() == value.to_dict()


def test_preferred_serialization_honors_legacy_override(
    monkeypatch, serialized_objects
):
    value = serialized_objects["frequency"]
    monkeypatch.setattr(type(value), "to_dict", lambda self: {"legacy_override": True})
    assert value.as_dict() == {"legacy_override": True}
