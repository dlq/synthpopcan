# Field Primer

This page is a broad introduction to the field around SynthPopCan. It is meant
to sit somewhere between a primer, a short methods essay, and a map of the
research area. You can use the command sections without reading it first, but it
explains why the commands are shaped the way they are.

## Why Synthetic Populations Exist

A synthetic population is a modelled population made of records that look like
people, households, families, dwellings, or other units. The records are not
supposed to be the original people. They are generated so that selected features
match a target population closely enough for a particular use.

This idea is useful because many research questions need row-shaped data:

- a simulation needs people in households;
- a teaching example needs realistic demographic variation;
- a digital-history project needs plausible household structure;
- a policy model needs units linked to geography;
- a software system needs test records that are not real people;
- a privacy-conscious workflow needs public outputs without distributing
  restricted microdata.

The danger is that a synthetic population looks more concrete than it is. A CSV
with one row per person can feel like evidence. It is better to read it as a
model: a disciplined argument about what a population could look like, given
source tables, microdata, category mappings, assumptions, random seeds, and
validation choices.

## A Short Lineage

Synthetic population work has roots in [spatial microsimulation](https://en.wikipedia.org/wiki/Spatial_microsimulation), transportation
planning, epidemiology, [statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control), and agent-based
simulation. Older IPF-based approaches often start with a microdata sample and
reweight it to match area-level margins.
[Pritchard and Miller's population synthesis work](https://doi.org/10.1007/s11116-011-9367-4)
is an important local reference for SynthPopCan because it treats many
categorical attributes sparsely and keeps household/person realization as a
separate stage after fitting.

More recent systems and papers broaden the field:

- [PopulationSim](https://activitysim.github.io/populationsim/) provides a
  production-grade Python reference for expanding household/person seed samples
  to match controls across geographies.
- [`synthpop`](https://www.synthpop.org.uk/resources.html) shows how tree-based
  models can synthesize tabular microdata while raising utility and
  disclosure-risk questions.
- Deep and hybrid population-synthesis work, such as
  [Borysov, Rich, and Pereira](https://arxiv.org/abs/1808.06910) and
  [Kim and Bansal](https://arxiv.org/abs/2208.01403), explores generative models
  for household/person relationships, geographic transfer, and structural-zero
  recovery.
- [Differential privacy work](https://csrc.nist.gov/pubs/sp/800/226/final)
  offers a formal way to reason about privacy loss, but it changes the modelling
  problem: one often measures noisy aggregates and synthesizes from those
  measurements rather than releasing raw trained models.

SynthPopCan's first design deliberately stays closer to explainable, auditable
methods: IPF, conditional-frequency models,
[CART-style tree models](https://scikit-learn.org/stable/modules/tree.html)
(Classification And Regression Trees — decision trees that recursively split
training data until each branch is relatively homogeneous),
constrained generation, validation, and provenance.

## What Makes Canadian Data Awkward

The Canadian case is not just "take a generic synthetic-population package and
point it at Statistics Canada." Several details matter.

Statistics Canada aggregate tables are not all shaped as ready-to-fit controls.
The [Census Profile](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/index.cfm?Lang=E)
is a long table of geographies and characteristics.
[WDS](https://www.statcan.gc.ca/en/developers/wds) tables have their own
dimensions, labels, value columns, metadata, and download formats. A table must
be inspected and normalized before it becomes a control table.

[PUMF microdata](https://www150.statcan.gc.ca/n1/pub/98m0002x/98m0002x2016001-eng.htm)
also has structure. The 2016 hierarchical PUMF is especially important because
it carries household, economic-family, census-family, and person identifiers. That makes it useful for household/person modelling, but it
also means that a person row is not the whole story. Household structure,
family relationships, and linked person composition are part of the model.

Finally, Canadian public tables may include rounding, suppression, sampling
notes, quality flags, different universes, and different geography levels. These
are not annoyances around the edge. They shape what a synthetic population can
honestly claim.

## Two Families of Methods

SynthPopCan currently separates two method families.

### IPF and Calibration

Iterative proportional fitting, often called IPF or raking, adjusts weights on a
seed table so that selected margins match target controls. The seed rows already
contain the variables. IPF changes how much each row counts.

This is powerful when the seed has the right columns and enough category
coverage. It is weak when the controls ask for things the seed cannot represent.
IPF cannot invent a missing variable, create a missing joint category, or fix
controls that describe incompatible populations.

```{figure} _static/ipf-diagram.svg
:alt: Three tables connected by arrows. The first table shows seed weights (4, 6, 3, 7) with row targets of 20 and 15 and column targets of 12 and 23 highlighted in blue. An arrow labelled IPF leads to the second table of fitted weights (5.9, 14.1, 6.1, 8.9) whose row and column sums match the targets exactly. A second arrow labelled integerize leads to the third table of integer counts (6, 14, 6, 9), with the fractional weights shown in small grey text. All margin totals are preserved.
:align: center

IPF adjusts the seed weights (left) until each row sum and column sum matches
the corresponding margin target (blue). The seed's proportional structure is
preserved; only the scale of each cell changes. The final step converts
fractional fitted weights into integer counts — a rounding decision that is
separate from the fitting itself, but one that must preserve the margin totals.
```

The most important conceptual distinction is between fitting and realization.
A weighted table is one object. An integer synthetic population is another. When
fractional weights are expanded into rows, a rounding or sampling decision has
been made.
[Lovelace and Ballas](https://arxiv.org/abs/1303.5228) discuss this problem
directly in the spatial microsimulation context.

### Tree-Based and Conditional Generation

Tree-based generation starts from training rows rather than a control table
alone. A decision tree asks branching questions about conditioning columns and
uses the observed outcomes in a group or leaf to generate target values. A
conditional-frequency model is even more direct: group by the conditioning
columns and sample target outcomes from that group.

Tree models are attractive because they can preserve richer combinations of
variables than simple margins. They can also support linked household/person
generation: generate household attributes first, then generate people inside
those households using shared conditions such as household size, tenure, or
geography.

```{figure} _static/tree-diagram.svg
:alt: A decision tree splitting first on Tenure (Owner / Renter) then on Household Size (1-2 / 3+). The four leaf nodes show observed dwelling-type frequency distributions (Apartment, Semi-detached, Single detached) with training-set counts.
:align: center

A conditional-frequency tree splits training rows by conditioning columns
(here Tenure then Household Size). Each leaf records the observed distribution
of the target variable (dwelling type). To generate a new record, walk the
tree using the row's known conditions and sample from the matching leaf.
```

Tree models do not remove the need for controls. A model can generate plausible
records and still fail local margins. For SynthPopCan, tree output is best read
as candidate records that may later need calibration, constrained sampling, or
repair against public controls.

## Why Forests Are Not the First Tool Here

A forest combines many trees, often improving predictive stability. Random
forests and gradient-boosted trees can be attractive when a single CART tree is
too unstable.

The tradeoff is interpretability. A single tree has leaves, supports, dominant
outcomes, and paths that can be inspected. A forest has many trees, aggregate
votes, and more complex internal evidence. For humanities and digital-humanities
readers, that difference matters. A forest may predict better while being harder
to explain, audit, or package as a public research artifact.

This does not mean forests are wrong. It means they should arrive with stronger
diagnostics: variable-importance reporting, out-of-domain checks, stability
tests, membership-risk thinking, and clear release rules.

## Structural Zeros and Sampling Zeros

One subtle idea appears again and again in synthetic-population work:
structural zeros are not the same as sampling zeros.

A structural zero is a combination that should not occur. A sampling zero is a
combination that could occur but was not observed in the seed or training data.
For example, "household size equals zero" is structurally impossible. A rare
age-language-tenure combination might be a sampling zero in a small geography.

IPF and tree models can both stumble here:

- IPF has no row to weight when a target cell is absent from the seed.
- A tree model may treat a missing combination as impossible because the
  training data never observed it.
- Deep generative models may recover some sampling-zero diversity, but they add
  their own interpretability and validation burdens.

For humanities work, this is not just a technical issue. It is a question about
what kind of absence the model is encoding.

## Privacy, Disclosure, and Model Artifacts

Synthetic data is not automatically private. A generated table can leak through
rare combinations, memorized rows, or highly distinctive linked households. A
trained model can also leak, even if it does not contain a raw CSV.

Tree models deserve special caution. A serialized tree can expose split
features, thresholds, leaf counts, class summaries, and rare paths. If a model
uses donor-style generation from terminal nodes, a small leaf can become too
close to the source records. If a whole model is distributed, white-box attacks
and membership-inference concerns become more relevant than they would be for a
closed internal service.

Linked household/person outputs raise the bar further. A household can be
distinctive because of the combination of dwelling attributes and person
composition, even when no single person-level field looks rare. Release checks
therefore need to consider household signatures, not just person rows one at a
time.

SynthPopCan's practical posture is conservative: working models stay private,
publishable-candidate models require audit evidence and provenance, and no
generated output should claim absolute anonymity. The detailed release rules
and what each check covers are in {doc}`tree`.

## Evaluation Is Not One Number

A synthetic population can be evaluated in several different ways. No single
metric is enough.

For IPF and calibrated outputs, check:

- absolute and relative margin error;
- worst controls and worst geographies;
- inconsistent margin totals;
- structural-zero and zero-cell diagnostics;
- extreme weights and effective diversity;
- integerization drift after expansion.

For tree-generated outputs, check:

- distribution similarity to training views;
- support and purity of groups or leaves;
- sensitivity to random seeds;
- rare generated combinations;
- out-of-domain conditions;
- household/person linkage;
- external controls, when available.

For all outputs, keep provenance: input files, source URLs, access status,
category mappings, commands, package version, random seeds, validation reports,
and notes about unresolved limitations.

## What Humanities Readers Can Bring

Humanities and digital-humanities readers often bring strengths that are
central to this work: attention to categories, sources, interpretation,
silences, provenance, and the politics of representation. Those are not
secondary concerns. They are the work.

Synthetic populations make choices visible:

- Which categories were preserved?
- Which identities were collapsed?
- Which geography became the unit of interpretation?
- Which source table was treated as authoritative?
- Which absences were interpreted as impossible?
- Which relationships were validated, and which were left unmeasured?

The aim is not to hide those choices behind a technical interface. The aim is
to make them explicit enough that readers can argue with them.

## Reading Map

Start with the command pages when you need to run a workflow:

- {doc}`which-workflow` when you know the task but not the right surface;
- {doc}`ipf` for margin-table calibration;
- {doc}`tree` for conditional and linked household/person generation;
- {doc}`controls` and {doc}`statcan` for preparing public aggregate sources;
- {doc}`validate` for checking generated artifacts.

Return to this primer when you need to explain what the output means, and use
{doc}`glossary` when a census, modelling, or software term needs a compact
definition.

## Tool Reference Map

This section maps field concepts to the current SynthPopCan documentation
surface. It is deliberately short; the command pages contain the actual
commands, options, examples, and troubleshooting.

- **Source visibility:** use {doc}`data` to check local data layout and inspect
  source-file shape before deciding whether a file belongs
  in a workflow.
- **Public aggregate tables:** use {doc}`statcan` to find, explain, and fetch
  Statistics Canada sources. The interpretive question is whether the table's
  dimensions, geography, year, and population universe fit the research
  question.
- **Control construction:** use {doc}`controls` when a source table needs to
  become a normalized margin or control CSV. This is where category mapping
  becomes explicit.
- **Seed and training rows:** use {doc}`microdata` when local microdata needs
  to become IPF seed rows or tree-training rows.
- **Calibration:** use {doc}`ipf` for the check, fit, report, validate pattern.
  IPF changes row weights; it does not invent unsupported categories.
- **Conditional generation:** use {doc}`tree` for tree-model training,
  generation, linked household/person workflows, and model-release review.
- **Validation:** use {doc}`validate` to keep explicit evidence beside each
  generated artifact. Validation is evidence, not a certificate.

## Further Reading

- ActivitySim,
  [PopulationSim documentation](https://activitysim.github.io/populationsim/),
  for a production-grade population synthesis workflow using seed samples and
  controls.
- Robin Lovelace and Dimitris Ballas,
  [Truncate, replicate, sample](https://arxiv.org/abs/1303.5228),
  for integerizing spatial microsimulation weights.
- Floriana Gargiulo, Sonia Ternes, Sylvie Huet, and Guillaume Deffuant,
  [An iterative approach for generating statistically realistic populations of households](https://arxiv.org/abs/0912.2826).
- The `synthpop` project,
  [resources and package documentation](https://www.synthpop.org.uk/resources.html),
  for tree-based synthetic microdata and disclosure-risk framing.
- scikit-learn,
  [Decision Trees user guide](https://scikit-learn.org/stable/modules/tree.html),
  for CART-style decision trees.
- Stanislav Borysov, Jeppe Rich, and Francisco Pereira,
  [Scalable Population Synthesis with Deep Generative Modeling](https://arxiv.org/abs/1808.06910),
  for a contrasting deep generative approach.
- Haewon Kim and Prateek Bansal,
  [A Deep Generative Model for Feasible and Diverse Population Synthesis](https://arxiv.org/abs/2208.01403),
  for structural-zero and sampling-zero concerns in newer models.
- Margaret Mitchell and co-authors,
  [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993),
  for documenting intended use, limitations, and evaluation.
- NIST,
  [SP 800-226: Guidelines for Evaluating Differential Privacy Guarantees](https://csrc.nist.gov/pubs/sp/800/226/final),
  for formal privacy-loss framing.
