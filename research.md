# SynthPopCan Research Notes

Date: 2026-06-21

## Purpose

This note synthesizes the local material currently in `~/Downloads` and recent external work relevant to a narrower near-term goal:

1. Build a Python library, CLI, and web app that can create a synthetic population through IPF from arbitrary Statistics Canada margin/control tables.
2. Build a second workflow that creates household- and person-level synthetic populations with a tree-based synthetic population generator for geographic subregions using Canadian 2016 Census data.
3. Leave broader SynthEco ecosystem enrichment, cohort attachment, and simulation work for later.

The main conclusion is that these should be treated as two related but distinct engines:

- A **general margin-table IPF engine** for arbitrary StatCan tables, where the user supplies or selects a margin table and the system constructs a fitted joint distribution against a seed sample or prior.
- A **2016 Census household/person engine** that uses the Canadian 2016 PUMF individual and hierarchical files, Census Profile controls, and geography-specific constraints. Tree models should generate realistic conditional household/person records, but they should be followed by calibration or constrained sampling so outputs match census controls.

## Local Material In Downloads

### Proposal And Product Intent

Relevant files:

- `/Users/dlq/Downloads/Proposal/CIHR Operating Research Grant 01.10.2018_PROPOSAL.pdf`
- `/Users/dlq/Downloads/Proposal/CIHR Operating Research Grant 01.10.2018_APPENDIX.pdf`
- `/Users/dlq/Downloads/Papers/SynthEco platform methods paper - 06 Aug 2020.docx`

The proposal describes SynthEco as a platform for creating, visualizing, and downloading "Synthetic Ecosystems": synthetic populations embedded in real geographic/environmental context. The near-term subset in this repo should focus only on the base population construction layer.

Important project requirements from the proposal/methods document:

- Use Python for the new toolkit.
- Ingest Statistics Canada census information in native formats as much as possible.
- Use Montreal as the exemplar geography.
- Produce households and persons with linking identifiers.
- Resolve geography at census tract level where possible.
- Make outputs usable outside the platform, preferably as CSV/Parquet tables plus metadata.
- Defer environmental components and cohort enrichment until the base synthetic population is solid.

The 2020 SynthEco methods draft is especially useful because it already translates the proposal into an implementation narrative:

- Base SE generation is a two-step process: census/built-environment base, then cohort/environment enhancement.
- Canadian inputs are described as Basic Summary Tables or profile-style aggregates plus PUMF microdata.
- IPF is used to fit disaggregate PUMF-like records to census tract controls.
- Pritchard and Miller's sparse list representation is explicitly called out as the memory-saving strategy.
- Canadian PUMF limitations are central: person and household samples are not always linked in the way US PUMS-style workflows assume.

### Pritchard Paper And Code

Relevant files:

- `/Users/dlq/Downloads/Papers/PritchardDissertation.pdf`
- `/Users/dlq/Downloads/Papers/Pritchard-Miller2012_Article_AdvancesInPopulationSynthesisF.pdf`
- `/Users/dlq/Downloads/Papers/drpritch_popsyn_200910/`

The Pritchard/Miller method is the strongest local algorithmic reference for the IPF side. Its core ideas are directly relevant:

- Use a sparse/list-based IPF rather than dense multidimensional arrays.
- Keep microdata records as rows with fitted expansion weights.
- Support many categorical attributes without materializing the full Cartesian product.
- Fit household and person controls simultaneously or in coordinated stages.
- Use conditional Monte Carlo allocation to turn fitted weights into integer household/person populations.

The code in `drpritch_popsyn_200910` is not a direct implementation target. It is old R code, tied to 1986 Ontario census data, RODBC, PostgreSQL/PostGIS, compiled `.so` helpers, and specific ILUTE/TTS geographies. It is still valuable as a reference design.

Key files:

- `synthesize.R`: first-stage IPF fitting.
- `synthesize2.R`: second-stage Monte Carlo allocation into dwellings, families, persons, and collective persons.
- `ipf_list.R`: sparse/list-based IPF.
- `IpfConstraint.R`: margin constraints with optional min/max tolerances.
- `pum86.R`: PUMF recoding and category collapsing.
- `censusTTS.R`: geography overlap allocation.
- `pop.sql`: merging multiple regional outputs with non-colliding IDs.

Design implications:

- Reimplement the algorithmic concepts in Python; do not port the R code line-for-line.
- Keep category recoding and margin definitions as explicit metadata, not as hardcoded procedural transformations.
- Preserve the two-phase distinction: fitting/calibration first, integer realization second.
- Expect geography-specific edge cases and suppressed/rounded controls.

