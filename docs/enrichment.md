# External-Data Enrichment

SynthPopCan can attach a normalized external-data table to a linked synthetic
population as a **sidecar layer**. Enrichment does not widen or rewrite
`households.csv` or `persons.csv`. It writes a separate layer plus a versioned
manifest that records the unchanged base hashes, source authority, resource
revision, geography context, linkage keys, validation, and limitations.

This framework is source-independent. Public, locally supplied, licensed, and
restricted datasets use the same contracts, but access to a dataset does not
establish permission to publish it or its derivatives. The maintained Can-FED
and ODEF adapters demonstrate area and facility sources; they do not define the
framework's scope.

```{admonition} Added in 0.7.0
:class: note

External-data enrichment publishes validated sidecars without rewriting the
linked base population.
```

## Before We Enrich

Enrichment begins with a research claim, not with a join. Before attaching a
layer, identify:

- **why** the source is relevant to the question;
- **what** its unit of observation is;
- **when** its observations apply;
- **who** publishes or governs it;
- **which** licence, access, and redistribution conditions apply;
- **how** its geography corresponds to the synthetic population; and
- **what the linkage cannot establish**.

An area-level deprivation measure, for example, can describe the context of a
DA. It does not become a measured attribute or exposure of every synthetic
person assigned to that DA. We record that distinction in `known_limitations`
and in the enrichment manifest.

## Geography Identity

A geography-bearing layer must declare:

- Census vintage;
- geography level;
- identifier namespace;
- identifier column; and
- optional DGUID column.

For example, a 2021 dissemination-area layer uses the namespace
`statcan:census:2021:da`. A bare `DAUID` is not sufficient to establish that
context. SynthPopCan rejects cross-vintage or cross-namespace joins rather than
assuming that matching-looking codes are equivalent.

## Contract Files

An enrichment bundle composes four records:

1. A **source profile** describes the publisher, authority, licence, access and
   redistribution status, version, observation period, geography, limitations,
   and English/French descriptive metadata.
1. A **resource record** identifies one immutable byte revision by SHA-256,
   size, media type, acquisition mode, and retrieval or registration time.
   Records for local, licensed, or restricted resources never contain local
   filesystem paths.
1. A **layer descriptor** records a normalized CSV's keys, variables, class,
   geography, source/resource lineage, row count, and checksum.
1. An **enrichment manifest** composes those records with the existing
   linked-population v1 manifest and hashes of the unchanged base tables.

The initial layer classes are area attributes, facilities/points, governed
household/person attachments, and relational or temporal layers. Supporting a
class does not mean that every linkage method within it is scientifically or
ethically justified.

## Maintained Public Adapters

The maintained adapters perform the complete source-specific workflow: fetch
or reuse reviewed bytes, verify the pinned revision, normalize by header name,
validate source semantics and geography, publish the sidecar, and write
`source-profile.json`, `resource-record.json`, `validation.json`, and
`manifest.json`. Pass `--resource PATH` to work from an already downloaded copy
of the reviewed archive without a network request.

Without `--resource`, the workflow first looks for the pinned SHA-256 object in
its content-addressed cache and can reuse it fully offline. A cache miss triggers
the bounded HTTPS download. `--cache-dir PATH` chooses another cache, and
`SYNTHPOPCAN_ENRICHMENT_CACHE` sets the shared default. Otherwise the cache is
`~/Library/Caches/synthpopcan/enrichment` on macOS and
`${XDG_CACHE_HOME:-~/.cache}/synthpopcan/enrichment` elsewhere. `--format json`
returns an `artifacts` object with all written paths and a `validation` object
with the full report.

### Can-FED v2 area context

The Can-FED adapter reads both public general-use categorical products and, by
default, publishes one 2021 DA-keyed sidecar containing the 1 km and 3 km
classes:

```bash
synthpopcan enrich can-fed population/ \
  --base-census-vintage 2021 \
  --base-geo-column DAUID \
  --buffer both \
  --out canfed-enrichment/
```

Use `--buffer 1km` or `--buffer 3km` for one product. The values are categorical
classes, not outlet counts. A class of zero means no establishments of that
type were observed in the source measure; classes 1 through 4 are nonzero
k-medians groups. For the two ratio measures, `not_applicable` means the source
published `..` because its denominator was zero.

The source represents August 2024 food-environment conditions using the 2024
Business Register, a 2024 road network, and 2021 DA geography. It is historical
area context—not a current establishment inventory or measured person-level
exposure. The detailed RDC-controlled measures are not acquired or emitted.

The reviewed archive currently contains 57,936 unique DA rows in each buffer
file, although the publisher's user guide says 28 DAs were excluded. The
validation report records this documentation/file discrepancy and reconciles
the bytes actually acquired rather than inventing an exclusion flag.

