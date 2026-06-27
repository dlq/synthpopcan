"""Canadian synthetic population tooling.

The top-level package intentionally exposes a small beginner-friendly API for
notebooks and short scripts. Import from modules such as ``synthpopcan.ipf`` or
``synthpopcan.tree`` when you need lower-level research and maintainer tools.
"""

from synthpopcan.api import (
    LinkedPopulation,
    calibrate_small_area_linked,
    expand_population,
    fit_ipf,
    generate_from_model,
    read_controls,
    read_model_package,
    read_seed,
    render_small_area_map,
    write_population,
    write_weights,
)

__all__ = [
    "LinkedPopulation",
    "__version__",
    "calibrate_small_area_linked",
    "expand_population",
    "fit_ipf",
    "generate_from_model",
    "read_controls",
    "read_model_package",
    "read_seed",
    "render_small_area_map",
    "write_population",
    "write_weights",
]

__version__ = "0.2.0"