### Canadian 2016 Census Data

Relevant root:

- `/Users/dlq/Downloads/Canadian 2016 Census`

Inventory observed locally:

- Census Profile Quebec CSD data:
  - `Census Profile Quebec/98-401-X2016065_English_CSV_data.csv`
  - about 2,887,395 data rows
  - 1,285 geographies
  - 1,135 distinct profile characteristics observed in the local file
- Montreal Census Tract profile subset:
  - `Census Tract Summaries 2016/98-401-X2016043_eng_CSV/98-401-X2016043_English_montreal.csv`
  - about 2,181,837 data rows
  - 971 geographies, including the Montreal CMA row plus 970 census tracts
  - same profile characteristic structure
- Flattened tract summary:
  - `Census Tract Summaries 2016/98-401-X2016043_eng_CSV/2016_SummaryTables_Flattened.csv`
  - 5,770 rows
  - 6,749 columns
- Individual PUMF:
  - `PUMF Census 2016/pumf-98M0001-E-2016-individuals/`
  - Montreal subset: `pumf-2016-Montreal-i.csv`, 108,580 rows, 141 columns
  - Quebec subset: `pumf-2016-Quebec-i.csv`, 215,042 rows, 141 columns
  - full individual file: `pumf-98M0001-E-2016-individuals_F1.csv`, 930,422 rows
- Hierarchical PUMF:
  - `PUMF Census 2016/pumf-98M0002-E-2016-hierarchical/`
  - `pumf-98M0002-E-2016-hierarchical_F1.csv`, 343,330 rows, 116 columns
  - includes `HH_ID`, `EF_ID`, `CF_ID`, and `PP_ID`, making it crucial for household/person relationship modeling.

The 2016 hierarchical PUMF should be treated as the first real household/person microdata input shape: a single person-row file with household, economic-family, census-family, and person identifiers. Separate household/person CSVs are useful as normalized outputs or small fixtures, but they should not be the assumed StatCan input shape.

The Census Profile CSVs are long tables. Each row is one geography-characteristic combination with total/male/female values. For general IPF, this is not automatically a ready-to-fit control table; the library needs a normalization step that maps profile rows to a small explicit control schema such as:

- geography id
- geography level
- characteristic id/name
- sex dimension if present
- value
- universe/denominator
- sample basis, quality flags, notes, and suppression markers

The PUMF files contain many coded variables. A serious implementation needs codebook-driven recoding before modeling. The local PUMF PDFs/documentation identify variables across demography, mobility, Indigenous population, ethnicity/visible minority, language, place of birth/immigration/citizenship, education, labour, commute, income, family composition, households, dwellings, geography, identifiers, and weights.

### Canadian 2011 Census And SPEW-Prepared Material

Relevant root:

- `/Users/dlq/Downloads/Canadian 2011 Census`

This appears to contain prior SPEW-oriented Montreal preprocessing:

- `MontrealFiles/counts_montreal.csv`
- `MontrealFiles/heir_montreal.csv`
- `MontrealFiles/montreal_pop_table.csv`
- `MontrealFiles/spew_files/pums/pums_h.csv`
- `MontrealFiles/spew_files/pums/pums_p.csv`
- Montreal shapefiles

This is useful as an example of how a finished data package can be organized, but the near-term target should use the 2016 Census files as the primary source.

### Derived GIS And Existing Synthetic-Looking Outputs

Relevant root:

- `/Users/dlq/Downloads/Derived GeoJSON GIS`

Useful observed files:

- `Montreal Census Tracts.geojson`: 970 features, aligning with the Montreal tract profile subset.
- `Canada Census Tracts.geojson`: 5,721 features.
- `Canada Census Subdivisions.geojson`: 5,162 features.
- `Canada Census Divisions.geojson`: 293 features.
- `Canada Census Metropolitan Areas.geojson`: 156 features.
- `SynthEco_MoNNET20200714.geojson`: 2,707 features.
- `syntheco_montreal.geojson`: 39,999 features with household/person-style fields such as `HH_ID`, `EF_ID`, `CF_ID`, `PP_ID`, and demographic variables.

These should not drive the first population synthesis engine, but they are valuable for:

- validating geography joins,
- designing output schemas,
- checking how previous SynthEco work represented people,
- later web-app map previews.

## Recent External Work, 2021-2026

### Production IPF And Calibration Tools

