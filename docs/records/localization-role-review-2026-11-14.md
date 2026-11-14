# Localization String Role Review — 2026-11-14

This is an inventory and preservation review, not a translation catalogue. It
records which contexts can safely be considered for translated presentation and
which must remain stable until a versioned contract says otherwise. It does not
claim that every string has been individually classified.

The current localization target is the web client. CLI and documentation
localization are deferred until a later decision, with no assigned release.
Their entries remain here to protect shared output and provenance, not as a
commitment to translate those surfaces.

## Reviewed Boundaries

| Surface | Evidence | Classification and handling |
| --- | --- | --- |
| Static web HTML | `src/synthpopcan/web/index.html`; [HTML snapshot](localization-web-html-2026-11-14.json) | Visible text and accessibility attributes are presentation candidates. IDs, classes, element attributes that drive behavior, and input values remain unchanged. Empty alternative text may be intentional. |
| JavaScript presentation and DOM | [JavaScript snapshot](localization-web-js-2026-11-14.json) | Direct `textContent` and `innerText` assignments are presentation candidates. DOM selectors, element types and structural properties are stable. Source-hash-bound reviews cover the 15 modules with inventoried expressions, including generated shell commands, CSV and starter records, HTTP/SSE protocol data, browser validation errors, and run summaries. A string's wording alone does not prove its role. |
| Browser-generated CLI commands | `src/synthpopcan/web/cli-commands.mjs` | Executable command syntax, quoting, filenames and options are machine-facing. The shell text also contains comments for readers, so treat each rendered command as a mixed artifact and retain its current bytes until a reviewed interface separates those concerns. |
| Python terminal output | `src/synthpopcan/cli.py`, `cli_geo.py`, `cli_tree.py`, `cli_output.py` | Help, tables and errors are human-facing in some modes, while JSON and other output can be consumed by automation. Keep command names, option names, schema keys, exit codes and machine outputs stable. An output call alone does not prove text is presentation-only. |
| Workflow progress and durable events | `src/synthpopcan/workflows/types.py`, `src/synthpopcan/runs.py`, `src/synthpopcan/web/run-events.mjs` | Stage identifiers, event fields and recorded event messages are serialized to `events.ndjson` and replayed over SSE. Preserve existing records and stream semantics. A later localized display needs a separate presentation mapping rather than changing historical event bytes. |
| Worker and maintainer logs | `src/synthpopcan/workflows/profiling.py`, `scripts/` | Profile logs capture subprocess stdout and stderr and their commands are retained as JSON. Maintainer scripts also emit diagnostic and machine-readable output. Keep log, command, checkpoint and evidence values stable; do not infer that `print` or `click.echo` is presentation-only. |
| Shared exceptions and HTTP error values | `src/synthpopcan/workflows/preflight.py`, `src/synthpopcan/webapi.py`, domain modules | Exception text can flow into both CLI messages and JSON error values. Treat these as mixed until an adapter provides a separate localizable presentation while maintaining existing API contracts. |
| Public and historical documentation | `docs/`, `docs/records/`, `plans/`, `adr/` | User-facing explanatory prose can be translated separately. Preserve command examples, identifiers, quoted source language, dated records, decisions, evidence and immutable artifact references. |

## Source Notices and Third-Party Text

