import { createLocalizationRuntime } from "./localization.mjs";

// Increment when the identity or meaning of a registered presentation changes.
export const PRESENTATION_REGISTRY_VERSION = 4;

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
        workflow: "small_area",
        stage: "validating",
        message: "Validating uploaded linked candidates",
        id: "web.smallarea.event01",
      },
      {
        workflow: "small_area",
        stage: "recoding",
        message: "Grouping candidate household sizes",
        id: "web.smallarea.event02",
      },
      {
        workflow: "small_area",
        stage: "calibrating",
        message: "Fitting candidates to small-area controls",
        id: "web.smallarea.event03",
      },
      {
        workflow: "small_area",
        stage: "mapping",
        message: "Rendering the standalone small-area map",
        id: "web.smallarea.event04",
      },
      {
        workflow: "small_area",
        stage: "completed",
        message: "Small-area synthesis completed",
        id: "web.smallarea.event05",
      },
      {
        workflow: "small_area",
        stage: "prepared-calibration",
        message: "Screening the linked candidate pool for the full control set",
        id: "web.smallarea.event06",
      },
      {
        workflow: "small_area",
        stage: "prepared-calibration",
        message: "Calibrating the prepared geography batch",
        id: "web.smallarea.event07",
      },
      {
        workflow: "small_area",
        stage: "prepared-calibration",
        message: "Combining assigned rows and validating household/person linkage",
        id: "web.smallarea.event08",
      },
      {
        workflow: "small_area",
        stage: "prepared-calibration",
        message: "Independently auditing every realized control cell",
        id: "web.smallarea.event09",
      },
      {
        workflow: "small_area",
        stage: "interrupted",
        message: "Run interrupted by application restart",
        id: "web.smallarea.event10",
      },
      {
        workflow: "small_area",
        stage: "interrupted",
        message: "Job manager shut down",
        id: "web.smallarea.event11",
      },
      {
        workflow: "small_area",
        stage: "queued",
        message: "Run queued",
        id: "web.ipf.event.queued",
      },
      {
        workflow: "small_area",
        stage: "running",
        message: "Worker process started",
        id: "web.ipf.event.started",
      },
      {
        workflow: "small_area",
        stage: "cancelling",
        message: "Cancellation requested",
        id: "web.ipf.event.cancelling",
      },
      {
        workflow: "small_area",
        stage: "cancelled",
        message: "Queued run cancelled",
        id: "web.ipf.event.cancelledqueued",
      },
      {
        workflow: "small_area",
        stage: "cancelled",
        message: "Run cancelled",
        id: "web.ipf.event.cancelled",
      },
      {
        workflow: "small_area",
        stage: "succeeded",
        message: "Run completed",
        id: "web.ipf.event.succeeded",
      },
      {
        workflow: "small_area",
        stage: "failed",
        message: "Worker timed out",
        id: "web.ipf.event.timedout",
      },
      {
        workflow: "small_area",
        stage: "failed",
        message: "Worker exited unexpectedly",
        id: "web.ipf.event.exited",
      },

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
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching Statistics Canada CT geography. Select the same Census vintage and geography as the pack.",
        id: "web.smallarea.conditional01",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching built-in broad pack. Choose compatible packs for the same Census vintage and geography.",
        id: "web.smallarea.conditional02",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Each conditional pack requires its matching source upload. Upload the source for every selected pack.",
        id: "web.smallarea.conditional03",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Conditional controls require person controls and an explicit Census geography. Supply both before continuing.",
        id: "web.smallarea.conditional04",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The selected source is not the expected Census Profile tract CSV or ZIP. Upload the source for the selected Census vintage and pack.",
        id: "web.smallarea.conditional05",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Conditional and person controls have incompatible private-household denominators. Check their source, geography, and Census vintage.",
        id: "web.smallarea.conditional06",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Conditional source counts exceed the permitted Census rounding envelope. Check the source counts and selected geography.",
        id: "web.smallarea.conditional07",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "A required conditional source count is suppressed or unavailable. Choose an area with published controls or omit the affected pack.",
        id: "web.smallarea.conditional08",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The conditional source contains duplicate rows or cells. Check the uploaded source for the selected geography.",
        id: "web.smallarea.conditional09",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Required conditional source rows or fields are missing. Check the uploaded source and selected geography.",
        id: "web.smallarea.conditional10",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "A required Census Profile row is unavailable or invalid. Check the source counts and choose an area with published controls.",
        id: "web.smallarea.conditional11",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "A Census Profile count is not rounded to base five. Check that the uploaded source contains the expected published counts.",
        id: "web.smallarea.conditional12",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack is not recognized. Choose a listed pack for the desired Census vintage and geography.",
        id: "web.smallarea.conditional13",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Conditional and person control geographies differ. Supply controls covering the same geographies.",
        id: "web.smallarea.conditional14",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "The under-15 conditional target is incompatible with the person controls. Check their age totals and source evidence.",
        id: "web.smallarea.conditional15",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Eligible category targets must sum to the age-15+ denominator. Check the conditional control counts and source evidence.",
        id: "web.smallarea.conditional16",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unsupported eligible category. Check the candidate fields and the pack crosswalk.",
        id: "web.smallarea.conditional17",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unknown age category. Check the age field and the pack crosswalk.",
        id: "web.smallarea.conditional18",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message:
          "Conditional controls could not be validated. Check the selected packs, source data, geography, and candidate support; use the CLI for detailed diagnostics.",
        id: "web.smallarea.conditional19",
      },
      {
        endpoint: "/api/runs",
        method: "POST",
        status: 400,
        message: "run preflight has blocking diagnostics",
        id: "web.smallarea.runblocked",
      },

      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Restart inputs changed during preflight; create a new run.",
        id: "web.smallarea.restart07",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "The prior model path is invalid; create a new run.",
        id: "web.smallarea.restart08",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "The prior model cannot be verified; create a new run.",
        id: "web.smallarea.restart09",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "The model has changed since the interrupted run; create a new run.",
        id: "web.smallarea.restart10",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "The run input directory is invalid; create a new run.",
        id: "web.smallarea.restart11",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Run input path is invalid; create a new run.",
        id: "web.smallarea.restart12",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Run has duplicate input identifiers.",
        id: "web.smallarea.restart13",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Run inputs have changed; create a new run.",
        id: "web.smallarea.restart14",
      },

      {
        endpoint: "run:small_area",
        method: "EVENT",
        status: 409,
        message: "Run interrupted.",
        id: "web.smallarea.interrupted",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching Statistics Canada CT geography. Select the same Census vintage and geography as the pack.",
        id: "web.smallarea.conditional01",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching Statistics Canada CT geography. Select the same Census vintage and geography as the pack.",
        id: "web.smallarea.conditional01",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching built-in broad pack. Choose compatible packs for the same Census vintage and geography.",
        id: "web.smallarea.conditional02",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack requires its matching built-in broad pack. Choose compatible packs for the same Census vintage and geography.",
        id: "web.smallarea.conditional02",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Each conditional pack requires its matching source upload. Upload the source for every selected pack.",
        id: "web.smallarea.conditional03",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Each conditional pack requires its matching source upload. Upload the source for every selected pack.",
        id: "web.smallarea.conditional03",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Conditional controls require person controls and an explicit Census geography. Supply both before continuing.",
        id: "web.smallarea.conditional04",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Conditional controls require person controls and an explicit Census geography. Supply both before continuing.",
        id: "web.smallarea.conditional04",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The selected source is not the expected Census Profile tract CSV or ZIP. Upload the source for the selected Census vintage and pack.",
        id: "web.smallarea.conditional05",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The selected source is not the expected Census Profile tract CSV or ZIP. Upload the source for the selected Census vintage and pack.",
        id: "web.smallarea.conditional05",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Conditional and person controls have incompatible private-household denominators. Check their source, geography, and Census vintage.",
        id: "web.smallarea.conditional06",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Conditional and person controls have incompatible private-household denominators. Check their source, geography, and Census vintage.",
        id: "web.smallarea.conditional06",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Conditional source counts exceed the permitted Census rounding envelope. Check the source counts and selected geography.",
        id: "web.smallarea.conditional07",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Conditional source counts exceed the permitted Census rounding envelope. Check the source counts and selected geography.",
        id: "web.smallarea.conditional07",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "A required conditional source count is suppressed or unavailable. Choose an area with published controls or omit the affected pack.",
        id: "web.smallarea.conditional08",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "A required conditional source count is suppressed or unavailable. Choose an area with published controls or omit the affected pack.",
        id: "web.smallarea.conditional08",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The conditional source contains duplicate rows or cells. Check the uploaded source for the selected geography.",
        id: "web.smallarea.conditional09",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The conditional source contains duplicate rows or cells. Check the uploaded source for the selected geography.",
        id: "web.smallarea.conditional09",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Required conditional source rows or fields are missing. Check the uploaded source and selected geography.",
        id: "web.smallarea.conditional10",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Required conditional source rows or fields are missing. Check the uploaded source and selected geography.",
        id: "web.smallarea.conditional10",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "A required Census Profile row is unavailable or invalid. Check the source counts and choose an area with published controls.",
        id: "web.smallarea.conditional11",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "A required Census Profile row is unavailable or invalid. Check the source counts and choose an area with published controls.",
        id: "web.smallarea.conditional11",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "A Census Profile count is not rounded to base five. Check that the uploaded source contains the expected published counts.",
        id: "web.smallarea.conditional12",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "A Census Profile count is not rounded to base five. Check that the uploaded source contains the expected published counts.",
        id: "web.smallarea.conditional12",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack is not recognized. Choose a listed pack for the desired Census vintage and geography.",
        id: "web.smallarea.conditional13",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The selected conditional pack is not recognized. Choose a listed pack for the desired Census vintage and geography.",
        id: "web.smallarea.conditional13",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Conditional and person control geographies differ. Supply controls covering the same geographies.",
        id: "web.smallarea.conditional14",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Conditional and person control geographies differ. Supply controls covering the same geographies.",
        id: "web.smallarea.conditional14",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "The under-15 conditional target is incompatible with the person controls. Check their age totals and source evidence.",
        id: "web.smallarea.conditional15",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "The under-15 conditional target is incompatible with the person controls. Check their age totals and source evidence.",
        id: "web.smallarea.conditional15",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Eligible category targets must sum to the age-15+ denominator. Check the conditional control counts and source evidence.",
        id: "web.smallarea.conditional16",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Eligible category targets must sum to the age-15+ denominator. Check the conditional control counts and source evidence.",
        id: "web.smallarea.conditional16",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unsupported eligible category. Check the candidate fields and the pack crosswalk.",
        id: "web.smallarea.conditional17",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unsupported eligible category. Check the candidate fields and the pack crosswalk.",
        id: "web.smallarea.conditional17",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unknown age category. Check the age field and the pack crosswalk.",
        id: "web.smallarea.conditional18",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Candidate people contain an unknown age category. Check the age field and the pack crosswalk.",
        id: "web.smallarea.conditional18",
      },
      {
        endpoint: "/api/preflight",
        method: "POST",
        status: 400,
        message:
          "Conditional controls could not be validated. Check the selected packs, source data, geography, and candidate support; use the CLI for detailed diagnostics.",
        id: "web.smallarea.conditional19",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Conditional controls could not be validated. Check the selected packs, source data, geography, and candidate support; use the CLI for detailed diagnostics.",
        id: "web.smallarea.conditional19",
      },

      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Only interrupted small-area runs can be restarted.",
        id: "web.smallarea.restart01",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "The run used a different SynthPopCan version; create a new run.",
        id: "web.smallarea.restart02",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Run evidence or inputs have changed; create a new run.",
        id: "web.smallarea.restart03",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Saved inputs no longer pass preflight; create a new run and check the controls and candidate support.",
        id: "web.smallarea.restart04",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message: "Not enough workspace capacity to restart this run.",
        id: "web.smallarea.restart05",
      },
      {
        endpoint: "/api/runs/:id/restart",
        method: "POST",
        status: 400,
        message:
          "Could not restart this run. Check its state and input integrity, or create a new run.",
        id: "web.smallarea.restart06",
      },

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