PopulationSim is the closest production-grade Python reference for an open population synthesis CLI. Its documentation frames population synthesis as expanding seed/reference samples to match marginal controls, producing household and person tables, and supporting controls at multiple geographic levels. It also notes limitations of simple IPF for simultaneous household/person fitting and describes entropy/list-balancing and integerization steps.

Sources:

- https://activitysim.github.io/populationsim/
- https://github.com/ActivitySim/populationsim

Relevance:

- Strong reference for CLI shape, configuration-driven workflows, validation summaries, and multi-geography controls.
- Less directly aligned with Canadian Census data quirks; designed mainly around US transportation planning inputs.
- Its current direction suggests the Python library should not expose only a black-box web workflow. It should also have reproducible config files.

Design implication:

- Use PopulationSim as a benchmark for user ergonomics: `synthpopcan run -c config -d data -o output`.
- Do not clone its model wholesale unless the Canadian PUMF/profile constraints fit cleanly. The Canadian household/person linkage problem and 2016 Census profile format justify a narrower custom core.

### Tree-Based Synthetic Microdata

The R `synthpop` package is the strongest reference for tree-based synthetic microdata. Its default synthesis method uses CART classification/regression trees, and its resources discuss utility, disclosure risk, and comparisons of tree-based methods including bagging and random forests.

Sources:

- https://www.synthpop.org.uk/
- https://www.synthpop.org.uk/get-started.html
- https://www.synthpop.org.uk/resources.html
- https://cran.r-project.org/web/packages/synthpop/synthpop.pdf

Relevance:

- Very relevant for the tree-based part of the proposed library.
- It targets synthetic versions of sensitive microdata, not geographically constrained full-population realization.
- Its sequential conditional modeling idea maps well to Canadian 2016 PUMF records: generate variables in an order, using previously generated variables as predictors.

Design implication:

- A Python tree engine should behave more like "conditional record generator plus calibration" than pure CART synthesis.
- Candidate methods:
  - CART/decision tree classifiers for categorical variables.
  - Random forests or gradient boosted trees when CART is too unstable.
  - Sequential conditional synthesis with explicit predictor matrices.
  - Rule constraints for impossible records.
  - Post-generation calibration against census margins.

Tree models alone will not guarantee tract-level margins. For this project they should be used to generate plausible records, then constrained by:

- IPF/raking weights,
- constrained sampling,
- integerization,
- or local repair to match margins.

### Privacy And Publishable Tabular Tree Models

For SynthPopCan, the privacy question is specifically about whether trained
tabular tree models can be distributed without leaking restricted Canadian
microdata. The short answer from the literature and guidance is: possibly, but
only after treating model artifacts as disclosure-risk objects in their own
right. A trained tree model is not automatically safe merely because it does not
look like a CSV of raw records.

Relevant work:

- `synthpop` is directly relevant because its CART synthesis method uses
  terminal tree nodes to draw synthetic values from observed donors in that
  node. Its documentation explicitly lists `minbucket`, the minimum number of
  observations in a terminal node, and notes that larger `minbucket` values can
  reduce disclosure risk. This maps closely to the proposed SynthPopCan
  publishable-model rule: no terminal leaf should be based on too few source
  records, and donor-based generation should not be publishable unless the donor
  mechanism itself is audited.
- scikit-learn tree artifacts expose split features, thresholds, node sample
  counts, weighted sample counts, impurity, and per-node class/value summaries.
  They normally do not store raw rows, but they can still encode rare paths and
  leaf summaries that reveal very small subgroups. The default parameters can
  grow unpruned trees unless `max_depth`, `min_samples_leaf`, `max_leaf_nodes`,
  or pruning controls are set deliberately.
- ICO guidance on AI and data protection identifies model inversion and
  membership inference as privacy attacks against trained models. It also makes
  an important distribution distinction: if a whole model is given to a third
  party, white-box attacks must be considered, and models that contain examples
  from training data by default should be treated as transfers of personal data.
- Membership inference remains an active risk for tabular synthetic data. Recent
  tabular studies show that attacks can identify whether records were used to
  train tabular synthesis models, with different attack signals working better
  for different architectures and datasets. One 2026 survey highlights
  "single-outs" or unique-signature records as especially vulnerable even when
  aggregate attack performance is mixed.
- Differentially private tabular synthesis is the strongest formal privacy
  direction, but it is not a free replacement for the first tree workflow. NIST
  SP 800-226 frames differential privacy as a way to quantify privacy loss, and
  NIST challenge work such as Private-PGM/MST shows a practical pattern:
  privately measure low-dimensional marginals, then synthesize from those noisy
  measurements. This is closer to a DP margin/IPF engine than to releasing a
  raw trained CART/random-forest model.
