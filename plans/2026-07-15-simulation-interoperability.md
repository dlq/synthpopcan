# Simulation Interoperability And Data Handoff Plan

Status: planned\
Created: 2026-07-15\
Last updated: 2026-07-15\
Target: `0.8.0`–`0.8.2`\
Next action: validate a simulator-neutral exchange contract against small,
officially documented input examples before implementing any adapter\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) | Prerequisites:
[local runtime](2026-07-10-local-web-application-runtime.md) and
[ecosystem enrichment](2026-07-15-ecosystem-enrichment.md)

## Purpose And Boundary

Make validated SynthPopCan populations straightforward to consume in external
transport, epidemiological, health, spatial, and general agent-based simulation
systems. SynthPopCan owns population construction, linkage, validation,
provenance, and export. The downstream platform owns simulation behaviour,
dynamics, interventions, calibration, execution, and result interpretation.

This track does **not** implement population simulation inside SynthPopCan. It
also does not claim that a household/person table is a runnable simulation.
Adapters must identify and validate every additional input required by their
target, such as land use, facilities, activities, schedules, travel skims,
routes, contact networks, disease states, or model code.

Keep the core schema simulator-neutral. Target-specific names, codes, XML,
objects, and configuration belong in optional adapters built on one versioned
interchange contract.

## Simulator-Neutral Interchange Bundle

The initial bundle should be a directory or archive containing:

- `persons.parquet` and `households.parquet`, with optional CSV equivalents;
- optional normalized `geographies`, `locations`, `memberships`, `activities`,
  `network_edges`, and `routes` tables when those layers exist;
- spatial layers in GeoParquet or GeoPackage, with GeoJSON or other
  target-compatible exports where required;
- `manifest.json` containing schema version, run identity, software version,
  seeds, parameters, row counts, checksums, and relationships between files;
- a machine-readable data dictionary covering types, units, code lists,
  missing-value semantics, cardinality, and observed-versus-modeled status;
- provenance, licence/access classification, geography and temporal coverage,
  coordinate reference system, and source/enrichment lineage;
- validation and assurance results, including linkage, uniqueness, population
  totals, structural rules, geography, time, network, and disclosure checks.

Stable keys should include `person_id`, `household_id`, `geography_id`, and,
where present, `location_id`, `activity_id`, and explicit network endpoint IDs.
Identifiers must be unique in their declared scope, stable within a versioned
run, free of private source identifiers, and accompanied by foreign-key and
cardinality rules.

The contract must specify:

- table ownership, primary keys, foreign keys, and allowed optionality;
- categorical code systems and target-specific crosswalks;
- weights and expansion/scaling semantics;
- coordinate reference systems, geometry roles, and spatial precision;
- time zones, date/time units, schedule ordering, and duration semantics;
- directed/undirected, weighted, temporal, and multilayer network semantics;
- privacy and redistribution classifications for every file and field;
- forward-compatibility and migration rules for schema versions.

## Target Families And Research Findings

### Table-oriented transport demand

**ActivitySim** is the closest initial transport target. Its documented model
inputs use household, person, land-use, and zone-indexed tables, commonly in CSV
or HDF5 form. A SynthPopCan adapter can provide households and persons plus
zone/categorical crosswalks, but a runnable model still needs target-specific
land-use, network, skim, settings, and coefficient inputs.

Research:

