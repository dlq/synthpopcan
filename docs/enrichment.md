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

Prepare a source-profile JSON and resource-record JSON before importing the
layer. Use `register-resource` to describe bytes already available locally:

```bash
synthpopcan enrich register-resource normalized-source.csv \
  --source-profile source-profile.json \
  --acquired-at 2026-07-29T12:00:00Z \
  --media-type text/csv \
  --public-locator https://example.org/source.csv \
  --out resource-record.json
```

For a restricted source, omit `--public-locator`. SynthPopCan generates an
opaque local identity and does not copy the path into the record.

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

## Claims and Limitations

An enrichment validation establishes recorded byte integrity, schema
compatibility, explicit geography semantics, key uniqueness, coverage
reporting, and preservation of the base population. It does not by itself
establish causal interpretation, exposure validity, representativeness,
capacity, accessibility, disclosure safety, or fitness for a particular
research question.
