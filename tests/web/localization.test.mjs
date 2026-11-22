import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  canonicalLocale,
  createLocalizationRuntime,
  LOCALE_STORAGE_KEY,
  parseTemplate,
} from "../../src/synthpopcan/web/localization.mjs";

const entry = (value, parameters = {}) => ({ kind: "text", parameters, value });

test("small-area convergence warnings use the correct French number form", () => {
  const catalogues = Object.fromEntries(
    ["en-CA", "fr-CA"].map((locale) => [
      locale,
      JSON.parse(
        readFileSync(
          new URL(`../../src/synthpopcan/web/messages.${locale}.json`, import.meta.url),
          "utf8",
        ),
      ),
    ]),
  );
  const runtime = createLocalizationRuntime({ catalogues });
  runtime.setLocale("fr-CA");
  assert.match(
    runtime.translate("web.smallarea.warning", { count: 1 }),
    /1 région n’a pas convergé/,
  );
  assert.match(
    runtime.translate("web.smallarea.warning", { count: 2 }),
    /2 régions n’ont pas convergé/,
  );
});
const plural = (one, other, extra = {}) => ({
  kind: "plural",
  count_parameter: "count",
  parameters: { count: "number" },
  forms: { one, other, ...extra },
});
function catalogues() {
  const messages = {
    "web.greeting": entry("Hello {name}", { name: "text" }),
    "web.item": plural("{count} item", "{count} items"),
    "web.queued": entry("Run queued."),
    "web.fallback.error": entry("Error"),
    "web.fallback.progress": entry("Progress"),
  };
  const french = {
    "web.greeting": entry("Bonjour {name}", { name: "text" }),
    "web.item": plural("{count} article", "{count} articles", {
      many: "{count} articles",
    }),
    "web.queued": entry("Exécution en attente."),
    "web.fallback.error": entry("Erreur"),
    "web.fallback.progress": entry("Progression"),
  };
  const make = (locale, entries) => ({
    schema_version: "synthpopcan-web-messages-v1",
    locale,
    revision: "test-1",
    messages: entries,
  });
  return { "en-CA": make("en-CA", messages), "fr-CA": make("fr-CA", french) };
}

test("canonical locales have explicit safe defaults", () => {
  for (const [input, expected] of [
    [undefined, "en-CA"],
    ["EN-ca", "en-CA"],
    ["fr", "fr-CA"],
    ["FR-ca", "fr-CA"],
    ["fr-FR", "en-CA"],
    ["en-US", "en-CA"],
    ["fr_CA", "en-CA"],
    [null, "en-CA"],
  ])
    assert.equal(canonicalLocale(input), expected);
});

test("preference failures are safe and selected values are canonical", () => {
  const calls = [];
  const storage = {
    getItem: (key) => {
      calls.push(key);
      return "fr";
    },
    setItem: (key, value) => calls.push([key, value]),
  };
  const runtime = createLocalizationRuntime({ catalogues: catalogues(), storage });
  assert.equal(runtime.locale, "fr-CA");
  assert.equal(runtime.setLocale("EN"), "en-CA");
  assert.deepEqual(calls, [LOCALE_STORAGE_KEY, [LOCALE_STORAGE_KEY, "en-CA"]]);
  const blocked = createLocalizationRuntime({
    catalogues: catalogues(),
    storage: {
      getItem() {
        throw Error();
      },
      setItem() {
        throw Error();
      },
    },
  });
  assert.equal(blocked.locale, "en-CA");
  assert.equal(blocked.setLocale("fr"), "fr-CA");
  const unavailable = createLocalizationRuntime({
    catalogues: { "en-CA": catalogues()["en-CA"] },
  });
  assert.equal(unavailable.setLocale("fr"), "en-CA");
});

test("locale changes rerender plain text without interpreting input as HTML", () => {
  const runtime = createLocalizationRuntime({ catalogues: catalogues() });
  const element = { textContent: "" };
  const detach = runtime.renderText(element, "web.greeting", {
    name: "<img src=x onerror=alert(1)>",
  });
  assert.equal(element.textContent, "Hello <img src=x onerror=alert(1)>");
  runtime.setLocale("fr-CA");
  assert.equal(element.textContent, "Bonjour <img src=x onerror=alert(1)>");
  detach();
  runtime.setLocale("en");
  assert.equal(element.textContent, "Bonjour <img src=x onerror=alert(1)>");
});