- Model cards provide a useful documentation pattern for publishable artifacts:
  every model package should include intended use, out-of-scope use, training
  source description, model type, parameters, evaluation results, limitations,
  and caveats. For SynthPopCan, privacy-audit results should be part of that
  model card rather than a separate optional note.

Design implications for SynthPopCan:

- Treat trained models as three possible release classes:
  - **Private working model**: trained from restricted microdata, may contain
    detailed trees, local encoders, diagnostics, and audit traces; not
    distributable.
  - **Audited publishable model**: contains only the allowed model
    representation, has no raw rows or source identifiers, satisfies minimum
    support and rare-combination checks, and ships with provenance plus a model
    card.
  - **DP or aggregate-trained model**: trained from public/open or
    differentially private aggregate measurements; preferred for broad public
    distribution once that machinery exists.
- For CART/random-forest style models, privacy checks should inspect the actual
  artifact, not only the training options. The audit should report minimum leaf
  support, number of leaves below threshold, deepest paths, highly pure leaves,
  rare target values, geography-specific leaves, and whether any serialized
  object contains source rows, row IDs, bootstrap indices, household IDs, or
  donor lists.
- Use conservative training defaults for any model that might later be
  packaged: non-trivial `min_samples_leaf`, maximum depth or maximum leaves,
  pruning, category coarsening, no KNN/SVM-style retained examples, and no
  donor lists in the exported artifact.
- Household/person linkage raises the bar. A linked household composition can
  be identifying even when each person-level field looks ordinary. Model audits
  should therefore check rare linked household signatures: household attributes
  plus ordered or summarized person composition, not just person rows one at a
  time.
- Geography should be part of the release policy. Canada-level and
  province-level models are the first plausible publishable targets. Smaller
  geographies should fail by default until support thresholds and rare-linked
  signature checks show that release risk is acceptable.
- The CLI should make this workflow explicit:

```bash
synthpopcan tree train ...
synthpopcan tree audit-model model.spcmodel --training-sample private.csv
synthpopcan tree package-model model.spcmodel --require-privacy-pass
```

The public-facing claim should be deliberately narrow: a publishable model has
passed SynthPopCan disclosure-risk checks and contains no intentionally stored
raw training rows. It should not claim absolute anonymity or legal privacy
safety, especially for restricted-source models.

Sources:

- synthpop resources and disclosure-risk publications:
  https://www.synthpop.org.uk/resources.html
- synthpop package documentation, especially `syn.ctree`, `syn.cart`, and
  `minbucket`: https://cran.r-project.org/web/packages/synthpop/synthpop.pdf
- scikit-learn `DecisionTreeClassifier` parameters:
  https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeClassifier.html
- scikit-learn tree structure internals:
  https://scikit-learn.org/stable/auto_examples/tree/plot_unveil_tree_structure.html
- scikit-learn `RandomForestClassifier` parameters:
  https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
- ICO guidance on model inversion, membership inference, and white-box model
  release:
  https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/guidance-on-ai-and-data-protection/how-should-we-assess-security-and-data-minimisation-in-ai/
- Shokri et al., "Membership Inference Attacks against Machine Learning
  Models" (2016): https://arxiv.org/abs/1610.05820
- Choquette-Choo et al., "Label-Only Membership Inference Attacks" (2020):
  https://arxiv.org/abs/2007.14321
- Hyeong et al., "An Empirical Study on the Membership Inference Attack against
  Tabular Data Synthesis Models" (2022): https://arxiv.org/abs/2208.08114
- Ward et al., "Ensembling Membership Inference Attacks Against Tabular
  Generative Models" (2025): https://arxiv.org/abs/2509.05350
- Pera et al., "SoK: Challenges in Tabular Membership Inference Attacks"
  (2026): https://arxiv.org/abs/2601.15874
- NIST SP 800-226, "Guidelines for Evaluating Differential Privacy Guarantees"
  (2025): https://csrc.nist.gov/pubs/sp/800/226/final
- McKenna et al., "Winning the NIST Contest: A scalable and general approach to
  differentially private synthetic data" (2021):
  https://arxiv.org/abs/2108.04978
- Mitchell et al., "Model Cards for Model Reporting" (2019):
  https://arxiv.org/abs/1810.03993

### Deep And Hybrid Population Synthesis

The last five years have seen active work on generative models for household/person population synthesis:

