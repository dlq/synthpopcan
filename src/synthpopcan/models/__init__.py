"""Packaged and downloadable linked model artifacts.

The installed package intentionally bundles only tiny demo data. Larger
publishable-candidate model packages are listed in a registry and fetched into a
local cache only when a user asks for them.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from synthpopcan.model_licensing import (
    STATCAN_OPEN_LICENCE_URL,
    normalize_prepared_model_licensing,
    statcan_prepared_model_licensing,
    synthetic_demo_model_licensing,
)

ProgressCallback = Callable[[int, int | None], None]

_RELEASE_BASE_URL = "https://github.com/dlq/synthpopcan/releases/download/v0.2.1"
_PUMF_2021_RELEASE_BASE_URL = (
    "https://github.com/dlq/synthpopcan/releases/download/v0.6.0"
)
_BROWSER_MODEL_MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024

# Statistics Canada public use microdata files are "Information" under the
# Statistics Canada Open Licence, which grants the right to distribute
# "Value-added Products" derived from them. Models trained on a PUMF are such a
# product, so the catalogue carries the licence's prescribed "Adapted from ...
# does not constitute an endorsement" attribution notice. Corrected package
# bytes will embed the same notice; registered historical bytes are enriched
# only after their catalogue checksum is verified.
_STATCAN_OPEN_LICENCE = STATCAN_OPEN_LICENCE_URL
_PUMF_2016_LICENSING = statcan_prepared_model_licensing(2016)
_PUMF_2021_LICENSING = statcan_prepared_model_licensing(2021)

_DEMO_CATALOGUE_METADATA = {
    "census_vintage": "Not applicable",
    "release_status": "publishable_candidate",
    "release_version": "v0.4.0",
    "source_licence": "Not applicable; synthetic demonstration rows.",
    "privacy": "No raw rows or source identifiers.",
    "privacy_review_status": "safe synthetic demo",
    "generation_limits": "Small exploratory browser runs.",
    "known_limitations": (
        "Synthetic demonstration only; not representative of Canada."
    ),
}
_PUMF_2016_CATALOGUE_METADATA = {
    "census_vintage": "2016 Census",
    "release_status": "publishable_candidate",
    "release_version": "v0.2.1",
    "provenance": _PUMF_2016_LICENSING["source_information"][  # type: ignore[index]
        "prescribed_notice"
    ],
    "source_licence": _STATCAN_OPEN_LICENCE,
    "privacy": "No raw rows or source identifiers.",
    "privacy_review_status": "publishable candidate; human review still required",
    "generation_limits": (
        "Small exploratory browser runs; use the CLI for large outputs."
    ),
    "known_limitations": (
        "Broad 2016 PUMF model; not calibrated to current or small-area controls. "
        "Generated source codes require field metadata for interpretation."
    ),
    "safe_demo": False,
    "distribution": "download",
    "compression": "gzip",
}
_PUMF_2021_CATALOGUE_METADATA = {
    "census_vintage": "2021 Census",
    "release_status": "publishable_candidate",
    "release_version": "v0.6.0",
    "provenance": _PUMF_2021_LICENSING["source_information"][  # type: ignore[index]
        "prescribed_notice"
    ],
    "source_licence": _STATCAN_OPEN_LICENCE,
    "privacy": "No raw rows or source identifiers.",
    "privacy_review_status": "publishable candidate; human review still required",
    "generation_limits": (
        "Use durable Python-backed web runs or the CLI; review memory, disk, and "
        "output scale before large generation."
    ),
    "known_limitations": (
        "Broad 2021 PUMF model; not calibrated to small-area controls. Generated "
        "source codes require field metadata for interpretation. Some sparse "
        "geographies use privacy-safe CART models instead of direct conditional "
        "frequencies."
    ),
    "safe_demo": False,
    "distribution": "download",
    "compression": "gzip",
}

_MODEL_PACKAGES: dict[str, dict[str, Any]] = {
    "demo-linked-household-person": {
        **_DEMO_CATALOGUE_METADATA,
        "filename": "demo-linked-household-person-package.json",
        "name": "Safe demo household/person package",
        "description": (
            "Tiny linked model trained from synthetic toy rows; not derived "
            "from Census microdata."
        ),
        "geography": "Demo regions",
        "provenance": "Synthetic toy rows only; not Census microdata.",
        "conditions": ["geo"],
        "default_generation": {
            "households": 10,
            "conditions": "geo=Demo North",
        },
        "safe_demo": True,
        "distribution": "bundled",
    },
    "montreal-cma-2016-all-fields": {
        "filename": "montreal-cma-2016-all-fields-package.json",
        "name": "Montreal CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for CMA 462."
        ),
        "geography": "Montreal CMA (CMA 462)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 1_009_496,
        "sha256": "94ff771884ead36b604d05c8e4043e36869da85c75aa1919f31adf21fd4aee97",
        "uncompressed_size_bytes": 64_234_759,
        "uncompressed_sha256": (
            "ebad14c83bf2aef47e3ac6e0684c1994ea0fa8cd83df7eaeb78a76077174ef91"
        ),
        "url": f"{_RELEASE_BASE_URL}/montreal-cma-2016-all-fields-package.json.gz",
    },
    "quebec-2016-all-fields": {
        "filename": "quebec-2016-all-fields-package.json",
        "name": "Quebec 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Quebec (PR 24)."
        ),
        "geography": "Quebec (PR 24)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 1_770_789,
        "sha256": "1f03b9c5e72c5641f31159f0af3d4c3839e142445f17c81d3fd2f969c74a0628",
        "uncompressed_size_bytes": 122_079_409,
        "uncompressed_sha256": (
            "7fbfa64e29ae5539f382475c472cb1fe48b988161e0b3a10ecd81fcaa942a7d7"
        ),
        "url": f"{_RELEASE_BASE_URL}/quebec-2016-all-fields-package.json.gz",
    },
    "ontario-2016-all-fields": {
        "filename": "ontario-2016-all-fields-package.json",
        "name": "Ontario 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Ontario (PR 35)."
        ),
        "geography": "Ontario (PR 35)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 3_005_146,
        "sha256": "7477a7161b8243aba5ef64c902a9db303290733edb5b2832210c1fd7075ff879",
        "uncompressed_size_bytes": 205_757_139,
        "uncompressed_sha256": (
            "0967ba99c4179e3de1d8436a14e0b3082bd4a7353c68b9c59a4c32977711e7ed"
        ),
        "url": f"{_RELEASE_BASE_URL}/ontario-2016-all-fields-package.json.gz",
    },
    "bc-2016-all-fields": {
        "filename": "bc-2016-all-fields-package.json",
        "name": "British Columbia 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for British Columbia (PR 59)."
        ),
        "geography": "British Columbia (PR 59)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 1_198_845,
        "sha256": "13b04e77c3aab726aaf1ef9164ec5ef1c2ed16d710f275f3b3dcfa09ca476f6a",
        "uncompressed_size_bytes": 75_781_376,
        "uncompressed_sha256": (
            "76e855c2d2bd6b62ef7e7073c4df5ea288fe0f8e060c5e36859c24047a56fb54"
        ),
        "url": f"{_RELEASE_BASE_URL}/bc-2016-all-fields-package.json.gz",
    },
    "alberta-2016-all-fields": {
        "filename": "alberta-2016-all-fields-package.json",
        "name": "Alberta 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Alberta (PR 48)."
        ),
        "geography": "Alberta (PR 48)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 1_008_748,
        "sha256": "da034db035a0ebc8d96cf012b3698fd6c14b648967389832446fe10c48b73ce8",
        "uncompressed_size_bytes": 63_448_287,
        "uncompressed_sha256": (
            "0f0f61fc0a3e188b1c64ea02acc3f05fbfdb0d993ffee3a901b5b51f7fe81814"
        ),
        "url": f"{_RELEASE_BASE_URL}/alberta-2016-all-fields-package.json.gz",
    },
    "toronto-cma-2016-all-fields": {
        "filename": "toronto-cma-2016-all-fields-package.json",
        "name": "Toronto CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Toronto CMA (CMA 535)."
        ),
        "geography": "Toronto CMA (CMA 535)",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 1_478_757,
        "sha256": "157778bc2bd095d65b1fab91fdbcb0385ed5de76baad20abe82817211b0735c2",
        "uncompressed_size_bytes": 93_385_062,
        "uncompressed_sha256": (
            "dd0caf299c852ed526861b9bc6e6a2d654bf0bbe51809d76c9b5e30da0381ae0"
        ),
        "url": f"{_RELEASE_BASE_URL}/toronto-cma-2016-all-fields-package.json.gz",
    },
    "vancouver-cma-2016-all-fields": {
        "filename": "vancouver-cma-2016-all-fields-package.json",
        "name": "Vancouver CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Vancouver CMA (CMA 933)."
        ),
        "geography": "Vancouver CMA (CMA 933)",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 687_436,
        "sha256": "a92cbb27f0e149bd7b83da2055b43d3a4fa1e5bc1567a29208c335f10fba49c6",
        "uncompressed_size_bytes": 40_937_245,
        "uncompressed_sha256": (
            "3e3565c2ba4dbfdab28bf907e256d48bb766971270dde09fde597afb57c210cf"
        ),
        "url": f"{_RELEASE_BASE_URL}/vancouver-cma-2016-all-fields-package.json.gz",
    },
    "manitoba-2016-all-fields": {
        "filename": "manitoba-2016-all-fields-package.json",
        "name": "Manitoba 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Manitoba (PR 46)."
        ),
        "geography": "Manitoba (PR 46)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 336_929,
        "sha256": "70ca5e7944ff135813d1aaff04f2f7c9a25f98bd3ecc27c069124aad784ffa6d",
        "uncompressed_size_bytes": 20_186_538,
        "uncompressed_sha256": (
            "82e8f03152568a3898c80de36705827f8a22101a1390a2b9f381df366a9088f4"
        ),
        "url": f"{_RELEASE_BASE_URL}/manitoba-2016-all-fields-package.json.gz",
    },
    "calgary-cma-2016-all-fields": {
        "filename": "calgary-cma-2016-all-fields-package.json",
        "name": "Calgary CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Calgary CMA (CMA 825)."
        ),
        "geography": "Calgary CMA (CMA 825)",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 391_581,
        "sha256": "0ed93270044c97fbd2d6b8e6222192dc438e990f2c5f70dbeb1ed9ada51b7500",
        "uncompressed_size_bytes": 22_635_036,
        "uncompressed_sha256": (
            "d55fe22cfa66c5b78545b65e3275972ebc2f37e714f9a6b266040ec9a0a407a2"
        ),
        "url": f"{_RELEASE_BASE_URL}/calgary-cma-2016-all-fields-package.json.gz",
    },
    "edmonton-cma-2016-all-fields": {
        "filename": "edmonton-cma-2016-all-fields-package.json",
        "name": "Edmonton CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Edmonton CMA (CMA 835)."
        ),
        "geography": "Edmonton CMA (CMA 835)",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 369_262,
        "sha256": "b600f19ffe7e257c4afbe618fb50d21a4ecadd2c498c14159c97f5179ee4d554",
        "uncompressed_size_bytes": 21_367_337,
        "uncompressed_sha256": (
            "c18b593c93fd02cc30ee07a956ace912b0072a8c14c6a538e94087592c27818a"
        ),
        "url": f"{_RELEASE_BASE_URL}/edmonton-cma-2016-all-fields-package.json.gz",
    },
    "saskatchewan-2016-all-fields": {
        "filename": "saskatchewan-2016-all-fields-package.json",
        "name": "Saskatchewan 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Saskatchewan (PR 47)."
        ),
        "geography": "Saskatchewan (PR 47)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 287_123,
        "sha256": "2b4430944d18d8161d22c2ce5dcfce0f6720aed4259197769971c62d3d320b70",
        "uncompressed_size_bytes": 17_458_623,
        "uncompressed_sha256": (
            "1bcb91caf412ba6c1b760fc51fb57ffcdc95608bdf20fb854237a4d5751f1a8f"
        ),
        "url": f"{_RELEASE_BASE_URL}/saskatchewan-2016-all-fields-package.json.gz",
    },
    "nova-scotia-2016-all-fields": {
        "filename": "nova-scotia-2016-all-fields-package.json",
        "name": "Nova Scotia 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Nova Scotia (PR 12)."
        ),
        "geography": "Nova Scotia (PR 12)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 244_276,
        "sha256": "f8212b336645225653b01f6976791efd7d58947bab4b95553978c62632686871",
        "uncompressed_size_bytes": 15_356_566,
        "uncompressed_sha256": (
            "70062e8d721d8ff29da0dbbfdbb455b9a9e519f9a69465898c571c6f799f06a4"
        ),
        "url": f"{_RELEASE_BASE_URL}/nova-scotia-2016-all-fields-package.json.gz",
    },
    "new-brunswick-2016-all-fields": {
        "filename": "new-brunswick-2016-all-fields-package.json",
        "name": "New Brunswick 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for New Brunswick (PR 13)."
        ),
        "geography": "New Brunswick (PR 13)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 202_698,
        "sha256": "167b5bd5a0398d48ceb50f01ef715add4c7e4d61c62713348a00f01e436787f1",
        "uncompressed_size_bytes": 12_499_103,
        "uncompressed_sha256": (
            "607a7a368746b755fb2e6b345a69219b6e655c3dd9f41aac670e6cbf1dd94876"
        ),
        "url": f"{_RELEASE_BASE_URL}/new-brunswick-2016-all-fields-package.json.gz",
    },
    "newfoundland-2016-all-fields": {
        "filename": "newfoundland-2016-all-fields-package.json",
        "name": "Newfoundland and Labrador 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Newfoundland and Labrador (PR 10)."
        ),
        "geography": "Newfoundland and Labrador (PR 10)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 138_661,
        "sha256": "b552c09faca4ac1e51510c3464fd480ace6a50ed60eb77e739832acdff6393f7",
        "uncompressed_size_bytes": 8_537_569,
        "uncompressed_sha256": (
            "c107a61c85d2f12b3c4b95656229e191287d6af927c53a7f18ad33ba8e9fe7c7"
        ),
        "url": f"{_RELEASE_BASE_URL}/newfoundland-2016-all-fields-package.json.gz",
    },
    "pei-2016-minimal": {
        "filename": "pei-2016-minimal-package.json",
        "name": "Prince Edward Island 2016 minimal linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for Prince Edward Island (PR 11). "
            "Uses a minimal column profile due to small sample size."
        ),
        "geography": "Prince Edward Island (PR 11)",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 100,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 4_486,
        "sha256": "60fedf9fedddc13848338b006a70efb04cef4f6aee300c4d2f3ffd6acf1f5bcb",
        "uncompressed_size_bytes": 65_948,
        "uncompressed_sha256": (
            "b9733fb70d83020444e811b3597fbb4621164290aa4982255a940b702f31a4ff"
        ),
        "url": f"{_RELEASE_BASE_URL}/pei-2016-minimal-package.json.gz",
    },
    "canada-2016-all-fields": {
        "filename": "canada-2016-all-fields-package.json",
        "name": "Canada 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the 2016 Census hierarchical PUMF for all Canada."
        ),
        "geography": "Canada",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        **_PUMF_2016_CATALOGUE_METADATA,
        "size_bytes": 8_286_186,
        "sha256": "2db0629d01ad91e050acfa956097ee48abb7ee07f2007a40df91786981127b04",
        "uncompressed_size_bytes": 531_314_980,
        "uncompressed_sha256": (
            "ce0bffe4945ccebd962010593d3b316dc7f6d7b7b5803271a54e3da94b7073ab"
        ),
        "url": f"{_RELEASE_BASE_URL}/canada-2016-all-fields-package.json.gz",
    },
}

_PUMF_2021_MODEL_SPECS = {
    "alberta-2021-all-fields": (
        "Alberta",
        "Alberta (PR 48)",
        1_436_472,
        "ac288bd8bbcaaa485709997793137faa3ef3c66422d246e4373c5508e0adddde",
        67_520_274,
        "494856a8c5ec501b6617da61ec967daaac4cc23511716eca91cb629f3bd1fca3",
    ),
    "bc-2021-all-fields": (
        "British Columbia",
        "British Columbia (PR 59)",
        1_758_080,
        "94c231604e8418ca357a62f35609e59096c3e00cf64604d4c19c34afd2636012",
        83_473_790,
        "b3714b8730e9a488f58747c00accb51f9bace53c5a5ccc7124b3115ba7e35c63",
    ),
    "calgary-cma-2021-all-fields": (
        "Calgary CMA",
        "Calgary CMA (CMA 825)",
        567_498,
        "2f03f4de785a6d383d7c828c5c72b52ed6e40bb0d9c7772f71cbf278872801ae",
        24_561_713,
        "5c3968a00eea53edb4f501d0f8dcf61674b586d3d40f4ffee8bd085fea3f21d2",
    ),
    "canada-2021-all-fields": (
        "Canada",
        "Canada",
        14_669_338,
        "3708009c4b5d5fc8a663f23e4c437756a441629e7fd03c68ed10748e4580667c",
        1_699_087_165,
        "d5117d688d0fad6789f6b41044d7c26634384cdc3e84c208d3f4252a8aa1d55c",
    ),
    "edmonton-cma-2021-all-fields": (
        "Edmonton CMA",
        "Edmonton CMA (CMA 835)",
        535_389,
        "44abe874115a4faeb52dfc03e3e752a333c29d1b609414ad5effcf372ada8574",
        23_322_256,
        "99d1664f63a627a6a77f5b1a1889eb8b8b54e31c6379b98fb4dac6944172c252",
    ),
    "manitoba-2021-all-fields": (
        "Manitoba",
        "Manitoba (PR 46)",
        331_238,
        "a56e0c80b468760b7a0790791c1667eed39746aac3e25ec65aad3d03441b8528",
        17_606_961,
        "0c77609d4ada13e0d0deb38f448a5470b04a1920c5416e9aa0f6665f39b630d5",
    ),
    "montreal-cma-2021-all-fields": (
        "Montreal CMA",
        "Montreal CMA (CMA 462)",
        979_348,
        "b5a2c023da4a0af36824259dfeb68213242271352a1b7a597b9700db38352eea",
        55_582_858,
        "f66bdd4e7f6140c9ba0bd43a2485c163cfec8afd8f2eda0daf047b0a501ad9ac",
    ),
    "new-brunswick-2021-all-fields": (
        "New Brunswick",
        "New Brunswick (PR 13)",
        200_930,
        "929859a2a5aa7c9eb6382a9b0f75f6568c15c73556bd340b95a4cead283745b1",
        10_341_321,
        "38ef27f345a432d23343c71eca5be2a7083b9ee97ce35f05c5dd009915a95d54",
    ),
    "newfoundland-2021-all-fields": (
        "Newfoundland and Labrador",
        "Newfoundland and Labrador (PR 10)",
        129_820,
        "4ef77ee62ccb30686ba3e0480c01ee54891561108a9d3a61181861e20871690a",
        6_593_431,
        "963efad475b7726db9d3f757dbf13957399371c1f55f194bad637aa257b7596f",
    ),
    "nova-scotia-2021-all-fields": (
        "Nova Scotia",
        "Nova Scotia (PR 12)",
        351_876,
        "20307e3bbcb1b50faa2225ca48ce61689878be24e68b27f15a43a33a05a50bb1",
        16_637_149,
        "ce931f2a193699b90b40431197eaa43008bfb13d78ba9b0e686d293bc345c1d7",
    ),
    "ontario-2021-all-fields": (
        "Ontario",
        "Ontario (PR 35)",
        2_989_767,
        "a799dc4b5b7af8d31464c82ccdb3862712b7938046a39f8e4059efb678d57d4f",
        179_551_354,
        "4ef6bbd567cfd099c8c81f76b566b6029bb33da7caac56e2297a1d4927cec299",
    ),
    "pei-2021-minimal": (
        "Prince Edward Island",
        "Prince Edward Island (PR 11)",
        5_027,
        "d47857c9b27e8c2fb4a37e8469fe6f4afc44a7fbc5673663d8909718a6e44b85",
        29_488,
        "280523e65f88801266d351a532dc9c94d2d270295699053660a320abd40b62b1",
    ),
    "quebec-2021-all-fields": (
        "Quebec",
        "Quebec (PR 24)",
        1_746_083,
        "39787ecc6449dff9ca0e99c4b6bc62d7b0eb7a45607a91f8cdadd70edcb3391f",
        105_674_442,
        "df75b07d25753a6a0e0a2d82a91ad17485f8cb4710fa5df9e3a45b27519aab48",
    ),
    "saskatchewan-2021-all-fields": (
        "Saskatchewan",
        "Saskatchewan (PR 47)",
        274_952,
        "a38bd3694d64d37e53f159aa35bd3b05b181192b353f818b6f98721a0a1c7d04",
        14_733_221,
        "e7023ed2e73258d0d5b9bb53ba5e4850b9f93dba63a0b57c2947e229157b9dc3",
    ),
    "toronto-cma-2021-all-fields": (
        "Toronto CMA",
        "Toronto CMA (CMA 535)",
        2_151_498,
        "1268594489a2c15c9b73efda6dd0cacfb28430c9302dbb4c3377c7139c384641",
        100_647_328,
        "5f545488c6fb20cc2a0189794abb372b347bd96b2f306c0aad7c99911a8e9a0e",
    ),
    "vancouver-cma-2021-all-fields": (
        "Vancouver CMA",
        "Vancouver CMA (CMA 933)",
        1_009_699,
        "66eec86662d7be2ad2f21bfc4cc836643a32d892a6c1837b15bbf67ad7f2ceed",
        45_022_923,
        "5b50eb14d29168f166c2b41299b9a399c0836793fd8de024d227d269d201d6ab",
    ),
}


def _pumf_2021_registry_entry(
    model_id: str,
    spec: tuple[str, str, int, str, int, str],
) -> dict[str, Any]:
    label, geography, size, sha256, uncompressed_size, uncompressed_sha256 = spec
    minimal = model_id.endswith("-minimal")
    profile = "minimal" if minimal else "broad"
    filename = f"{model_id}-package.json"
    limitation = (
        " Uses a minimal column profile due to small sample size." if minimal else ""
    )
    return {
        "filename": filename,
        "name": f"{label} 2021 {profile} linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            f"the 2021 Census hierarchical PUMF for {geography}.{limitation}"
        ),
        "geography": geography,
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 100 if minimal else 1000,
            "conditions": "",
        },
        **_PUMF_2021_CATALOGUE_METADATA,
        "size_bytes": size,
        "sha256": sha256,
        "uncompressed_size_bytes": uncompressed_size,
        "uncompressed_sha256": uncompressed_sha256,
        "url": f"{_PUMF_2021_RELEASE_BASE_URL}/{filename}.gz",
    }


_MODEL_PACKAGES.update(
    {
        model_id: _pumf_2021_registry_entry(model_id, spec)
        for model_id, spec in _PUMF_2021_MODEL_SPECS.items()
    }
)

# Concept DOIs for the archived model packages on Zenodo. Each always
# resolves to the newest archived version of that package.
_MODEL_CONCEPT_DOIS: dict[str, str] = {
    "alberta-2016-all-fields": "10.5281/zenodo.21461536",
    "alberta-2021-all-fields": "10.5281/zenodo.21461540",
    "bc-2016-all-fields": "10.5281/zenodo.21461542",
    "bc-2021-all-fields": "10.5281/zenodo.21461544",
    "calgary-cma-2016-all-fields": "10.5281/zenodo.21461553",
    "calgary-cma-2021-all-fields": "10.5281/zenodo.21461555",
    "canada-2016-all-fields": "10.5281/zenodo.21461558",
    "canada-2021-all-fields": "10.5281/zenodo.21461577",
    "edmonton-cma-2016-all-fields": "10.5281/zenodo.21461579",
    "edmonton-cma-2021-all-fields": "10.5281/zenodo.21461581",
    "manitoba-2016-all-fields": "10.5281/zenodo.21461583",
    "manitoba-2021-all-fields": "10.5281/zenodo.21461586",
    "montreal-cma-2016-all-fields": "10.5281/zenodo.21461589",
    "montreal-cma-2021-all-fields": "10.5281/zenodo.21461592",
    "new-brunswick-2016-all-fields": "10.5281/zenodo.21461595",
    "new-brunswick-2021-all-fields": "10.5281/zenodo.21461597",
    "newfoundland-2016-all-fields": "10.5281/zenodo.21461599",
    "newfoundland-2021-all-fields": "10.5281/zenodo.21461601",
    "nova-scotia-2016-all-fields": "10.5281/zenodo.21461603",
    "nova-scotia-2021-all-fields": "10.5281/zenodo.21461605",
    "ontario-2016-all-fields": "10.5281/zenodo.21461607",
    "ontario-2021-all-fields": "10.5281/zenodo.21461609",
    "pei-2016-minimal": "10.5281/zenodo.21461611",
    "pei-2021-minimal": "10.5281/zenodo.21461526",
    "quebec-2016-all-fields": "10.5281/zenodo.21461613",
    "quebec-2021-all-fields": "10.5281/zenodo.21461615",
    "saskatchewan-2016-all-fields": "10.5281/zenodo.21461617",
    "saskatchewan-2021-all-fields": "10.5281/zenodo.21461619",
    "toronto-cma-2016-all-fields": "10.5281/zenodo.21461621",
    "toronto-cma-2021-all-fields": "10.5281/zenodo.21461623",
    "vancouver-cma-2016-all-fields": "10.5281/zenodo.21461625",
    "vancouver-cma-2021-all-fields": "10.5281/zenodo.21461629",
}

# Attach the archival identifier to every package that has one. The bundled
# demo has no Zenodo record, so it simply has no DOI.
for _model_id, _doi in _MODEL_CONCEPT_DOIS.items():
    _MODEL_PACKAGES[_model_id]["doi"] = _doi


def model_catalogue() -> list[dict[str, Any]]:
    """Return model packages known to SynthPopCan."""

    return [model_catalogue_entry(model_id) for model_id in _MODEL_PACKAGES]


def model_catalogue_entry(model_id: str) -> dict[str, Any]:
    """Return public catalogue metadata for one registered model package."""

    metadata = model_registry_entry(model_id)
    if metadata.get("safe_demo") is True:
        licensing = synthetic_demo_model_licensing()
    elif metadata.get("census_vintage") == "2016 Census":
        licensing = statcan_prepared_model_licensing(2016)
    elif metadata.get("census_vintage") == "2021 Census":
        licensing = statcan_prepared_model_licensing(2021)
    else:
        raise ValueError(
            f"model package {model_id} has an unsupported licensing vintage"
        )
    return {
        "id": model_id,
        "name": str(metadata["name"]),
        "description": str(metadata["description"]),
        "kind": "linked_household_person",
        "geography": str(metadata["geography"]),
        "census_vintage": str(metadata["census_vintage"]),
        "release_status": str(metadata["release_status"]),
        "release_version": str(metadata["release_version"]),
        "provenance": str(metadata["provenance"]),
        "source_licence": str(metadata["source_licence"]),
        "licensing": licensing,
        "doi": metadata.get("doi"),
        "privacy": str(metadata["privacy"]),
        "privacy_review_status": str(metadata["privacy_review_status"]),
        "generation_limits": str(metadata["generation_limits"]),
        "known_limitations": str(metadata["known_limitations"]),
        "conditions": list(metadata["conditions"]),  # type: ignore[arg-type]
        "outputs": ["households.csv", "persons.csv"],
        "default_generation": metadata["default_generation"],
        "safe_demo": bool(metadata["safe_demo"]),
        "distribution": str(metadata["distribution"]),
        "installed": model_is_installed(model_id),
        "size_bytes": metadata.get("size_bytes"),
        "uncompressed_size_bytes": metadata.get("uncompressed_size_bytes"),
        "browser_compatible": model_browser_compatible(model_id),
        "browser_max_uncompressed_size_bytes": (_BROWSER_MODEL_MAX_UNCOMPRESSED_BYTES),
    }


def model_browser_compatible(model_id: str) -> bool:
    """Return whether a registered package may be loaded into browser memory."""

    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") == "bundled":
        return True
    size = metadata.get("uncompressed_size_bytes")
    return isinstance(size, int) and size <= _BROWSER_MODEL_MAX_UNCOMPRESSED_BYTES


def model_payload(model_id: str) -> dict[str, Any]:
    """Return a linked model package by ID.

    Bundled demo packages load immediately. Downloadable packages must be
    fetched into the local model cache first.
    """

    metadata = model_registry_entry(model_id)
    package_path = _model_path(model_id)
    if metadata.get("distribution") == "download":
        _verify_model_checksum(package_path, metadata)
    payload = json.loads(package_path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"model package {model_id} must be a JSON object")
    payload.setdefault("name", metadata["name"])
    payload.setdefault("description", metadata["description"])
    payload.setdefault("generation_defaults", metadata["default_generation"])
    catalogue_entry = model_catalogue_entry(model_id)
    payload.setdefault("licensing", catalogue_entry["licensing"])
    payload.setdefault(
        "catalogue_metadata",
        {
            key: catalogue_entry[key]
            for key in (
                "census_vintage",
                "release_version",
                # provenance and source_licence carry the Statistics Canada
                # attribution notice into every loaded payload, so generated
                # artifacts and manifests inherit the required credit.
                "provenance",
                "source_licence",
                "privacy_review_status",
                "generation_limits",
                "known_limitations",
                "size_bytes",
            )
        },
    )
    return normalize_prepared_model_licensing(payload)


def model_registry_entry(model_id: str) -> dict[str, Any]:
    """Return metadata for one registered model package."""

    return _MODEL_PACKAGES[model_id]


def model_is_installed(model_id: str) -> bool:
    """Return whether a model package can be loaded without downloading."""

    try:
        _model_path(model_id)
    except FileNotFoundError:
        return False
    return True


def model_cache_path(model_id: str) -> Path:
    """Return the local cache path for a downloadable model package."""

    metadata = model_registry_entry(model_id)
    return model_cache_dir() / str(metadata["filename"])


def model_cache_dir() -> Path:
    """Return the directory used for downloaded model packages."""

    override = os.environ.get("SYNTHPOPCAN_MODEL_CACHE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "synthpopcan" / "models"
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "SynthPopCan" / "models"
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "synthpopcan" / "models"
    return Path.home() / ".cache" / "synthpopcan" / "models"


def fetch_model_package(
    model_id: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Download a registered model package into the local cache and verify it."""

    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") != "download":
        return _model_path(model_id)
    destination = model_cache_path(model_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _model_cache_lock(destination):
        if destination.exists():
            try:
                _verify_model_checksum(destination, metadata)
            except ValueError:
                # A corrupt cached file would fail verification on every retry;
                # remove it while holding the per-model cache lock.
                destination.unlink()
            else:
                return destination

        download_path = _unique_cache_temp(destination, ".download")
        temporary_path = _unique_cache_temp(destination, ".part")
        url = str(metadata["url"])
        try:
            with urlopen(url, timeout=60) as response:
                total_bytes = _download_size(response, metadata)
                if progress_callback:
                    progress_callback(0, total_bytes)
                with download_path.open("wb") as handle:
                    downloaded = 0
                    while chunk := response.read(1024 * 1024):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_bytes)
            _verify_download_checksum(download_path, metadata)
            _unpack_downloaded_model(download_path, temporary_path, metadata)
            _verify_model_checksum(temporary_path, metadata)
            temporary_path.replace(destination)
        finally:
            download_path.unlink(missing_ok=True)
            temporary_path.unlink(missing_ok=True)
    return destination


