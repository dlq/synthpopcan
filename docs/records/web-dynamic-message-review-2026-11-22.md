# Web dynamic-message review and French review handoff

The `1.3.0` core web preview uses presentation registry version 5. This is a
review of message identity and data boundaries, not human approval of the
French translations. All French catalogue entries remain draft, and no covered
messages are claimed until a qualified human records the review.

## Dynamic messages

| Source | Presentation | Boundary |
| --- | --- | --- |
| IPF, model and small-area fixed progress events | Exact workflow, stage and complete message select a catalogue ID. Shared interruption events are mapped for all three workflows. | Existing event records and replay order are unchanged. A different workflow, stage or message is not inferred to have the same meaning. |
| Known HTTP and client validation failures | Exact endpoint, method, status and complete message select a catalogue ID. Structured IPF diagnostics use their known fields. | Other errors preserve their original detail under a localized generic heading. Source labels and values remain source data. |
| Parameterized progress, worker exceptions, older events and unrecognized responses | A localized generic heading precedes the original message. | No parsing or translation is guessed from an English prefix; original detail remains available, including any English text. |
| Run results, events, API data and artifacts | Presentation is rendered in the browser. | Switching language must not alter requests, event history, reproduction commands, diagnostic values, file bytes or checksums. |

The installed-wheel browser scenarios cover the IPF, model and small-area
workflows, including language changes and preservation of run evidence. The
localization unit tests exercise complete-context matching, historical and
parameterized fallback, and interruption replay for all three workflows. These
checks establish presentation behavior; they do not certify the translations.
An unpublished local build of the current `1.2.1` source produced both a wheel
and source archive; each contained byte-identical copies of the current runtime,
presentation registry and both catalogues. This is packaging evidence for the
current checkout, not a published release or final `1.3.0` acceptance.

## Human review handoff

Review `src/synthpopcan/web/messages.fr-CA.json` against the English catalogue,
the [core baseline](core-web-localization-baseline-2026-11-21.md), and the
[catalogue contract](../web-localization-contract.md). Check terminology and
context in the running workflows, especially limitations, errors, privacy,
source attribution, accessibility, plurals, and placeholders. The catalogue
and [coverage report](web-localization-coverage.json) identify draft IDs;
neither generated English source values nor third-party labels should be
represented as reviewed French copy.

For each approved entry, record the real reviewer's name and review date in
its provenance, add only accepted IDs to the declared covered set, and run the
catalogue and distribution checks. Resolve questionable wording with the
reviewer rather than marking it reviewed automatically. Core acceptance also
requires packaged wheel and sdist checks, long French layouts, keyboard access,
fallback and machine-data parity. Those automated checks can be prepared in
advance, but the review and the `1.3.0` release gate remain open.