- Kim and Bansal, "A Deep Generative Model for Feasible and Diverse Population Synthesis" (2022), proposes GAN/VAE regularization to reduce structural zeros while recovering sampling zeros.
- Neekhra et al., "Synthpop++: A Hybrid Framework for Generating A Country-scale Synthetic Population" (2023), combines multiple surveys and maintains family structures, demographics, socioeconomic, health, and geolocation attributes.
- Qian et al., "A Deep Generative Framework for Joint Households and Individuals Population Synthesis" (2024), uses a VAE-style framework for household-individual and individual-individual relationships, with transfer learning and tract-level marginal alignment.
- Yang et al., "Deep and diverse population synthesis for multi-person households using generative models" (2025), uses generative models for multi-person household diversity and margin fit.
- Tulchinsky et al., "Generating geographically and economically realistic large-scale synthetic contact networks" (2024), starts with households from census data and then assigns schools/workplaces/contact networks.

Sources:

- https://arxiv.org/abs/2208.01403
- https://arxiv.org/abs/2304.12284
- https://arxiv.org/abs/2407.01643
- https://arxiv.org/abs/2508.09964
- https://arxiv.org/abs/2406.14698

Relevance:

- These papers confirm that household/person relationship modeling is the hard part.
- They also show that modern work is moving beyond pure IPF, especially for high-dimensional records and household member relationships.
- However, deep models are likely too much for the first version of a transparent StatCan-focused Python library.

Design implication:

- Keep the first release explainable and auditable: IPF, tree models, constrained sampling, and validation.
- Reserve deep generative models as a later plugin interface once the data normalization and validation layers exist.
- Borrow evaluation ideas: structural-zero checks, diversity/sampling-zero metrics, marginal fit, household relationship realism, and external benchmark validation.

### Wider SynthEco-Style Implementation Scan

A wider search for "SynthEco-style" work from roughly 2020-2026 did not turn up a direct modern equivalent of the original SynthEco proposal: a maintained open-source system that ingests Canadian census/PUMF data, generates household/person synthetic populations, attaches local environment/cohort layers, and exposes this as a reusable library, CLI, and web platform.

What does exist is a set of adjacent implementation families:

1. **SPEW remains the closest conceptual ancestor, but it is older.** SPEW is explicitly a synthetic ecosystems package and directly matches the language of the original SynthEco proposal. It is implemented as an R package, with a GitHub repository and CRAN-style installation, but the public GitHub release appears to date from 2017. It is still useful as a conceptual and packaging reference, especially for the distinction between agent generation, geographic regions, and environment components. It should not be treated as a current implementation base.

2. **SynthPops is a useful public-health contact-network generator, but not a census-table IPF toolkit.** SynthPops is a Python package for synthetic populations used in COVID-19 epidemic analyses. It creates populations with multilayer contact networks and includes household, school, workplace, and long-term-care-facility logic. The repository and documentation indicate that it is no longer actively maintained, but its module boundaries are instructive: separate concerns for data distributions, households, schools, workplaces, contact networks, and plotting. It is a useful design reference for later environment/contact layers, not a fit for the near-term Canadian IPF/table-ingestion core.

3. **Recent open contact-network work covers later SynthEco layers.** Tulchinsky et al. (2024) describe an open-source pipeline that first creates a household synthetic population from public census data, then assigns people to schools and workplaces and builds a contact network. This is close to the later "ecosystem" part of SynthEco: households plus schools/workplaces plus network edges. It is US-focused and appears more concerned with epidemic contact networks than reusable census ingestion, but it is a strong reference for the future stage where SynthPopCan assigns schools/workplaces and constructs interaction layers.

4. **BESSIE and FRED show how synthetic populations are consumed by simulators.** BESSIE is an open agent-based epidemic simulator that uses a synthetic population with demographic attributes, households, activities, and location visits. Recent FRED-related papers also use US census-derived synthetic populations as simulation baselines. These are not population-synthesis libraries, but they clarify downstream expectations: stable agent IDs, household IDs, location/activity tables, schedules or visit layers, and reproducible scenario comparisons.

5. **Starsim and Vivarium are relevant as simulation frameworks, not input-data builders.** Starsim is an actively maintained Python/R agent-based disease modeling framework with dynamic transmission networks, calibration support, and population/network abstractions. Vivarium is a Python microsimulation framework that has moved into a renamed suite. These frameworks reinforce the value of clean population-table boundaries and calibration hooks, but they do not replace the need for a Canadian census-specific population builder.