The default output is `canfed-v2-both.csv`; single-buffer runs write
`canfed-v2-1km.csv` or `canfed-v2-3km.csv`. `DAUID` is the text key. For each
selected suffix (`_1km` and/or `_3km`), the adapter appends that suffix to each
of these eight value-column stems:

```text
grocery_store_class
superstore_class
convenience_store_class
fruit_vegetable_market_class
restaurant_class
limited_service_fast_food_class
modified_retail_food_environment_index_class
restaurant_mix_class
```

The first six classify the source's outlet-density measure (outlets per square
kilometre of network buffer). The modified retail food environment index is the
source-defined proportion of healthier outlets among the included food outlets;
restaurant mix is the proportion of fast-food places among fast-food and
restaurant places. See the [official Can-FED v2 user
guide](https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012025002-eng.htm)
for the outlet definitions and formulas.

Every column uses a metric- and buffer-specific ordinal classification: `0`
means zero density, and `1` through `4` run from the lowest to highest nonzero
k-medians group. `not_applicable` is limited to the two ratios and means their
source denominator was zero. Class numbers are not quantities: class `4` is not
twice class `2`, and classes must not be compared as equal magnitudes across
metrics or buffer sizes.

```python
import synthpopcan as spc
from synthpopcan.geography import statcan_geography_universe

result = spc.enrich_can_fed(
    "population/",
    output_dir="canfed-enrichment/",
    base_geography=statcan_geography_universe(2021, "da", "DAUID"),
)
assert result.validation["passed"]
```

### ODEF v3 facility inventory

The ODEF adapter publishes the corrected v3.0.1 national educational-facility
inventory as a point sidecar:

```bash
synthpopcan enrich odef population/ --out odef-enrichment/
```

This attaches the national inventory without claiming that its facilities have
been assigned to the population. To request an explicit coverage comparison,
the household table must contain compatible 2021 CSDUIDs and the linked
population's `manifest.json` must declare the same column as
`geography.household_column`:

```bash
synthpopcan enrich odef population/ \
  --base-csd-column CSDUID \
  --out odef-enrichment/
```

The product was released on December 13, 2024. The official URL is named
`v3.0`, but its current corrected bytes identify v3.0.1; the correction notice
is dated November 17, 2025. The correction restored `facility_type` and fixed
Manitoba official-language-minority-school information. The adapter preserves
the facility and source IDs, provider and authority, provider-specific facility
type, grades and ISCED indicators, language indicators, address fields, source
update date, 2021 CSD context, source WKT, and parsed coordinate pair.

The live facility CSV differs from both its bundled record layout and older
product-page prose: it omits the declared `postOfficeBoxNumber`, has no CMA
fields, and stores coordinates in one WKT field rather than separate source
longitude and latitude columns. These differences travel in validation
evidence. Missing coordinates and CSDs remain missing, and possible duplicates
are reported without automatically deleting colocated schools or campuses.

The normalized file is `odef-v3.0.1-facilities.csv`, keyed by `facility_id`.
Its remaining columns are grouped as follows:

- source identity and governance: `province_code`, `province_numeric_code`,
  `source_id`, `provider`, `authority_id`, `authority_name`,
  `source_facility_id`, `facility_name`, and `facility_type`;
- address and level text: `source_address`, `street_address`, `postal_code`,
  `locality`, `min_grade`, and `max_grade`;
- education/language flags: `isced_010`, `isced_020`, `isced_1`, `isced_2`,
  `isced_3`, `isced_4_plus`, `official_language_minority_school`,
  `french_immersion`, `early_immersion`, `middle_immersion`, and
  `late_immersion`;
- geography: `CSDUID`, `CSDDGUID`, `csd_name`, `longitude`, `latitude`, and
  `geometry_wkt`; and
- source timing: `source_updated_date`.

Identifiers and source dates remain text. Flags are `true`, `false`, or blank
when the source supplied no value; blank does not mean false. Coordinates are
parsed from the source `POINT (longitude latitude)` text while the original WKT
is retained. Because the reviewed methodology does not explicitly declare its
coordinate reference system, the adapter does not manufacture a CRS claim.

```python
result = spc.enrich_odef(
    "population/",
    output_dir="odef-enrichment/",
)
assert result.validation["source_validation"]["ungeocoded_count"] >= 0
```

ODEF is an inventory. It does not establish capacity, catchment, quality,
eligibility, accessibility, enrolment, service use, or causal effects.

## Import a Normalized Layer

**Template: replace the fictional source, paths, identifiers, dates, licence,
and research limitations.** A real project should prepare the source profile
from the publisher's documentation before normalizing or joining the data.

Create `source-profile.json`:

```json
{
  "schema_version": "synthpopcan-source-profile-v1",
  "source_id": "example.area-context.2025",
  "publisher_id": "example-publisher",
  "titles": {
    "en": "Example area context",
    "fr": "Contexte territorial d'exemple"
  },
  "descriptions": {
    "en": "Fictional DA-level context used to demonstrate the enrichment contract.",
    "fr": "Contexte fictif au niveau des AD utilisé pour démontrer le contrat d'enrichissement."
  },
  "canonical_url": "https://example.org/context",
  "acquisition_mode": "public-download",
  "authority": "Example publisher",
  "licence_id": "CC-BY-4.0",
  "source_version": "2025.1",
  "publication_date": "2026-01-15",
  "observation_period": {
    "start": "2025-01-01",
    "end": "2025-12-31"
  },
  "unit_of_observation": "2021 dissemination area",
  "access_classification": "public",
  "redistribution_status": "permitted with attribution",
  "geography": {
    "schema_version": "synthpopcan-geography-universe-v1",
    "census_vintage": 2021,
    "geography_level": "da",
    "identifier_namespace": "statcan:census:2021:da",
    "identifier_column": "DAUID",
    "dguid_column": null
  },
  "translation_provenance": {
    "fr": "Project translation for this fictional example."
  },
  "known_limitations": [
    "Area context is not person-level exposure."
  ]
}
```

This profile is deliberately verbose. It separates a stable project identifier
from the publisher's title, states whether the French text is official or a
project translation, and records both observation time and publication time.

Normalize the source into a CSV containing only the declared keys and variables.
For example:

```text
DAUID,context_category
24660001,A
24660002,B
```

These are fictional rows. Replace them with identifiers from the population's
declared DA universe, and keep the transformation code or notebook that
produced the normalized file.

Use `register-resource` to describe the exact normalized source bytes already
available locally:

```bash
synthpopcan enrich register-resource normalized-source.csv \
  --source-profile source-profile.json \
  --acquired-at 2026-07-29T12:00:00Z \
  --media-type text/csv \
  --public-locator https://example.org/source.csv \
  --out resource-record.json
```

The source profile's acquisition mode controls the resource record. For a
`local-provided`, `licensed`, or `restricted` source, omit `--public-locator`.
SynthPopCan generates an opaque local identity unless we supply
`--opaque-local-id`, and it does not copy the local path into the record.

Import a geography-keyed area layer:

```bash
synthpopcan enrich import population/ normalized-layer.csv \
  --source-profile source-profile.json \
  --resource-record resource-record.json \
  --layer-id example.area-context.v1 \
  --layer-class area-attributes \
  --key-column DAUID \
  --variable context_category \
  --base-census-vintage 2021 \
  --base-geo-level da \
  --base-geo-namespace statcan:census:2021:da \
  --base-geo-column DAUID \
  --limitation "Area context is not person-level exposure." \
  --out enrichment/
```

The import fails on missing keys or columns, duplicate keys, checksum
inconsistency, an incompatible geography universe, or invalid source/resource
lineage. Its report lists unmatched source and base geographies; incomplete
coverage is evidence to interpret rather than a reason to silently drop rows.

Recompute every base and sidecar hash later:

```bash
synthpopcan enrich validate enrichment/manifest.json \
  --population population/
```

## Python

The beginner API exposes the same import workflow:

```python
import synthpopcan as spc

result = spc.enrich_population(
    "population/",
    "normalized-layer.csv",
    source_profile="source-profile.json",
    resource_record="resource-record.json",
    layer_id="example.area-context.v1",
    layer_class="area-attributes",
    key_columns=["DAUID"],
    variables=["context_category"],
    base_geography={
        "schema_version": "synthpopcan-geography-universe-v1",
        "census_vintage": 2021,
        "geography_level": "da",
        "identifier_namespace": "statcan:census:2021:da",
        "identifier_column": "DAUID",
        "dguid_column": None,
    },
    output_dir="enrichment/",
    limitations=["Area context is not person-level exposure."],
)

assert result.validation["passed"]
```

Maintained source adapters implement the same describe, acquire-or-reference,
normalize, and validate stages. Researchers can use the generic import path
without waiting for a built-in adapter, but SynthPopCan cannot validate an
undocumented transformation performed outside the project.

## Command Reference

### `enrich can-fed`

Runs the maintained public Can-FED v2 area adapter.

- `POPULATION`: linked-population v1 directory.
- `--base-census-vintage`: required declaration; only 2021 is compatible.
- `--base-geo-column`: household DA identifier column; defaults to `DAUID`.
- `--buffer 1km|3km|both`: selected categorical product; defaults to both.
- `--resource`: optional reviewed ZIP already downloaded.
- `--cache-dir`: optional content-addressed download cache.
- `--acquired-at`: optional ISO 8601 retrieval time; generated in UTC when
  omitted.