- [ActivitySim: how the system works](https://activitysim.github.io/activitysim/develop/howitworks.html)
- [ActivitySim: anatomy of a model](https://activitysim.github.io/activitysim/develop/users-guide/model_anatomy.html)
- [ActivitySim development and supported data stores](https://activitysim.github.io/activitysim/develop/development.html)

### Transport and mobility simulation

**MATSim** represents people through plans containing activities and travel
legs, with activity locations tied to coordinates or network links. Exporting
demographics and home locations is not sufficient: the adapter requires an
activity/schedule layer and an independently supplied transport network.

**SUMO** requires a road network and traffic demand expressed as routes, trips,
flows, or person stages with departure times. A SUMO adapter therefore belongs
after activities, schedules, locations, modes, and route/network relationships
exist; it must not infer a complete mobility model from population rows alone.

Research:

- [MATSim book](https://matsim.org/files/book/partOne-latest.pdf)
- [SUMO simulation basics](https://sumo.dlr.de/docs/Simulation/Basic_Definition.html)
- [SUMO person definition](https://sumo.dlr.de/docs/Specification/Persons.html)

### Health and epidemiological simulation

**Starsim** exposes a Python `People` abstraction with agent-state arrays and
network concepts. It is a strong early Python adapter candidate: translate
validated DataFrames into people/state arrays, preserve weights explicitly, and
attach contact layers only when their semantics have been validated.

**FRED** demonstrates the importance of geolocated households, schools,
workplaces, group quarters, and daily mixing locations. Its public materials are
useful for contract design, but custom Canadian-population ingestion must be
verified against the maintained standalone software before FRED becomes a
supported adapter rather than a research reference.

**Vivarium** uses model-specific HDF artifacts and keyed population structures.
Treat it as a later specialized artifact builder rather than assuming that the
generic person table is directly consumable.

Research:

- [Starsim: people, states, and arrays](https://docs.starsim.org/user_guide/basics_people.html)
- [FRED synthetic populations](https://fred.publichealth.pitt.edu/syn_pops)
- [FRED model overview](https://fred.publichealth.pitt.edu/fredModel)
- [Vivarium artifacts](https://vivarium.readthedocs.io/en/latest/tutorials/artifact.html)

### General and spatial agent-based modeling

**Mesa** can construct agents from pandas DataFrames, making a documented
Python loader and example model useful. Mesa has no universal domain schema;
each consuming model still owns the mapping from exchange fields to its agent
attributes and behaviours.

**GAMA** can create agents from CSV and spatial data such as shapefiles and can
work with GeoJSON and other GIS formats. A useful adapter should include
portable tabular/spatial outputs, explicit CRS metadata, and a small GAML import
example rather than a GAMA-specific core schema.

**AnyLogic** can initialize agent populations from spreadsheets or database
tables. It is a candidate for documented CSV/XLSX/database mappings, but it is
proprietary and model-specific, so support should follow demonstrated demand
rather than drive the interchange design.

Research:

- [Mesa Agent API](https://mesa.readthedocs.io/stable/apis/agent.html)
- [GAMA agent creation from files](https://gama-platform.org/wiki/1.9.2/Statements)
- [GAMA file formats](https://gama-platform.org/wiki/1.9.1/DefiningExportFiles)
- [AnyLogic population creation from database data](https://anylogic.help/anylogic/connectivity/agent-db.html)

## Adoption, Maintenance, And Canadian Context Snapshot

Snapshot date: 2026-07-15. GitHub stars measure public repository attention,
not scientific validity, installed use, agency adoption, or commercial use.
Recent commits count commits since 2026-04-15. Repository migrations and
projects that commit directly rather than through pull requests make activity
counts non-comparable in detail; use them as maintenance signals only.

| Platform | GitHub stars | Recent commits | Maintenance/adoption interpretation |
| --- | ---: | ---: | --- |
| [SUMO](https://github.com/eclipse-sumo/sumo) | 4,102 | 1,173 | Largest and most visibly active open repository in this set; broad transport-simulation use. |
| [Mesa](https://github.com/mesa/mesa) | 3,729 | 38 | Largest general-purpose Python ABM community in this set; active major-version development. |
| [MATSim](https://github.com/matsim-org/matsim-libs) | 623 | 172 | Established transport-research community with active core maintenance. |
| [ActivitySim](https://github.com/ActivitySim/activitysim) | 246 | 6 | Smaller specialized planning-agency consortium; influential in activity-based travel-demand work. |
| [GAMA](https://github.com/gama-platform/gama) | 111 | 366 | Active current repository; the archived 1.x repository has 308 stars, so repository migration understates its history. |
| [FRED](https://github.com/PublicHealthDynamicsLab/FRED) | 83 | 0 | Historically important population-health simulator, but its public repository was last pushed in May 2024. |
| [Starsim](https://github.com/starsimhub/starsim) | 39 | 137 | Young and comparatively small, but under active development with frequent releases. |
| [Vivarium](https://github.com/ihmeuw/vivarium-suite) | 2 | 466 | Newly consolidated monorepo; predecessor repositories carry its history, making current stars uninformative while commits show active development. |
| AnyLogic | Not comparable | Not comparable | Proprietary commercial product without an open core repository; evaluate through demonstrated user demand rather than GitHub metrics. |

Practical popularity groupings:

- Transport: SUMO has the largest public repository footprint; MATSim has an
  established research community; ActivitySim is important among North American
  regional planning agencies.
- General-purpose ABM: Mesa is the leading Python-oriented candidate in this
  set; GAMA is the stronger spatial/GIS-oriented environment; AnyLogic serves a
  separate proprietary/commercial market.
- Population health: FRED is historically established but publicly dormant;
  Starsim is the strongest rising open candidate; Vivarium is active but tied to
  a more specialized health-microsimulation artifact ecosystem.

Documented Canadian and Québec connections:

1. **SUMO has the strongest direct Montréal/Québec evidence.** Concordia
   University used SUMO in recent Montréal traffic-safety research, and a
   separate study constructed a large-scale Montréal traffic model with SUMO.
   See the [Concordia project](https://hvg.ece.concordia.ca/projects/fvts/pr1/)
   and [Montréal model study](https://www.sciencedirect.com/science/article/pii/S2352146524003557).
1. **MATSim has a strong broader Canadian transport connection and Montréal
   research examples.** The official gallery documents a Greater Toronto
   scenario based on TASHA demand, while MATSim user-meeting material includes
   Montréal cases. See the [Toronto scenario](https://matsim.org/gallery/toronto/)
   and [2024 user-meeting programme](https://www.matsim.org/conferences/mum2024/Preliminary-Schedule.pdf).
1. **ActivitySim has current Canadian agency adoption.** TransLink in Metro
   Vancouver has developed and calibrated an ActivitySim model and, as of its
   2025 report, planned to operate it in parallel with its production trip-based
   model while validation continued. See
   [TransLink's ActivitySim experience](https://modelingmobility.org/presentations/2025/Sunday/3_30-5_00/ActivitySim/2.%20TransLink_s%20ActivitySim%20Experience%20-%20MoMo%202025.pdf).
1. **GAMA is a plausible spatial and Francophone research target, not a proven
   Québec standard.** Its GIS orientation and Francophone documentation may
   reduce adoption friction, but current research did not establish common use
   by Québec agencies or universities.
1. **Mesa, Starsim, Vivarium, FRED, and AnyLogic have no established Québec
   population-simulation footprint in the evidence reviewed so far.** Individual
   Canadian uses may exist; do not describe any as a regional standard without
   stronger institutional or publication evidence.

The Gouvernement du Québec documents operational transportation-modeling
platforms for six metropolitan regions, including Montréal and Québec, but its
public overview describes model classes rather than naming these software
packages. Do not infer official adoption from academic regional case studies.
See [Québec urban transportation models](https://www.quebec.ca/transports/recherches-statistiques/planification/modeles-transport-urbain).

Current adapter-priority implication:

1. ActivitySim first for a table-oriented handoff with demonstrated Canadian
   agency relevance.
1. MATSim and SUMO when `0.7.3` supplies the activity, schedule, location, and
   network prerequisites; emphasize SUMO's Montréal research relevance.
1. Mesa as the generic Python ABM handoff.
1. Starsim as the forward-looking population-health handoff.
1. GAMA when spatial/Francophone users validate the need and example workflow.

Keep FRED as the proposal-era historical compatibility reference, not the first
adapter, unless its maintained custom-population interface is confirmed. Also
research Statistics Canada's
[POHEM](https://www.statcan.gc.ca/en/microsimulation/modgen/new/mods/pohem) as a
Canadian-specific health microsimulation system, while making no compatibility
commitment until an external population-import contract is found.

## Adapter Contract

Each adapter must:

1. declare the interchange schema versions and optional tables it accepts;
1. declare target platform/version assumptions and required external inputs;
1. validate keys, codes, units, geography, time, weights, and prerequisites;
1. translate without silently inventing behavioural or mobility assumptions;
1. write a target mapping report with source and target fields, conversions,
   dropped fields, defaults, warnings, and unsupported semantics;
1. preserve the originating run ID, file checksums, provenance, and validation
   evidence alongside the exported files;
1. distinguish `population data exported` from `runnable model assembled`;
1. provide an exact command or Python call that reproduces the export.

Adapters should be optional modules or extras so simulator-specific dependency
stacks do not become mandatory SynthPopCan runtime dependencies.

## Release Slices

### 0.8.0: Interchange foundation

- Freeze and document interchange schema version 1 on top of the stable
  `0.6.1` linked-population schema and applicable `0.7.x` enrichment contracts.
- Implement bundle writing, schema validation, manifests, data dictionaries,
  checksums, mapping reports, and privacy/access classifications.
- Support Parquet as the loss-preserving tabular form, CSV as the broadly
  accessible form, and appropriate modern GIS output for spatial layers.
- Publish small synthetic bundles covering person/household only; geography and
  locations; activities; and multilayer networks.
- Provide generic Python/pandas loading examples without simulator dependencies.
- Map each interchange/run bundle to an RO-Crate profile so its people,
  software version, inputs, outputs, licences, checksums, provenance, and
  validation evidence can travel as one standards-based research object; keep
  the native SynthPopCan manifest authoritative until the mapping is validated.

### 0.8.1: Initial table and Python adapters

- Validate target contracts using pinned official examples before coding.
- Implement and document ActivitySim, Starsim, Mesa, and GAMA adapters where
  contract research confirms a maintainable path.
- Keep target libraries optional and test exports using small synthetic fixtures.
- Clearly report which external land-use, model, network, or configuration
  inputs remain the consumer's responsibility.

### 0.8.2: Transport-plan adapters

- Implement MATSim population/plan export only after activity, location, time,
  mode, and network-link prerequisites are available and validated.
- Implement SUMO person/trip/route demand export only for supported demand
  semantics; require a compatible external network and routing workflow.
- Add schedule, chronology, coordinate/network-link, mode, and demand-total
  reconciliation tests.
- Demonstrate import or minimal smoke execution against pinned supported target
  versions without treating simulator outcomes as SynthPopCan correctness.

### Candidate follow-ons

- Verify whether maintained standalone FRED supports a stable custom Canadian
  population import contract; do not promise FRED Web upload support.
- Prototype Vivarium artifact building only with a concrete model and its
  required population structure.
- Document AnyLogic table mappings when a user/model supplies the target agent
  definition and confirms the proprietary workflow is worth maintaining.
- Evaluate other platforms through the same contract-first process rather than
  adding format names to the core schema.

## Correctness And Compatibility Evidence

For every supported adapter:

- derive tests from independently read target documentation and official small
  examples, not solely from the adapter implementation;
- validate row counts, identifier linkage, household membership, weights,
  categorical crosswalks, units, geography, coordinates, time ordering, and
  network endpoints before and after translation;
- compare source and exported aggregate totals and record all expected losses;
- retain golden schema/fixture outputs and review intended changes explicitly;
- run target parsers or minimal import/smoke workflows in a separate optional CI
  tier when licensing, size, and installation permit;
- pin and report tested platform versions, monitor contract changes, and avoid
  claiming compatibility with untested versions;
- keep simulation outputs, behavioural validity, disease dynamics, traffic
  assignment, and policy interpretation outside SynthPopCan's correctness
  claims.

## Acceptance Criteria

- The interchange bundle is versioned, self-describing, independently
  validated, reproducible, and readable without installing a simulator.
- Required and optional tables, keys, units, codes, weights, spatial/time
  semantics, provenance, privacy classification, and migration policy are
  documented and machine-checkable.
- No adapter silently creates schedules, networks, behaviour, or target-model
  defaults that materially change interpretation.
- Every supported target has a mapping specification, prerequisite validator,
  synthetic fixture, aggregate reconciliation, exact reproduction command, and
  pinned compatibility evidence.
- An export clearly says whether it is a population contribution or a complete
  runnable target input, and lists all missing external components.
- Simulator-specific dependencies remain optional and do not enlarge the core
  package dependency set.
- Restricted/private inputs and prohibited derived values are never included in
  public exchange bundles, fixtures, documentation, logs, or releases.
