# Getting Started

This page comes after the {doc}`introduction` and {doc}`installation`. It helps
us choose a first practical workflow, then points us to the walkthrough and
reference material for that path.

## Check the Installation First

Before choosing a workflow, make sure the installation check succeeds:

```bash
synthpopcan --help
```

If the terminal cannot find `synthpopcan`, return to {doc}`installation`. That
page explains installation with `pip`, one-off commands with `uvx`, and commands
run from a source checkout. It also includes a short fictional generation and
validation example. Once that example works, the same installation is ready for
the paths below.

## Choose a Workflow

SynthPopCan has several entry points because people come to synthetic
population work with different questions. We can choose a path before learning
all of the command names.

SynthPopCan has three friendly surfaces: the **local web app**, the **command
line**, and the **beginner Python API**. They can do related work, but they
serve different research habits.

In practice, we usually start with a **research question**, choose the surface
that fits our working style, and keep the generated files together with
**validation reports** and **method notes**. A web session is good for guided
inspection, the command line is good for reproducible runs, and a notebook is
good when code, prose, and interpretation need to sit side by side.

### Quick Decision Table

Scan these choices first, then use the matching path below for context and next
steps.

| Situation | Start Here |
| --- | --- |
| We want the friendliest first run | {doc}`web-app` |
| We want a reproducible terminal workflow | {doc}`command-line` |
| We want a notebook | {doc}`library-getting-started` |
| We have seed rows and margins | {doc}`ipf` |
| We have a reviewed model package | {doc}`tree-generate` |
| We need to train or audit a model | {doc}`tree` |
| We need CT, CSD, ADA, or DA assignment | {doc}`small-area` |
| We need smaller verified map geometry | {doc}`geodata` |
| We need to attach external context | {doc}`enrichment` |
| We need to inspect data first | {doc}`data` |
| We need to check results | {doc}`validate` |

(if-we-want-to-try-synthpopcan)=

```{rubric} If We Want To Try SynthPopCan
:class: workflow-step
```

Start with the {doc}`web-app`.

The local web app is the gentlest first contact because it gives us **forms**,
**previews**, and **downloads**. It is useful when we are learning what the
inputs look like or when we want to inspect a result before writing a script.

Use this path when:

- we want guided local exploration;
- we want to see the shape of controls, generated rows, and validation output;
- we are not yet sure which command-line workflow we need.

After that, move to {doc}`command-line` when we need reproducibility. It maps the
command groups onto the same beginner workflows and explains how to find help at
each level.

(if-we-want-a-notebook-or-teaching-script)=

```{rubric} If We Want a Notebook or Teaching Script
:class: workflow-step
```

Start with {doc}`library-getting-started`.

The beginner Python API is designed for **Jupyter notebooks**, **classroom
examples**, and **research notes** where code and prose live together. It
exposes a small surface:

- read seed rows;
- read controls;
- fit IPF weights;
- generate from a reviewed model package;
- calibrate linked candidates to small-area controls;
- render calibrated small-area output as a browser map; and
- attach a validated external-data sidecar without rewriting the population.

Use this path when:

- we want a notebook that explains the decisions as it runs;
- we want to save plots, notes, and outputs together;
- we want Python without learning the lower-level modules first.

The deeper library discussion is in {doc}`library`, and the generated reference
is in {doc}`api`.

(if-we-have-seed-rows-and-control-totals)=

```{rubric} If We Have Seed Rows and Control Totals
:class: workflow-step
```

If we already have normalized controls, start with {doc}`ipf`. If we still need
to find and prepare public totals, follow {doc}`statcan`, then {doc}`controls`,
and continue to {doc}`ipf`. The {doc}`command-line` chapter shows this complete
sequence as one workflow.

IPF is the right first method when our **seed table already contains the
columns we want to fit**. For example, if the seed rows contain age group and
sex, and the controls contain age and sex totals, IPF can adjust weights so the
seed rows match those totals.

Use this path when:

- the variables we need already exist in the seed rows;
- we have public control totals or can build them from a Statistics Canada
  table;
- weighted output is acceptable, or we can expand weights later.

Do not use IPF to **invent a missing variable**. If the seed rows do not contain
a column, IPF cannot fit controls for that column.

(if-we-have-or-need-linked-households-and-people)=

```{rubric} If We Have or Need Linked Households and People
:class: workflow-step
```

