# Release Checklist

Use this checklist before publishing a package release or a public model
artifact.

## Python Package Release

1. Confirm the working tree is clean.

1. Run local verification:

   ```bash
   uv run ruff check src tests scripts
   uv run ruff format --check src tests scripts
   uv run pytest
   uv run sphinx-build -E -W -b html docs docs/_build/html
   npm run check:web
   uv build
   ```

1. Update `CHANGELOG.md`.

1. Confirm `pyproject.toml` has the intended version.

1. Commit the release changes.

1. Create or update the release tag.

1. Push `main` and the tag.

1. Confirm GitHub CI passes.

1. Run the manual PyPI publishing workflow when the release should be published
   to [PyPI](https://pypi.org/).

## Model Package Release

Large model packages should be [GitHub Release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), not files in the Python
wheel or git history.

Before publishing a model package:

1. Confirm the package is explicitly intended for public distribution.

1. Confirm the package contains no raw source rows, source row identifiers, or
   private local paths.

1. Review provenance, citation, access, and redistribution notes.

1. Run the relevant SynthPopCan audit and release-readiness checks.

1. Record the package size and SHA-256 checksum.

1. Upload the package to the intended GitHub Release.

1. Update the model registry with the release URL, size, and checksum.

1. Test the fetch path:

   ```bash
   SYNTHPOPCAN_MODEL_CACHE=/tmp/synthpopcan-model-smoke \
     synthpopcan models fetch MODEL_ID
   ```

1. Inspect the package:

   ```bash
   synthpopcan tree inspect-package MODEL_ID
   ```

1. Update documentation if the model becomes part of the supported public
   workflow.

Passing SynthPopCan's checks means the artifact passed the project's current
release-readiness criteria. It is not a claim of official approval, legal
privacy certification, or suitability for every research use.
