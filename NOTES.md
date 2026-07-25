# SynthPopCan Research Notes

Date: 2026-06-21

## Purpose

This note synthesizes project source material reviewed locally, along with
recent external work relevant to a narrower near-term goal:

1. Build a Python library, CLI, and web app that can create a synthetic population through IPF from arbitrary Statistics Canada margin/control tables.
1. Build a second workflow that creates household- and person-level synthetic
   populations with a tree-based synthetic population generator for geographic
   subregions using explicit Canadian 2016 and 2021 Census source profiles.
1. Leave broader SynthEco ecosystem enrichment, cohort attachment, and simulation work for later.

Current codebase status, 2026-07-25:

- The active roadmap is now `PLANS.md`; this file is the research and design
  notes companion.
- The Python library, Click CLI, durable FastAPI/Uvicorn local web app, Sphinx
  docs, and correctness suite are implemented; the current release is v0.6.2.
- IPF from normalized controls, StatCan WDS source discovery/normalization,
  microdata adapters, linked household/person model generation, validation,
  prepared-model generation, and small-area linked synthesis all share working
  Python-backed CLI, library, or local-web surfaces as appropriate.
- The small-area linked synthesis MVP can assign linked
  household/person candidates to census tracts and aggregate dissemination
  areas using Census Profile controls. The 33-entry prepared-model catalogue
  contains a fictional demo plus parallel 2016 and 2021 packages for Canada,
  nine provinces, five PUMF-coded CMAs, and minimal Prince Edward Island
  packages; territorial and broader CMA packages remain open work.
- Small-area fitting can optionally refine household weights against linked
  person controls while preserving whole-household assignment, with diagnostics
  that separate fractional fit from integerized residuals.
- The local web app guides durable backend IPF, prepared-model, and small-area
  runs with streamed uploads, progress, cancellation, recovery, bounded
  previews, and CLI reproduction metadata. Large results remain on disk rather
  than being loaded into browser memory. Exact executable reproduction of
  every small-area condition and optional map remains `0.6.3` work.
- The linked household/person/geography output contract is versioned, explicit
  2016 and 2021 PUMF adapters and prepared models are available, and releases
  and model packages have citation metadata and archival DOIs.
- The older phase sketch near the end of this file should be read as research
  background, not the live implementation checklist.

Research questions tracked by this note:

- Keep the source-access and correction notes for 2016 and 2021 Canadian
  census/public-use microdata current, and research later vintages before
  implementing them so adapters follow documented product differences rather
  than assumptions carried forward from either supported year.
- Add Canadian disclosure-control and dissemination guidance to the privacy
  section before calling any restricted-source model package publicly
  publishable. The current notes cover model privacy literature, but the release
  policy should also cite the relevant Canadian/StatCan disclosure context.
- Add a focused note on calibration controls for generated household/person
  model outputs: which StatCan tables are appropriate, which universes must not
  be mixed, and when a control implies an enrichment step rather than IPF.
- Keep watching for maintained population- and tabular-synthesis
  implementations that could improve correctness, performance, or
  interoperability. The browser is now a guided client over shared Python
  workflows, so a browser-side implementation would need a concrete benefit
  and parity evidence rather than being an architectural goal by itself.
- Evaluate the Prédhumeau-Manley national Canadian dataset as an external
  schema, validation, and performance benchmark. Do not make its 9.6 GB archive
  a default download or silently treat its generated records as observed truth.

Recent research findings, 2026-06-24:

- Statistics Canada now lists 2021 Census PUMFs in the same public catalogue
  family as earlier Census PUMFs. The catalogue page lists 2021 individuals and
  hierarchical files, 2016 individuals and hierarchical files, 2011 NHS files,
  and older 2006/2001/1996/1991 files. It also says PUMFs are distributed as
  CSV or TXT plus documentation such as user guides, codebooks, layout cards, or
  syntax files. This reinforces the adapter strategy: do not bake the 2016
  hierarchical columns into the generic microdata layer; treat each year/product
  as a documented source profile.
- The 2021 individuals PUMF page says the file is a 2.7% anonymous-response
  sample with 144 variables, restricted geography at provinces/territories and
  metropolitan areas, and both ASCII and CSV data plus SAS/SPSS/Stata source
  code. It also has a correction notice for the `IMMCAT5` metadata labels. The
  implemented 2021 adapter and prepared-model provenance therefore treat the
  corrected v2 product as a distinct source and do not assume metadata labels
  are immutable.
