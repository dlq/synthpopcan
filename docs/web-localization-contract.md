# Web Localization Contract for 1.2.0

Status: design decision for `I18N12-02`; implementation is scheduled in
`I18N12-03` through `I18N12-05`. This document describes the intended contract,
not functionality already shipped.

The scope is the local-web client. CLI and public-documentation localization
are deferred. The [role review](records/localization-role-review-2026-11-14.md)
identifies existing static text, dynamic messages, source labels, logs, and
standalone artifacts. Its machine-output and source-provenance boundaries
remain in force.

## Decision and Boundary

The browser owns locale selection, message lookup, plural selection, and
human-readable formatting. A versioned, packaged static catalogue supplies
project-authored web messages. The client uses the same catalogue for visible
text, accessibility labels, and browser-originated errors. Domain and workflow
code continue to produce the existing language-neutral data and current English
messages; the browser derives a presentation without modifying the source.

The selected locale does not add or change request parameters, URLs or headers
for existing API endpoints, and is not persisted in runs, events, reports or
other evidence. Browser-supplied default headers are unaffected. Selection is a
browser preference, not an input to population generation or calibration. JSON keys and values, event records,
status codes, CLI output, source data, CSV, output filenames, shell reproduction
commands, checksums, and persisted artifacts must remain unchanged across locales.
A translation may change only the client's rendered human-facing presentation.

## Locale Selection

The canonical supported locales are `en-CA` and `fr-CA`. Accept `en` and `fr`
as aliases, and accept case variants of those aliases and canonical tags; store
and expose only the canonical tag. Do not silently map `fr-FR`, `en-US`, or
another region to a Canadian locale. Invalid, unsupported, unavailable, or
malformed selections resolve to `en-CA`.

With no explicit selection, use `en-CA` for compatibility rather than inferring
a locale from browser or operating-system settings. A web-client language
control sets the selection; persist it as a versioned browser-local preference,
under the key `synthpopcan.web.locale.v1`, not in a run. If storage is unavailable, use the selection for the current page
only and fall back to `en-CA` on the next load. The UI remains usable without
storage. Switching locale must rerender covered text and already displayed
client presentations without mutating underlying API responses or event data.

## Catalogue Format and Message Identity

Use UTF-8 JSON files shipped with the web assets in the wheel and sdist. Each
locale file is an object with `schema_version`, canonical `locale`, a catalogue
`revision`, and a `messages` object keyed by stable message IDs. The schema
identifier is `synthpopcan-web-messages-v1`. IDs use lower-case dotted names
such as `web.run.queued` and describe meaning and context, not displayed English
or DOM positions. IDs must be unique; incompatible meaning or parameter changes
require a new ID rather than reuse. Catalogue revisions identify content, not
a change to the v1 schema.

Each message entry declares its kind, named parameter types, source and review
metadata, and text. A `text` entry has one `value`; a `plural` entry declares a
numeric `count` parameter and a `forms` object. For example, this illustrates
the shape and does not claim an approved French translation:

```json
{
  "schema_version": "synthpopcan-web-messages-v1",
  "locale": "en-CA",
  "revision": "example-1",
  "messages": {
    "web.run.queued": {
      "kind": "text",
      "parameters": {},
      "value": "Run queued.",
      "provenance": {"kind": "project", "source_id": "web.run.queued", "review": "reviewed", "reviewer": "example reviewer", "reviewed_on": "2026-11-14"}
    },
    "web.run.rows": {
      "kind": "plural",
      "count_parameter": "count",
      "parameters": {"count": "number"},
      "forms": {"one": "{count} row", "other": "{count} rows"},
      "provenance": {"kind": "project", "source_id": "web.run.rows", "review": "reviewed", "reviewer": "example reviewer", "reviewed_on": "2026-11-14"}
    }
  }
}
```

Both locale files shipped together use the same nonempty catalogue revision;
the declared covered set is versioned with that revision. `en-CA` is the
canonical source catalogue. Its declared parameters are `text`,
`number`, or `date`; a text parameter is an opaque value, not an HTML fragment.
Templates support literal text and named `{parameter}` placeholders only. Braces
are escaped as `{{` and `}}`; unbalanced braces, undeclared names, and missing
required arguments are invalid. A parameter's identity, not its English order,
lets a translation reorder it. A translated entry must have the same kind,
parameter names and types, and placeholder set in each applicable form as its
English entry. Extra or missing parameters and invalid value types fail
validation rather than being silently converted into machine output.

Select plural forms using `Intl.PluralRules` for the canonical locale and the
original finite numeric `count`, with an explicit `other` form. Each declared
locale must provide every plural category returned by that locale's cardinal
rules for a covered plural message. Format display numbers and dates using
`Intl.NumberFormat` and `Intl.DateTimeFormat` with the selected locale and
explicit, message-reviewed options; do not change underlying numbers, dates,
CSV, or JSON. Date inputs must be valid explicit timestamps or dates with a
specified time-zone interpretation; never infer a time zone from an ambiguous
string. Preserve identifiers, filenames, user-entered text, source labels, and
command fragments as opaque parameters. Insert output with `textContent` or
equivalent text APIs; catalogue text and parameters are never executable HTML.

