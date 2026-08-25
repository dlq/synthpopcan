# Family Relationships And Residential Placement Plan

Status: conditional research\
Created: 2026-08-20\
Last updated: 2026-08-20\
Target: no scheduled release; one family-structure proof and one bounded
urban/rural placement pilot after their evidence gates pass\
Next action: write a 2021 hierarchical-PUMF relationship crosswalk and a
National Address Register coverage/capacity assessment for two candidate areas\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Outcome

Determine whether SynthPopCan should add two related capabilities:

1. explicit economic-family and census-family membership and person roles
   within generated households; and
1. optional allocation of whole generated households to plausible residential
   address or building-unit candidates.

These are research tracks, not current product commitments. Family generation
must represent only relationships supported by the source concepts. Residential
placement must be described as synthetic allocation, never recovery of an
observed residence.

The tracks are related because placement operates on whole households and must
preserve all household, family, and person links. They otherwise have separate
data, privacy, schema, and validation gates and may advance independently.

## Ownership And Boundaries

This plan owns the evidence question, bounded pilots, sequencing, and acceptance
criteria for family relationships and residential placement.

- The [expanded hierarchical tree-model plan](2026-08-01-expanded-hierarchical-tree-models.md)
  owns model/profile design and the richer linked-artifact contract.
- The [expanded small-area controls plan](2026-08-01-expanded-small-area-controls.md)
  owns public family and dwelling controls, their universes, and calibration.
- The [methodological validation plan](2026-08-02-methodological-validation-and-uncertainty.md)
  owns shared utility, uncertainty, and disclosure-risk methods.
- [ADR-0007](../adr/0007-explicit-geography-identity.md) governs explicit
  geography identity and vintage.
- [ADR-0009](../adr/0009-separate-display-and-analytical-geodata.md) keeps
  display geometry distinct from analytical allocation data.

Neither track authorizes redistribution of restricted microdata, confidential
register content, or identifiable source households.

## Track A — Family Membership And Relationships

### Evidence available

The 2016 and 2021 hierarchical Census PUMFs contain household membership plus
economic-family and census-family identifiers, status/structure fields, and
person roles such as `EF_RP` and `CF_RP`. This is enough to investigate explicit
family entities and role-consistent membership within synthetic households.

It is not evidence for an unrestricted kinship graph. The public source does
not necessarily identify every pairwise biological, adoptive, step-family, or
caregiving relationship between household members. The supported claim should
therefore be bounded to generated economic-family and census-family membership,
structure, and documented roles unless a later source supports more.

### Required discovery artifact

Create a vintage-specific relationship crosswalk that records:

- every household, economic-family, and census-family identifier or role field;
- its Statistics Canada definition and population universe;
- nesting and cardinality rules;
- which member-to-member relationships can be derived without ambiguity;
- which relationships are unavailable, grouped, or merely inferred;
- applicability, unknown, and not-in-census-family states;
- cross-vintage definition differences; and
- compatible Census Profile controls and their universes, if any.

The crosswalk must distinguish a household reference person, economic-family
reference person, census-family reference person, spouse/partner, child, other
relative, non-relative, and person outside a census family wherever the source
does. It must not translate those roles into unsupported genealogy.

### Design proof

Use a separately versioned experimental artifact containing:

- households;
- economic families nested according to the source definition;
- census families nested according to the source definition;
- people with household and applicable family membership;
- documented role codes rather than opaque relationship labels; and
- explicit `unknown`, `not_applicable`, and `not_represented` states.

Generate structure before attributes: household composition, family entities,
family membership and roles, then person attributes. CART or conditional
frequency blocks may generate documented roles, but identifiers and referential
links are structural outputs rather than target categories.

### Family acceptance gate

A pilot advances only if:

- every generated person belongs to exactly one generated household;
- every non-null family reference resolves to an existing generated family;
- family nesting, reference-person cardinality, and membership counts reconcile;
- age, marital-status, partner, child, and household-composition invariants are
  independently recomputed rather than trusted from generator output;
- held-out family structures and role distributions remain credible;
- source sparsity and rare family signatures pass privacy review; and
- a household/person-only compatibility view can be produced without inventing
  or changing relationships.

## Track B — Residential Address And Building Placement

### Public candidate sources