- The 2021 hierarchical PUMF is listed as released after the 2021 individuals
  file, and the main PUMF page has a correction notice for `STIR_GRP` in the
  hierarchical file. That is a practical warning for SynthPopCan: model
  packages should record both data product IDs and correction dates, not just
  "2021 Census".
- Statistics Canada's Census Dictionary is the authoritative place for census
  concepts, variables, geography terms, and comparability between census years.
  Adapter profiles should link to the relevant dictionary/reference guide and
  should keep recodes explicit rather than relying only on column names.
- The Statistics Act makes the confidentiality rule explicit: information
  obtained under the Act must not be disclosed in a way that can be related to
  an identifiable person, business, or organization. For SynthPopCan, this
  supports a conservative release claim: a package may pass project
  disclosure-risk checks, but it should not claim legal anonymization or
  Statistics Canada endorsement.
- The Statistics Canada Open Licence permits use and value-added products, but
  it prohibits using the information to try to identify an individual, and it
  prohibits presenting outputs as if they reveal confidential Statistics Canada
  information. Public model packages and generated outputs should therefore
  include source acknowledgment, no-endorsement language, and a statement that
  outputs are SynthPopCan-derived synthetic artifacts.
- Recent work on 2021 Census random rounding argues that some hierarchical
  published counts can be partially or exactly "unrounded." Even if that paper
  is not official guidance, it is directly relevant to calibration controls:
  SynthPopCan should not treat rounded/suppressed/public table cells as if they
  are exact confidential truth, and should avoid combining many overlapping
  rounded tables in a way that invites reconstruction claims.
- Browser-first Python is technically plausible. Pyodide's
  built package list currently includes relevant scientific packages such as
  NumPy, pandas, Polars, SciPy, scikit-learn, PyArrow, DuckDB, and XGBoost. That
  does not make full model training in-browser a good default. SynthPopCan has
  since selected durable Python backend workflows and removed the duplicate
  JavaScript synthesis tier; revisit Pyodide only for a concrete offline or
  distribution use case, measured against the shared backend contract.

Sources for this follow-up:

- Statistics Canada PUMF catalogue: https://www150.statcan.gc.ca/n1/pub/98m0001x/index-eng.htm
- Statistics Canada PUMF product family: https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X
- 2021 individuals PUMF: https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X2021001
- 2016 hierarchical PUMF catalogue family: https://www150.statcan.gc.ca/n1/en/catalogue/98M0002X
- 2021 Census Dictionary: https://www12.statcan.gc.ca/census-recensement/2021/ref/dict/index-eng.cfm
- Statistics Act: https://laws-lois.justice.gc.ca/eng/acts/S-19/FullText.html
- Statistics Canada Open Licence: https://www.statcan.gc.ca/en/terms-conditions/open-licence
- West, Vecna, and Chowdhury, "Random (Un)rounding" (2023): https://arxiv.org/abs/2307.13859
- Pyodide built packages: https://pyodide.org/en/stable/usage/packages-in-pyodide.html

The main conclusion is that these should be treated as two related but distinct engines:

- A **general margin-table IPF engine** for arbitrary StatCan tables, where the user supplies or selects a margin table and the system constructs a fitted joint distribution against a seed sample or prior.
- A **census-vintage household/person engine** with explicit 2016 and 2021 PUMF
  adapters, Census Profile controls, and geography-specific constraints. Tree
  models generate plausible conditional household/person records and can be
  followed by calibration or constrained sampling so compatible outputs match
  selected census controls.

## Local Source Material Reviewed

### Proposal And Product Intent

Reviewed source-bundle entries:

- `Proposal/CIHR Operating Research Grant 01.10.2018_PROPOSAL.pdf`
- `Proposal/CIHR Operating Research Grant 01.10.2018_APPENDIX.pdf`
- `Papers/SynthEco platform methods paper - 06 Aug 2020.docx`

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

### Canadian Food Environment Dataset

Statistics Canada's Canadian Food Environment Dataset (Can-FED) is a
first-class public source for the later SynthEco enrichment stage:

