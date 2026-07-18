import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/build_all_model_packages.py"
SPEC = importlib.util.spec_from_file_location("build_all_model_packages", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCES = MODULE.SOURCES
targets_for_year = MODULE.targets_for_year


def test_2021_batch_declares_complete_parallel_catalogue() -> None:
    targets = targets_for_year(2021)
    ids = {target["id"] for target in targets}

    assert len(targets) == 16
    assert "canada-2021" in ids
    assert "quebec-2021" in ids
    assert "montreal-cma-2021" in ids
    assert {target["package_file"] for target in targets} >= {
        "canada-2021-all-fields-package.json",
        "quebec-2021-all-fields-package.json",
        "montreal-cma-2021-all-fields-package.json",
        "pei-2021-minimal-package.json",
    }
    assert SOURCES[2021].name == "data_donnees_2021_hier_v2.csv"


def test_2016_batch_retains_historical_scope() -> None:
    ids = {target["id"] for target in targets_for_year(2016)}

    assert len(ids) == 13
    assert "canada-2016" not in ids
    assert "quebec-2016" not in ids
    assert "montreal-cma-2016" not in ids
    assert SOURCES[2016].name == "data_donnees_2016_hier.csv"
