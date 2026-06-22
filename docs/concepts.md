# Core Concepts

This page explains the main ideas behind SynthPopCan in plain language. The goal
is not to teach every statistical detail. It is to make the command names,
intermediate files, and validation checks easier to understand.

## Synthetic Population

A synthetic population is a generated table of people, households, or other
units. The rows are not real individuals. They are constructed so that totals,
categories, and relationships look like a target population.

For example, a synthetic population for a small geography might preserve:

- age-group totals;
- sex totals;
- household-size totals;
- tenure or dwelling categories;
- links between generated households and generated people.

The exact quality of a synthetic population depends on the source data, the
control totals, the model, and the validation steps. SynthPopCan keeps these
pieces explicit so a researcher can review what happened.

## Seed Records

A seed file is the set of example records that a workflow starts from. In an IPF
workflow, the seed records are reweighted until their totals match the controls.

Seed records usually contain:

- an identifier column;
- one or more category columns such as `AGEGRP`, `SEX`, or `TENUR`;
- an optional source weight column;
- sometimes geography or household identifiers.

The seed is not just an input file. It defines what the fitted population can
represent. If a category is absent from the seed, IPF cannot use that category
later.

## Control Totals

Control totals are the targets a synthetic population should match. They are
often prepared from a Statistics Canada table or a local long-format CSV.

SynthPopCan uses a normalized long control format:

```text
margin,dimensions,AGEGRP,SEX,count
age,AGEGRP,adult,,100
age,AGEGRP,child,,100
sex,SEX,,F,100
sex,SEX,,M,100
```

The `dimensions` column says which seed column defines the margin. The `count`
column says the target total for that category.

## IPF

IPF stands for iterative proportional fitting. In SynthPopCan, IPF adjusts seed
record weights so the weighted totals match the control totals.

IPF is useful when:

- you have a seed file with the right columns;
- you have trustworthy control totals;
- the seed categories and control categories can be matched;
- you want compact fitted weights before deciding whether to expand full rows.

IPF is not useful when:

- the seed is missing the variable named by a control table;
- the control totals contradict each other;
- the seed has no examples for a required category;
- the research question needs a new attribute that has not been modelled,
  recoded, or added yet.

## Weights and Expanded Rows

SynthPopCan writes fitted weights by default because they are compact and
auditable. A weights file says how much each seed row counts in the fitted
population.

Expanded rows are useful for tools that expect one row per generated person or
household. They are larger and should usually be created after the fit has been
checked.

## Linked Household and Person Models

Some research questions need households and people to stay connected. For
example, a generated household with `household_size = 3` should have exactly
three linked generated people.

The linked tree workflow trains separate household and person models from a
hierarchical microdata file, then generates households first and people second.
Validation checks whether the links are consistent.

## Provenance

Provenance means keeping track of where an output came from:

- source file or table;
- selected columns;
- geography filters;
- random seed;
- model or command version;
- fit and validation reports.

For humanities and digital-humanities work, provenance is part of interpretation.
It lets another reader understand the choices behind a result.
