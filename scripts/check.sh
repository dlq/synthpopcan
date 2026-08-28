#!/bin/sh
set -eu

uv lock --check
version=$(uv run --locked python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
uv run --locked python scripts/build_release_evidence.py \
  --check-source-version \
  --version "$version"
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked pyright src scripts
uv run --locked cffconvert --validate
git ls-files -z -- '*.md' | \
  xargs -0 uv run --locked --group docs mdformat --check
uv run --locked --group docs doc8 docs
uv run --locked pytest \
  --cov=src/synthpopcan \
  --cov-branch \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95
uv run --locked --group docs sphinx-build -E -W -b html docs docs/_build/html
npm run check:web
npm run test:web:coverage
npm run test:web:e2e