6. **pseudopeople is relevant for synthetic records and entity-resolution testing.** `pseudopeople` is a Python package for generating realistic simulated data about a fictional US population for record-linkage and data-science testing. It is not a geographic synthetic ecosystem builder, but it is a useful reminder that synthetic population outputs may be valuable beyond simulation: record linkage, privacy-preserving software tests, QA fixtures, and scalable algorithm testing.

Design implications for SynthPopCan:

- There is room for a Canadian-focused library; the search did not reveal an obvious maintained competitor that solves the same StatCan/PUMF problem.
- The first deliverable should stay focused on the hard missing piece: Canadian data ingestion, margin normalization, household/person synthesis, calibration, validation, and export.
- Later ecosystem layers should be modular rather than embedded in the core synthesis engine. Useful future modules are `schools`, `workplaces`, `healthcare`, `food_environment`, `road_network`, and `contacts`.
- Output schemas should anticipate downstream simulation consumers: stable person and household IDs, optional location/activity tables, deterministic run metadata, and validation artifacts.
- The web app should expose data mapping and validation first. Rich ecosystem/contact-network visualization can wait until the core population is reproducible.

Sources:

- SPEW paper: https://arxiv.org/abs/1701.02383
- SPEW GitHub: https://github.com/leerichardson/spew
- SynthPops GitHub: https://github.com/synthpops/synthpops
- SynthPops documentation: https://docs.idmod.org/projects/synthpops/en/latest/
- Open synthetic contact networks paper: https://arxiv.org/abs/2406.14698
- BESSIE paper: https://arxiv.org/abs/2203.11414
- FRED-related synthetic-population use: https://arxiv.org/abs/2307.12186
- FRED-related intervention modeling: https://arxiv.org/abs/2308.13040
- Starsim GitHub: https://github.com/starsimhub/starsim
- Starsim documentation: https://starsim.org/
- Vivarium GitHub: https://github.com/ihmeuw/vivarium
- pseudopeople GitHub: https://github.com/ihmeuw/pseudopeople

### Statistics Canada Data Access

Statistics Canada's Web Data Service (WDS) is the current official API for data and metadata released through Statistics Canada. It exposes metadata, vectors, cube/table downloads, and full-table CSV downloads.

Sources:

- https://www.statcan.gc.ca/en/developers/wds
- https://www.statcan.gc.ca/en/developers/wds/user-guide

Important WDS facts for this project:

- WDS is REST/JSON and intended for technical users.
- It supports metadata lookup and full table CSV download methods.
- It uses product IDs, cube/table metadata, coordinates, and vectors.
- It has request-rate limits and is not intended for huge point-by-point bulk extraction.

Design implication:

- The library should support both:
  - remote WDS/table-download ingestion for current StatCan tables,
  - local bulk CSV ingestion for downloaded 2016 Census files.
- "Any margin table on the StatCan site" should be interpreted as: any table that can be normalized into a declared control schema. Arbitrary tables may need user mapping because table dimensions, universes, notes, and geography columns differ.

## Proposed System Shape

### Python Library

Suggested package boundary:

```text
synthpopcan/
  data/
    statcan_wds.py
    census_profile.py
    pumf.py
    geography.py
  controls/
    schema.py
    normalize.py
    validate.py
  ipf/
    dense.py
    sparse_list.py
    integerize.py
  tree/
    sequence.py
    models.py
    constraints.py
    calibrate.py
  synth/
    household_person.py
    margin_only.py
  validation/
    margins.py
    household_structure.py
    structural_zeros.py
    reports.py
  io/
    metadata.py
    exports.py
```

Core abstractions:

- `ControlTable`: normalized margins/targets with dimensions, geography, value, flags, universe, source metadata.
- `SeedSample`: microdata rows, weights, variable metadata, and geography coverage.
- `FitResult`: fitted fractional weights or fitted joint distribution with diagnostics.
- `SyntheticPopulation`: realized person/household tables plus metadata and validation.
- `VariableSpec`: variable type, categories, missing/suppression codes, recodes, structural rules.
- `GeographySpec`: geography id, level, parent/child relationships, geometry path if available.

Storage choices:

- Use Parquet internally for large normalized tables.
- Use CSV for user-facing exports where requested.
- Use JSON/YAML for configs and metadata.
- Consider DuckDB or Polars for large local Census Profile scans; Pandas alone will work for prototypes but will become memory-heavy.

### CLI

Suggested commands:

