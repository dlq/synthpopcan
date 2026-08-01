"""Smoke-test the installed ``model-build`` extra outside the checkout."""

from __future__ import annotations

import os
from importlib.metadata import requires
from pathlib import Path

import synthpopcan
from synthpopcan.tree import TreeTrainingSample, train_cart_model

package_path = Path(synthpopcan.__file__).resolve()
source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
if source_root in package_path.parents:
    raise RuntimeError(f"model-build smoke imported from checkout: {package_path}")
assert "site-packages" in package_path.parts

requirements = requires("synthpopcan") or []
assert any(
    "scikit-learn" in requirement
    and "extra == 'model-build'" in requirement.replace('"', "'")
    for requirement in requirements
)

sample = TreeTrainingSample(
    level="household",
    source_format="synthetic-smoke-fixture",
    records=(
        {"geo": "A", "tenure": "owner"},
        {"geo": "A", "tenure": "renter"},
        {"geo": "B", "tenure": "owner"},
        {"geo": "B", "tenure": "renter"},
    ),
    columns=("geo", "tenure"),
    target_columns=("tenure",),
    conditioning_columns=("geo",),
    geography_column="geo",
)
model = train_cart_model(sample, random_seed=7, min_samples_leaf=1, max_depth=2)
payload = model.to_dict()
assert payload["model_type"] == "cart"
assert payload["privacy"]["contains_raw_rows"] is False

print(f"Installed model-build smoke passed: {package_path}")
