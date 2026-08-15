# Installation

SynthPopCan is a **command-line tool** and **Python library**. Using it requires
opening a **terminal**, a text window where we type commands rather than click
buttons. The examples in this documentation use a **Unix-style shell** on
macOS, Linux, and Windows through the Windows Subsystem for Linux (WSL).
Automated release checks run on Ubuntu; macOS and WSL are best-effort supported,
and native Windows Python is not a supported 1.0 environment. See the
[support policy](stewardship.md#supported-environments) for the exact boundary.

For a short introduction, start with MDN's [Command Line Crash
Course](https://developer.mozilla.org/en-US/docs/Learn_web_development/Getting_started/Environment_setup/Command_line).
For a longer research-oriented lesson, use [Library Carpentry: The UNIX
Shell](https://librarycarpentry.github.io/lc-shell/) or [Software Carpentry: The
Unix Shell](https://swcarpentry.github.io/shell-novice/). These lessons assume no
previous shell experience and explain folders, paths, files, commands, options,
and pipes.

````{admonition} Windows users
:class: note

We recommend using the **Windows Subsystem for Linux (WSL)** so the Unix-style
examples on this site work unchanged. Follow Microsoft's [Install
WSL](https://learn.microsoft.com/en-us/windows/wsl/install) guide, then open the
**Ubuntu** profile in [Windows
Terminal](https://learn.microsoft.com/en-us/windows/terminal/) and run:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
python3 --version
```

The final command must report Python 3.11 or newer. Continue through this page
inside the Ubuntu terminal. For help locating Windows files from WSL, see
Microsoft's [WSL development-environment
guide](https://learn.microsoft.com/en-us/windows/wsl/setup/environment).
````

SynthPopCan can be installed from [PyPI](https://pypi.org/), run as a one-off
command with `uvx`, or installed from a source checkout for development. If we
only want to **use the command line or beginner Python API**, start with the
PyPI installation. If we want to **edit the code, documentation, or tests**, use
the source checkout.

```{admonition} Published and development documentation
:class: note

`pip install synthpopcan` and `uvx synthpopcan` install the current published
package. The `latest` documentation can also describe development features
planned for the next release; use `stable` for the latest tagged version.
```

## Requirements

- Python 3.11 or newer in the macOS, Linux, or WSL environment where we will run
  SynthPopCan. Versions 3.11 through 3.14 are in the current automated release
  matrix; a newer Python has not yet received that release coverage. Download from
  [python.org/downloads](https://www.python.org/downloads/) on macOS, use the
  operating system's package manager on Linux, or follow the WSL steps above on
  Windows.
- Git, only when cloning from the repository.
- `pip`, which is included with most Python installations.
- Optional: [`uv`](https://docs.astral.sh/uv/), when using `uvx` for one-off commands or when working on the
  source checkout.
- Local source data staged outside git when working with real census or private files.

We do not need a database, a cloud account, or a web server for the
command-line workflows.

## Install From PyPI

For most readers, the best first path is the **published package from PyPI**.
Create a project folder and an isolated Python environment first:

```bash
mkdir synthpopcan-work
cd synthpopcan-work
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install synthpopcan
```

The virtual environment keeps SynthPopCan and its dependencies separate from
other Python projects. When we return to this folder in a new terminal session,
activate it again before running SynthPopCan:

```bash
cd synthpopcan-work
source .venv/bin/activate
```

Then check that the command is available:

```bash
synthpopcan --help
```

This is the best path when we want to run **command-line examples**, use the
**beginner API in a notebook**, or build small teaching workflows without
editing SynthPopCan itself.

````{admonition} Optional CART model training in 0.7.0
:class: note

Starting with `0.7.0`, the package keeps scikit-learn out of the ordinary
runtime installation. Reading portable model JSON, generating populations, and training
`conditional-frequency` models do not require it. Install the model-building
extra only when we need to **train CART models**:

```bash
python -m pip install "synthpopcan[model-build]"
```

Starting with `0.7.0`, the base package does not install scikit-learn. A source
checkout's development environment includes it through `uv sync`.

````

For notebook work, install SynthPopCan into the same Python environment that
[Jupyter](https://jupyter.org/) uses. A minimal notebook smoke test is:

```python
import synthpopcan as spc

spc.__version__
```

## Run One-Off Commands With `uvx`

If we have `uv` installed but do not want to install SynthPopCan into the
current environment, `uvx` can download the package and run the `synthpopcan`
command in an isolated temporary environment:

```bash
uvx synthpopcan --help
uvx synthpopcan guide ipf
```

This is useful for trying the CLI or running a short command. For repeated work
in a project folder or notebook, a normal `pip` installation is usually easier
to reason about.

## Install From a Source Checkout

A source checkout is a local copy of the SynthPopCan repository cloned from
GitHub. Use one when we want to **edit SynthPopCan**, **run the tests**, **build
the documentation locally**, or work against unreleased changes.

Clone the repository, then enter the checkout:

```bash
git clone https://github.com/dlq/synthpopcan.git
cd synthpopcan
```

The repository currently uses `uv` for repeatable local development. If we do
not have `uv`, install it from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

From the repository root:

```bash
uv sync
```

This creates a local environment and installs SynthPopCan with its runtime
dependencies.

For documentation work:

```bash
uv sync --group docs
```

## Run the Command

If SynthPopCan was installed with `pip`, run:

```bash
synthpopcan --help
```

When working directly from a source checkout with `uv`, prefix commands with
`uv run` so they use the checkout's isolated Python environment — a separate
installation that keeps SynthPopCan's dependencies from interfering with other
Python projects on the same machine:

```bash
uv run synthpopcan --help
```

The rest of the documentation usually shows `synthpopcan ...` to focus on the
tool itself. If we are using `uvx`, replace `synthpopcan ...` with
`uvx synthpopcan ...`. If we are working from a checkout, use
`uv run synthpopcan ...`.

Beginner command-line guidance is available with:

```bash
synthpopcan guide ipf
synthpopcan guide model
synthpopcan guide small-area
```

## Quick Getting Started

This short workflow generates ten linked households and their people from the
**bundled synthetic teaching model**. It works after a PyPI installation, under
`uvx`, or from a source checkout. It does not need an internet connection,
public census files, or private microdata.

```bash
synthpopcan models generate demo-linked-household-person \
  --households 10 \
  --condition "geo=Demo North" \
  --out synthpopcan-quickstart \
  --random-seed 42

synthpopcan validate linked synthpopcan-quickstart
```

The output directory contains `households.csv`, `persons.csv`, and a generation
manifest. The validation command checks that people remain linked to known
households and that recorded household sizes agree with the generated person
rows. The model is deliberately small and fictional: it tests the installation,
but it does not represent a Canadian population.

If we are running from a source checkout without activating the environment, we
can add `uv run` before each `synthpopcan` command.

Once this check succeeds, continue to [Getting Started](getting-started.md).
That page helps us choose between the local web app, a command-line workflow,
and a self-contained notebook example.

## Local Data

SynthPopCan looks for local data under `data/` by default. Raw and private data
should stay out of git.

```text
data/
  raw/
  derived/
  work/
  private/
    sources/
```

Check the expected local layout with:

```bash
uv run synthpopcan data doctor
```

Use `--data-root PATH` or `SYNTHPOPCAN_DATA_ROOT` when the data lives somewhere
else.

## Working Folder Advice

Run commands from a **project working directory** where we are comfortable
creating input, output, and report files. Source contributors should use the
repository root for the development commands in
[CONTRIBUTING.md](https://github.com/dlq/synthpopcan/blob/main/CONTRIBUTING.md).
In examples, lines ending with `\` continue onto the next line.

Most examples write small files such as `seed.csv`, `weights.csv`, and
`fit-report.json` in the current directory. For a real project, create a
separate working folder so outputs from different runs do not get mixed
together.

## Find SynthPopCan Online

- **Documentation:** <https://synthpopcan.readthedocs.io/>
- **Source code and issues:** <https://github.com/dlq/synthpopcan>
- **Package:** <https://pypi.org/project/synthpopcan/>
