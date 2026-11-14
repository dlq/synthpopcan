# English/French Internationalization And Localization Plan

Status: active feature implementation\
Created: 2026-08-19\
Last updated: 2026-10-22\
Target: web-client infrastructure in `1.2.0`, core web localization in
`1.3.0`, and complete supported web-client coverage in `1.4.0`\
Next action: implement locale resolution and the browser presentation runtime
defined by the `I18N12-02` catalogue contract\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) |
[Release train](2026-08-19-post-1-0-release-train.md)

## Outcome

Make the SynthPopCan web client usable in Canadian English and French without
translating or destabilizing machine contracts. English remains the default
for compatibility, while a user can explicitly select French in the web client.
CLI and public-documentation localization are deferred without a release date;
their existing English text and machine interfaces remain supported.

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
Short `en` and `fr` inputs are accepted as documented aliases; the browser-local
preference records the canonical locale without changing run evidence.
Unsupported or incomplete locales fall
back predictably to `en-CA`; missing translations fail the catalogue gate in
CI rather than leaking message IDs to users.

## PR-Sized Work

Only the committed `1.2.0` foundation is executable here. Before `1.3.0` or
`1.4.0` is promoted to the committed next release, replace its release-level
surface list with a new table that divides web workflows and human translation
review into independent slices.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `I18N12-01` | `done` | Frozen `1.x` interface and supported-surface inventory | Classified inventory of web-client, shared machine-stable, historical, and verbatim-source strings | Every supported web route is covered; shared CLI/machine keys, identifiers, logs, and source labels are separately protected |
| `I18N12-02` | `done` | `I18N12-01` | Message-catalogue contract and implementation decision | A reviewed contract defines message IDs, `en-CA`/`fr-CA`, aliases, fallback, provenance, placeholders, plurals, and the boundary between domain results and presentation text |
| `I18N12-03` | `ready` | `I18N12-02` | Web-client locale resolution, interpolation, pluralization, and human-formatting runtime | Unit tests prove canonicalization and deterministic fallback; unsupported locales and missing entries never alter machine output or expose message IDs |
| `I18N12-04` | `blocked` | `I18N12-03` | Packaged English/French catalogue skeleton and compatibility tests | Wheel and sdist contain the catalogues; completeness, placeholder parity, plural forms, fallback, pseudo-localization, and cross-locale machine fixtures pass |
| `I18N12-05` | `blocked` | `I18N12-01`, `I18N12-02`, `I18N12-04` | Static guard and machine-readable coverage report for covered modules | New hard-coded user-facing strings fail the guard; declared untranslated surfaces are counted and safely fall back to English |

The [inventory and role review](../docs/records/localization-role-review-2026-11-14.md)
cover the web client and its dynamic data boundaries. CLI localization and
translations of generated reports or standalone maps are deferred.

The review identified web invalidation logic that matched English display-text
prefixes. Those checks now use language-neutral state; browser scenarios cover
the affected paths. The [web message-catalogue contract](../docs/web-localization-contract.md)
defines exact-match presentation for reviewed static server messages and safe
fallback for unknown, parameterized, and historical messages.

## `1.2.0` — Internationalization Foundation

Add infrastructure without claiming that the product is already fully
localized:

- inventory and classify web-client strings and shared machine-contract boundaries;
- establish a web-client message-catalogue boundary;
- define explicit locale selection, canonicalization, fallback, interpolation,
  pluralization, date/number formatting, and translation-provenance rules;
- add extraction or static checks that reject newly hard-coded user-facing
  strings in covered modules;
- keep structured JSON, persisted schemas, logs intended for automation, and
  identifiers locale-neutral; and
- add catalogue completeness, placeholder-parity, fallback, packaging, and
  pseudo-localization tests.

Acceptance gate:

- the string inventory covers every supported web route and the shared
  machine-output boundaries it encounters;
- canonical locale and fallback behavior are documented and deterministic;
- catalogues are packaged in wheel and sdist artifacts;
- placeholder names and plural forms agree across English and French entries;
- machine-output compatibility fixtures are unchanged across locales; and
- `1.2.0` may ship with incomplete French prose only when the untranslated
  surfaces are explicitly reported and safely fall back to English.

## `1.3.0` — Core Web-Client Localization

Localize the workflows most users encounter:

- local-web navigation, forms, status messages, validation feedback, progress,
  result summaries, and accessibility labels;
- web workflow text for model discovery and generation, small-area planning,
  calibration and run management; and
- human-readable web tables and explanatory text while preserving exact JSON
  and artifact contracts.

Acceptance gate:

- every core workflow completes in both `en-CA` and `fr-CA` from an installed
  wheel;
- browser scenarios cover locale selection, fallback, errors, and mixed
  human/machine output;
- reviewed French terminology is consistent across the web client;
- no localized message changes a schema key, identifier, exit code, or
  numerical result; and
- release documentation states the remaining untranslated advanced surfaces
  rather than claiming full localization.

## `1.4.0` — Complete Supported Web-Client Localization

Complete the English/French web-client promise:

- localize every supported local-web client route and accessibility surface;
- cover advanced workflows that remained outside the `1.3.0` core tranche;
  and
- publish a machine-readable web-client localization coverage report binding
  catalogue revision, locale, missing-message count, and test evidence.

Acceptance gate:

- supported web-client message coverage is 100% for both locales, with zero
  fallback on tested supported paths;
- generated commands, schema names, identifiers, and links remain stable across
  the supported locales;
- accessibility and layout checks cover representative long French strings;
- installed wheel/sdist web-client smokes pass in both locales;
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

- CLI localization, deferred for a later decision without an assigned release;
- public-documentation translation, deferred outside the web-client scope;
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