- Canonical product page: https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012022001-eng.htm
- It provides pan-Canadian retail food-environment measures at dissemination-area level.
- Its intended uses include studying relationships between local food environments, dietary intake, and health outcomes, which directly matches the project's public-health purpose.
- The public measures are based on 2018 food-outlet data; all derived layers and analyses must preserve that vintage and must not imply current establishment availability.
- The public DA-level product must remain distinguishable from more detailed material available under controlled access through Statistics Canada Research Data Centres.
- A supported Can-FED layer should document outlet categories, access metrics, geography linkage, missingness, provenance, and uncertainty before comparing access across synthetic population groups.

### Pritchard Paper And Code

Reviewed source-bundle entries:

- `Papers/PritchardDissertation.pdf`
- `Papers/Pritchard-Miller2012_Article_AdvancesInPopulationSynthesisF.pdf`
- `Papers/drpritch_popsyn_200910/`

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

Canonical local roots:

- national PUMFs: `data/raw/statcan/census/2016/pumf/`
- PUMF metadata: `data/raw/statcan/census/2016/metadata/pumf/`
- Census Profiles: `data/raw/statcan/census/2016/profiles/`
- CT/ADA/CSD boundaries: `data/derived/statcan/census/2016/boundaries/`
- regional subsets/intermediates: `data/derived/statcan/census/2016/`

The converted CT and ADA GeoJSON files replace their source shapefile
components locally. An unused exploratory 2016 FSA boundary download was
removed; postal geography can be fetched again if it becomes a requirement.

Inventory observed locally:

- National Census Profile through CSD level:
  - `data/raw/statcan/census/2016/profiles/csd/national/2016-census-profile-csd-all.csv`
  - 12,288,843 data rows across province, census-division, and CSD records
  - 5,162 national CSD boundaries; 4,552 CSDs have complete household-size and
    tenure controls in the current extractor
- Montreal Census Tract profile subset:
  - `data/derived/statcan/census/2016/profiles/ct/98-401-X2016043_English_montreal.csv`
  - about 2,181,837 data rows
  - 971 geographies, including the Montreal CMA row plus 970 census tracts
  - same profile characteristic structure
- Flattened tract summary:
  - `data/derived/statcan/census/2016/profiles/ct/2016_SummaryTables_Flattened.csv`
  - 5,770 rows
  - 6,749 columns
- Individual PUMF:
  - `data/raw/statcan/census/2016/pumf/individual/`
  - Montreal subset: `data/derived/statcan/census/2016/pumf/individual/subsets/pumf-2016-Montreal-i.csv`, 108,580 rows, 141 columns
  - Quebec subset: `data/derived/statcan/census/2016/pumf/individual/subsets/pumf-2016-Quebec-i.csv`, 215,042 rows, 141 columns
  - full individual file: `data_donnees_2016_ind.csv`, 930,421 data records
- Hierarchical PUMF:
  - `data/raw/statcan/census/2016/pumf/hierarchical/`
  - `data_donnees_2016_hier.csv`, 343,330 rows, 116 columns
  - includes `HH_ID`, `EF_ID`, `CF_ID`, and `PP_ID`, making it crucial for household/person relationship modeling.

The 2016 and 2021 hierarchical PUMFs are the supported real
household/person microdata input shapes: person-row files with household,
economic-family, census-family, and person identifiers, interpreted through
separate vintage-specific adapters. Separate household/person CSVs are useful
as normalized outputs or small fixtures, but they should not be assumed to be
the native Statistics Canada input shape.

### Local 2021 Census Data

The 2021 raw cache is intentionally an inventory of acquired products rather
than a mirror of the 2016 directory. Both years have hierarchical and
individual PUMFs plus their codebooks. Both caches now have matching CT, ADA,
and national CSD Census Profile coverage. The 2021 cache additionally has the
national Dissemination Geographies Relationship File, which relates DGUIDs
across geographic levels.

Canonical local 2021 roots:

- national PUMFs: `data/raw/statcan/census/2021/pumf/`
- PUMF metadata: `data/raw/statcan/census/2021/metadata/pumf/`
- Census Profiles: `data/raw/statcan/census/2021/profiles/`
- geography relationships: `data/raw/statcan/census/2021/geography/relationships/`
- prepared CT/ADA/CSD boundaries: `data/derived/statcan/census/2021/boundaries/`

