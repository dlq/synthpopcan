# Command-Line Getting Started

The SynthPopCan command line is useful when we want a workflow that is
**repeatable**, **recordable**, and suitable for a methods note or research
script. This page explains how the commands fit together. The chapters that
follow provide the concepts, complete option references, worked examples, and
troubleshooting guidance for each command group.

If `synthpopcan --help` does not work yet, return to {doc}`installation`. If we
are still deciding between the command line, local web app, and Python library,
start with {doc}`getting-started`.

## How a Command Is Put Together

Most commands have this shape:

```text
synthpopcan COMMAND [SUBCOMMAND] [OPTIONS]
```

For example:

```bash
synthpopcan data doctor
synthpopcan statcan wds search "population age sex"
synthpopcan ipf fit --help
synthpopcan geodata fetch --help
synthpopcan enrich import --help
```

Here, `data`, `statcan`, `ipf`, `geodata`, and `enrich` are **command groups**. A
group usually contains more specific **subcommands**, such as `doctor`, `search`,
or `fit`. Named options such as `--seed`, `--controls`, and `--out` tell that
subcommand which files to read, what choices to apply, and where to write its
result.

The examples in these docs omit the shell prompt, so we enter the command
beginning with `synthpopcan`. A backslash (`\`) at the end of a line means that
the same command continues on the next line.

We label examples by what they need:

- **Runnable teaching example:** safe to enter as shown after installation.
- **Continue from the previous step:** uses files created earlier in the same
  walkthrough.
- **Template: replace these paths:** shows a complete command shape, but expects
  our own input filenames or package ID.
- **Source checkout required:** uses a teaching fixture or development command
  from the repository.
- **Network required:** contacts a public service or downloads an artifact.
- **Restricted source data required:** operates on microdata that must remain in
  an appropriately controlled local environment.

A command can carry more than one label. Command-reference examples are usually
templates; worked walkthroughs state when they are runnable from beginning to
end.

```{admonition} Why the examples begin with synthpopcan
:class: note

The chapters use `synthpopcan ...` as the canonical form after installation.
For a one-off `uvx` invocation or a source checkout, the prefix changes to
`uvx synthpopcan ...` or `uv run synthpopcan ...`. The commands, subcommands,
and options after that prefix remain the same. See {doc}`installation` for the
three installation and invocation paths.
```

## Find Commands and Options

We do not need to memorize the interface. Help is available at every level:

```bash
synthpopcan --help
synthpopcan statcan --help
synthpopcan statcan wds --help
synthpopcan statcan wds search --help
```

Running `synthpopcan` without a command prints a short workflow chooser. The
`guide` commands provide a compact sequence for each beginner workflow:

```bash
synthpopcan guide ipf
synthpopcan guide model
synthpopcan guide small-area
```

Use the guide when we need the **next command**. Use the documentation chapter
when we need to understand **why that step exists**, how to interpret its
inputs, or what can go wrong.

## Choose a Workflow

The sidebar follows the order in which commands usually enter a research
workflow. We may skip a page when its input is already prepared.

### Seed Rows and Public Controls

Use this path when we have seed records that already contain the variables we
want to fit:

1. {doc}`data` to check the local data layout and inspect files safely.
1. {doc}`statcan` to find or download public aggregate tables, when needed.
1. {doc}`controls` to interpret and normalize aggregate totals.
1. {doc}`ipf` to check compatibility and fit seed-record weights.
1. {doc}`validate` to compare the result with the controls and keep a report.

### A Reviewed Model Package

Use this path when a suitable linked household/person package already exists:

1. {doc}`tree-generate` to inspect or fetch the package and generate candidates.
1. {doc}`small-area` when the candidates must be assigned and calibrated to CTs,
   ADAs, or DAs.
1. {doc}`validate` before interpreting or sharing the generated population.

Small-area assignment is optional. A project that does not need local geography
can validate the generated household/person files directly.

For restartable national 2021 execution, `synthpopcan geo national-da` and
`synthpopcan geo national-ada` provide matching `fetch-profiles`, `prepare`,
and `run` interfaces. They share planning and execution contracts while
retaining the different official source layouts and identifiers for each
geography level. Their runners reuse conditioned candidate pools, checkpoint
atomic batches, support bounded process and fitting parallelism, and produce
aggregate national evidence. Detailed batch maps are opt-in; one compact
national overview is produced after completion. See {doc}`small-area` before
attempting a national run.

```{admonition} Unreleased 0.7.0 commands
:class: note

The national DA/ADA commands are implemented on the development branch but are
not included in the published `0.6.3` package. Use a source checkout until
`0.7.0` is published.
```

### Prepared Display Boundaries

Use {doc}`geodata` when a map needs smaller, prepared display geometry rather
than a new conversion from the canonical Statistics Canada boundary product.
The `geodata-v1` release contains checksummed 2016 national and 2021 national or
province/territory assets. These files are for **visualization only**: they do
not replace canonical boundaries for geographic selection, measurement, or
reconciliation.

The `geodata` command group is an unreleased `0.7.0` development feature. The
separately versioned `geodata-v1` assets are already published so their bytes
and checksums remain stable while the CLI proceeds toward the software release.

### External Context

After creating a linked population, use {doc}`enrichment` to register an
immutable source revision and attach a normalized geography, facility, or
other governed sidecar layer. Enrichment keeps the base household/person files
unchanged and rejects implicit cross-vintage geography joins.

The `enrich` command group is also an unreleased `0.7.0` development feature.

### Developing a Model

This is the advanced path for researchers who have appropriate access to source
microdata and need to create a model package:

1. {doc}`microdata` to inspect and prepare seed or training tables.
1. {doc}`tree` to train, audit, and package tree models.
1. {doc}`tree-generate` to generate from the reviewed package.
1. {doc}`small-area` when geographic calibration is required.
1. {doc}`validate` to check the resulting artifacts.

Model development adds methodological and privacy responsibilities. It is not a
prerequisite for using an existing reviewed package.

## Work With Files Deliberately

Paths are interpreted relative to the terminal's **current working directory**
unless we provide an absolute path. Before a serious run, create a separate
working directory so inputs, generated files, reports, and notes from different
runs do not become mixed together.

Commands that write files use options such as `--out`, `--out-dir`, or
`--report`. Some expect a filename; others create several artifacts in a
directory. Check the subcommand's `--help` and the corresponding documentation
page before a long run.

Inspection commands generally print a readable table. Where `--format json` is
available, use it for scripts or when another program will read the result. A
JSON option changes the presentation of a report; it does not turn raw source
data into a safe public artifact.

For every substantive run, keep:

- the exact command and SynthPopCan version;
- source citations and input filenames;
- category mappings and geography choices;
- random seeds and model-package identifiers;
- generated files and validation reports;
- notes about failed controls, sparse categories, and unresolved limitations.

These materials are part of the **research record**, not incidental by-products
of running the software.

## When a Command Fails

SynthPopCan reports a non-zero exit status when it cannot complete a command.
Read the first error before changing the invocation. Common causes include a
misspelled path, a missing column, incompatible controls, a private-data guard,
or an unavailable network source.

Use `--help` to check the command shape, then use the **Troubleshooting** section
of the relevant chapter. In particular:

- use {doc}`data` for paths, encodings, delimiters, and private-data handling;
- use {doc}`controls` and {doc}`ipf` for category or seed-coverage problems;
- use {doc}`statcan` for source downloads and changing table structures;
- use {doc}`tree-generate` and {doc}`tree` for model-package problems;
- use {doc}`small-area` for geography, scale, and calibration problems;
- use {doc}`validate` when a command finishes but the result still needs
  interpretation.

The {doc}`web-app` chapter documents the related `synthpopcan serve` command.
That command launches a guided local browser interface; it is an alternative
way to operate selected workflows, rather than another stage in the command-line
sequence.
