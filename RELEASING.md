# Release Checklist

Use this checklist before publishing a package release or a public model
artifact.

## Python Package Release

1. Confirm the working tree is clean.

1. Run local verification:

   ```bash
   ./scripts/check.sh
   UV_LOCKED=1 sh scripts/check-correctness.sh
   uv lock --check
   uv build
   sh scripts/check-wheel.sh
   ```

   Run the distribution checks with a fresh `dist/` containing exactly the one
   wheel and one sdist just built. The smoke check deliberately refuses stale,
   additional, or ambiguously versioned SynthPopCan distributions.

1. Update `CHANGELOG.md`.

1. Confirm `pyproject.toml` and `synthpopcan.__version__` have the intended
   version. The local, CI, manifest, wheel, and sdist gates require those values,
   the release tag, both CFF versions, and the dated changelog entry to agree.

1. Update `CITATION.cff` so both `version` fields and both `date-released`
   fields match the release. This is what GitHub's citation widget shows.
   `tests/test_docs.py` checks it against the package version and changelog
   date. Remove the preceding release's version DOI while the new archive is
   pending; retain the stable concept DOI. After Zenodo mints the new version
   DOI, add it to both citation blocks and identify it as that archived release
   in a follow-up documentation commit.

1. Remove a previous release's Software Heritage snapshot from `CITATION.cff`
   when its description no longer covers the release being prepared. Keep the
   older SWHIDs in their dated preservation record; add a new snapshot to CFF
   only after Software Heritage has completed a full visit containing the new
   annotated tag.

1. Leave the version out of `.zenodo.json`. Zenodo takes the version from the
   release tag, so adding one here would create a second place to drift.
   Because `.zenodo.json` exists, Zenodo **ignores `CITATION.cff` entirely**
   and builds the archived record from `.zenodo.json` alone — keep both files
   accurate, but remember only the latter reaches the DOI record.

1. Commit the release changes.

1. Create an annotated release tag from the verified release commit.

1. Push `main`, confirm GitHub CI passes for the release commit, then push the
   tag.

1. Create a GitHub Release from the tag using the matching `CHANGELOG.md` entry.
   Confirm it is neither a draft nor a prerelease and is marked latest.
   Identify the tested commit and summarize the correctness evidence using
   language scoped to [`CORRECTNESS.md`](CORRECTNESS.md), for example:

   > This release passed SynthPopCan's correctness-assurance suite, including
   > mathematical invariants, independent implementation comparisons,
   > deterministic reproduction checks, cross-language parity tests, a public
   > Statistics Canada reference fixture, and an isolated installed-wheel test.

   Do not describe this as proof of statistical fitness, source-data accuracy,
   privacy certification, or correctness for every possible input.

1. For a major or preservation-significant release, request a Software Heritage
   capture of the public Git origin. Wait for a `succeeded` task and `full`
   visit, verify the snapshot maps the annotated release tag to the expected
   release object and revision, then record the returned snapshot, release, and
   qualified SWHIDs in a dated preservation record. Never publish a pending or
   inferred SWHID. Add the completed snapshot identifier to `CITATION.cff` in a
   follow-up metadata commit.

1. Run the manual **Publish Python package** workflow by selecting the annotated
   release tag itself in GitHub's **Use workflow from** control and entering the
   same tag as the workflow input. Running it from `main`, even when `main`
   still points at the same commit, is intentionally rejected: the dispatch
   ref, dispatch SHA, workflow-definition SHA, annotated tag, and package commit
   must all identify the exact release commit. The commit must also be contained
   in `main` and have a successful `push` run of the complete **CI** workflow.

   The workflow uses the committed lock without rewriting it, reruns the Python
   coverage and extended correctness suites, and smoke-tests the wheel, sdist,
   `model-build` extra, and a fictional installed-package analogue of the Quebec
   case-study interface. It checks Quebec's installed catalogue entry but does
   not download or claim to test the 106 MB released Quebec model bytes.

   Publication is serialized per tag. The workflow verifies the remote
   annotated tag and non-draft, non-prerelease GitHub Release before attachment
   and again immediately before PyPI. Existing named release assets are skipped
   only when their GitHub SHA-256 digest and size exactly match; a differing,
   duplicate, or extraneous asset fails the release, and no asset is clobbered.
   It attaches both distributions, the exact-CI-run record, correctness and
   coverage XML, distribution-smoke log, lock/build inputs, release evidence
   manifest, and `SHA256SUMS` before PyPI starts. A separately permissioned job
   publishes GitHub build-provenance attestations for both distributions.
   External actions are pinned to reviewed full commit SHAs. Confirm the
   workflow succeeds and PyPI reports the intended version.

1. Download `SHA256SUMS` and the release assets into one directory, then run
   `sha256sum --check SHA256SUMS`. Confirm `manifest.json` names the release tag
   and its full commit, dispatch ref/SHA, and workflow-definition SHA.

1. Install the published wheel in a clean environment and smoke test the version,
   CLI entry point, guide commands, bundled demo generation, and model catalogue.

1. Confirm Read the Docs `latest` points to the release commit and `stable`
   points to the release tag. Check a cache-busted public page after both builds
   succeed.