Start with {doc}`tree-generate` if we have a reviewed package. Use {doc}`tree`
when we need to train, audit, or package models.

Linked household/person workflows are useful when **generated people need to
belong to generated households**. The model package supplies candidate
household and person rows. Validation then checks whether the household/person
links still make sense.

Use this path when:

- household structure matters to the research question;
- we need person rows that inherit household context;
- we are working from a reviewed model package or preparing one.

Tree output should be read as **modelled candidate data**. It still needs
validation, and it may need calibration to public controls.

(if-we-need-small-area-geography)=

```{rubric} If We Need Small-Area Geography
:class: workflow-step
```

Start with {doc}`small-area`.

Small-area linked synthesis is the **bridge** between broad generated
household/person candidates and public Census Profile controls for target
geographies. It is the path we use when generated households need to be assigned
to **census tracts**, **aggregate dissemination areas**, or **dissemination
areas**. Census subdivisions are also supported when municipal or
municipal-equivalent geography fits the research question.

Use this path when:

- we already have candidate linked household/person rows;
- we have Census Profile controls for CTs, CSDs, ADAs, or DAs;
- we want output households and people with an assigned geography column.

Dissemination blocks belong later in the workflow. They are better understood
as a **placement geography** after households have been calibrated to CTs,
CSDs, ADAs, or DAs.

(if-we-need-map-geometry)=

```{rubric} If We Need Smaller Map Geometry
:class: workflow-step
```

Start with {doc}`geodata` after reading {doc}`small-area`.

Prepared geodata is a **presentation layer**, not another calibration step. It
downloads a versioned, checksummed display copy of a canonical Census boundary
so a map can be smaller and faster. It does not select places, create controls,
or change the geography assigned to synthetic households and people.

Use this path when:

- the population already has an explicit Census geography;
- a canonical boundary is too large for convenient interactive display;
- the `geodata-v1` catalogue contains the exact year, level, and regional scope
  we need; and
- we will retain the canonical analytical-boundary provenance separately.

The `geodata` commands were added in `0.7.0`. Display assets are published in
the separately versioned `geodata-v1` release.

(if-we-need-external-context)=

```{rubric} If We Need External Context
:class: workflow-step
```

Start with {doc}`enrichment`.

An enrichment layer adds area characteristics, facilities, governed
household/person attributes, or relational context **beside** a linked
population. It does not widen or rewrite the base household and person tables.
The manifest records the source revision, licence and access context,
geography identity, linkage keys, coverage, limitations, and checksums.

Use this path when:

- the synthetic population already exists;
- a research question needs context from another documented source;
- any requested join or coverage comparison uses compatible geography
  identifiers (an unlinked ODEF facility inventory does not require one); and
- we need to prove that the original linked population remained unchanged.

The enrichment framework was added in `0.7.0`. Use `synthpopcan enrich can-fed`
or `spc.enrich_can_fed` for reviewed 2021 DA food-environment context, and
`synthpopcan enrich odef` or `spc.enrich_odef` for the reviewed educational-
facility inventory. Use `enrich import` or `spc.enrich_population` for another
documented normalized layer.

(if-we-are-still-inspecting-sources)=

```{rubric} If We Are Still Inspecting Sources
:class: workflow-step
```

Start with {doc}`data`, {doc}`statcan`, and {doc}`microdata`.

Synthetic population work often begins **before modelling**. We need to know
what a source file contains, which categories it uses, which geography it
covers, and whether the file can be redistributed.

Use this path when:

- we are not sure what columns or categories are available;
- we need to document local source files;
- we are checking whether a file belongs in a public workflow, a private cache,
  or a derived model package.

(if-we-need-to-check-an-output)=

```{rubric} If We Need To Check an Output
:class: workflow-step
```

Start with {doc}`validate`.

Validation is **not a final polish step**. It is how we learn what the generated
population can and cannot support.

Use this path when:

- we need to compare output rows back to controls;
- we need to check household/person links;
- we need a report to keep with a method note, notebook, or release artifact.

## What We Should Keep With Any Workflow

Whatever path we choose, keep enough evidence for another reader to understand
the run:

- input file names and source citations;
- category mappings and filters;
- command lines or notebook cells;
- random seeds;
- SynthPopCan version;
- validation reports;
- notes about controls that failed, sparse categories, and unresolved caveats.

That record is part of the **research output**.