```bash
synthpopcan statcan download --product-id ... --out data/raw
synthpopcan census normalize-profile --input ... --geo-level ct --out data/normalized
synthpopcan pumf normalize --input ... --dictionary ... --out data/normalized
synthpopcan ipf fit --controls controls.yaml --seed seed.parquet --out runs/run_id
synthpopcan synth realize --fit runs/run_id/fit.parquet --method integerize --out runs/run_id
synthpopcan tree train --config tree.yaml --pumf data/normalized/pumf.parquet --out models/tree
synthpopcan tree synthesize --model models/tree --controls controls.yaml --geo ... --out runs/run_id
synthpopcan validate --population runs/run_id --controls controls.yaml --out runs/run_id/report
```

The CLI should treat configs as first-class artifacts so every run is reproducible.

### Web App

The web app should not own the synthesis logic. It should orchestrate the library/CLI.

First useful web app scope:

- Upload/select StatCan CSV or WDS product.
- Preview inferred dimensions and geography.
- Map table dimensions into `ControlTable`.
- Select seed sample and variables.
- Run IPF or tree workflow.
- Show validation: margin error, geography coverage, impossible-record checks, household/person consistency.
- Download CSV/Parquet/metadata bundle.

Avoid in the first web version:

- cohort attachment,
- school/workplace assignment,
- interactive agent-level map rendering for millions of people,
- deep model training.

### Engine 1: General StatCan Margin-Table IPF

Inputs:

- StatCan table from WDS/full-table download or local CSV.
- User-selected dimensions to control.
- Optional seed sample; if none is supplied, the engine can fit a joint table but cannot create rich individual records beyond the table dimensions.
- Geography mapping.

Algorithm:

1. Normalize StatCan table to `ControlTable`.
2. Validate that selected controls share compatible universes.
3. Build seed/prior table from seed microdata or uniform/smoothed prior.
4. Run dense IPF for small low-dimensional problems; run sparse/list IPF for high-dimensional microdata.
5. Integerize fitted weights.
6. Sample or replicate records.
7. Validate all controlled margins.

Hard parts:

- StatCan tables often mix universes, notes, sex dimensions, percentages, totals, and suppressed values.
- IPF requires compatible margins. "Any table" is possible only after schema mapping and validation.
- Random rounding and suppression mean exact equality is not always the right target; tolerances matter.

Near-term implementation stance:

- Make arbitrary StatCan ingestion flexible, but require explicit config for any table that is not a known Census Profile shape.
- Provide strong diagnostics when margins are incompatible.

### Engine 2: 2016 Census Tree-Based Household/Person Synthesis

Inputs:

- 2016 individual PUMF.
- 2016 hierarchical PUMF.
- 2016 Census Profile controls for Montreal/Quebec.
- Census tract geographies.
- Variable recode/config specs.

Proposed model:

1. Normalize PUMF files and recode variables into analysis categories.
2. Train household-level sequential tree models from hierarchical PUMF:
   - household size,
   - dwelling type,
   - tenure,
   - household income,
   - family/economic-family structure,
   - other selected household variables.
3. Train person-level sequential tree models conditional on household variables and previously generated person variables:
   - age group,
   - sex,
   - marital/family status,
   - education,
   - labour force,
   - income,
   - language/immigration variables where supported.
4. For each target geography, generate candidate households/persons.
5. Calibrate candidate weights or sample candidates so controlled household and person margins match Census Profile controls.
6. Realize integer households and linked persons.
7. Validate household-person consistency and controlled margins.

Why tree models:

- They handle mixed categorical/numeric predictors.
- They capture nonlinear conditional relationships without requiring hand-written parametric models.
- CART-style models are easy to inspect.
- Ensembles improve quality but reduce interpretability.

Risks:

- Tree models can reproduce PUMF geography-level biases if trained only at coarse geography.
- They can generate plausible records that still fail local tract margins.
- They need explicit structural rules to avoid impossible household/person combinations.
- Some 2016 controls are profile rows, percentages, or long-form sample estimates rather than direct count controls.

Recommendation:

- Start with a small controlled variable set:
  - household: household size, dwelling type, tenure, household income band if reliable.
  - person: age group, sex, family/marital status, labour force status, education band.
- Validate on Montreal tracts.
- Add variables only after margin fit and household consistency are stable.

## Validation Requirements

Every run should emit machine-readable and human-readable validation:

- Total population and households by geography.
- Absolute and relative margin error by control.
- Worst controls and worst geographies.
- Household size distribution.
- Person count per household sanity checks.
- Family/person role consistency checks.
- Structural-zero checks.
- Seed coverage and zero-cell diagnostics.
- Suppression/rounding notes.
- Random seed and reproducibility metadata.