## Model Package Release

Large model packages should be GitHub Release assets, not files in the Python
wheel or git history.

Before publishing a model package:

1. Confirm
   [ADR-0014](adr/0014-separate-prepared-model-and-source-licensing.md) has
   status **Accepted** and that every completed package licensing object is
   bound to its exact machine-readable `policy_decision`: `status: accepted`,
   `basis: maintainer-selected-permissive-default`, Darcy Quesnel as
   `decided_by`, `2026-08-15` as `decided_on`, accepted ADR-0014, and
   `external_legal_review: not-obtained`. This is a project policy decision, not
   an assertion of Statistics Canada approval or legal advice. External review
   is welcome but optional and is not a `1.0.0` or publication gate. If material
   authoritative guidance later conflicts with the policy, stop new publication,
   record the guidance, and prospectively review the contract, tooling, metadata,
   and affected artifacts.

1. Confirm ADR-0014's exact **Archive correction implementation** field is
   **Completed**. Independent adversarial review closed every prior
   destructive-boundary, draft-ownership, identity, remote-asset, transaction,
   and resume-state finding on 2026-08-15; 137 focused tests, Ruff, Pyright, and
   diff checks passed. Re-run the maintained gates on the exact candidate
   commit rather than treating this recorded review as a substitute for release
   CI.

1. Confirm the package is explicitly intended for public distribution.

1. Confirm the package contains no raw source rows, source row identifiers, or
   private local paths.

1. Review provenance, citation, access, and redistribution notes.

1. Confirm the package is derived only from Statistics Canada public use
   microdata, and that it carries the required attribution. PUMFs are covered by
   the [Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence), which
   permits distributing derived "Value-added Products" with its prescribed
   notice; `tests/test_models.py` enforces that every Census-derived catalogue
   entry carries it. Packages built from access-controlled sources are not
   published.

1. Inspect the immutable package bytes, not only the installed registry or
   archive landing page. They must embed a versioned rights block containing:

   - the exact `Adapted from Statistics Canada ... This does not constitute an endorsement ...` notice for the source product and Census reference year;
   - the Statistics Canada Open Licence URL;
   - the CC BY 4.0 URL and a statement limiting that grant to copyright or
     similar rights the package author owns or controls in original selection,
     organization, schema, documentation, and model representation, while
     excluding source classifications, facts, and unprotectable numeric
     results; and
   - a statement that the rights are cumulative and scoped, not alternative
     licences for the package as a whole.

   Generated-artifact provenance and model inspection output must retain the
   source notice and rights references.

1. Run the relevant SynthPopCan audit and release-readiness checks.

1. Record the package size and SHA-256 checksum.

1. Upload the package to the intended GitHub Release. Model assets do not have
   to live on the newest release: `_RELEASE_BASE_URL` in
   `src/synthpopcan/models/__init__.py` names the release that hosts them, and
   all assets must stay on that release until the base URL is updated in the
   same change that moves them.

1. Update the model registry with the release URL, size, and checksum.

1. Regenerate the archive metadata from the registry, passing the software
   concept DOI so each model record links back to it:

   ```bash
   uv run python scripts/build_zenodo_depositions.py --concept-doi DOI
   ```

   These default manifests are review-only and cannot be deposited. Zenodo's
   GitHub integration archives only the source tarball, so model assets are
   never captured automatically.

1. Before publication, inspect Zenodo's rendered rights presentation. Prefer
   scoped multiple or custom rights statements for CC BY 4.0 and the Statistics
   Canada Open Licence. When the legacy API cannot express per-right scopes,
   use its verified `other-open` compatibility value and put the complete
   composite scope in both the record description and package bytes. Never use
   the legacy `license: cc-by-4.0` field alone: it applies one licence to every
   deposited file and does not communicate the approved scope.

1. Test the fetch path:

   ```bash
   SYNTHPOPCAN_MODEL_CACHE=/tmp/synthpopcan-model-smoke \
     synthpopcan models fetch MODEL_ID
   ```

1. Inspect the package:

   ```bash
   synthpopcan models build inspect MODEL_ID
   ```

1. Update documentation if the model becomes part of the supported public
   workflow.

For the 32 records that predate the scoped presentation:

1. correct published metadata in place so the existing identifiers continue to
   resolve and the previous ambiguity is disclosed;
1. if model bytes need the embedded notice or any other correction, publish a
   new version under the existing concept DOI with new checksums and a new
   version DOI;
1. retain the historical version and mark it superseded for licensing clarity;
   never overwrite, delete, or silently relabel its files; and
1. update the SynthPopCan registry only after the corrected artifact and its
   archive metadata are verified together.

The correction executor is fail-closed and uses two explicit operations per
model. Build the corrected package bytes locally from the checksum-bound
historical `.json.gz` files; do not reserialize or materialize the largest JSON
packages. The record index must use schema
`synthpopcan-zenodo-record-index-v1` and map every model ID to exact
`latest_record_id`, `concept_doi`, and `version_doi` values. Supply the exact
validated licensing object separately for each Census vintage. The version DOI
must be `10.5281/zenodo.LATEST_RECORD_ID`; all record IDs and concept/version
DOIs must be globally distinct across the index:

```bash
uv run python scripts/build_corrected_model_assets.py \
  --assets-dir PATH/TO/HISTORICAL-ASSETS \
  --record-index PATH/TO/record-index.json \
  --licensing-2016 PATH/TO/licensing-2016.json \
  --licensing-2021 PATH/TO/licensing-2021.json \
  --new-package-version NEW_VERSION \
  --out PATH/TO/correction-candidates
```

Complete-catalogue mode requires all 32 registered downloadable models and
refuses unknown, duplicate, or missing identities. `--test-subset MODEL_ID` may
be repeated for at most eight models, but marks the resulting index explicitly
non-production. The builder streams both checksum passes, validates the full
top-level JSON object, refuses an existing or duplicate `licensing` key, inserts
only the exact validated contract immediately after the root `{`, and preserves
every historical uncompressed byte around that insertion. This keeps licensing
verification bounded even for the 1.7 GB package. The builder uses deterministic
gzip metadata, refuses to overwrite output, reverifies the same historical file
descriptor during the transformation, and verifies the new compressed and
uncompressed bytes. It stages the complete bundle before atomically creating
its output directory and publishes each file with a no-clobber link, cleaning
up all owned artifacts if any model or index step fails. Its
`synthpopcan-zenodo-correction-candidates-v1` index binds the historical and new
hashes, package schema/type/version, model ID, Census vintage, licensing schema,
and record/concept/version identities; it explicitly records that no model was
retrained. It makes no network request or archive write.

Build executable deposition manifests from that emitted candidate index:

```bash
uv run python scripts/build_zenodo_depositions.py \
  --concept-doi DOI \
  --correction-candidates \
    PATH/TO/correction-candidates/correction-candidates.json
uv run python scripts/deposit_zenodo_records.py --dry-run \
  --manifests-dir data/derived/zenodo/depositions/corrections
```

`correct-existing-metadata` edits only the published record's rights and
provenance presentation while preserving title, creators, resource type,
version, record ID, version DOI, and concept DOI. `create-new-version` invokes
Zenodo's new-version action on the latest record, removes inherited historical
files only from the mutable draft, uploads the verified candidate under a new
version-bearing filename, records `isNewVersionOf`, and verifies both versions.
Checkpoints are keyed by operation, model, package version, asset SHA-256, and
desired-metadata SHA-256, so interrupted created, uploaded, draft, and published
states resume without treating changed work as complete. The builder also emits
an execution index containing the exact approved operation identities and
candidate-envelope digest. Before removing an inherited file or editing an
existing record, the executor binds the draft's record, version DOI, concept,
parent, and reserved DOI and writes an operation-specific ownership marker into
draft metadata. Unowned or ambiguously owned drafts fail closed. Verified
checkpoints are remotely reverified on every later run rather than skipped.

Production correction writes require ADR-0014 Accepted, its exact maintainer
policy authority and date, and
`Archive correction implementation: Completed`. Keep
`Archive correction execution: Pending` until all 64 live operations and 32
registry updates are verified. Only then may it become Completed; fresh
production model records are blocked until that marker, the exact 64-operation
index/checkpoints, and the 32 verified registry candidates agree on model,
record/version/concept DOI, URL, filename, and compressed and uncompressed
size/hash. A registry candidate file is emitted only for verified production
correction versions, never for fresh records, drafts, or sandbox runs.

Passing SynthPopCan's checks means the artifact passed the project's current
release-readiness criteria. It is not a claim of official approval, legal
privacy certification, or suitability for every research use.

## Prepared Geodata Release

Prepared display boundaries use their own release line and are not Python-wheel
or model-package assets. Before publishing them:

1. Confirm every source is a canonical Statistics Canada boundary with recorded
   Census vintage, product provenance, and licence attribution.

1. Run the simplification tests and build the intended display files as
   described in `CONTRIBUTING.md`.

1. Build the compressed assets with
   `SYNTHPOPCAN_GEODATA_RELEASE_BASE_URL` pinned to the final immutable release
   tag URL.

1. Audit `geodata-catalogue.json`: expected year/level/PRUID coverage, unique
   IDs and filenames, exact release URLs, non-empty sizes, representation, and
   both SHA-256 fields must be present.

1. Independently recompute the compressed checksums, decompress representative
   and edge-case assets, and verify their unpacked checksums and GeoJSON shape.

1. Create the dedicated GitHub Release, upload every catalogue asset and the
   catalogue itself, then confirm the release is not marked as the latest
   Python software release.

1. Run a bounded remote smoke test through both the CLI and library using a
   fresh `SYNTHPOPCAN_GEODATA_CACHE`. Check exact national and regional matches,
   cache reuse, and one expected refusal for a mismatched scope.

1. Record the geodata tag, catalogue digest, source commit, audit result, and
   smoke-test command in the release notes.

Publishing verifies the identity and integrity of display derivatives. It does
not make them suitable for spatial measurement, geographic reconciliation, or
other analytical uses reserved for canonical boundaries.
