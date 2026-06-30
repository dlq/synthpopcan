# Which Workflow Should We Use?

SynthPopCan has several entry points because people come to synthetic
population work with different questions. This page helps us choose a first
path before we learn the command names.

```{figure} _static/user-routes.svg
:alt: Three parallel routes through SynthPopCan: web app, command line, and Python notebook. Each route starts from a research question and ends with generated data plus validation notes.
:align: center

SynthPopCan has three friendly surfaces: the local web app, the command line,
and the beginner Python API. They can do related work, but they serve different
research habits.
```

## If We Want To Try SynthPopCan

Start with the {doc}`web-app`.

The local web app is the gentlest first contact because it gives us forms,
previews, and downloads. It is useful when we are learning what the inputs look
like or when we want to inspect a result before writing a script.

Use this path when:

- we want guided local exploration;
- we want to see the shape of controls, generated rows, and validation output;
- we are not yet sure which command-line workflow we need.

After that, move to the command-line pages when we need reproducibility.

## If We Want a Notebook or Teaching Script

Start with {doc}`library-getting-started`.

The beginner Python API is designed for Jupyter notebooks, classroom examples,
and research notes where code and prose live together. It exposes a small
surface:

- read seed rows;
- read controls;
- fit IPF weights;
- generate from a reviewed model package;
- calibrate linked candidates to small-area controls.

Use this path when:

- we want a notebook that explains the decisions as it runs;
- we want to save plots, notes, and outputs together;
- we want Python without learning the lower-level modules first.

The deeper library discussion is in {doc}`library`, and the generated reference
is in {doc}`api`.

## If We Have Seed Rows and Control Totals

Start with {doc}`ipf`, then use {doc}`controls` and {doc}`statcan` as needed.

IPF is the right first method when our seed table already contains the columns
we want to fit. For example, if the seed rows contain age group and sex, and the
controls contain age and sex totals, IPF can adjust weights so the seed rows
match those totals.

Use this path when:

- the variables we need already exist in the seed rows;
- we have public control totals or can build them from a Statistics Canada
  table;
- weighted output is acceptable, or we can expand weights later.

Do not use IPF to invent a missing variable. If the seed rows do not contain a
column, IPF cannot fit controls for that column.

## If We Have or Need Linked Households and People

Start with {doc}`tree-generate` if we have a reviewed package. Use {doc}`tree`
when we need to train, audit, or package models.

Linked household/person workflows are useful when generated people need to
belong to generated households. The model package supplies candidate household
and person rows. Validation then checks whether the household/person links still
make sense.

Use this path when:

- household structure matters to the research question;
- we need person rows that inherit household context;
- we are working from a reviewed model package or preparing one.

Tree output should be read as modelled candidate data. It still needs
validation, and it may need calibration to public controls.

## If We Need Small-Area Geography

Start with {doc}`small-area`.

Small-area linked synthesis is the bridge between broad generated
household/person candidates and public Census Profile controls for target
geographies. It is the path we use when generated households need to be assigned
to census tracts, aggregate dissemination areas, or dissemination areas.

Use this path when:

- we already have candidate linked household/person rows;
- we have Census Profile controls for CTs, ADAs, or DAs;
- we want output households and people with an assigned geography column.

Dissemination blocks belong later in the workflow. They are better understood
as a placement geography after households have been calibrated to CTs, ADAs, or
DAs.

## If We Are Still Inspecting Sources

Start with {doc}`data`, {doc}`statcan`, and {doc}`microdata`.

Synthetic population work often begins before modelling. We need to know what a
source file contains, which categories it uses, which geography it covers, and
whether the file can be redistributed.

Use this path when:

- we are not sure what columns or categories are available;
- we need to document local source files;
- we are checking whether a file belongs in a public workflow, a private cache,
  or a derived model package.

## If We Need To Check an Output

Start with {doc}`validate`.

Validation is not a final polish step. It is how we learn what the generated
population can and cannot support.

Use this path when:

- we need to compare output rows back to controls;
- we need to check household/person links;
- we need a report to keep with a method note, notebook, or release artifact.

## A Simple Decision Table

| Situation | Start Here | Why |
| --- | --- | --- |
| We want the friendliest first run | {doc}`web-app` | Forms, previews, and downloads reduce setup friction. |
| We want a notebook | {doc}`library-getting-started` | Prose, code, outputs, and interpretation stay together. |
| We have seed rows and margins | {doc}`ipf` | IPF adjusts weights to match controls already represented in the seed. |
| We have a reviewed model package | {doc}`tree-generate` | Generate linked households and people from the package. |
| We need to train or audit a model | {doc}`tree` | Advanced model-building and release-readiness tools live there. |
| We need CT, ADA, or DA assignment | {doc}`small-area` | Calibrate linked candidates to small-area controls. |
| We need to inspect data first | {doc}`data` | Check local layout, source shape, and provenance before modelling. |
| We need to check results | {doc}`validate` | Keep evidence with the generated output. |

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

That record is part of the research output.