| Material | Evidence | Preservation rule |
| --- | --- | --- |
| Statistics Canada attribution and no-endorsement notice | `src/synthpopcan/model_licensing.py`, `src/synthpopcan/models/__init__.py`, packaged model licensing, [licensing review](prepared-model-licensing-review-2026-08-15.md) | The notice, product titles, catalogue identifiers, licence URLs and linked source conditions are carried in machine-readable model metadata and reviewed evidence. Preserve the recorded notice and provenance. A separately displayed translation requires an identified authoritative version or a clearly labeled project translation. |
| Census Profile, PUMF and WDS labels | `_profile_preparation.py`, `_control_pack_catalogue.py`, `statcan.py`, downloaded or user-supplied source data | Source labels, characteristic IDs, categories and provenance are data, not project-authored message IDs. Preserve them in artifacts and crosswalks. If a source offers a verified French label, record its source and vintage rather than inventing an official equivalent. |
| Prepared-model and upstream licence metadata | `model_licensing.py`, package JSON, `LICENSE`, `package-lock.json` | Preserve licence names, SPDX identifiers, legal notices, URLs, rights-holder fields and package metadata. Project-authored explanatory text can have a separate translated presentation; it must not rewrite the embedded licence layer. |
| Map style and library | `map_render.py` | Generated maps load MapLibre assets and an OpenFreeMap style. Preserve external URLs, upstream attribution and notices supplied by the style or library; review provider terms and actual rendered attribution when building a localized map presentation. |
| Historical quotations and third-party responses | `docs/records/`, `adr/`, source response handlers | Keep original quotations, externally supplied messages and archived evidence with their provenance. A translation must be separate and labeled, not substituted into the original evidence. |

The [Python context snapshot](localization-python-roles-2026-11-14.json)
records source hashes, locations, and output sinks. Roles named `mixed` are
conservative preservation decisions, not proof that every use is either user
prose or a machine contract. `unresolved-preserve-until-reviewed` identifies
locations for further review. The Python scan includes maintainer scripts and
thus is larger than the earlier package-only line inventory.

The JavaScript snapshot covers string-literal and template expressions parsed
by the locked Biome installation. It is not a complete parser-based catalogue
of comments, regular expressions, HTML embedded in Python templates, dynamic
server text, CSS, external source labels or third-party notices. Maintain the
scope limitation until those sources have been assessed.

## Presentation Used as Control State

The review found that `runs-workbench.mjs` and `small-area-workflow.mjs`
matched English display-text prefixes when invalidating an in-flight operation.
Those checks now use language-neutral operation state. Browser scenarios replace
the displayed text while uploads, preflights and small-area start are delayed,
then verify that changed inputs still invalidate the stale operation.

## Dynamic Text And Scope Decision

| Web-visible source | Review and handling |
| --- | --- |
| Run progress and terminal errors | `run-events.mjs` displays the persisted `event.message`; `runs-workbench.mjs` displays run error messages. Preserve the stored event and error payloads. A future client catalogue needs a stable way to map those records to localized presentation, with a safe fallback for unknown or historical values. |
| API error responses and preflight diagnostics | `webapi.py` returns structured JSON but sometimes forwards validated exception text; the browser displays `payload.error` or diagnostic `detail`. These are mixed machine/human outputs, not strings that can be translated in place. Define version-compatible message identifiers or client-side presentation at `I18N12-02`; keep raw details and current machine responses unchanged. |
| Catalogue, source and user-supplied labels | Model names, provenance, geography, source labels, filenames, CSV cell values and external service responses are dynamic data. Preserve the original values and provenance; localize surrounding client labels separately. The inventory does not claim an official French equivalent for external data. |
| Generated commands, reports and standalone maps | Browser-generated commands combine shell syntax with explanatory comments and remain byte-stable. Reports and standalone map HTML are generated artifacts rather than the local-web client; their labels and filenames are outside the current web-client localization scope. The map templates in `map_render.py` mix user-supplied titles, translated-label candidates such as `Variable`, legend-scale text and tooltip descriptions with machine geometry, variable IDs, URLs and serialized data; preserve the complete artifact until a separately scoped map-localization design is reviewed. |
| Locale-dependent formatting | The run list and numeric summaries use `Intl.DateTimeFormat` or `toLocaleString` with ambient browser defaults. Inventory these as runtime formatting decisions rather than fixed text; make them follow the selected web locale without changing numeric machine data. |

The review covers the current 16 web modules, their static HTML, supported
web routes, and the boundaries through which dynamic text reaches the client.
It deliberately does not enumerate unknown future user inputs or third-party
responses. Human French translations, message IDs, locale behavior and a
mapping for mixed server text remain implementation work, not completed by
this inventory.