Use the public [National Address Register](https://www150.statcan.gc.ca/n1/en/catalogue/46260002)
as the primary candidate inventory. It is derived from Statistics Canada's
Statistical Building Register and exposes non-confidential commercial and
residential addresses. Its data model distinguishes a physical location from
one or more address/building-unit records and includes representative
coordinates and building-usage codes where available.

Use the [Open Database of Buildings](https://www150.statcan.gc.ca/n1/pub/34-26-0001/342600012018001-eng.htm)
only as complementary physical evidence such as footprints, area, type, or
height. Its harmonized source coverage and attributes vary by jurisdiction.

The richer [Statistical Building Register](https://www23.statcan.gc.ca/imdb/p2SV.pl?Function=getSurvey&SDDS=5380)
contains buildings and building units, addresses, geography, type, and usage,
but is confidential. Its existence does not make those internal attributes
available to this project.

### Placement interpretation

Placement means allocating a synthetic household to a plausible residential
candidate inside an explicit Census geography and vintage. It does not mean:

- identifying where a source household lived;
- asserting that a generated household is an observed resident;
- treating a coordinate as rooftop-accurate when it is a blockface or other
  representative point;
- equating an address, building, dwelling, occupied private dwelling, and
  household; or
- forcing every household onto a real address when coverage or capacity is
  insufficient.

### Required discovery artifact

For one urban and one rural Canadian case, record:

- NAR and building-data vintage, licence, retrieval method, and hashes;
- address and location counts, residential/partial/unknown usage, duplicate and
  missing identifiers, coordinate provenance, and geography assignment;
- the number of apparent unit addresses per location and its limitations as a
  capacity proxy;
- building-footprint match rate and attribute availability;
- Census occupied-private-dwelling and household controls at the chosen level;
- collective-dwelling treatment;
- unmatched Census demand and unused candidate supply; and
- urban/rural differences, boundary effects, and known jurisdictional gaps.

### Allocation proof

Implement the first experiment as an optional sidecar, not as a mutation of the
core linked-population contract. Each allocation should retain:

- synthetic household identifier;
- source geography identity and vintage;
- candidate location and address identifiers, with precise address fields
  separately access-classified;
- candidate usage and capacity evidence;
- allocation method and random seed;
- status such as `allocated`, `synthetic_residual`, `unmatched`, or `withheld`;
- confidence/quality flags; and
- input source versions and hashes.

Allocate whole households. Candidate capacity should use observed public unit
records where credible, constrained by Census totals. Unknown capacity must be
represented as uncertainty or a bounded range, not silently converted to one
dwelling. Residual synthetic locations are preferable to duplicate or
impossible address assignments.

### Placement acceptance gate

A pilot advances only if:

- the candidate universe and Census control universe are reconciled explicitly;
- allocation never breaks household, family, or person linkage;
- residential capacity assumptions are inspectable and sensitivity-tested;
- mixed-use, multi-unit, vacant, collective, unknown, and unmatched cases have
  explicit handling;
- aggregation back to the source Census geography reproduces required
  household/dwelling totals within stated tolerances;
- coordinate accuracy and address completeness are reported rather than
  implied;
- exact addresses and coordinates receive a documented privacy and
  disclosure-risk review; and
- exports label placement as synthetic and do not expose precise locations by
  default.

## Sequencing

1. Complete the family relationship crosswalk.
1. Complete the two-area address/building coverage and capacity assessment.
1. Decide independently whether each source is adequate for a bounded proof.
1. If family structure advances, prove the separately versioned linked schema
   and invariants before adding family-aware controls.
1. If placement advances, build a sidecar allocator using the existing whole
   household as its atomic unit.
1. Repeat placement with richer family-aware households only after both pilots
   pass independently.
1. Consider a public release only after compatibility, statistical utility,
   uncertainty, privacy, documentation, and provenance gates pass.

## Explicit Deferrals

- arbitrary household-to-household social or kinship networks;
- reconstruction of biological genealogy;
- confidential SBgR access as an assumed dependency;
- national address placement before bounded urban/rural evidence;
- random address assignment that ignores capacity;
- default publication of exact civic addresses or coordinates;
- collective-population generation; and
- simulation of moves, household formation, births, deaths, or family change.

## Completion

This plan is complete when each track has either passed its bounded acceptance
gate with a named follow-on implementation scope or has a recorded no-go result
explaining the evidence gap. A successful family pilot must have a versioned,
validated relationship contract. A successful placement pilot must have a
reproducible, privacy-reviewed sidecar allocation with honest residual and
uncertainty handling.
