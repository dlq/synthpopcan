# Security And Disclosure

SynthPopCan works with public aggregate data, local raw data caches, generated
synthetic populations, and reviewed model artifacts. Treat data handling and
model release as part of the project's security posture.

## Reporting Issues

Please do not open a public issue that includes private data, raw Census
microdata rows, credentials, access-controlled files, or a suspected disclosure
example. Use a private contact route for sensitive reports.

For now, contact the maintainer listed in `pyproject.toml`.

## Sensitive Materials

Do not commit:

- raw Census microdata;
- access-controlled research datasets;
- generated full-population CSV outputs;
- credentials, tokens, or API keys;
- local machine paths that reveal private storage layouts;
- model artifacts that contain raw source rows, row identifiers, or unreleased
  review material.

Reviewed model packages can still carry disclosure risk. A package being JSON
rather than CSV does not make it automatically safe. Use the model audit,
release, and packaging workflows before sharing any model trained from
restricted or sensitive source data.

## Supported Versions

SynthPopCan is pre-alpha. There is no stable supported release line yet.