def _unique_cache_temp(destination: Path, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=suffix, dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


@contextmanager
def _model_cache_lock(destination: Path) -> Generator[None]:
    """Serialize cache updates across threads and processes without dependencies."""

    lock_path = destination.with_suffix(destination.suffix + ".lock")
    started = time.monotonic()
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > 300
            except FileNotFoundError:
                continue
            if stale:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() - started > 120:
                raise TimeoutError(
                    f"timed out waiting for model cache lock {lock_path}"
                ) from None
            time.sleep(0.05)
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def remove_cached_model(model_id: str) -> bool:
    """Remove a downloaded model package from the local cache."""

    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") != "download":
        return False
    path = model_cache_path(model_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def _model_path(model_id: str) -> Path:
    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") == "bundled":
        return Path(
            str(files("synthpopcan.models").joinpath(str(metadata["filename"])))
        )
    path = model_cache_path(model_id)
    if path.exists():
        return path
    raise FileNotFoundError(
        f"model package {model_id} is not downloaded; run "
        f"`synthpopcan models fetch {model_id}`"
    )


def _verify_model_checksum(path: Path, metadata: dict[str, Any]) -> None:
    expected = metadata.get("uncompressed_sha256") or metadata.get("sha256")
    _verify_checksum(path, expected, metadata)


def _verify_download_checksum(path: Path, metadata: dict[str, Any]) -> None:
    _verify_checksum(path, metadata.get("sha256"), metadata)


def _verify_checksum(path: Path, expected: object, metadata: dict[str, Any]) -> None:
    if not expected:
        return
    # file_digest streams the file, so the 0.5 GB Canada package is not read
    # into memory just to hash it.
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != expected:
        raise ValueError(
            f"downloaded model checksum did not match for {metadata.get('filename')}"
        )


def _unpack_downloaded_model(
    download_path: Path,
    destination: Path,
    metadata: dict[str, Any],
) -> None:
    compression = metadata.get("compression")
    if compression == "gzip":
        with gzip.open(download_path, "rb") as source, destination.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        return
    if compression:
        raise ValueError(f"unsupported model package compression: {compression}")
    download_path.replace(destination)


def _download_size(response: object, metadata: dict[str, Any]) -> int | None:
    headers = getattr(response, "headers", {})
    content_length = None
    if hasattr(headers, "get"):
        content_length = headers.get("Content-Length")
    if content_length:
        try:
            return int(content_length)
        except ValueError:
            pass
    size = metadata.get("size_bytes")
    return size if isinstance(size, int) else None
