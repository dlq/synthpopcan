"""Canadian synthetic population tooling.

The top-level package intentionally exposes a small beginner-friendly API for
notebooks and short scripts. Import from modules such as ``synthpopcan.ipf`` or
``synthpopcan.tree`` when you need lower-level research and maintainer tools.
The beginner surface also supports validated enrichment sidecars without
exposing source-specific adapter internals.
"""

from synthpopcan.api import (
    ControlTable,
    EnrichmentResult,
    IPFResult,
    LinkedPopulation,
    LinkedPopulationFiles,
    PopulationRows,
    SmallAreaResult,
    calibrate_small_area,
    enrich_can_fed,
    enrich_odef,
    enrich_population,
    expand_population,
    fetch_model,
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
    "EnrichmentResult",
    "IPFResult",
    "LinkedPopulation",
    "LinkedPopulationFiles",
    "PopulationRows",
    "SmallAreaResult",
    "__version__",
    "calibrate_small_area",
    "enrich_can_fed",
    "enrich_odef",
    "enrich_population",
    "expand_population",
    "fetch_model",
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

__version__ = "0.7.2"
