# Python 3.15 platform-support decision — 2026-11-22

**Decision:** add standard CPython 3.15 to the supported Python matrix and
package classifier. The regular Ubuntu matrix includes the `performance`
extra, uses the existing affected-test selection on pull requests and runs the
full application suite on pushes. The stable required `Python` summary still
depends on the entire matrix. Python 3.12 remains the coverage and quality
baseline, so this does not duplicate the full coverage gate.

Python 3.15 is a [stable bugfix release](https://www.python.org/downloads/),
with its [release schedule](https://peps.python.org/pep-0790/) extending
security maintenance to 2031. The [clean Linux acceptance](python-3.15-linux-acceptance-2026-11-22.md)
passed the full suite with coverage, extended correctness, both optional extras,
documentation, browser scenarios, and installed wheel and source-distribution
smokes on CPython 3.15.2. It used a clean Ubuntu x86-64 runner and the committed
numerical lock; it was not a test of this later matrix change. The earlier
[macOS ARM64 review](python-3.15-review-2026-11-20.md) passed the full suite
with the same refreshed NumPy and SciPy versions, and the
[lock review](python-3.15-lock-review-2026-11-21.md) checked the refreshed
runtime graph and build-tool limitations. Those are point-in-time results,
not ongoing macOS automation.

After adding the matrix and classifier in this checkout, a fresh locked
CPython 3.15.2 environment on macOS ARM64 ran the push CI compatibility
selection with the `performance` extra: 2,838 passed, seven skipped and five
coverage-tool integration cases deselected. An upstream pytest/AnyIO
deprecation warning remained. The documentation build, lock consistency and
matrix/classifier consistency checks also passed locally.

The existing [platform policy](../stewardship.md#supported-environments)
continues to apply: Ubuntu CI is tested, macOS and Ubuntu under WSL are
best-effort, and native Windows Python is not a supported 1.x environment.
Free-threaded builds, untested architectures, optional live data and external
services are not established by these runs. Some development tools may require
building from source; that is distinct from the runtime installation evidence.
The newly added matrix job must pass on the actual change once run on GitHub;
the historical acceptance run does not establish that result.
