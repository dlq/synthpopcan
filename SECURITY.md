# Security And Disclosure

SynthPopCan works with public aggregate data, local raw data caches, generated
synthetic populations, and reviewed model artifacts. Treat data handling and
model release as part of the project's security posture.

## Supported versions

Security fixes are provided for the latest released version of SynthPopCan.
Please upgrade to the newest release before reporting a problem that may already
have been fixed.

## Reporting A Vulnerability

Please do not open a public issue that includes private data, raw Census
microdata rows, credentials, access-controlled files, a suspected disclosure
example, or details of a security vulnerability.

Use GitHub's private vulnerability reporting for this repository:

<https://github.com/dlq/synthpopcan/security/advisories/new>

Include the affected version, the steps needed to reproduce the issue, its
potential impact, and any suggested mitigation. You should receive an initial
response within seven days. Confirmed vulnerabilities will be handled through
a private repository security advisory until a fix and coordinated disclosure
are ready.

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

For ordinary bugs that do not have a security impact, use the public issue
tracker:

<https://github.com/dlq/synthpopcan/issues/new/choose>
