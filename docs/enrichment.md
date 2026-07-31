# External-Data Enrichment

SynthPopCan can attach a normalized external-data table to a linked synthetic
population as a **sidecar layer**. Enrichment does not widen or rewrite
`households.csv` or `persons.csv`. It writes a separate layer plus a versioned
manifest that records the unchanged base hashes, source authority, resource
revision, geography context, linkage keys, validation, and limitations.

This framework is source-independent. Public, locally supplied, licensed, and
restricted datasets use the same contracts, but access to a dataset does not
establish permission to publish it or its derivatives. Can-FED and ODEF are
planned reference adapters; they do not define the framework's scope.

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
   redistribution status, version, observation period, variables, geography,
   limitations, and English/French descriptive metadata.
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