Provenance is per entry: project-authored translations record the source ID,
review status, reviewer and review date before they can be declared covered.
Third-party wording records its source, language, vintage and whether it is an
official source text or a project translation. Never replace a prescribed
notice or silently present an unverified translation as official. Machine
source fields remain unmodified even when an independently attributed label is
shown alongside them.

## Missing Entries and Fallback

A 1.2.0 catalogue skeleton may declare a surface or message untranslated. An
entry becomes **covered** only when both locale entries and their required
forms, parameters and review metadata pass validation. CI fails for a missing
or invalid entry *inside the declared covered set*; the coverage report counts
and names excluded or untranslated surfaces. This reconciles partial 1.2.0
coverage with the later requirement that covered messages never leak IDs.

At runtime, a missing or invalid French entry falls back to the valid English
entry for that ID. Invalid arguments or a corrupt entry must not expose the ID,
render partial markup, or crash the workflow: use a fixed, safe English
presentation fallback, retain any already-authorized diagnostic detail, and
record a developer diagnostic without secrets or user data. If the ID is
unknown or the English entry is also unavailable, use the same fixed English
fallback. Do not substitute an unrelated translation or silently omit an error.

## Dynamic Server Messages

Current `_error_response` returns `{"error": message}`. Durable `RunEvent`
records contain `stage` and `message`, and the client displays those fields
from HTTP or SSE. Some messages include filenames, counts or exception text;
stage names can be reused across workflows. They are existing machine-readable
and persisted values even when shown to people.

For **known, fixed, project-authored** messages only, maintain a versioned,
client-side exact-match presentation registry. An error key consists of its
endpoint family, request method, HTTP status and complete original error text;
an event key consists of workflow, stage and complete original message text.
Each maps to one catalogue ID with no inferred parameters. Reject duplicate
keys and conflicting mappings in validation. The client may render the mapped
message in the selected locale while retaining the original response or event
unchanged. A stage, status, or partial English prefix alone is never a message
identity. Do not apply this mapping to source-provided labels, third-party
notices, user input, or arbitrary exception text.

For unknown, parameterized, malformed, or historical messages, do not guess by
regex, substitute fragments, or interpret content as markup. Show a localized
generic context such as an error or progress heading, followed by the original
authorized plain-text detail exactly as received. The detail can remain
English; document this limitation and count it as untranslated. A missing
message uses a safe generic fallback rather than displaying `undefined` or a
catalogue ID. Do not reveal internal exceptions or raw response bodies that
the current API intentionally suppresses.

For example, an explicitly registered `ipf` / `reading-inputs` / `Reading seed records and controls` event can display a translated catalogue message. An
unrecognized `Finished batch <name>` event keeps its exact original detail;
the client does not extract or translate `<name>`. Replayed old events follow
the same rule, so changing languages never rewrites `events.ndjson`.

A future protocol may introduce independently versioned semantic codes and
validated parameters, but this tranche does not add, rename, or translate
fields in HTTP JSON, SSE, saved events, or manifests. Any such protocol change
requires its own compatibility decision and tests.

## Required Implementation and Acceptance Evidence

`I18N12-03` implements and tests canonicalization, browser-local preference,
lookup, safe fallback, named parameters, escaping, plural and display formatting,
and locale switching. `I18N12-04` packages both catalogue files and verifies
wheel and sdist contents, declared coverage, placeholder/type/form parity,
review provenance, pseudo-localization, and English fallback for declared gaps.
`I18N12-05` adds a scoped static guard and a machine-readable coverage report;
uncovered modules remain explicitly listed rather than being claimed as covered.

The implementation must demonstrate all of the following:

- explicit, absent, unsupported, malformed, alias and case-variant locale
  inputs; storage failure; locale switching and fallback without leaked IDs;
- invalid catalogues, duplicate IDs and dynamic-map keys, missing arguments,
  wrong parameter types, literal braces, reordering, plural boundaries and
  unavailable French forms;
- malicious-looking text and user-supplied filenames rendered as plain text,
  with identifiers and original third-party notices unchanged;
- known and unknown HTTP errors; repeated stages in different workflows;
  parameterized messages; historical event replay; and localized presentation
  without mutating or serializing translated data;
- identical input requests and byte-for-byte deterministic fixture responses, event logs,
  manifests, CSV, reproduction commands, output artifacts and exit codes across
  locale selections, including failure paths; and
- browser and installed-distribution tests that identify untranslated
  presentation and verify the packaged English fallback.
