# Contributing

SynthPopCan is early-stage research software. Keep changes small, reviewable,
and grounded in the existing code and documentation structure.

## Development Setup

Install the Python and documentation dependencies:

```bash
uv sync --group dev --group docs
```

Install web tooling:

```bash
npm ci
```

Run the normal checks before opening a pull request:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest
uv run sphinx-build -W -b html docs docs/_build/html
npm run check:web
```

## Data And Model Safety

Do not commit raw Census microdata, downloaded bulk data caches, generated CSV
outputs, private research datasets, or local reference corpora. Keep those files
under ignored paths such as `data/raw`, `data/private`, `references`, `runs`, or
`outputs`.

Reviewed model packages may be published only when they are explicitly intended
for distribution and carry provenance and disclosure-risk metadata. Large
packages should be uploaded as GitHub Release assets and listed in the model
registry, not bundled into the normal Python package.

Before contributing a model artifact:

- verify it contains no raw source rows or source identifiers;
- inspect its provenance and redistribution notes;
- run the relevant SynthPopCan audit/release workflow;
- confirm large files are distributed as release assets with checksums and
  fetched on demand by `synthpopcan models fetch`.
- follow `docs/release-checklist.md` before updating the public model registry.

## Documentation

User-facing behavior should be documented where readers will look for it:

- `README.md` for project orientation and public-repo expectations;
- `docs/` for workflow and API documentation;
- `PLANS.md` for open roadmap items;
- `NOTES.md` for research notes.

Avoid putting long walkthroughs in the README when they belong in Sphinx docs.