The national 2021 through-CSD profile contains 14,386,308 rows. Its 4,554 CSDs
with requested controls all join to the 5,161-feature boundary file; 4,517 have
complete household-size and tenure controls. Boundary-only CSDs should not be
treated as join failures: empty geographies, suppression, and unavailable
characteristics can prevent a complete control vector.

Consult each vintage's `manifest.json` for the products actually present. Do
not infer column compatibility from directory symmetry. The 2021 profiles use
DGUIDs, `CHARACTERISTIC_ID`, and separate count/rate fields, while the 2016
profiles use member-ID columns and sex-total fields. The small-area reader has
explicit mappings for both vintages. A file previously labelled as a 2016
DA-all profile was removed after its own header identified it as a Designated
Places profile; future controls must use a verified DA product.

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

Reviewed source-bundle root:

- `Canadian 2011 Census/`

This appears to contain prior SPEW-oriented Montreal preprocessing:

- `MontrealFiles/counts_montreal.csv`
- `MontrealFiles/heir_montreal.csv`
- `MontrealFiles/montreal_pop_table.csv`
- `MontrealFiles/spew_files/pums/pums_h.csv`
- `MontrealFiles/spew_files/pums/pums_p.csv`
- Montreal shapefiles

This is useful as an example of how a finished data package can be organized, but the near-term target should use the 2016 Census files as the primary source.

### Derived GIS And Existing Synthetic-Looking Outputs

Reviewed source-bundle root:

- `Derived GeoJSON GIS/`

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

### A National DA-Level Synthetic Population For Canada

Prédhumeau and Manley (2023) provide the most directly comparable public
Canadian result found so far: a national synthetic population of people linked
to households, localized at the dissemination-area level. The paper is a
*Scientific Data* data descriptor, the versioned 2.1.0 dataset is archived on
Zenodo under CC BY 4.0, and the generation code has its own Zenodo archive.

Sources:

- Paper: https://doi.org/10.1038/s41597-023-02030-4
- Dataset v2.1.0: https://doi.org/10.5281/zenodo.7572117
- Generation code v2.0.0: https://doi.org/10.5281/zenodo.7569219

Published artifact:

- The dataset archive is 9.6 GB and contains 364 CSV files in 13
  province/territory folders.
- It includes a 2016 base population and nine projection scenarios for 2021,
  2023, and 2030.
- Each person row includes a household ID, sex, primary-household-maintainer
  status, age group and age, DA code, education, labour-force status, household
  size, income, and inferred household type.
- The authors describe extraction by geographic hierarchy and downstream use
  for agent-based modelling, policy scenarios, local-data enrichment, and
  placement into residential geography.

Method:

1. Build a 2016 base population province by province and DA by DA from the
   weighted Individual PUMF and Census Profile marginals.
1. Use QISI, combining IPF with Quasirandom Integer Sampling, to generate whole
   people while retaining the selected margins.
1. Reconcile source categories and DA subtotals before fitting. The workflow
   adjusts rounded or missing subtotals to the DA population and assigns ages
   0-14 to broad education, labour-force, and income categories so those
   variable totals cover the same population.
1. Project the 2016 population to later years by province, scenario, age, and
   sex, duplicating or deleting sampled people within age-sex groups.
1. Create households around people identified as primary maintainers, complete
   them using household-size and broad age information, and infer one of five
   simplified household types from household size and member ages.

Validation findings:

- The 2021 projection is compared with the 2021 Census at DA, city, and national
  levels using Pearson correlation, normalized RMSE, and relative absolute
  error, as well as an exact-PUMF-combination plausibility check.
- For almost all evaluated DA categories, the paper reports correlation above
  0.9 and normalized RMSE below 1%. Half of DAs are within 9% relative absolute
  error and 75% are within 14.55%, according to the paper's summary.
- The national comparison reports that 95.7% of synthetic people have an
  attribute combination exactly observed in the 2016 Individual PUMF. This is
  evidence that the generated combinations are donor-like; it is not an
  independent test of household linkage, local historical truth, or novelty.
- Rare older age groups, income below $20,000, households with five or more
  people, one-parent families, and the residual household-type category are
  less reliable at DA level.
- Large local errors can reflect land-use and institutional change between
  censuses. The paper discusses a student-housing DA where 2016 counts,
  projected 2021 counts, and observed 2021 dwelling counts differ sharply.
