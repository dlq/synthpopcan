# Core Web Localization Baseline — 2026-11-21

This is the `I18N13-01` inventory and terminology baseline, not translated
coverage. It describes source commit `79626fc9963d7d8104446675b6dee89a6779b635`
and catalogue revision `runtime-preview-1`. Both locale catalogues have six
draft IDs and **zero reviewed covered IDs**. Proposed French terms below are
unreviewed; no translation or third-party source notice is approved by this
record.

## Enumerated Source Inventory

The line-level inventories are part of this baseline, not illustrative samples:

- [HTML text and accessibility inventory](localization-web-html-2026-11-14.json):
  147 visible-text and selected accessibility-attribute entries, including
  form labels, options, placeholders, help text and headings in
  `src/synthpopcan/web/index.html`.
- [JavaScript expression inventory](localization-web-js-2026-11-14.json):
  926 string and template expressions in 18 modules. Its conservative roles
  include presentation candidates and machine/data expressions; inclusion does
  not make a literal safe to translate. Inspect the source context and sink
  before assigning a message ID.
- [Web and Python role review](localization-role-review-2026-11-14.md) and its
  [Python snapshot](localization-python-roles-2026-11-14.json) cover shared
  errors, persisted progress, source notices, commands and automation output.
  Python entries are a conservative cross-project inventory, not a claim that
  all are web reachable.

All HTML and JavaScript file hashes in those snapshots were compared against
this baseline revision and match. The inventories do not enumerate arbitrary
future API or user-supplied values, browser-generated validation, CSS content,
external responses, or every server-generated dynamic message. Those boundaries
are explicitly classified below and require per-message review, not automatic
extraction into a catalogue.

| Core surface | Source and enumerated text | Dynamic states to cover in subsequent slices |
| --- | --- | --- |
| Shared shell and run history | `index.html` topbar, `.workbench`, run list and `aria-*`; `app.mjs`, `run-list.mjs`, `run-workbench-model.mjs`, `runs-workbench.mjs`, `localization-ui.mjs` | Initial loading, empty/populated run list, workflow and status labels, selected run, locale selection and persistence, unavailable workspace and accessible help. The workspace path and run IDs are opaque values. |
| IPF | `index.html` input/configure/preflight/run/results steps; `runs-workbench.mjs`, `run-api.mjs`, `run-events.mjs`, `run-workbench-model.mjs`, `result-ui.mjs`, `preview.mjs`, `form-utils.mjs`, `http.mjs` | Demo and uploads, invalid inputs, configuration and preflight, running/cancelling/interruption/restart, completion/failure, previews, downloads and reproduction. Progress and diagnostics may be persisted or supplied by the server. |
| Prepared model | `index.html` model-inputs and shared run steps; `runs-workbench.mjs`, `run-workbench-model.mjs`, `run-api.mjs`, `result-ui.mjs` | Catalogue loading/unavailable, select/install/remove, provenance and limitations, package upload, scale and preflight, generation, progress, failures and results. Model metadata and notices are source data. |
| Small-area durable run | `index.html` small-area form, conditional packs and shared run steps; `small-area-workflow.mjs`, `small-area-request.mjs`, `runs-workbench.mjs`, `run-api.mjs`, `result-ui.mjs` | Pack/source/evidence selection, conditional-family compatibility, scale estimates, preflight warnings and failures, start, cancellation, interruption/restart and summaries. Pack IDs and supplied source values stay stable. |
| Generated and shared boundaries | `cli-commands.mjs`, `starter-files.mjs`, `csv.mjs`, `operation-sequencer.mjs`, `http.mjs`; Python API, workflows and run store | Commands and starter CSV mix machine syntax with prose; retain their bytes. JSON, SSE events and saved evidence remain unchanged. Map and report artifacts are outside this core-web tranche. |

`app.mjs` derives accessible labels and tooltips from visible labels and
`data-help`; changing only the visible text would leave stale accessible text.
`run-list.mjs` uses ambient `Intl.DateTimeFormat`, while
`small-area-workflow.mjs` uses ambient `toLocaleString`; later implementation
must use the selected locale for presentation without changing stored data.

## Existing Message IDs And Fallback

The complete current set, in both `messages.en-CA.json` and
`messages.fr-CA.json`, is `web.language.label`, `web.language.coverage`,
`web.fallback.error`, `web.fallback.progress`, `web.ipf.reading`, and
`web.upload.invalid`. All are draft. Only the latter two have registered
fixed-message server mappings: respectively IPF/`reading-inputs`/`Reading seed records and controls`, and POST `/api/uploads`/400/`upload is invalid`. Other
inventory entries have **no assigned message ID**; later slices must assign
stable context-based IDs rather than deriving IDs from English or line numbers.

The [contract](../web-localization-contract.md) controls canonical locales,
English default, browser-local preference and deterministic fallback. Missing
or invalid French entries fall back to valid English; an unavailable/invalid ID
uses a safe English fallback. Unknown, parameterized or historical server
messages keep their original authorized detail alongside generic presentation;
never infer identity from a prefix or rewrite recorded events. Preserve
source-provided labels, model licensing and Statistics Canada notices, user
inputs, identifiers, filenames, CSV cells and command syntax. Any separately
displayed source translation needs attribution and an identified official
version or an explicit project-translation label.

## Terminology For Human Review

These are draft candidates, not catalogue entries or approved translations.
Use authoritative bilingual terms where the source concept matches; confirm
context and wording with a named reviewer before marking messages covered.

| English concept | Proposed Canadian French | Context and source |
| --- | --- | --- |
| private household | ménage privé | [Statistics Canada definition](https://www23.statcan.gc.ca/imdb/p3Var_f.pl?Function=DEC&Id=251053&wbdisable=true); distinguish people from dwellings. |
| household size | taille du ménage | [Statistics Canada census table](https://www150.statcan.gc.ca/t1/tbl1/fr/tv.action?pid=9810024001&request_locale=fr). |
| tenure | mode d’occupation | [Statistics Canada census table](https://www150.statcan.gc.ca/t1/tbl1/fr/tv.action?pid=9810024001&request_locale=fr); verify housing-specific context. |
| population synthesis | synthèse de population | Project terminology; review as a technical concept, not an official source label. |
| small area | petite région | Project draft; confirm geographic context and avoid implying a specific Statistics Canada geography. |
| control / target | contrainte / cible | Project drafts; distinguish an input margin from its numeric target. |
| calibration / fit | calage / ajustement | Project drafts; check statistical and UI context. |
| seed records / random seed | enregistrements de départ / graine aléatoire | Project drafts; the two meanings of seed must remain distinct. |
| preflight | vérification préalable | Project draft for the check before starting a run. |
| run / restart | exécution / redémarrer | Project drafts; distinguish a durable run from one invocation. |
| control pack / evidence | ensemble de contraintes / éléments justificatifs | Project drafts; preserve pack identifiers and distinguish source evidence from a control. |
| convergence / residual | convergence / écart résiduel | Project drafts; preserve the distinction between completion and convergence. |

## Handoff

`I18N13-02` starts with shared navigation, run list, locale control and
keyboard/focus coverage. Assign IDs and test rerendering of visible and
accessible text together. The IPF, model, small-area and dynamic-message slices
then use this baseline and keep unrecognized text outside the coverage claim.
`I18N13-07` requires an actual reviewer and date for every covered French entry.
