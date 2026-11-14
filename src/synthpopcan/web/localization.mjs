/** Browser-only localization. API and persisted objects are never changed. */
export const LOCALE_STORAGE_KEY = "synthpopcan.web.locale.v1";
const FALLBACK = "Message unavailable.";
const VERSION = "synthpopcan-web-messages-v1";
const ID = /^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$/;
const NAME = /^[a-z][a-z0-9_]*$/;
const has = (object, key) => Object.hasOwn(object, key);

export function canonicalLocale(value) {
  if (typeof value !== "string") return "en-CA";
  const locale = value.toLowerCase();
  if (locale === "fr" || locale === "fr-ca") return "fr-CA";
  return "en-CA";
}

function object(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Parse placeholders and escaped braces without interpreting markup. */
export function parseTemplate(template) {
  if (typeof template !== "string") throw new TypeError("Invalid template");
  const tokens = [];
  let text = "";
  for (let i = 0; i < template.length; i += 1) {
    const char = template[i];
    if (char === "{" && template[i + 1] === "{") {
      text += "{";
      i += 1;
    } else if (char === "}" && template[i + 1] === "}") {
      text += "}";
      i += 1;
    } else if (char === "{") {
      const end = template.indexOf("}", i + 1);
      const name = template.slice(i + 1, end);
      if (end < 0 || !NAME.test(name)) throw new TypeError("Invalid placeholder");
      if (text) tokens.push({ text });
      text = "";
      tokens.push({ name });
      i = end;
    } else if (char === "}") {
      throw new TypeError("Unbalanced brace");
    } else {
      text += char;
    }
  }
  if (text) tokens.push({ text });
  return tokens;
}

function signature(entry, locale) {
  if (!object(entry) || !object(entry.parameters)) throw new TypeError("Invalid entry");
  const params = Object.keys(entry.parameters).sort();
  if (
    params.some(
      (name) =>
        !NAME.test(name) ||
        !["text", "number", "date"].includes(entry.parameters[name]),
    )
  ) {
    throw new TypeError("Invalid parameters");
  }
  let forms;
  if (entry.kind === "text") {
    forms = { text: entry.value };
  } else if (
    entry.kind === "plural" &&
    entry.parameters[entry.count_parameter] === "number" &&
    object(entry.forms)
  ) {
    forms = entry.forms;
    const categories = new Intl.PluralRules(locale).resolvedOptions().pluralCategories;
    if (!categories.every((category) => has(forms, category)) || !has(forms, "other")) {
      throw new TypeError("Missing plural form");
    }
  } else {
    throw new TypeError("Invalid kind");
  }
  for (const template of Object.values(forms)) {
    if (typeof template !== "string" || !template.trim())
      throw new TypeError("Empty template");
    const names = [
      ...new Set(
        parseTemplate(template)
          .filter((token) => token.name)
          .map((token) => token.name),
      ),
    ].sort();
    if (JSON.stringify(names) !== JSON.stringify(params))
      throw new TypeError("Placeholder mismatch");
  }
  return JSON.stringify({
    kind: entry.kind,
    params: params.map((name) => [name, entry.parameters[name]]),
    count: entry.count_parameter ?? null,
  });
}

function getEntry(catalogues, locale, id) {
  const catalogue = catalogues[locale];
  if (
    !object(catalogue) ||
    catalogue.schema_version !== VERSION ||
    catalogue.locale !== locale ||
    typeof catalogue.revision !== "string" ||
    !catalogue.revision ||
    !object(catalogue.messages) ||
    !has(catalogue.messages, id)
  )
    return null;
  return catalogue.messages[id];
}

function validArguments(entry, params) {
  if (!object(params)) return false;
  const names = Object.keys(entry.parameters).sort();
  if (JSON.stringify(names) !== JSON.stringify(Object.keys(params).sort()))
    return false;
  return names.every((name) => {
    const value = params[name];
    switch (entry.parameters[name]) {
      case "text":
        return typeof value === "string";
      case "number":
        return typeof value === "number" && Number.isFinite(value);
      case "date":
        return validDate(value);
      default:
        return false;
    }
  });
}

function validDate(value) {
  if (value instanceof Date) return Number.isFinite(value.getTime());
  if (
    typeof value !== "string" ||
    !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2}))?$/.test(
      value,
    ) ||
    !Number.isFinite(Date.parse(value))
  )
    return false;
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  return (
    calendar.getUTCFullYear() === year &&
    calendar.getUTCMonth() === month - 1 &&
    calendar.getUTCDate() === day
  );
}

function renderEntry(entry, grammarLocale, displayLocale, params) {
  const template =
    entry.kind === "plural"
      ? (entry.forms[
          new Intl.PluralRules(grammarLocale).select(params[entry.count_parameter])
        ] ?? entry.forms.other)
      : entry.value;
  return parseTemplate(template)
    .map((token) => {
      if (has(token, "text")) return token.text;
      const value = params[token.name];
      switch (entry.parameters[token.name]) {
        case "number":
          return new Intl.NumberFormat(displayLocale, {}).format(value);
        case "date":
          return new Intl.DateTimeFormat(displayLocale, {
            timeZone: "UTC",
            year: "numeric",
            month: "short",
            day: "numeric",
          }).format(new Date(value));
        default:
          return value;
      }
    })
    .join("");
}