- Income is carried forward from 2016 without a salary update, so age-sex
  projection does not make every attribute current. The authors similarly note
  changing education patterns and increasing uncertainty for longer horizons.
- Household construction is explicitly approximate. Some people may retain
  `HID=-1`, and simplified household-type rules do not fully represent shared
  accommodation, complex families, large age-gap couples, institutions, or
  relationships among all members.

Implications for SynthPopCan:

- **Geographic architecture:** this is strong evidence that province-batched,
  DA-level national synthesis is a practical architecture. A country-wide run
  should be an orchestrated collection of small-area fits with restartable
  artifacts and aggregate diagnostics, not one monolithic fit.
- **Control semantics:** category harmonization and total reconciliation need
  provenance. SynthPopCan should report when it broadens a category, borrows a
  provincial distribution, changes a subtotal, or changes the represented
  population universe; it should not silently reproduce another study's
  under-15 recodes.
- **Zero cells:** assigning a small probability to empty seed states is a useful
  sampling-zero strategy but can violate a structural zero. Any comparable
  support-repair feature needs an explicit policy, audit trail, and validation.
- **Integer realization:** QISI is a relevant comparison for SynthPopCan's
  deterministic systematic integerization. Benchmark total and margin
  residuals, reproducibility, runtime, memory, and sparse-candidate behaviour
  before considering an alternative backend.
- **Household modelling:** person-first heuristic household assignment provides
  a useful contrast with SynthPopCan's linked-candidate approach. Benchmark
  unassigned people, household-size fit, inferred type fit, age relationships,
  and rare household signatures rather than comparing person margins alone.
- **Projection:** future-year support should separate demographic projection
  from local spatial redistribution and attribute updating. Age-sex totals at
  province level do not establish current DA geography, income, education,
  housing, or institutional composition.
- **Validation:** add multi-scale summaries and relative-error distributions,
  but do not reduce quality to one correlation. Rare-category, household-link,
  integerized-residual, structural-zero, temporal-drift, and geography-change
  checks remain necessary.
- **Interoperability:** evaluate a metadata-first reader or schema crosswalk for
  the published CSV columns and DA identifiers. Any full-data benchmark should
  be opt-in, cached outside git, checksum-verified, and attributed under CC BY
  4.0.

This work narrows an earlier research claim in these notes: there *is* a recent,
open, national Canadian synthetic-population dataset and generation workflow.
The remaining gap is not simply national coverage. SynthPopCan's distinctive
work is an inspectable general-purpose toolchain, explicit 2016/2021 source
profiles, linked-candidate generation, control and provenance diagnostics,
CLI/library/web parity, and reproducible user-owned workflows.

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

- Use PopulationSim as a benchmark for future configuration-driven ergonomics. A possible later command shape would be `synthpopcan run -c config -d data -o output`; this is not part of the current CLI.
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

- UNECE's *Synthetic Data for Official Statistics: A Starter Guide*
  (ECE/CES/STAT/2022/6), developed with substantial Statistics Canada
  authorship, is an authoritative reference for release use cases, synthesis
  methods, disclosure-risk assessment, and utility evaluation. It distinguishes
  dummy, fully synthetic, and partially synthetic files; emphasizes that
  utility is specific to an intended analytical use; and treats utility and
  disclosure risk as a joint, context-dependent assessment rather than a claim
  of zero risk. For SynthPopCan, this guidance applies most directly to
  tree-model releases, restricted-source or cohort enrichment, and public
  output review. It complements but does not establish numerical correctness of
  the IPF, calibration, sampling, or linked-population algorithms.
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
- The current CLI makes this workflow explicit with audit and packaging gates:

```bash
synthpopcan models build train training.csv \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --out person-model.json

synthpopcan models build audit person-model.json \
  --min-support 50 \
  --max-purity 0.95

synthpopcan models build prepare-release person-model.json \
  --out person-model-publishable.json \
  --manifest-out person-model-release.manifest.json \
  --review-note "Reviewed for minimum support, purity, and raw-row metadata."
```

The public-facing claim should be deliberately narrow: a publishable model has
passed SynthPopCan disclosure-risk checks and contains no intentionally stored
raw training rows. It should not claim absolute anonymity or legal privacy
safety, especially for restricted-source models.

Sources:

- UNECE, *Synthetic Data for Official Statistics: A Starter Guide*
  (ECE/CES/STAT/2022/6):
  https://unece.org/statistics/publications/synthetic-data-official-statistics-starter-guide
- UN Digital Library record and stable publication metadata:
  https://digitallibrary.un.org/record/4027270
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

1. **SynthPops is a useful public-health contact-network generator, but not a census-table IPF toolkit.** SynthPops is a Python package for synthetic populations used in COVID-19 epidemic analyses. It creates populations with multilayer contact networks and includes household, school, workplace, and long-term-care-facility logic. The repository and documentation indicate that it is no longer actively maintained, but its module boundaries are instructive: separate concerns for data distributions, households, schools, workplaces, contact networks, and plotting. It is a useful design reference for later environment/contact layers, not a fit for the near-term Canadian IPF/table-ingestion core.

1. **Recent open contact-network work covers later SynthEco layers.** Tulchinsky et al. (2024) describe an open-source pipeline that first creates a household synthetic population from public census data, then assigns people to schools and workplaces and builds a contact network. This is close to the later "ecosystem" part of SynthEco: households plus schools/workplaces plus network edges. It is US-focused and appears more concerned with epidemic contact networks than reusable census ingestion, but it is a strong reference for the future stage where SynthPopCan assigns schools/workplaces and constructs interaction layers.

1. **BESSIE and FRED show how synthetic populations are consumed by simulators.** BESSIE is an open agent-based epidemic simulator that uses a synthetic population with demographic attributes, households, activities, and location visits. Recent FRED-related papers also use US census-derived synthetic populations as simulation baselines. These are not population-synthesis libraries, but they clarify downstream expectations: stable agent IDs, household IDs, location/activity tables, schedules or visit layers, and reproducible scenario comparisons.

1. **Starsim and Vivarium are relevant as simulation frameworks, not input-data builders.** Starsim is an actively maintained Python/R agent-based disease modeling framework with dynamic transmission networks, calibration support, and population/network abstractions. Vivarium is a Python microsimulation framework that has moved into a renamed suite. These frameworks reinforce the value of clean population-table boundaries and calibration hooks, but they do not replace the need for a Canadian census-specific population builder.

1. **pseudopeople is relevant for synthetic records and entity-resolution testing.** `pseudopeople` is a Python package for generating realistic simulated data about a fictional US population for record-linkage and data-science testing. It is not a geographic synthetic ecosystem builder, but it is a useful reminder that synthetic population outputs may be valuable beyond simulation: record linkage, privacy-preserving software tests, QA fixtures, and scalable algorithm testing.

Design implications for SynthPopCan:

- Prédhumeau and Manley provide a recent national Canadian dataset and archived
  generation scripts. The remaining opportunity is not to claim that no
  Canadian synthesis exists; it is to provide a maintained, reusable toolchain
  with explicit source profiles, general control ingestion, linked-candidate
  workflows, provenance, validation, and library/CLI/web interfaces.
- Keep the first deliverable focused on Canadian data ingestion, margin
  normalization, household/person synthesis, calibration, validation, and
  export, while treating the published national dataset as a related method and
  possible interoperability benchmark.
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

### Fit Of Simulation Frameworks For Canadian And Quebec Rules

Canadian and Quebec simulation rules exist, but as a fragmented collection
rather than a single reusable rulebook. Important sources include Statistics
Canada's Demosim demographic competing-risk model and POHEM health models,
OncoSim cancer models, the Quebec/Canada COMPAS health microsimulation, ISQ
demographic assumptions, and CCDSS/SISMACQ disease-surveillance estimates.
Access varies: some methods and aggregate rates are public, COMPAS has published
code and technical documentation for at least one application, and other
production coefficients, source microdata, or model implementations are
restricted or available only by request. Any reused rule therefore needs
jurisdiction, population, observation period, source, estimation method,
uncertainty, and validation provenance; an older Canadian estimate must not be
treated as a timeless national default.

For reusing these rules in downstream simulations, the current framework
ranking is:

1. **OpenM++** is the closest technical match to Canada's Modgen-derived
   microsimulation heritage. Its entities, events, continuous-time competing
   risks, scenario parameters, replications, and aggregate tables fit Demosim,
   POHEM, COMPAS, and OncoSim-style life-course models. It is the strongest
   long-term target for rigorous demographic and longitudinal microsimulation,
   although model development and compilation are comparatively demanding.
