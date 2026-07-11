"""Sphinx configuration for SynthPopCan documentation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "SynthPopCan"
author = "Darcy Quesnel"
copyright = "2026, SynthPopCan contributors"
html_title = "SynthPopCan"
html_baseurl = "https://synthpopcan.readthedocs.io/en/latest/"
html_show_sphinx = False
pygments_style = "github-light"
pygments_dark_style = "github-dark"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "../assets/branding/logo/synthpopcan-logo-256.png"
html_favicon = "../assets/branding/icon/favicon.ico"
html_theme_options = {
    "source_repository": "https://github.com/dlq/synthpopcan/",
    "source_branch": "main",
    "source_directory": "docs/",
    "top_of_page_buttons": [],
    "light_css_variables": {
        "color-brand-primary": "#2f6f73",
        "color-brand-content": "#245c60",
    },
    "dark_css_variables": {
        "color-brand-primary": "#8fd0d2",
        "color-brand-content": "#a7dadd",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/dlq/synthpopcan",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0"
                     viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53
                    5.47 7.59.4.07.55-.17.55-.38
                    0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94
                    -.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52
                    -.01-.53.63-.01 1.08.58 1.23.82.72 1.21
                    1.87.87 2.33.66.07-.52.28-.87.51-1.07
                    -1.78-.2-3.64-.89-3.64-3.95
                    0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12
                    0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8
                    4.58c.68 0 1.36.09 2 .24 1.53-1.04
                    2.2-.82 2.2-.82.44 1.1.16 1.92.08
                    2.12.51.56.82 1.27.82 2.15
                    0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54
                    1.48 0 1.07-.01 1.93-.01 2.2
                    0 .21.15.46.55.38A8.01 8.01 0 0 0 16
                    8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}

myst_heading_anchors = 3
copybutton_prompt_text = r"^\$ |^>>> |^\.\.\. "
copybutton_prompt_is_regexp = True

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