function buildRegistry(records, fields) {
  const result = new Map();
  for (const record of records) {
    if (
      !object(record) ||
      fields.some((key) =>
        key === "status"
          ? !Number.isInteger(record[key]) || record[key] < 100 || record[key] > 599
          : typeof record[key] !== "string" || !record[key],
      ) ||
      typeof record.id !== "string" ||
      !ID.test(record.id)
    )
      throw new TypeError("Invalid presentation mapping");
    const key = JSON.stringify(fields.map((field) => record[field]));
    if (result.has(key)) throw new TypeError("Duplicate presentation mapping");
    result.set(key, record.id);
  }
  return result;
}

export function createLocalizationRuntime({
  catalogues = {},
  storage = null,
  onDiagnostic = (code) => console.warn("Localization diagnostic:", code),
  eventMappings = [],
  errorMappings = [],
} = {}) {
  const events = buildRegistry(eventMappings, ["workflow", "stage", "message"]);
  const errors = buildRegistry(errorMappings, [
    "endpoint",
    "method",
    "status",
    "message",
  ]);
  const listeners = new Set();
  function available(value) {
    const selected = canonicalLocale(value);
    if (selected === "en-CA") return selected;
    const french = catalogues["fr-CA"];
    const english = catalogues["en-CA"];
    return object(english) &&
      english.schema_version === VERSION &&
      english.locale === "en-CA" &&
      object(english.messages) &&
      object(french) &&
      french.schema_version === VERSION &&
      french.locale === "fr-CA" &&
      object(french.messages) &&
      typeof french.revision === "string" &&
      french.revision.length > 0 &&
      french.revision === english?.revision
      ? selected
      : "en-CA";
  }
  let locale = "en-CA";
  try {
    locale = available(storage?.getItem(LOCALE_STORAGE_KEY));
  } catch {
    /* Storage is optional. */
  }
  function diagnose(code) {
    try {
      onDiagnostic(code);
    } catch {
      /* Diagnostics cannot break rendering. */
    }
  }
  function translate(id, params = {}) {
    try {
      if (typeof id !== "string" || !ID.test(id)) throw new TypeError("Invalid ID");
      const english = getEntry(catalogues, "en-CA", id);
      if (!english) throw new TypeError("Missing English entry");
      const expected = signature(english, "en-CA");
      if (!validArguments(english, params)) throw new TypeError("Invalid arguments");
      let entry = english;
      let grammar = "en-CA";
      if (locale === "fr-CA") {
        try {
          const candidate = getEntry(catalogues, "fr-CA", id);
          if (
            candidate &&
            catalogues["fr-CA"].revision === catalogues["en-CA"].revision &&
            signature(candidate, "fr-CA") === expected
          ) {
            entry = candidate;
            grammar = "fr-CA";
          } else diagnose("invalid-translation");
        } catch {
          diagnose("invalid-translation");
        }
      }
      return renderEntry(entry, grammar, locale, params);
    } catch {
      diagnose("message-fallback");
      return FALLBACK;
    }
  }
  function presentation(map, fields, context, heading) {
    const original = typeof context?.message === "string" ? context.message : "";
    const key = JSON.stringify(fields.map((field) => context?.[field]));
    const id = map.get(key);
    if (id) {
      const translated = translate(id);
      if (translated !== FALLBACK) return translated;
    }
    const title = translate(heading);
    const safeTitle =
      title === FALLBACK ? (heading.endsWith("error") ? "Error" : "Progress") : title;
    return original ? `${safeTitle}: ${original}` : safeTitle;
  }
  return {
    get locale() {
      return locale;
    },
    setLocale(value) {
      locale = available(value);
      try {
        storage?.setItem(LOCALE_STORAGE_KEY, locale);
      } catch {
        /* Keep the page selection. */
      }
      for (const listener of listeners) {
        try {
          listener(locale);
        } catch {
          diagnose("render-failure");
        }
      }
      return locale;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    translate,
    renderText(element, id, params = {}) {
      const render = () => {
        element.textContent = translate(id, params);
      };
      render();
      return this.subscribe(render);
    },
    presentEvent(context) {
      return presentation(
        events,
        ["workflow", "stage", "message"],
        context,
        "web.fallback.progress",
      );
    },
    presentError(context) {
      return presentation(
        errors,
        ["endpoint", "method", "status", "message"],
        context,
        "web.fallback.error",
      );
    },
    formatNumber(value, options) {
      try {
        if (typeof value !== "number" || !Number.isFinite(value) || !object(options))
          throw new TypeError("Invalid number formatting input");
        return new Intl.NumberFormat(locale, options).format(value);
      } catch {
        diagnose("format-failure");
        return FALLBACK;
      }
    },
    formatDate(value, options) {
      try {
        if (
          !validDate(value) ||
          !object(options) ||
          typeof options.timeZone !== "string" ||
          !options.timeZone
        )
          throw new TypeError("Invalid date formatting input");
        return new Intl.DateTimeFormat(locale, options).format(new Date(value));
      } catch {
        diagnose("format-failure");
        return FALLBACK;
      }
    },
  };
}
