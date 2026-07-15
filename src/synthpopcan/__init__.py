"""Canadian synthetic population tooling.

The top-level package intentionally exposes a small beginner-friendly API for
notebooks and short scripts. Import from modules such as ``synthpopcan.ipf`` or
``synthpopcan.tree`` when you need lower-level research and maintainer tools.
"""

from synthpopcan.api import (
    ControlTable,
    IPFResult,
    LinkedPopulation,
    LinkedPopulationFiles,
    PopulationRows,
    SmallAreaResult,
    calibrate_small_area,
    expand_population,
    fit_ipf,
    generate_from_model,
    read_controls,
    read_model_package,
    read_seed,
    render_small_area_map,
    write_linked_population,
    write_population,
    write_weights,
)

__all__ = [
    "ControlTable",
    "IPFResult",
    "LinkedPopulation",
    "LinkedPopulationFiles",
    "PopulationRows",
    "SmallAreaResult",
    "__version__",
    "calibrate_small_area",
    "expand_population",
    "fit_ipf",
    "generate_from_model",
    "read_controls",
    "read_model_package",
    "read_seed",
    "render_small_area_map",
    "write_linked_population",
    "write_population",
    "write_weights",
]

__version__ = "0.5.1"
