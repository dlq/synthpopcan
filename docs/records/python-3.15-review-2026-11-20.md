# Python 3.15 Reassessment — 2026-11-20

**Decision:** retain Python 3.11–3.14 as the supported blocking CI matrix for
now. Python 3.15 is promising, but the committed lock and Linux acceptance gate
have not yet met the conditions for adding it. No runtime-support classifier,
CI matrix, project lock or public support claim changes as a result of this
assessment.

The earlier Python 3.15.0rc1 check passed 100 API/IPF/schema tests, but the
optional model-build environment could not use a SciPy wheel and required a
separate OpenBLAS installation to build from source. That was prerelease
evidence and did not establish support.

Evidence on macOS 27.2.1 ARM64, CPython 3.15.2, at source commit
`557578f194365d54186a5ca75d9cbc38275d0eb4`:

- A wheel-only install of the current locked graph failed on locked NumPy
  `2.5.0`; the current lock also has no CPython 3.15 wheels for its selected
  SciPy `1.18.0`. This is a lockfile limitation, not a claim that upstream has
  no newer compatible wheels.
- In a separate temporary copy, refreshing only NumPy and SciPy resolved them
  to `2.5.5` and `1.18.1` for this platform. The base runtime plus both
  `performance` and `model-build` extras then installed from binary wheels.
  The actual repository lockfile was not changed.
- With that temporary refresh, the full Python suite passed **2,810 tests**,
  with **7 skipped** and **95.40%** branch coverage. Ruff, Pyright, CFF
  validation and the Sphinx build also passed. The installed PyPI `1.2.1`
  wheel passed its base, performance-extra and model-build-extra smokes in
  separate clean Python 3.15 environments with freshly resolved dependencies.
  The SHA-256-verified published sdist also passed the base installed-package
  smoke after being built in a clean environment.
- A wheel-only install including development/documentation tools stopped at
  PyYAML `6.0.3`; a normal install on this machine succeeded by building
  PyYAML, MarkupSafe and docopt from source. This is not evidence that a clean
  machine or Linux can build them without system prerequisites.
- These results do not test the full release workflow, sdist optional-extra
  installation, Linux/WSL, Windows, free-threaded Python, or every supported
  platform. Optional live Statistics Canada and other marked tests remained
  skipped.

Follow-up: review a targeted lockfile update and its existing Python 3.11–3.14
matrix; assess the development-tool source-build/wheel gap; then run the full
locked 3.15 suite, documentation, installed wheel and sdist with both extras,
release checks and browser scenarios on clean Linux CI. Verify supported
platform policy separately before adding `3.15` to classifiers, CI and public
support documentation. Prefer a separate reviewed change rather than silently
upgrading dependencies as part of this plan-only update.

Upstream references: [Python 3.15.0 release](https://www.python.org/downloads/release/python-3150/),
[NumPy 2.5.5 wheels](https://pypi.org/project/numpy/2.5.5/),
[SciPy 1.18.1 wheels](https://pypi.org/project/scipy/1.18.1/), and
[Numba 0.68.1 wheels](https://pypi.org/project/numba/0.68.1/).