test("template parsing, plurals, formatting and error fallbacks are deterministic", () => {
  assert.deepEqual(parseTemplate("{{{name}}}"), [
    { text: "{" },
    { name: "name" },
    { text: "}" },
  ]);
  assert.throws(() => parseTemplate("Bad {name"), /placeholder/);
  assert.throws(() => parseTemplate("Bad }"), /brace/);
  const runtime = createLocalizationRuntime({ catalogues: catalogues() });
  assert.equal(runtime.translate("web.item", { count: 1 }), "1 item");
  assert.equal(runtime.translate("web.item", { count: 2 }), "2 items");
  runtime.setLocale("fr");
  assert.equal(runtime.translate("web.item", { count: 1 }), "1 article");
  assert.equal(runtime.translate("web.item", { count: 2 }), "2 articles");
  assert.equal(runtime.translate("web.greeting", {}), "Message unavailable.");
  assert.equal(
    runtime.translate("web.greeting", { name: "x", extra: 1 }),
    "Message unavailable.",
  );
  assert.equal(runtime.translate("web.item", { count: NaN }), "Message unavailable.");
  assert.equal(runtime.translate("web.unknown"), "Message unavailable.");
  assert.equal(
    runtime.formatNumber(1234.5, {}),
    new Intl.NumberFormat("fr-CA", {}).format(1234.5),
  );
  assert.equal(
    runtime.formatDate("2024-01-03", { timeZone: "UTC", year: "numeric" }),
    "2024",
  );
  assert.equal(
    runtime.formatDate("2024-01-03T12:00:00", { timeZone: "UTC" }),
    "Message unavailable.",
  );
  assert.equal(runtime.formatDate("2024-01-03", {}), "Message unavailable.");
  assert.equal(
    runtime.formatDate("2024-02-30", { timeZone: "UTC" }),
    "Message unavailable.",
  );
  assert.equal(runtime.formatNumber(Infinity, {}), "Message unavailable.");
});

test("invalid or incomplete French entries fall back to valid English", () => {
  const catalogs = catalogues();
  catalogs["fr-CA"].messages["web.greeting"].value = "Bonjour {other}";
  const diagnostics = [];
  const runtime = createLocalizationRuntime({
    catalogues: catalogs,
    onDiagnostic: (code) => diagnostics.push(code),
  });
  runtime.setLocale("fr");
  assert.equal(runtime.translate("web.greeting", { name: "Ada" }), "Hello Ada");
  assert.deepEqual(diagnostics, ["invalid-translation"]);
  catalogs["en-CA"].messages["web.greeting"].value = "broken {";
  assert.equal(
    runtime.translate("web.greeting", { name: "Ada" }),
    "Message unavailable.",
  );
  assert.equal(diagnostics.at(-1), "message-fallback");
});

test("pseudo-localized templates preserve placeholder identity and text safety", () => {
  const catalogs = catalogues();
  catalogs["fr-CA"].messages["web.greeting"].value = "［Bôôñĵôûr {name}］";
  const runtime = createLocalizationRuntime({ catalogues: catalogs });
  runtime.setLocale("fr-CA");
  const element = { textContent: "" };
  runtime.renderText(element, "web.greeting", { name: "<user>" });
  assert.equal(element.textContent, "［Bôôñĵôûr <user>］");
});

test("server messages map only by complete context without modifying data", () => {
  const events = [
    { workflow: "ipf", stage: "queued", message: "Run queued", id: "web.queued" },
  ];
  const errors = [
    {
      endpoint: "runs",
      method: "POST",
      status: 400,
      message: "Bad input",
      id: "web.queued",
    },
  ];
  const runtime = createLocalizationRuntime({
    catalogues: catalogues(),
    eventMappings: events,
    errorMappings: errors,
  });
  runtime.setLocale("fr");
  const original = Object.freeze({
    workflow: "ipf",
    stage: "queued",
    message: "Run queued",
  });
  assert.equal(runtime.presentEvent(original), "Exécution en attente.");
  assert.equal(
    runtime.presentEvent({ ...original, workflow: "model" }),
    "Progression: Run queued",
  );
  assert.equal(
    runtime.presentEvent({ ...original, message: "Run queued / user text" }),
    "Progression: Run queued / user text",
  );
  assert.equal(
    runtime.presentError({
      endpoint: "runs",
      method: "POST",
      status: 400,
      message: "Bad input",
    }),
    "Exécution en attente.",
  );
  assert.equal(
    runtime.presentError({
      endpoint: "runs",
      method: "POST",
      status: 400,
      message: "Bad <input>",
    }),
    "Erreur: Bad <input>",
  );
  assert.deepEqual(original, {
    workflow: "ipf",
    stage: "queued",
    message: "Run queued",
  });
  assert.throws(
    () => createLocalizationRuntime({ eventMappings: [...events, ...events] }),
    /Duplicate/,
  );
});
