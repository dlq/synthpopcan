"""Sphinx configuration for SynthPopCan documentation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "SynthPopCan"
author = "Darcy Quesnel"
copyright = "2026, Darcy Quesnel"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = (
    "sphinx_rtd_theme"
    if importlib.util.find_spec("sphinx_rtd_theme") is not None
    else "alabaster"
)
html_static_path = ["_static"]

myst_heading_anchors = 3

autoclass_content = "both"
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_mock_imports = [
    package
    for package in ("numpy", "sklearn")
    if importlib.util.find_spec(package) is None
]
napoleon_use_param = True
napoleon_use_rtype = True
