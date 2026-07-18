#!/bin/sh
set -eu

uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pyright src
uv run pytest \
  --cov=src/synthpopcan \
  --cov-branch \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95
uv run sphinx-build -E -W -b html docs docs/_build/html
npm run check:web
npm run test:web
npm run test:web:e2e