1. **Starsim** is the most practical first adapter. Its modern Python,
   array-based person states, demographic and disease modules, interventions,
   products, calibration, and scenario tooling fit COMPAS/POHEM-like health
   transitions and CCDSS calibration targets. Detailed service choice,
   capacity, and queues would still require new modules.
1. **JUNE**, and potentially its Canadian descendant ODFEM, best fit the more
   ambitious SynthEco-style world of households, schools, workplaces,
   facilities, routines, contacts, disease, and policy. Porting Canadian
   chronic-disease and healthcare-utilization rules would be substantial.
   ODFEM could rank highly, but its public code availability, licensing,
   interfaces, and active status need confirmation before it becomes a
   dependency.
1. **GAMA** is the strongest complement for explicitly spatial services and
   institutions: clinic, school, food, rural-access, facility-placement, and
   environmental scenarios. Canadian health hazards would need translation
   into GAML.
1. **Mesa** is useful for approachable Python prototypes, teaching models, and
   testing a platform-neutral intervention manifest, but it supplies fewer
   public-health components and is not the preferred national-scale runtime.
1. **ActivitySim**, **MATSim**, and **SUMO** are specialized supporting tools,
   not homes for the main Canadian health rule set. ActivitySim fits destination
   and mode choice, MATSim fits travel-plan and network feedback, and SUMO fits
   detailed vehicle and road operations. Their outputs can feed a health or
   microsimulation model.

This ranking answers a narrow question: how naturally could a framework express
the Canadian and Quebec transition rules found in the literature? It is not a
recommendation that one of these frameworks should own the broader SynthEco
simulation world. OpenM++ is a close historical and mathematical match but has
compiler, generated-code, specialist-language, and accessibility costs that do
not fit the project's Python-first and non-specialist-facing direction well
enough to justify a commitment. Its useful ideas can be studied independently
of its platform.

Starsim and JUNE also have a material domain limitation. Starsim's central
abstractions concern diseases, health states, transmission networks, products,
and interventions. JUNE represents a richer society of households, schools,
workplaces, activities, and facilities, but primarily to create contacts and
support epidemiological simulation. Both may become valuable specialist
consumers of SynthPopCan output; neither should define a general world intended
also for food availability, healthcare capacity, education access, housing,
transport, environmental exposure, and institutional allocation.

Much of that broader public-health work may not require agent simulation at
all. A synthetic population combined with facilities, capacities, travel
networks, and environmental layers can support static accessibility,
distributional, demand-pressure, exposure, and counterfactual analyses. Dynamic
simulation becomes justified when time, behaviour, queues, adaptation,
interactions, resource constraints, or feedback change the result.

The far-future direction should therefore be compositional rather than centered
on one engine. Population and environment data remain platform-neutral;
accessibility, service capacity and queues, transport, health transitions,
disease/contact dynamics, and outcomes may be separate components or specialist
adapters. GAMA may be useful for spatial institutions, Mesa for approachable
prototypes, Starsim for health and disease, JUNE/ODFEM for routines and contact
worlds, and ActivitySim/MATSim/SUMO for mobility at different levels. These are
candidate roles, not commitments.

A future intervention manifest can describe timing, targets, resource changes,
eligibility, capacities, coverage, requested outcomes, and assumption
provenance in readable YAML. It cannot by itself supply the causal rules: each
component must still document how people and institutions respond and how
those responses affect outcomes. Research into this broader simulation layer
belongs after stable population generation, governed enrichment, and the
simulator-neutral interchange bundle, and should begin only with a concrete
public-health question for which static analysis is insufficient.

Sources:

- OpenM++ documentation: https://openmpp.org/wiki/openmpp-wiki.html
- Starsim documentation: https://docs.starsim.org/
- JUNE paper: https://doi.org/10.1098/rsos.210506
- GAMA documentation: https://gama-platform.org/wiki/OptimizingModels
- Demosim overview: https://www.statcan.gc.ca/en/microsimulation/demosim/demosim
- Statistics Canada health models: https://www.statcan.gc.ca/en/microsimulation/health/health
- COMPAS technical documentation: https://creei.ca/compas/
- Published COMPAS CVD code: https://github.com/CEDIA-models/compascvd2017
- OncoSim: https://www.partnershipagainstcancer.ca/tools/oncosim/
- CCDSS: https://health-infobase.canada.ca/ccdss/
- SISMACQ: https://www.inspq.qc.ca/boite-outils-pour-la-surveillance-post-sinistre-des-impacts-sur-la-sante-mentale/systemes-de-surveillance/systeme-integre-de-surveillance-des-maladies-chroniques-du-quebec-sismacq

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

