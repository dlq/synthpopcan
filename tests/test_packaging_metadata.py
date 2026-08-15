from __future__ import annotations

import re
import tomllib
from pathlib import Path


def test_build_backend_is_exactly_pinned_and_locked() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    expected_requirement = "hatchling==1.32.0"

    assert project["build-system"]["requires"] == [expected_requirement]
    assert expected_requirement in project["dependency-groups"]["dev"]

    lock = tomllib.loads(Path("uv.lock").read_text())
    hatchling_versions = [
        package["version"]
        for package in lock["package"]
        if package["name"] == "hatchling"
    ]
    assert hatchling_versions == ["1.32.0"]


def test_readme_uses_absolute_links_for_package_indexes() -> None:
    readme = Path("README.md").read_text()
    markdown_targets = re.findall(r"\]\(([^)\s]+)", readme)
    html_targets = re.findall(r'\b(?:href|src)=["\']([^"\']+)', readme)
    targets = [*markdown_targets, *html_targets]
    relative_targets = [
        target
        for target in targets
        if not target.startswith(("https://", "http://", "mailto:", "#"))
    ]

    assert targets
    assert not relative_targets
    assert (
        "https://raw.githubusercontent.com/dlq/synthpopcan/main/"
        "assets/branding/logo/synthpopcan-logo-512.png"
    ) in html_targets
