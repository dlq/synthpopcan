# Glossary

This glossary explains terms that appear across SynthPopCan. It is written for
readers who may be comfortable with historical, social, or cultural sources but
new to synthetic population methods.

## Synthetic Population Terms

**Synthetic population**
: A generated table of people, households, dwellings, or other units. The rows
are not real people. They are modelled records designed to match selected
features of a target population.

**Synthetic household**
: A generated household row. In linked workflows, person rows point back to a
synthetic household identifier.

**Synthetic person**
: A generated person row. A synthetic person may carry individual attributes,
such as age group or sex, and household context inherited from their synthetic
household.

**Linked household/person output**
: Two generated tables that belong together: one household table and one person
table. Person rows include a household identifier so we can check that each
person belongs to a generated household.

**Seed records**
: Starting rows used by IPF. IPF changes how much each seed row counts; it does
not invent missing columns.

**Weight**
: A number saying how much a row counts. A row with weight `4.5` represents
four and a half units in a weighted table. We may later convert fractional
weights into integer rows.

**Expanded population**
: A table with one row per generated unit. Expanded files are often easier for
downstream tools to understand, but they can be much larger than weighted
files.

**Candidate rows**
: Plausible generated rows before final calibration or selection. In
small-area workflows, model packages generate candidate households and people;
calibration chooses which households are assigned to each target geography.

**Validation report**
: A structured report that checks generated output against controls or checks
whether linked household/person rows remain internally consistent.

**Provenance**
: Evidence about where data came from and how it was transformed: source files,
URLs, access restrictions, column mappings, command lines, random seeds,
software versions, and validation reports.

## Controls and IPF

**Control**
: A target total the generated or weighted population should match. Controls
usually come from public aggregate data, such as a Census Profile table.

**Control table**
: A normalized file of controls that SynthPopCan can read.

**Margin**
: One set of control totals. A sex margin might contain totals for women, men,
and other published categories. A joint age-by-sex margin contains totals for
each age and sex combination.

**Dimension**
: A column or category axis used by a control. In an age-by-sex margin, the
dimensions are age and sex.

**IPF**
: Iterative proportional fitting, also called raking. IPF repeatedly adjusts
row weights until weighted totals match selected margins as closely as
possible.

**Integerization**
: The step that turns fractional weights into whole counts or expanded rows.
This is separate from IPF fitting and can introduce small differences from the
fitted weighted totals.

**Structural zero**
: A category combination that should not exist, such as a household with zero
people.

**Sampling zero**
: A category combination that could exist but does not appear in the seed or
training sample. Sampling zeros are difficult because a model may mistake
absence in the sample for impossibility.

**Incompatible controls**
: Controls that cannot all be fitted together because they describe different
universes, use mismatched categories, or imply different totals.

## Model Terms

**Tree model**
: A model that splits training rows into groups and uses the observed outcomes
in those groups to generate new values.

**Decision tree**
: A tree made from repeated questions, such as "is tenure owner or renter?" and
"is household size one, two, or three or more?"

**CART**
: Classification And Regression Trees, a common family of decision-tree
methods.

**Conditional-frequency model**
: A simpler model that groups rows by conditioning columns and samples outcomes
from the observed frequencies in each group.

**Forest model**
: A model that combines many trees. Forests can be more stable for prediction,
but they are harder to explain as a single research artifact.

**Support**
: The amount of training data behind a group, branch, or leaf. Low support means
the model is relying on very few examples.

**Purity**
: How dominant one outcome is inside a group or leaf. High purity can be normal,
but high purity with low support can signal memorization or disclosure risk.

**Model package**
: A reviewed artifact that contains enough model information and metadata to
generate synthetic rows without redistributing raw microdata.

## Canadian Census Geography

**Province or territory**
: One of Canada's top-level political geographies, such as Quebec, Ontario, or
Nunavut.

**Census division (CD)**
: A regional geography between province/territory and municipality-like units.
Depending on the province, CDs may correspond to counties, regional districts,
regional county municipalities, or similar units.

**Census subdivision (CSD)**
: Usually a municipality or municipality-like unit: a city, town, village,
township, parish, reserve, or unorganized area.

**Census metropolitan area (CMA)**
: A large urban region organized around a major urban core and commuting zone.

**Census agglomeration (CA)**
: A smaller urban region organized around a smaller core population.

**Census tract (CT)**
: A relatively stable small urban geography, usually in CMAs and larger CAs.
CTs are useful for urban case studies but do not cover all of Canada.

**Aggregate dissemination area (ADA)**
: A grouping of dissemination areas. ADAs cover Canada and are often a useful
first wall-to-wall geography for province-wide or country-wide synthesis.

**Dissemination area (DA)**
: A small standard geography used for publishing census data. DAs cover Canada
and are finer than ADAs, but controls can become sparse.

**Dissemination block (DB)**
: The smallest standard census geography. DBs are best treated as a later
placement geography, not the first place to calibrate household composition.

**Target geography**
: The geography we are fitting or assigning output to, such as CT, ADA, or DA.

**Wall-to-wall coverage**
: Complete coverage of a province, territory, or country. CTs are not
wall-to-wall because they exist only in tracted urban areas; ADAs and DAs are
wall-to-wall.

## Statistics Canada and Source Terms

**Statistics Canada**
: Canada's national statistical agency and the source of many public aggregate
tables used by SynthPopCan.

**Census Profile**
: A large public census table that reports many characteristics for many
geographies. SynthPopCan can turn selected Census Profile rows into controls.

**WDS**
: Statistics Canada's Web Data Service, an API for finding and downloading
public data products and metadata.

**PUMF**
: Public Use Microdata File. A PUMF contains anonymized sampled records, but it
is still governed by documentation, access rules, and disclosure constraints.

**Hierarchical PUMF**
: A PUMF structure where household, family, and person records can be linked.
The 2016 hierarchical PUMF is important for linked household/person modelling.

**Universe**
: The population a table describes. Two tables can use similar categories but
still be incompatible if their universes differ.

**Suppression**
: A source-data protection practice where some cells are withheld or altered,
often because counts are too small or quality is too weak.

**Rounding**
: A public-data protection and presentation practice where counts are rounded.
Rounded controls may not add up exactly.

**Special code**
: A value such as "not applicable," "not available," "valid skip," or "not
stated." These codes should be decoded before being treated as ordinary
numeric values.

## Software Surfaces

**Local web app**
: A browser interface started with `synthpopcan serve`. It runs locally and is
meant for guided exploration, not public deployment.

**CLI**
: Command-line interface. The `synthpopcan` command is the main CLI.

**Beginner API**
: The small top-level Python API exposed as `import synthpopcan as spc`. It is
meant for notebooks, teaching examples, and short scripts.

**Advanced library**
: Lower-level Python modules for contributors and people building reusable
research tools.

**Read the Docs**
: The hosted documentation site for SynthPopCan:
<https://synthpopcan.readthedocs.io/>.
