"""Sphinx configuration for SynthPopCan documentation."""

from __future__ import annotations

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

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

myst_heading_anchors = 3

autoclass_content = "both"
autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_use_param = True
napoleon_use_rtype = True
