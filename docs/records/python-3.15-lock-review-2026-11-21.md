# Python 3.15 Lockfile Review — 2026-11-21

**Decision:** retain the repository lock and supported Python 3.11–3.14 matrix
for now. A targeted numerical refresh is a viable candidate for a separate
reviewed change, but clean Linux Python 3.15 acceptance and a support decision
remain outstanding. This record does not promote Python 3.15 or claim Linux
execution based on a cross-platform resolver check.

## Isolated Resolutions

At source commit `79626fc9963d7d8104446675b6dee89a6779b635`, the committed
lock's SHA-256 was
`b405b7a37cab32b7d978e35162091ad636d14bf1ed53af78cbd27d93ac91bf62`.
A temporary copy was resolved with `uv lock --upgrade-package numpy --upgrade-package scipy`, without updating the repository lock. The resulting
lock SHA-256 was
`9de5f07de6b4c6956d0e8b089099a9ac3d07dc123cb3ecd05d3a07673a9a9232`.
Only the following package versions changed:

| Package | Committed lock | Temporary lock |
| --- | --- | --- |
| NumPy | 2.4.6 for Python 3.11; 2.5.0 for 3.12+ | 2.4.6 for 3.11; 2.5.5 for 3.12+ |
| SciPy | 1.17.1 for Python 3.11; 1.18.0 for 3.12+ | 1.17.1 for 3.11; 1.18.1 for 3.12+ |

On macOS ARM64 with CPython 3.15.2, independent clean base,
`performance`, and `model-build` environments, as well as a combined-extras
environment, installed the locked third-party runtime dependencies with
`uv sync --no-build`; the local project itself was built by uv. The locked
runtime/combined-extras requirements also resolved with `uv pip install --dry-run --only-binary :all: --python-version 3.15 --python-platform x86_64-unknown-linux-gnu`. That is wheel-availability evidence only: it did
not install or execute the packages on Linux. It does not cover every platform
or free-threaded Python.

## Development-Tool Build Requirements

With the numerical-only lock, a wheel-only macOS Python 3.15 environment
including dev and docs stopped at PyYAML 6.0.3. A normal isolated sync succeeded
on this machine, building PyYAML and MarkupSafe from source. The prior review
also observed a docopt source build; a cached built wheel can conceal that
requirement, so a fresh cache is important when assessing wheel-only installs.
`pre-commit` pulls in PyYAML; `cffconvert → pykwalify → docopt` pulls in docopt.

A second isolated lock additionally upgraded PyYAML 6.0.3 → 6.0.4 and
MarkupSafe 3.0.3 → 3.0.4; its SHA-256 was
`2484b3cbaa28a76e2cbfe25e7db4697f8149d80b5b7da95089b28ab05a99d9cc`.
In a fresh cache, a binary-only dev/docs sync then stopped at docopt 0.6.2,
whose published distribution is source-only. A normal sync succeeded, building
docopt locally. This second candidate was **not** the lock tested by the
supported-Python matrix below; it needs separate compatibility review before
adoption. It is not necessary to introduce a third-party replacement package
to claim support. Clean Linux must demonstrate any source-build prerequisites.

Sources: [NumPy 2.5.5](https://pypi.org/project/numpy/2.5.5/),
[SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/),
[PyYAML 6.0.4](https://pypi.org/project/PyYAML/6.0.4/),
[MarkupSafe 3.0.4](https://pypi.org/project/MarkupSafe/3.0.4/), and
[docopt 0.6.2](https://pypi.org/project/docopt/0.6.2/).

## Supported-Python Regression Matrix

The numerical-only temporary lock was tested on macOS ARM64 using isolated
Python environments and the same full selections as the push CI matrix.
These are local results, not GitHub Actions or clean Linux results.

| Python | Selection | Result |
| --- | --- | --- |
| 3.11 | Full, excluding `coverage_gate` | 2,805 passed, 7 skipped, 5 deselected |
| 3.12 | Full with branch coverage gate | 2,810 passed, 7 skipped; 95.40% coverage |
| 3.13 | Full, excluding `coverage_gate` | 2,805 passed, 7 skipped, 5 deselected |
| 3.14 | Full, excluding `coverage_gate` | 2,805 passed, 7 skipped, 5 deselected |

The initial temporary source archive lacked Git metadata needed by two
inventory tests. After initializing the temporary checkout and granting the
localhost access required by web integration tests, the complete 3.11 suite
was rerun. A sandboxed retry without localhost access also failed web tests;
that result is a test-environment limitation, not matrix acceptance evidence.
One upstream pytest/AnyIO deprecation warning remained. Optional live-data and
other marked tests were skipped as reported by the suite.

## Next Gate

Review the numerical-only refresh as its own change, including the dev-tool
choices above, then run `ASSURE315-02`: full locked Python 3.15 acceptance on
clean Linux, including coverage, extended correctness, docs, web/browser,
wheel and sdist installation with both extras. Record platform and skips. Only
then decide whether platform evidence supports `ASSURE315-03` and changes to
CI, classifiers and public support. Do not treat a local macOS matrix or an
index dry run as the clean Linux gate.