- `--out`: destination enrichment directory.
- `--format summary|json`: human-readable or machine-readable report.

### `enrich odef`

Runs the maintained corrected ODEF v3.0.1 facility adapter.

- `POPULATION`: linked-population v1 directory.
- `--base-csd-column`: optional household 2021 CSDUID column. For a coverage
  comparison, the population's `manifest.json` must declare this same column as
  `geography.household_column`. Omit the option when attaching the national
  point inventory without a direct population join.
- `--resource`: optional reviewed ZIP already downloaded.
- `--cache-dir`: optional content-addressed download cache.
- `--acquired-at`: optional ISO 8601 retrieval time; generated in UTC when
  omitted.
- `--out`: destination enrichment directory.
- `--format summary|json`: human-readable or machine-readable report.

### `enrich register-resource`

Hashes one local resource and writes an immutable
`synthpopcan-resource-record-v1` JSON document.

- `RESOURCE`: exact local file to hash; the path is used for reading but is not
  written into the record.
- `--source-profile`: required versioned source-profile JSON.
- `--acquired-at`: required retrieval or registration timestamp, normally ISO
  8601 UTC.
- `--media-type`: required media type such as `text/csv`.
- `--public-locator`: authoritative public URL, required for public-download or
  public-API sources and forbidden for non-public acquisition modes.
- `--opaque-local-id`: optional non-sensitive identifier for a non-public
  resource; generated when omitted.
- `--out`: required resource-record JSON path.

The recorded SHA-256 digest identifies one byte revision. If the publisher
updates the file, register the new bytes as another resource rather than
overwriting the old record.

### `enrich import`

Validates and publishes one normalized CSV sidecar and a composition manifest.

- `POPULATION`: linked-population v1 directory containing `households.csv`,
  `persons.csv`, and its manifest.
- `LAYER`: normalized CSV to validate and copy.
- `--source-profile` and `--resource-record`: required lineage records.
- `--layer-id`: stable project identifier for this normalized layer.
- `--layer-class`: one of `area-attributes`, `facilities-points`,
  `household-person`, or `networks-activities-relationships`.
- `--key-column`: required linkage column; repeat for a composite key.
- `--variable`: value column to publish; repeat for multiple variables.
- `--observed-status`: `observed`, `derived`, or `modeled`.
- `--limitation`: reader-facing limitation; repeat as needed.
- `--base-census-vintage`, `--base-geo-level`, `--base-geo-namespace`,
  `--base-geo-column`, and `--base-dguid-column`: explicit base geography
  context. Supply the first four together for Census geography joins.
- `--out`: destination enrichment directory.
- `--format summary|json`: human-readable or machine-readable validation
  result.

The output directory contains the copied layer and `manifest.json`. The base
population remains in its original directory.

### `enrich validate`

Recomputes every recorded base-population and sidecar checksum:

```bash
synthpopcan enrich validate enrichment/manifest.json \
  --population population/ \
  --format json
```

- `MANIFEST`: enrichment manifest to verify.
- `--population`: required linked-population directory referenced by the
  manifest.
- `--format summary|json`: presentation format.

Validation should be repeated after copying or archiving an enrichment bundle.
It detects changed bytes and broken paths; it does not repeat the substantive
research review.

## Claims and Limitations

An enrichment validation establishes recorded byte integrity, schema
compatibility, explicit geography semantics, key uniqueness, coverage
reporting, and preservation of the base population. It does not by itself
establish causal interpretation, exposure validity, representativeness,
capacity, accessibility, disclosure safety, or fitness for a particular
research question.

## Troubleshooting

**The source profile is rejected:** check its schema version, stable lowercase
IDs, bilingual title/description mappings, acquisition mode, access
classification, and geography object. Public acquisition requires public
access; licensed and restricted modes require the matching access class.

**The resource record and source profile disagree:** do not edit the generated
checksum record by hand. Confirm that both name the same `source_id`,
`source_version`, and acquisition mode, then register the intended bytes again.

**The layer has duplicate keys:** decide whether the source should have one row
per area, a composite key, or a different layer class. Do not discard duplicate
rows merely to make validation pass.

**The geography join is refused:** compare Census vintage, geography level,
identifier namespace, and identifier column. Matching strings from different
vintages or namespaces are not sufficient evidence for a join.

**Coverage is incomplete:** inspect the reported unmatched base and source
identifiers. Record a defensible exclusion or limitation; do not silently
replace missing values or drop population rows.

**Validation says the base population changed:** restore the exact population
revision named by the manifest or create a new enrichment bundle against the
new revision. An enrichment manifest is not transferable between different
base bytes.

For lower-level source, resource, layer, and manifest objects, continue to
{doc}`library`. Exact signatures are in {doc}`api`.