Minimum acceptance criteria for a first serious run:

- Controlled margins match within explicit tolerance.
- No orphaned persons or households.
- Household size equals linked person count, unless a documented collective/non-private household path exists.
- All output records carry source/run metadata.

## Recommended Near-Term Roadmap

### Phase 1: Data Normalization

- Create normalized readers for 2016 Census Profile long CSV.
- Create normalized readers for 2016 individual and hierarchical PUMF.
- Create codebook/recode metadata for a small first variable set.
- Join Montreal tract controls to `Montreal Census Tracts.geojson` IDs.

### Phase 2: General IPF Prototype

- Implement dense IPF for small margin tables.
- Implement sparse/list IPF for PUMF rows.
- Add integerization and reproducible sampling.
- Add validation reports.

### Phase 3: 2016 Household/Person Prototype

- Build a household/person output schema.
- Train a basic CART/random-forest sequential generator on hierarchical PUMF.
- Constrain/calibrate generated records to selected tract controls.
- Validate Montreal tract outputs.

### Phase 4: CLI And Reproducibility

- Add config-driven CLI commands.
- Store outputs under run directories.
- Emit metadata and validation summaries.

### Phase 5: Web App

- Build a thin orchestration app around existing library commands.
- Prioritize control-table mapping, run management, validation viewing, and downloads.

## Open Questions

- Which exact first geography should be targeted: Montreal CMA, city of Montreal, all Montreal tracts, or selected pilot tracts?
- Should the first output represent private households only, or also collective/non-private populations?
- Which variables are mandatory for the first useful population?
- Should the first tree engine use decision trees for interpretability or random forests/gradient boosting for quality?
- How much exact margin fit is required given Census random rounding and suppression?
- Should the first web app run locally only, or be deployable for remote users?

## Source List

Local sources:

- `/Users/dlq/Downloads/Proposal/CIHR Operating Research Grant 01.10.2018_PROPOSAL.pdf`
- `/Users/dlq/Downloads/Proposal/CIHR Operating Research Grant 01.10.2018_APPENDIX.pdf`
- `/Users/dlq/Downloads/Papers/SynthEco platform methods paper - 06 Aug 2020.docx`
- `/Users/dlq/Downloads/Papers/PritchardDissertation.pdf`
- `/Users/dlq/Downloads/Papers/Pritchard-Miller2012_Article_AdvancesInPopulationSynthesisF.pdf`
- `/Users/dlq/Downloads/Papers/drpritch_popsyn_200910/`
- `/Users/dlq/Downloads/Canadian 2016 Census/`
- `/Users/dlq/Downloads/Canadian 2011 Census/`
- `/Users/dlq/Downloads/Derived GeoJSON GIS/`

External sources checked:

- PopulationSim documentation: https://activitysim.github.io/populationsim/
- PopulationSim GitHub: https://github.com/ActivitySim/populationsim
- Statistics Canada WDS: https://www.statcan.gc.ca/en/developers/wds
- Statistics Canada WDS user guide: https://www.statcan.gc.ca/en/developers/wds/user-guide
- synthpop package site: https://www.synthpop.org.uk/
- synthpop get started: https://www.synthpop.org.uk/get-started.html
- synthpop resources: https://www.synthpop.org.uk/resources.html
- synthpop CRAN manual: https://cran.r-project.org/web/packages/synthpop/synthpop.pdf
- Kim and Bansal, 2022: https://arxiv.org/abs/2208.01403
- Neekhra et al., 2023: https://arxiv.org/abs/2304.12284
- Qian et al., 2024: https://arxiv.org/abs/2407.01643
- Tulchinsky et al., 2024: https://arxiv.org/abs/2406.14698
- Yang et al., 2025: https://arxiv.org/abs/2508.09964
- SPEW GitHub: https://github.com/leerichardson/spew
- SynthPops GitHub: https://github.com/synthpops/synthpops
- SynthPops documentation: https://docs.idmod.org/projects/synthpops/en/latest/
- BESSIE paper: https://arxiv.org/abs/2203.11414
- FRED-related synthetic-population use: https://arxiv.org/abs/2307.12186
- FRED-related intervention modeling: https://arxiv.org/abs/2308.13040
- Starsim GitHub: https://github.com/starsimhub/starsim
- Starsim documentation: https://starsim.org/
- Vivarium GitHub: https://github.com/ihmeuw/vivarium
- pseudopeople GitHub: https://github.com/ihmeuw/pseudopeople