Current implemented command families include:

```bash
synthpopcan statcan wds search "population dwelling"
synthpopcan statcan wds explain PRODUCT_ID
synthpopcan statcan wds fetch PRODUCT_ID --out-dir data/raw/statcan/wds
synthpopcan statcan census-profile fetch --year 2016 --geo-level pt --out-dir data/raw/statcan/census/2016/profiles/pt
synthpopcan controls from-wds TABLE.zip --dimensions "GEO,Age group,Sex" --count-column VALUE --out controls.csv
synthpopcan controls from-census-profile PROFILE.csv --mapping census-profile-mapping.json --out controls.csv
synthpopcan microdata export-seed hierarchical.csv --input-format statcan-2016-hierarchical --columns AGEGRP,SEX --out seed.csv
synthpopcan ipf fit --controls controls.csv --seed seed.csv --out weights.csv --report fit-report.json
synthpopcan ipf expand --weights weights.csv --out synthetic.csv
synthpopcan models build train-linked hierarchical.csv --input-format statcan-2016-hierarchical --household-model-out household-model.json --person-model-out person-model.json --manifest-out linked-training.manifest.json
synthpopcan models generate linked-model-package.json --households 1000 --out synthetic-population
synthpopcan validate ipf --population weights.csv --controls controls.csv --kind weights
synthpopcan validate linked synthetic-population
```

Future configuration-driven commands may still be useful, but they should be introduced after the explicit CSV/JSON workflow remains stable. The CLI should eventually treat configs as first-class artifacts so every run is reproducible.

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
1. Validate that selected controls share compatible universes.
1. Build seed/prior table from seed microdata or uniform/smoothed prior.
1. Run dense IPF for small low-dimensional problems; run sparse/list IPF for high-dimensional microdata.
1. Integerize fitted weights.
1. Sample or replicate records.
1. Validate all controlled margins.

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
1. Train household-level sequential tree models from hierarchical PUMF:
   - household size,
   - dwelling type,
   - tenure,
   - household income,
   - family/economic-family structure,
   - other selected household variables.
1. Train person-level sequential tree models conditional on household variables and previously generated person variables:
   - age group,
   - sex,
   - marital/family status,
   - education,
   - labour force,
   - income,
   - language/immigration variables where supported.
1. For each target geography, generate candidate households/persons.
1. Calibrate candidate weights or sample candidates so controlled household and person margins match Census Profile controls.
1. Realize integer households and linked persons.
1. Validate household-person consistency and controlled margins.

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

## Historical Near-Term Roadmap Sketch

This sketch records the initial research interpretation of the work. It is not
the active implementation plan; use `PLANS.md` for current sequencing.

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

## Original Research Open Questions

These questions are still useful context, but some now have partial answers in
the current codebase and roadmap.

- Which exact first geography should be targeted: Montreal CMA, city of Montreal, all Montreal tracts, or selected pilot tracts?
- Should the first output represent private households only, or also collective/non-private populations?
- Which variables are mandatory for the first useful population?
- Should the first tree engine use decision trees for interpretability or random forests/gradient boosting for quality?
- How much exact margin fit is required given Census random rounding and suppression?
- Should the first web app run locally only, or be deployable for remote users?

## Source List

Reviewed local source-bundle entries:

- `Proposal/CIHR Operating Research Grant 01.10.2018_PROPOSAL.pdf`
- `Proposal/CIHR Operating Research Grant 01.10.2018_APPENDIX.pdf`
- `Papers/SynthEco platform methods paper - 06 Aug 2020.docx`
- `Papers/PritchardDissertation.pdf`
- `Papers/Pritchard-Miller2012_Article_AdvancesInPopulationSynthesisF.pdf`
- `Papers/drpritch_popsyn_200910/`
- `Canadian 2016 Census/`
- `Canadian 2011 Census/`
- `Derived GeoJSON GIS/`

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
