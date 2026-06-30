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
html_title = "SynthPopCan"
html_baseurl = "https://synthpopcan.readthedocs.io/en/latest/"

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
html_logo = "../assets/branding/logo/synthpopcan-logo-512.png"
html_favicon = "../assets/branding/logo/synthpopcan-logo-512.png"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
    "style_external_links": True,
}
html_context = {
    "display_github": True,
    "github_user": "dlq",
    "github_repo": "synthpopcan",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

myst_heading_anchors = 3

autoclass_content = "both"
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_mock_imports = [
    package
    for package in ("numpy", "pandas", "sklearn", "scipy", "polars")
    if importlib.util.find_spec(package) is None
]
napoleon_use_param = True
napoleon_use_rtype = True
