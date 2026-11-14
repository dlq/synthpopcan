import { createLocalizationRuntime } from "./localization.mjs";

// Increment when the identity or meaning of a registered presentation changes.
export const PRESENTATION_REGISTRY_VERSION = 1;

let activeRuntime = null;
const errorViews = new Map();

export function presentWebError(error) {
  const message = error instanceof Error ? error.message : String(error);
  if (!activeRuntime) return message;
  return activeRuntime.presentError({ ...error?.presentationContext, message });
}

export function clearWebError(element) {
  errorViews.delete(element);
}

export function renderWebError(element, error) {
  errorViews.set(element, error);
  element.textContent = presentWebError(error);
}

/** Initialize the small draft catalogue; uncovered interfaces remain English. */
export async function initializeLocalization() {
  const catalogues = {};
  await Promise.all(
    ["en-CA", "fr-CA"].map(async (locale) => {
      try {
        const response = await fetch(`./messages.${locale}.json`);
        if (response.ok) catalogues[locale] = await response.json();
      } catch {
        // Missing catalogue files must not prevent the app from starting.
      }
    }),
  );
  let storage = null;
  try {
    storage = window.localStorage;
  } catch {
    // A browser may forbid even accessing localStorage.
  }
  const runtime = createLocalizationRuntime({
    catalogues,
    storage,
    eventMappings: [
      {
        workflow: "ipf",
        stage: "reading-inputs",
        message: "Reading seed records and controls",
        id: "web.ipf.reading",
      },
    ],
    errorMappings: [
      {
        endpoint: "/api/uploads",
        method: "POST",
        status: 400,
        message: "upload is invalid",
        id: "web.upload.invalid",
      },
    ],
  });
  activeRuntime = runtime;
  runtime.subscribe(() => {
    for (const [element, error] of errorViews) {
      if (!element.isConnected) errorViews.delete(element);
      else element.textContent = presentWebError(error);
    }
  });
  const select = document.querySelector("#web-locale");
  const label = document.querySelector("#web-locale-label");
  const notice = document.querySelector("#web-locale-notice");
  // Keep the built-in English labels usable if a catalogue cannot be loaded.
  if (runtime.translate("web.language.label") !== "Message unavailable.") {
    runtime.renderText(label, "web.language.label");
  }
  if (runtime.translate("web.language.coverage") !== "Message unavailable.") {
    runtime.renderText(notice, "web.language.coverage");
  }
  select.value = runtime.locale;
  document.documentElement.lang = runtime.locale;
  select.addEventListener("change", () => {
    select.value = runtime.setLocale(select.value);
    document.documentElement.lang = runtime.locale;
  });
  return runtime;
}
