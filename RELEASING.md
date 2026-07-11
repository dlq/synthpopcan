# Release Checklist

Use this checklist before publishing a package release or a public model
artifact.

## Python Package Release

1. Confirm the working tree is clean.

1. Run local verification:

   ```bash
   ./scripts/check.sh
   uv build
   ```

1. Update `CHANGELOG.md`.

1. Confirm `pyproject.toml` has the intended version.

1. Commit the release changes.

1. Create an annotated release tag from the verified release commit.

1. Push `main`, confirm GitHub CI passes for the release commit, then push the
   tag.

1. Create a GitHub Release from the tag using the matching `CHANGELOG.md` entry.
   Confirm it is neither a draft nor a prerelease and is marked latest.

1. Run the manual **Publish Python package** workflow from the release commit.
   Confirm the workflow succeeds and PyPI reports the intended version.

1. Install the published wheel in a clean environment and smoke test the version,
   CLI entry point, guide commands, bundled demo generation, and model catalogue.

1. Confirm Read the Docs `latest` points to the release commit and `stable`
   points to the release tag. Check a cache-busted public page after both builds
   succeed.

## Model Package Release

Large model packages should be GitHub Release assets, not files in the Python
wheel or git history.

Before publishing a model package:

1. Confirm the package is explicitly intended for public distribution.

1. Confirm the package contains no raw source rows, source row identifiers, or
   private local paths.

1. Review provenance, citation, access, and redistribution notes.

1. Run the relevant SynthPopCan audit and release-readiness checks.

1. Record the package size and SHA-256 checksum.

1. Upload the package to the intended GitHub Release. Model assets do not have
   to live on the newest release: `_RELEASE_BASE_URL` in
   `src/synthpopcan/models/__init__.py` names the release that hosts them, and
   all assets must stay on that release until the base URL is updated in the
   same change that moves them.

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
