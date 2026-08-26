# English/French Internationalization And Localization Plan

Status: active feature implementation\
Created: 2026-08-19\
Last updated: 2026-08-19\
Target: infrastructure in `1.2.0`, core product localization in `1.3.0`, and
complete supported-surface coverage in `1.4.0`\
Next action: inventory every user-facing CLI, local-web, and documentation
string; classify machine-stable output separately; and select the smallest
message-catalogue implementation that supports Canadian English and French\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) |
[Release train](2026-08-19-post-1-0-release-train.md)

## Outcome

Make SynthPopCan genuinely usable in Canadian English and French without
translating or destabilizing machine contracts. English remains the default
for compatibility, while a user can explicitly select French and receive a
coherent experience across the supported command-line, local-web, and public
documentation surfaces.

This work distinguishes:

- **internationalization (i18n):** extracting user-facing messages, defining
  locale selection and fallback, and preventing new interface text from being
  hard-coded outside the catalogue boundary; and
- **localization (l10n):** reviewed Canadian English and French wording,
  formatting, navigation, help, errors, guides, and documentation.

The bilingual Quebec case study and bilingual descriptive metadata are useful
content, but they do not by themselves constitute product localization.
Likewise, the planned mother-tongue and home-language control families are
statistical features, not translated interfaces.

## Stable Boundaries

Localization must not alter:

- CLI command and option names;
- JSON keys, schema identifiers, field identifiers, control-family IDs, model
  IDs, geography namespaces, or exit codes;
- CSV headers, artifact filenames, checksums, DOI/SWHID values, URLs, or
  provenance identities;
- numerical formatting inside machine-readable outputs; or
- authoritative third-party notices, classifications, and labels unless an
  official translated form is available and its provenance is recorded.

Human-readable prose may be localized. Machine-readable output remains
language-neutral and byte-stable except where an explicitly versioned schema
adds localized descriptive fields. Any sourced label must distinguish an
official French or English value from a reviewed project translation.

Canonical supported locales will use BCP 47 identifiers `en-CA` and `fr-CA`.
Short `en` and `fr` inputs may be accepted as documented aliases, but persisted
evidence records the canonical locale. Unsupported or incomplete locales fall
back predictably to `en-CA`; missing translations fail the catalogue gate in
CI rather than leaking message IDs to users.

## `1.2.0` — Internationalization Foundation

Add infrastructure without claiming that the product is already fully
localized:

- inventory and classify every current user-facing string;
- establish one message-catalogue boundary shared by CLI and local-web code
  where practical;
- define explicit locale selection, canonicalization, fallback, interpolation,
  pluralization, date/number formatting, and translation-provenance rules;
- add extraction or static checks that reject newly hard-coded user-facing
  strings in covered modules;
- keep structured JSON, persisted schemas, logs intended for automation, and
  identifiers locale-neutral; and
- add catalogue completeness, placeholder-parity, fallback, packaging, and
  pseudo-localization tests.

Acceptance gate:

- the string inventory covers every documented CLI path and supported web
  route;
- canonical locale and fallback behavior are documented and deterministic;
- catalogues are packaged in wheel and sdist artifacts;
- placeholder names and plural forms agree across English and French entries;
- machine-output compatibility fixtures are unchanged across locales; and
- `1.2.0` may ship with incomplete French prose only when the untranslated
  surfaces are explicitly reported and safely fall back to English.

## `1.3.0` — Core CLI And Local-Web Localization

Localize the workflows most users encounter:

- top-level help, guide navigation, common validation and usage errors, model
  discovery/inspection/generation, tree generation, small-area planning and
  calibration, bundle creation/validation, and local-server startup;
- local-web navigation, forms, status messages, validation feedback, progress,
  result summaries, and accessibility labels;
- short workflow guides and the bilingual case-study path; and
- human-readable table headings and explanatory text while preserving exact
  JSON and artifact contracts.

Acceptance gate:

- every core workflow completes in both `en-CA` and `fr-CA` from an installed
  wheel;
- CLI and browser scenario matrices cover locale selection, fallback, errors,
  and mixed human/machine output;
- reviewed French terminology is consistent across CLI, web, and guides;
- no localized message changes a schema key, identifier, exit code, or
  numerical result; and
- release documentation states the remaining untranslated advanced surfaces
  rather than claiming full localization.

## `1.4.0` — Complete Supported-Surface Localization

Complete the English/French product promise:

- localize every supported CLI help/error/table surface and every supported
  local-web route;
- publish maintained English and French versions of all supported user guides,
  tutorials, compatibility/support material, and API-facing explanatory pages;
- provide stable language navigation and canonical links without breaking
  existing English documentation URLs;
- cover advanced workflows that remained outside the `1.3.0` core tranche;
  and
- publish a machine-readable localization coverage report binding catalogue
  revision, documentation revision, locale, missing-message count, and test
  evidence.

Acceptance gate:

- supported CLI and web message coverage is 100% for both locales, with zero
  fallback on tested supported paths;
- the maintained documentation inventory has an English and reviewed French
  counterpart, except for explicitly preserved historical records and
  verbatim external material;
- link, code-block, command, schema-name, identifier, and cross-language
  navigation checks pass for both documentation builds;
- accessibility and layout checks cover representative long French strings;
- installed wheel/sdist and public documentation smokes pass in both locales;
  and
- the compatibility contract and support policy describe the exact bilingual
  surface and its maintenance expectations.

## Translation Quality And Governance

- Prefer official Statistics Canada bilingual terminology where available.
- Mark project-authored translations and retain their reviewer, review date,
  source message ID, and catalogue revision.
- Require human review for release-blocking French text; automated translation
  may assist drafting but is not authoritative release evidence.
- Treat privacy, provenance, licensing, suppression, limitation, and warning
  text as high-risk terminology requiring focused review and parity tests.
- Preserve historical dated records in their original language unless a new,
  clearly identified translation is added; do not silently rewrite evidence.
- Accept community corrections through the normal reviewed contribution path,
  with the same compatibility and documentation gates as source changes.

## Out Of Scope

- translating command names, option names, schema keys, identifiers, or source
  data values merely for presentation;
- claiming that all third-party metadata has an official bilingual source;
- silently localizing machine JSON, CSV contracts, or reproducibility evidence;
- adding languages beyond English and French before the two-locale maintenance
  process is demonstrably sustainable; and
- coupling localization completion to whether the `1.3.0` language-control
  families pass their independent statistical evidence gates.

## Release Movement Rules

- The `1.2.0` i18n foundation may not displace its conditional-person-control
  evidence gate; split unfinished localization infrastructure rather than
  weakening either tranche.
- Core localization may move independently of individual `1.3.0` statistical
  control families because interface translation and control evidence have
  separate acceptance criteria.
- `1.4.0` is a provisional follow-on until `1.2.0` proves the catalogue and
  packaging boundary. Revisit its target window after each minor release.
- A missing translation may fall back during `1.2.0` and declared `1.3.0`
  partial coverage, but it becomes release-blocking for the supported `1.4.0`
  surface.
