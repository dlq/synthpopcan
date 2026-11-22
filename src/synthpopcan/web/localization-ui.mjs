import { createLocalizationRuntime } from "./localization.mjs";

// Increment when the identity or meaning of a registered presentation changes.
export const PRESENTATION_REGISTRY_VERSION = 3;

let activeRuntime = null;
const errorViews = new Map();

export function getLocalizationRuntime() {
  return activeRuntime;
}

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
        workflow: "model",
        stage: "checking-model",
        message: "Checking package provenance and privacy",
        id: "web.model.event.checking",
      },
      {
        workflow: "model",
        stage: "validating",
        message: "Validating household and person linkage",
        id: "web.model.event.validating",
      },
      {
        workflow: "model",
        stage: "completed",
        message: "Prepared-model generation completed",
        id: "web.model.event.completed",
      },
      {
        workflow: "model",
        stage: "queued",
        message: "Run queued",
        id: "web.ipf.event.queued",
      },
      {
        workflow: "model",
        stage: "running",
        message: "Worker process started",
        id: "web.ipf.event.started",
      },
      {
        workflow: "model",
        stage: "cancelling",
        message: "Cancellation requested",
        id: "web.ipf.event.cancelling",
      },
      {
        workflow: "model",
        stage: "cancelled",
        message: "Queued run cancelled",
        id: "web.ipf.event.cancelledqueued",
      },
      {
        workflow: "model",
        stage: "cancelled",
        message: "Run cancelled",
        id: "web.ipf.event.cancelled",
      },
      {
        workflow: "model",
        stage: "succeeded",
        message: "Run completed",
        id: "web.ipf.event.succeeded",
      },
      {
        workflow: "model",
        stage: "failed",
        message: "Worker timed out",
        id: "web.ipf.event.timedout",
      },
      {
        workflow: "model",
        stage: "failed",
        message: "Worker exited unexpectedly",
        id: "web.ipf.event.exited",
      },
      {
        workflow: "ipf",
        stage: "reading-inputs",
        message: "Reading seed records and controls",
        id: "web.ipf.reading",
      },
      {
        workflow: "ipf",
        stage: "fitting",
        message: "Fitting seed weights to control margins",
        id: "web.ipf.fitting",
      },
      {
        workflow: "ipf",
        stage: "writing-report",
        message: "Writing IPF fit diagnostics",
        id: "web.ipf.report",
      },
      {
        workflow: "ipf",
        stage: "writing-artifacts",
        message: "Writing compact fitted weights",
        id: "web.ipf.writing",
      },
      {
        workflow: "ipf",
        stage: "completed",
        message: "IPF fitting completed",
        id: "web.ipf.completed",
      },
      {
        workflow: "ipf",
        stage: "queued",
        message: "Run queued",
        id: "web.ipf.event.queued",
      },
      {
        workflow: "ipf",
        stage: "running",
        message: "Worker process started",
        id: "web.ipf.event.started",
      },
      {
        workflow: "ipf",
        stage: "cancelling",
        message: "Cancellation requested",
        id: "web.ipf.event.cancelling",
      },
      {
        workflow: "ipf",
        stage: "cancelled",
        message: "Queued run cancelled",
        id: "web.ipf.event.cancelledqueued",
      },
      {
        workflow: "ipf",
        stage: "cancelled",
        message: "Run cancelled",
        id: "web.ipf.event.cancelled",
      },
      {
        workflow: "ipf",
        stage: "succeeded",
        message: "Run completed",
        id: "web.ipf.event.succeeded",
      },
      {
        workflow: "ipf",
        stage: "failed",
        message: "Worker timed out",
        id: "web.ipf.event.timedout",
      },
      {
        workflow: "ipf",
        stage: "failed",
        message: "Worker exited unexpectedly",
        id: "web.ipf.event.exited",
      },
    ],
    errorMappings: [
      {
        endpoint: "/api/models/:id/install",
        method: "POST",
        status: 502,
        message: "model download failed",
        id: "web.model.error.download",
      },
      {
        endpoint: "/api/models/:id/install",
        method: "POST",
        status: 502,
        message: "model package failed validation",
        id: "web.model.error.validation",
      },
      {
        endpoint: "/api/models/:id/install",
        method: "POST",
        status: 404,
        message: "Unknown model",
        id: "web.model.error.unknown",
      },
      {
        endpoint: "/api/models/:id",
        method: "DELETE",
        status: 404,
        message: "Unknown model",
        id: "web.model.error.unknown",
      },
      {
        endpoint: "client:model",
        method: "VALIDATE",
        status: 400,
        message: "Choose a catalogue model or package JSON.",
        id: "web.model.error.selection",
      },
      {
        endpoint: "client:model",
        method: "VALIDATE",
        status: 400,
        message: "Conditions must use name=value pairs.",
        id: "web.model.error.conditions",
      },
      {
        endpoint: "/api/uploads",
        method: "POST",
        status: 400,
        message: "upload is invalid",
        id: "web.upload.invalid",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message: "preflight request is invalid",
        id: "web.ipf.error.preflight",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message: "IPF preflight has blocking input diagnostics",
        id: "web.ipf.error.blocked",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message: "run request is invalid",
        id: "web.ipf.error.run",
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
  // Preserve the original English content if a catalogue is unavailable.
  for (const element of document.querySelectorAll("[data-i18n]")) {
    const original = element.textContent;
    const render = () => {
      const translated = runtime.translate(element.dataset.i18n);
      element.textContent =
        translated === "Message unavailable." ? original : translated;
    };
    render();
    runtime.subscribe(render);
  }
  for (const element of document.querySelectorAll("[data-i18n-aria-label]")) {
    const original = element.getAttribute("aria-label");
    const render = () => {
      const translated = runtime.translate(element.dataset.i18nAriaLabel);
      element.setAttribute(
        "aria-label",
        translated === "Message unavailable." ? original : translated,
      );
    };
    render();
    runtime.subscribe(render);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    const original = element.getAttribute("placeholder");
    const render = () => {
      const translated = runtime.translate(element.dataset.i18nPlaceholder);
      element.setAttribute(
        "placeholder",
        translated === "Message unavailable." ? original : translated,
      );
    };
    render();
    runtime.subscribe(render);
  }
  select.value = runtime.locale;
  document.documentElement.lang = runtime.locale;
  select.addEventListener("change", () => {
    select.value = runtime.setLocale(select.value);
    document.documentElement.lang = runtime.locale;
  });
  return runtime;
}
