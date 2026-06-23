# Introduction

SynthPopCan helps researchers build and check Canadian synthetic populations.
The project is early-stage, but the current command-line tools already support
small, inspectable workflows for control tables, IPF calibration, Statistics
Canada sources, microdata-derived seed files, linked household/person models,
and validation reports.

The intended audience includes humanities and digital-humanities researchers,
social scientists, policy researchers, and technically curious project teams.
The documentation assumes that many readers care more about source choices,
categories, provenance, and interpretation than about Python internals.

For a broader methods-oriented introduction, read the {doc}`field-primer`. It
explains the field around synthetic populations, IPF, tree models, disclosure
risk, validation, and why these outputs should be treated as interpretive
artifacts rather than recovered facts.

## What Is a Synthetic Population?

A synthetic population is a generated table of people, households, or other
units. The rows are not real people. They are constructed so that selected
features match a target population.

For example, a synthetic population might be designed so that:

- age-group totals match a Statistics Canada table;
- sex totals match the same geography;
- generated households have plausible household sizes;
- generated people remain linked to generated households;
- validation reports show which targets were matched and where errors remain.

Synthetic populations are useful when a project needs row-shaped data but cannot
use real individual records directly. They are also useful for simulation,
teaching, exploratory modelling, and reproducible demonstrations.

For broader context, Borysov, Rich, and Pereira describe population synthesis as
generating realistic micro-agents for simulation work, while Gargiulo and
co-authors show why household structure matters when synthetic people need to be
grouped into realistic households. See the reading list at the end of this page.

## Two Main Ways SynthPopCan Generates Rows

SynthPopCan currently has two main generation paths.

**IPF calibration** starts with a seed table. The seed contains example rows and
columns such as age group, sex, tenure, or geography. IPF adjusts the row weights
until the weighted totals match a set of control totals. This is best when the
seed already contains the variables you want to fit.

**Tree-based generation** trains a model from microdata-derived training rows,
then generates new rows from the model. The linked tree workflow trains
household and person models together so generated people can remain connected to
generated households.

A decision tree is a set of repeated questions. For example, a household model
might first split records by province, then by tenure, then by household size,
and finally use the observed outcomes in the matching branch to generate a new
row. A forest model, such as a random forest, combines many trees trained on
different samples or feature subsets. Forests can be more stable for prediction,
but they are harder to inspect as a single research object. SynthPopCan does not
currently train random forests; it uses conditional-frequency and CART-style
tree models because their groups, leaves, supports, and dominant outcomes can be
audited and explained. The scikit-learn decision-tree guide is a useful
technical reference for CART-style splits, while the population-synthesis
literature listed below gives broader context for why household/person
relationships matter.

Tree-based generation is not automatically better than IPF. It can produce rows
with richer combinations of variables, but the quality of the model depends on
the training rows, the column choices, and the amount of support behind each
branch. A bad model may reproduce a biased training sample, memorize rare
patterns, generate implausible household/person combinations, or look precise
while resting on very few source records. Treat tree output as a modelled
artifact that needs validation, not as a recovered version of the original
population.

These approaches can be combined. A tree model can generate candidate rows, and
IPF can later calibrate compatible columns to public control totals.

## Treat Generated Populations as Arguments, Not Facts

Synthetic populations can be persuasive because they look like ordinary data:
one row per person, one row per household, familiar column names, and tidy CSV
files. That familiar shape can create false confidence. A generated table is not
a recovered census file. It is an argument made from source data, modelling
choices, category mappings, random seeds, and validation thresholds.

This matters especially for humanities and digital-humanities work, where the
purpose is often interpretation rather than operational prediction. A model can
be technically valid and still be a poor fit for a research question. For
example:

- an IPF fit can match age and sex margins while destroying relationships the
  controls never measured;
- a tree model can reproduce patterns in restricted training data that are too
  local, too sparse, or too identifying to share;
- a validation report can show that selected targets match while saying nothing
  about unmeasured variables;
- a clean CSV can hide incompatible source universes, such as different years,
  geographies, household definitions, or inclusion rules.

The safest reading is: SynthPopCan helps make modelling choices explicit. It
does not make those choices automatically correct. Keep the reports, source
notes, mappings, and commands with the output so readers can evaluate the chain
of decisions.

## Important Terms

**Seed file:** The starting rows for IPF. IPF changes how much each row counts;
it does not invent new columns.

**Control table:** A table of target totals, usually from a public aggregate
source. Controls say what the fitted population should match.

**Margin:** One set of controls, such as age group, sex, or a joint age-by-sex
table.

**Weight:** A number saying how much a seed row counts in the fitted population.

**Expanded rows:** A full synthetic CSV with one row per generated person or
household. Expanded files can become large, so weights are often better for
inspection.

**Validation report:** A check that compares generated output back to controls
or checks household/person linkage.

**Tree support:** The amount of training data behind a tree group or leaf. Low
support means the generated outcome may be based on too few examples.

**Purity:** How dominant one outcome is within a group or leaf. Very high purity
can be harmless for common patterns, but for small groups it may indicate
memorization or disclosure risk.

**Provenance:** Notes and metadata that explain source files, geography,
columns, category mappings, random seeds, commands, and validation results.

## A Repeating Workflow Pattern

Most SynthPopCan workflows follow the same pattern:

1. Inspect source files before transforming them.
1. Choose the columns and categories that matter for the research question.
1. Normalize control totals or export seed/training rows.
1. Check compatibility before fitting or generating.
1. Fit, generate, or package outputs.
1. Validate the result.
1. Keep the commands, mappings, reports, and notes together.

This pattern is intentionally conservative. It helps readers understand not only
what the tool produced, but what choices shaped the result.

The rest of the documentation follows this pattern. Use [Sources](sources.md)
and [Data](data.md) when you are still inspecting files, [Statistics Canada
Sources](statcan.md) and [Controls](controls.md) when you are preparing public
aggregate totals, [IPF](ipf.md) when you are fitting seed rows to controls,
[Tree Models](tree.md) when you are training or using conditional generation,
and [Validate](validate.md) when you are checking outputs. If you prefer Python
notebooks to command-line workflows, start with
[Getting Started With the Beginner API](library-getting-started.md).

## Further Reading

- Stanislav Borysov, Jeppe Rich, and Francisco Pereira,
  [Scalable Population Synthesis with Deep Generative Modeling](https://arxiv.org/abs/1808.06910).
- Floriana Gargiulo, Sonia Ternes, Sylvie Huet, and Guillaume Deffuant,
  [An iterative approach for generating statistically realistic populations of households](https://arxiv.org/abs/0912.2826).
- scikit-learn,
  [Decision Trees user guide](https://scikit-learn.org/stable/modules/tree.html).
- Pascal Jutras-Dube and co-authors,
  [Copula-based transferable models for synthetic population generation](https://arxiv.org/abs/2302.09193).
- Robin Lovelace and Dimitris Ballas,
  [Truncate, replicate, sample: a method for creating integer weights for spatial microsimulation](https://arxiv.org/abs/1303.5228).
