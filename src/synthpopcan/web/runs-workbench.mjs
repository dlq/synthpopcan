import { stringifyCsv } from "./csv.mjs";
import { numberValue, optionalNumberValue } from "./form-utils.mjs";
import { ApiError } from "./http.mjs";
import { IPF_MESSAGE_IDS } from "./ipf-messages.mjs";
import { clearWebError, renderWebError } from "./localization-ui.mjs";
import { MODEL_MESSAGE_IDS } from "./model-messages.mjs";
import { createOperationSequencer } from "./operation-sequencer.mjs";
import {
  artifactUrl,
  cancelRun,
  createRun,
  getRun,
  listRuns,
  preflightRun,
  previewArtifact,
  restartRun,
  uploadCsv,
} from "./run-api.mjs";
import { followRunEvents } from "./run-events.mjs";
import { localizedStatus, renderRunList } from "./run-list.mjs";
import {
  buildIpfRequest,
  buildModelOptions,
  buildModelRequest,
  fileLabel,
  ipfPreflightView,
  ModelConditionError,
  modelPreflightItems,
  presentIpfProblems,
  runResultView,
  workflowTitle,
} from "./run-workbench-model.mjs";
import { SMALL_AREA_MESSAGE_IDS } from "./small-area-messages.mjs";
import { buildAgeSexControlRows, buildAgeSexSeedRows } from "./starter-files.mjs";

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
let presentationRuntime = null;
const localizedViews = new Map();
let ipfDiagnosticRenderer = null;

function translateOwned(id, fallback, params = {}) {
  const result = presentationRuntime?.translate(id, params);
  return !result || result === "Message unavailable." ? fallback : result;
}

function setOwnedText(element, text) {
  const id = Object.hasOwn(SMALL_AREA_MESSAGE_IDS, text)
    ? SMALL_AREA_MESSAGE_IDS[text]
    : Object.hasOwn(MODEL_MESSAGE_IDS, text)
      ? MODEL_MESSAGE_IDS[text]
      : Object.hasOwn(IPF_MESSAGE_IDS, text)
        ? IPF_MESSAGE_IDS[text]
        : null;
  if (id) localizedViews.set(element, { id, text });
  else localizedViews.delete(element);
  element.textContent = id ? translateOwned(id, text) : text;
}

export function bindRunsWorkbench(bootstrap, localization) {
  presentationRuntime = localization;
  const state = {
    runs: [],
    selectedRun: null,
    workflow: "ipf",
    uploads: null,
    preflight: null,
    stopEvents: null,
    viewRevision: 0,
    operations: createOperationSequencer(),
    eventViews: [],
    localization,
  };
  localization.subscribe(() => {
    ipfDiagnosticRenderer?.();
    for (const [element, view] of localizedViews) {
      if (!element.isConnected) localizedViews.delete(element);
      else element.textContent = translateOwned(view.id, view.text, view.params);
    }
    const status = document.querySelector("#run-status").dataset.status;
    if (status) setRunStatus(status);
    for (const view of state.eventViews) {
      view.element.textContent = localization.presentEvent(view.context);
    }
    for (const link of document.querySelectorAll("[data-artifact-filename]")) {
      const filename = link.dataset.artifactFilename;
      link.textContent = translateOwned("web.ipfui.download", `Download ${filename}`, {
        filename,
      });
    }
    renderModelOptions();
  });
  setRunStatus(document.querySelector("#run-status").dataset.status);
  document.querySelector("#workspace-location").textContent = bootstrap.workspace;
  document.querySelector("#new-run").addEventListener("click", () => newDraft(state));
  document
    .querySelector("#use-demo-ipf")
    .addEventListener("click", () => useDemoFiles(state));
  document.querySelector("#start-model-workflow").addEventListener("click", () => {
    invalidateDraftOperations(state);
    state.workflow = "model";
    setRunHeading(
      "New durable run",
      "Generate from a prepared model",
      "draft",
      "model",
    );
    showStep("model-inputs");
    showMessage("", "");
  });
  document
    .querySelector("#ipf-seed-file")
    .addEventListener("change", () => filesChanged(state));
  document
    .querySelector("#ipf-controls-file")
    .addEventListener("change", () => filesChanged(state));
  document
    .querySelector("#upload-inputs")
    .addEventListener("click", () => uploadInputs(state));
  document
    .querySelector("#check-preflight")
    .addEventListener("click", () => checkPreflight(state));
  document
    .querySelector("#check-model-preflight")
    .addEventListener("click", () => checkModelPreflight(state));
  document.querySelector("#run-model-select").addEventListener("change", () => {
    state.operations.invalidate("model-install");
    invalidatePreflight(state);
    updateModelCatalogueActions();
  });
  document
    .querySelector("#run-model-file")
    .addEventListener("change", () => invalidatePreflight(state));
  document
    .querySelector("#install-run-model")
    .addEventListener("click", () => changeModelInstallation(state, "install"));
  document
    .querySelector("#remove-run-model")
    .addEventListener("click", () => changeModelInstallation(state, "remove"));
  document.querySelector("#start-run").addEventListener("click", () => startRun(state));
  document
    .querySelector("#cancel-run")
    .addEventListener("click", () => requestCancel(state));
  document
    .querySelector("#restart-run")
    .addEventListener("click", () => requestRestart(state));
  document.querySelectorAll("[data-go-step]").forEach((button) => {
    button.addEventListener("click", () => {
      let step = button.dataset.goStep;
      if (step === "configure" && state.workflow === "model") step = "model-inputs";
      if (step === "inputs" && state.workflow === "model") {
        state.workflow = "ipf";
        setRunHeading("New durable run", "IPF from margin tables", "draft");
      }
      showStep(step);
    });
  });
  for (const selector of [
    "#ipf-weight-field",
    "#ipf-max-iterations",
    "#ipf-tolerance",
    "#ipf-allow-nonconverged",
    "#run-model-households",
    "#run-model-conditions",
    "#run-model-random-seed",
  ]) {
    document
      .querySelector(selector)
      .addEventListener("input", () => invalidatePreflight(state));
  }
  bindLegacyTools(state);
  document.addEventListener("synthpopcan:run-created", async (event) => {
    const viewRevision = state.viewRevision;
    await refreshRuns(state);
    const detail = event.detail?.run
      ? event.detail
      : { run: event.detail, select: true };
    if (detail.select && state.viewRevision === viewRevision)
      await selectRun(state, detail.run);
  });
  loadModelCatalogue(state);
  refreshRuns(state, true);
}

function bindLegacyTools(state) {
  document.querySelector("#small-area-back").addEventListener("click", showWorkbench);
  document.querySelectorAll("[data-workflow-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      invalidateWorkbenchViewOperations(state);
      state.viewRevision += 1;
      state.stopEvents?.();
      state.stopEvents = null;
      const name = button.dataset.workflowTab;
      document.querySelector(".workbench").hidden = true;
      document.querySelectorAll("[data-workflow-panel]").forEach((panel) => {
        const active = panel.dataset.workflowPanel === name;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      });
    });
  });
}

async function refreshRuns(state, selectNewest = false) {
  const operation = state.operations.begin("runs-list");
  const viewRevision = state.viewRevision;
  try {
    const runs = (await listRuns()).runs;
    if (!operation.isCurrent()) return;
    state.runs = runs;
    renderRunList(
      document.querySelector("#runs-list"),
      state.runs,
      state.selectedRun?.run_id,
      (run) => selectRun(state, run),
    );
    if (selectNewest && state.runs.length > 0 && state.viewRevision === viewRevision)
      await selectRun(state, state.runs[0]);
  } catch (error) {
    if (operation.isCurrent()) showErrorMessage(error);
  }
}

function newDraft(state) {
  invalidateWorkbenchViewOperations(state);
  state.viewRevision += 1;
  showWorkbench();
  state.stopEvents?.();
  state.stopEvents = null;
  state.selectedRun = null;
  state.eventViews = [];
  document.querySelector("#restart-run").hidden = true;
  state.workflow = "ipf";
  state.uploads = null;
  state.preflight = null;
  for (const id of ["#ipf-seed-file", "#ipf-controls-file"])
    document.querySelector(id).value = "";
  filesChanged(state);
  setRunHeading("New durable run", "IPF from margin tables", "Draft");
  clearResults();
  showMessage("", "");
  showStep("inputs");
  renderRunList(document.querySelector("#runs-list"), state.runs, null, (run) =>
    selectRun(state, run),
  );
}

function invalidateWorkbenchViewOperations(state) {
  for (const name of [
    "runs-list",
    "follow-run",
    "results",
    "cancel-run",
    "restart-run",
    "model-install",
  ])
    state.operations.invalidate(name);
  invalidateDraftOperations(state);
}

function useDemoFiles(state) {
  const seed = new File(
    [stringifyCsv(buildAgeSexSeedRows())],
    "demo-age-sex-seed.csv",
    { type: "text/csv" },
  );
  const controls = new File(
    [stringifyCsv(buildAgeSexControlRows())],
    "demo-age-sex-controls.csv",
    { type: "text/csv" },
  );
  setInputFiles("#ipf-seed-file", [seed]);
  setInputFiles("#ipf-controls-file", [controls]);
  filesChanged(state);
  showMessage("Demo files are ready to upload.", "success");
}

function setInputFiles(selector, files) {
  const transfer = new DataTransfer();
  for (const file of files) transfer.items.add(file);
  document.querySelector(selector).files = transfer.files;
}

function filesChanged(state) {
  state.operations.invalidate("upload");
  state.uploads = null;
  invalidatePreflight(state);
  if (document.querySelector("#workbench-message").dataset.phase === "uploading")
    showMessage("Files changed. Upload the current pair to continue.", "warning");
  const seed = document.querySelector("#ipf-seed-file").files?.[0];
  const controls = document.querySelector("#ipf-controls-file").files?.[0];
  setOwnedText(document.querySelector("#seed-upload-status"), fileLabel(seed));
  setOwnedText(document.querySelector("#controls-upload-status"), fileLabel(controls));
  document.querySelector("#upload-inputs").disabled = !(seed && controls);
}

async function uploadInputs(state) {
  const operation = state.operations.begin("upload");
  const button = document.querySelector("#upload-inputs");
  button.disabled = true;
  showMessage("Streaming the two CSV files into the local workspace…", "", "uploading");
  const seedFile = document.querySelector("#ipf-seed-file").files[0];
  const controlsFile = document.querySelector("#ipf-controls-file").files[0];
  try {
    const [seed, controls] = await Promise.all([
      uploadCsv(seedFile),
      uploadCsv(controlsFile),
    ]);
    if (!operation.isCurrent()) return;
    state.uploads = { seed, controls };
    showMessage("Inputs uploaded and fingerprinted.", "success");
    showStep("configure");
  } catch (error) {
    if (!operation.isCurrent()) return;
    showErrorMessage(error);
    button.disabled = false;
  }
}

function invalidateDraftOperations(state) {
  state.operations.invalidate("upload");
  state.uploads = null;
  invalidatePreflight(state);
}

function invalidatePreflight(state) {
  state.operations.invalidate("preflight");
  state.operations.invalidate("start-run");
  state.preflight = null;
  document.querySelector("#start-run").disabled = true;
  document.querySelector("#check-model-preflight").disabled = false;
  if (
    ipfDiagnosticRenderer ||
    document.querySelector("#workbench-message").dataset.phase === "preflight"
  )
    showMessage("Inputs changed. Check the current settings again.", "warning");
}

function buildRequest(state) {
  return buildIpfRequest({
    uploads: state.uploads,
    weightColumn: document.querySelector("#ipf-weight-field").value.trim(),
    maxIterations: numberValue("#ipf-max-iterations"),
    tolerance: numberValue("#ipf-tolerance"),
    allowNonconverged: document.querySelector("#ipf-allow-nonconverged").checked,
  });
}

async function checkPreflight(state) {
  const operation = state.operations.begin("preflight");
  showMessage("Checking input structure and workspace capacity…", "", "preflight");
  try {
    const request = buildRequest(state);
    const preflight = await preflightRun(request);
    if (!operation.isCurrent()) return;
    state.preflight = preflight;
    const problems = renderPreflight(preflight);
    document.querySelector("#start-run").disabled = !preflight.ready;
    showStep("preflight");
    if (preflight.ready) {
      showMessage("Preflight passed. The run is ready to start.", "success");
    } else if (problems.length === 0) {
      showMessage("Preflight found a workspace capacity problem.", "error");
    }
  } catch (error) {
    if (operation.isCurrent()) showErrorMessage(error);
  }
}

async function checkModelPreflight(state) {
  const operation = state.operations.begin("preflight");
  showMessage(
    "Checking package provenance, privacy, and output scale…",
    "",
    "preflight",
  );
  const button = document.querySelector("#check-model-preflight");
  button.disabled = true;
  try {
    const draft = snapshotModelDraft();
    let inputs;
    if (draft.file) {
      const uploaded = await uploadCsv(draft.file);
      if (!operation.isCurrent()) return;
      state.uploads = { package: uploaded };
      inputs = { package_upload_id: uploaded.upload_id };
    } else {
      inputs = { model_id: draft.modelId };
    }
    const preflight = await preflightRun(buildModelRequest(inputs, draft.options));
    if (!operation.isCurrent()) return;
    state.workflow = "model";
    state.preflight = preflight;
    renderModelPreflight(preflight);
    document.querySelector("#start-run").disabled = !preflight.ready;
    showStep("preflight");
    showMessage(
      preflight.ready
        ? "Model preflight passed. Provenance and privacy metadata are recorded."
        : "Model preflight found a blocking scale problem.",
      preflight.ready ? "success" : "error",
    );
  } catch (error) {
    if (operation.isCurrent()) {
      if (
        error instanceof ModelConditionError ||
        error instanceof ModelSelectionError
      ) {
        error.presentationContext = {
          endpoint: "client:model",
          method: "VALIDATE",
          status: 400,
        };
      }
      showErrorMessage(error);
    }
  } finally {
    if (operation.isCurrent()) button.disabled = false;
  }
}

class ModelSelectionError extends Error {}

function snapshotModelDraft() {
  const file = document.querySelector("#run-model-file").files?.[0];
  const modelId = document.querySelector("#run-model-select").value;
  if (!file && !modelId)
    throw new ModelSelectionError("Choose a catalogue model or package JSON.");
  return {
    file,
    modelId,
    options: buildModelOptions({
      households: numberValue("#run-model-households"),
      conditions: document.querySelector("#run-model-conditions").value,
      randomSeed: optionalNumberValue("#run-model-random-seed"),
    }),
  };
}

function renderModelPreflight(preflight) {
  setOwnedText(
    document.querySelector("#preflight-intro"),
    "Review model provenance, privacy, supported conditions, and workspace capacity before starting.",
  );
  renderDiagnostics(
    document.querySelector("#preflight-results"),
    modelPreflightItems(preflight),
  );
}

function renderPreflight(preflight) {
  setOwnedText(
    document.querySelector("#preflight-intro"),
    "Review parsed records, control margins, expected output, and workspace capacity before starting.",
  );
  const { items, problems } = ipfPreflightView(preflight);
  renderDiagnostics(document.querySelector("#preflight-results"), items);
  if (problems.length) {
    showMessage("", "error");
    const element = document.querySelector("#workbench-message");
    ipfDiagnosticRenderer = () => {
      const localized = presentIpfProblems(
        preflight.input_diagnostics,
        (id, parameters) => presentationRuntime.translate(id, parameters),
      );
      element.textContent = localized.includes("Message unavailable.")
        ? problems.join(" ")
        : localized.join(" ");
    };
    ipfDiagnosticRenderer();
  }
  return problems;
}

async function startRun(state) {
  if (!state.preflight?.request) return;
  const operation = state.operations.begin("start-run");
  const request = structuredClone(state.preflight.request);
  document.querySelector("#start-run").disabled = true;
  showMessage("Creating the durable run…", "");
  try {
    const run = await createRun(request);
    if (!operation.isCurrent()) {
      await refreshRuns(state);
      return;
    }
    state.selectedRun = run;
    setRunHeading(
      "",
      workflowTitle(run.workflow),
      run.status,
      run.workflow,
      run.run_id.slice(-12),
    );
    showStep("run");
    showMessage("Run queued. You can safely refresh this page.", "success");
    await refreshRuns(state);
    if (!operation.isCurrent() || state.selectedRun?.run_id !== run.run_id) return;
    followRun(state, run.run_id);
  } catch (error) {
    if (!operation.isCurrent()) return;
    showErrorMessage(error);
    document.querySelector("#start-run").disabled = false;
  }
}

function followRun(state, runId) {
  const operation = state.operations.begin("follow-run");
  state.stopEvents?.();
  const events = document.querySelector("#progress-events");
  events.replaceChildren();
  state.eventViews = [];
  state.stopEvents = followRunEvents(runId, {
    onEvent: (event) => {
      if (operation.isCurrent() && state.selectedRun?.run_id === runId)
        appendProgressEvent(events, event, state, state.localization);
    },
    onReconnect: () => {
      if (operation.isCurrent() && state.selectedRun?.run_id === runId)
        document.querySelector("#run-progress").removeAttribute("value");
    },
    onTerminal: async (run) => {
      if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
      state.selectedRun = run;
      state.stopEvents = null;
      await refreshRuns(state);
      if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
      await showTerminalRun(state, run);
    },
  });
}

function appendProgressEvent(list, event, state, localization) {
  const item = document.createElement("li");
  const context = {
    workflow: state.selectedRun?.workflow,
    stage: event.stage,
    message: event.message,
  };
  item.textContent = localization.presentEvent(context);
  state.eventViews.push({ element: item, context });
  item.dataset.eventId = event.id;
  list.append(item);
  const progress = document.querySelector("#run-progress");
  if (event.completed != null && event.total)
    progress.value = (event.completed / event.total) * 100;
}

async function requestCancel(state) {
  if (!state.selectedRun) return;
  const runId = state.selectedRun.run_id;
  const operation = state.operations.begin("cancel-run");
  document.querySelector("#cancel-run").disabled = true;
  try {
    const run = await cancelRun(runId);
    if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
    state.selectedRun = run;
    setRunStatus(run.status);
    showMessage("Cancellation requested.", "warning");
  } catch (error) {
    if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
    showErrorMessage(error);
    document.querySelector("#cancel-run").disabled = false;
  }
}

async function requestRestart(state) {
  if (!state.selectedRun) return;
  const runId = state.selectedRun.run_id;
  const operation = state.operations.begin("restart-run");
  const button = document.querySelector("#restart-run");
  button.disabled = true;
  try {
    const run = await restartRun(runId);
    if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
    await refreshRuns(state);
    if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
    await selectRun(state, run);
  } catch (error) {
    if (!operation.isCurrent() || state.selectedRun?.run_id !== runId) return;
    if (error instanceof ApiError && error.presentationContext) {
      error.presentationContext.endpoint = "/api/runs/:id/restart";
    }
    showErrorMessage(error);
    button.disabled = false;
  }
}

async function selectRun(state, summary) {
  const viewRevision = state.viewRevision + 1;
  state.viewRevision = viewRevision;
  state.operations.invalidate("restart-run");
  state.operations.invalidate("follow-run");
  state.operations.invalidate("results");
  state.stopEvents?.();
  state.stopEvents = null;
  try {
    showWorkbench();
    const run = await getRun(summary.run_id);
    if (state.viewRevision !== viewRevision) return;
    state.selectedRun = run;
    document.querySelector("#restart-run").hidden = true;
    renderRunList(
      document.querySelector("#runs-list"),
      state.runs,
      run.run_id,
      (item) => selectRun(state, item),
    );
    state.workflow = run.workflow;
    setRunHeading(
      "",
      workflowTitle(run.workflow),
      run.status,
      run.workflow,
      run.run_id.slice(-12),
    );
    if (TERMINAL.has(run.status)) await showTerminalRun(state, run);
    else {
      document.querySelector("#cancel-run").disabled = run.status === "cancelling";
      showStep("run");
      showMessage("Reconnected to the durable run.", "success");
      followRun(state, run.run_id);
    }
  } catch (error) {
    if (state.viewRevision === viewRevision) showErrorMessage(error);
  }
}

async function showTerminalRun(state, run) {
  const operation = state.operations.begin("results");
  const isCurrent = () =>
    operation.isCurrent() && state.selectedRun?.run_id === run.run_id;
  if (!isCurrent()) return;
  setRunStatus(run.status);
  document.querySelector("#cancel-run").disabled = true;
  if (run.status !== "succeeded") {
    showStep("run");
    const restart = document.querySelector("#restart-run");
    restart.hidden = run.status !== "interrupted" || run.workflow !== "small_area";
    restart.disabled = false;
    const message = run.error?.message ?? `Run ${run.status}.`;
    const terminalError = new Error(message);
    if (run.workflow === "small_area" && run.status === "interrupted") {
      terminalError.presentationContext = {
        endpoint: "run:small_area",
        method: "EVENT",
        status: 409,
      };
    }
    showErrorMessage(terminalError, run.status === "cancelled" ? "warning" : "error");
    return;
  }
  showStep("results");
  showMessage("Run completed and persisted in the workspace.", "success");
  await showSucceededRun(run, isCurrent);
}

async function showSucceededRun(run, isCurrent) {
  const view = runResultView(run);
  if (view.warning) {
    showMessage("", "warning");
    const element = document.querySelector("#workbench-message");
    const presentation = {
      id: "web.smallarea.warning",
      text: view.warning,
      params: { count: run.summary.non_converged_count },
    };
    localizedViews.set(element, presentation);
    element.textContent = translateOwned(
      presentation.id,
      presentation.text,
      presentation.params,
    );
  }
  setOwnedText(
    document.querySelector("#results-intro"),
    view.intro ??
      "The completed run and its artifacts are stored in the local workspace.",
  );
  setOwnedText(document.querySelector("#preview-heading"), view.previewHeading);
  if (view.secondaryPreviewHeading !== null) {
    setOwnedText(
      document.querySelector("#secondary-preview-heading"),
      view.secondaryPreviewHeading,
    );
  }
  document.querySelector("#secondary-preview-block").hidden =
    !view.showSecondaryPreview;
  renderDiagnostics(document.querySelector("#fit-diagnostics"), view.diagnostics);
  renderArtifacts(run);
  document.querySelector("#reproduction-command").textContent =
    run.reproduction?.shell ?? "";

  for (const [target, logicalName] of view.previews) {
    const artifact = run.artifacts.find((item) => item.logical_name === logicalName);
    if (!artifact) continue;
    const preview = await previewArtifact(run.run_id, artifact.artifact_id);
    if (!isCurrent()) return;
    renderPreview(document.querySelector(`#${target}-preview`), preview);
  }
}

function renderArtifacts(run) {
  const artifacts = document.querySelector("#run-artifacts");
  artifacts.replaceChildren();
  for (const artifact of run.artifacts) {
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = artifactUrl(run.run_id, artifact.artifact_id);
    link.dataset.artifactFilename = artifact.filename;
    link.textContent = translateOwned(
      "web.ipfui.download",
      `Download ${artifact.filename}`,
      { filename: artifact.filename },
    );
    artifacts.append(link);
  }
}

function renderPreview(element, preview) {
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const column of preview.columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const row of preview.rows) {
    const tr = document.createElement("tr");
    for (const column of preview.columns) {
      const cell = document.createElement("td");
      cell.textContent = row[column] ?? "";
      tr.append(cell);
    }
    body.append(tr);
  }
  table.append(head, body);
  element.replaceChildren(table);
}

function renderDiagnostics(element, items) {
  element.replaceChildren();
  for (const [label, value] of items) {
    const card = document.createElement("div");
    const term = document.createElement("strong");
    setOwnedText(term, label);
    const detail = document.createElement("span");
    const displayValue = String(value ?? "—");
    if (
      [
        "Workspace capacity",
        "Converged",
        "Publishable candidate",
        "Linked validation",
        "Realized maximum error",
        "Largest residual",
      ].includes(label)
    ) {
      setOwnedText(detail, displayValue);
    } else {
      detail.textContent = displayValue;
    }
    card.append(term, detail);
    element.append(card);
  }
}

function showStep(name) {
  document.querySelectorAll("[data-run-step]").forEach((step) => {
    const active = step.dataset.runStep === name;
    step.classList.toggle("active", active);
    step.hidden = !active;
  });
  document.querySelectorAll("[data-step-indicator]").forEach((item) => {
    item.classList.toggle("active", item.dataset.stepIndicator === name);
  });
}

function setRunHeading(kicker, title, status, workflow = "ipf", runId = null) {
  const kickerElement = document.querySelector("#run-kicker");
  if (runId === null) {
    setOwnedText(kickerElement, kicker);
  } else {
    const view = {
      id: "web.run.identifier",
      text: `Run ${runId}`,
      params: { id: runId },
    };
    localizedViews.set(kickerElement, view);
    kickerElement.textContent = translateOwned(view.id, view.text, view.params);
  }
  setOwnedText(document.querySelector("#run-title"), title);
  const steps = document.querySelector("#run-steps");
  const modelSteps = workflow === "model";
  const smallAreaSteps = workflow === "small_area";
  steps.dataset.i18nAriaLabel = smallAreaSteps
    ? "web.smallarea.steps"
    : modelSteps
      ? "web.modelui.steps"
      : "web.ipfui.steps";
  steps.setAttribute(
    "aria-label",
    translateOwned(
      steps.dataset.i18nAriaLabel,
      smallAreaSteps
        ? "Small-area run steps"
        : modelSteps
          ? "Model run steps"
          : "IPF run steps",
    ),
  );
  if (workflow === "model") {
    setOwnedText(
      document.querySelector("#run-subtitle"),
      "Generate linked households and people from a prepared model.",
    );
  } else if (workflow === "small_area") {
    setOwnedText(
      document.querySelector("#run-subtitle"),
      "Generate and calibrate linked households and people for small areas.",
    );
  } else if (workflow === "ipf") {
    setOwnedText(
      document.querySelector("#run-subtitle"),
      "Fit compact weights from seed records and normalized controls.",
    );
  }
  setRunStatus(status);
}

function setRunStatus(status) {
  const element = document.querySelector("#run-status");
  element.className = `run-status ${status}`;
  element.dataset.status = status;
  element.textContent = localizedStatus(status);
}

function showMessage(message, kind, phase = "") {
  ipfDiagnosticRenderer = null;
  const element = document.querySelector("#workbench-message");
  clearWebError(element);
  element.className = `result-box ${kind}`.trim();
  element.dataset.phase = phase;
  setOwnedText(element, message);
}

function showErrorMessage(error, kind = "error") {
  showMessage("", kind);
  renderWebError(document.querySelector("#workbench-message"), error);
}

function clearResults() {
  for (const selector of [
    "#preflight-results",
    "#fit-diagnostics",
    "#primary-preview",
    "#secondary-preview",
    "#run-artifacts",
    "#progress-events",
  ])
    document.querySelector(selector).replaceChildren();
  document.querySelector("#reproduction-command").textContent = "";
  document.querySelector("#start-run").disabled = true;
  document.querySelector("#cancel-run").disabled = false;
}

async function loadModelCatalogue(state) {
  const operation = state.operations.begin("catalogue-load");
  const select = document.querySelector("#run-model-select");
  const smallAreaSelect = document.querySelector("#small-area-premade-model");
  try {
    const response = await fetch("/api/models");
    if (!response.ok) throw new Error("Model catalogue unavailable");
    const payload = await response.json();
    if (!operation.isCurrent()) return;
    const selected = select.value;
    const smallAreaSelected = smallAreaSelect.value;
    const runOptions = [new Option("Choose a catalogue model", "")];
    runOptions[0].dataset.modelPlaceholder = "true";
    const smallAreaOptions = [new Option("Choose a prepared model", "")];
    setOwnedText(smallAreaOptions[0], "Choose a prepared model");
    for (const model of payload.models) {
      const option = document.createElement("option");
      option.value = model.id;
      option.dataset.modelName = model.name;
      option.dataset.modelGeography = model.geography;
      option.dataset.installed = String(model.installed);
      option.dataset.distribution = model.distribution;
      runOptions.push(option);

      const smallAreaOption = document.createElement("option");
      smallAreaOption.value = model.id;
      smallAreaOption.textContent = `${model.name} · ${model.geography}`;
      smallAreaOption.dataset.distribution = model.distribution;
      smallAreaOption.dataset.installed = String(model.installed);
      smallAreaOptions.push(smallAreaOption);
    }
    select.replaceChildren(...runOptions);
    renderModelOptions();
    smallAreaSelect.replaceChildren(...smallAreaOptions);
    if ([...select.options].some((option) => option.value === selected)) {
      select.value = selected;
    }
    if (
      [...smallAreaSelect.options].some((option) => option.value === smallAreaSelected)
    ) {
      smallAreaSelect.value = smallAreaSelected;
    }
    updateModelCatalogueActions();
  } catch {
    if (!operation.isCurrent()) return;
    for (const target of [select, smallAreaSelect]) {
      target.replaceChildren(
        new Option(
          target === select ? "Choose a catalogue model" : "Choose a prepared model",
          "",
        ),
      );
      if (target === smallAreaSelect)
        setOwnedText(target.options[0], "Choose a prepared model");
      if (target === select) {
        target.options[0].dataset.modelPlaceholder = "true";
        renderModelOptions();
      }
      const option = document.createElement("option");
      option.disabled = true;
      option.textContent = "Premade models unavailable";
      setOwnedText(option, "Premade models unavailable");
      target.append(option);
    }
    updateModelCatalogueActions();
  }
}

function updateModelCatalogueActions() {
  const option = document.querySelector("#run-model-select").selectedOptions[0];
  const downloadable = option?.dataset.distribution === "download";
  const installed = option?.dataset.installed === "true";
  document.querySelector("#install-run-model").disabled = !downloadable || installed;
  document.querySelector("#remove-run-model").disabled = !downloadable || !installed;
}

async function changeModelInstallation(state, action) {
  const operation = state.operations.begin("model-install");
  const select = document.querySelector("#run-model-select");
  const modelId = select.value || select.selectedOptions[0]?.value;
  if (!modelId) return;
  const install = action === "install";
  const status = document.querySelector("#run-model-catalogue-status");
  const buttons = [
    document.querySelector("#install-run-model"),
    document.querySelector("#remove-run-model"),
  ];
  buttons.forEach((button) => {
    button.disabled = true;
  });
  clearWebError(status);
  setOwnedText(
    status,
    install ? "Downloading and verifying model…" : "Removing model…",
  );
  try {
    const response = await fetch(
      `/api/models/${encodeURIComponent(modelId)}${install ? "/install" : ""}`,
      {
        method: install ? "POST" : "DELETE",
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new ApiError(payload.error || "Model catalogue update failed", {
        endpoint: install ? "/api/models/:id/install" : "/api/models/:id",
        method: install ? "POST" : "DELETE",
        status: response.status,
      });
    }
    if (!operation.isCurrent()) {
      await loadModelCatalogue(state);
      return;
    }
    await loadModelCatalogue(state);
    if (!operation.isCurrent()) return;
    select.value = install ? modelId : "";
    updateModelCatalogueActions();
    setOwnedText(
      status,
      install
        ? "Model downloaded, verified, and ready for durable Python runs."
        : payload.removed
          ? "Downloaded model removed from the local cache."
          : "The model was not present in the local cache.",
    );
  } catch (error) {
    if (!operation.isCurrent()) return;
    localizedViews.delete(status);
    renderWebError(status, error);
    updateModelCatalogueActions();
  }
}

function renderModelOptions() {
  const select = document.querySelector("#run-model-select");
  for (const option of select.options) {
    if (option.dataset.modelPlaceholder === "true") {
      setOwnedText(option, "Choose a catalogue model");
    } else if (option.dataset.modelName !== undefined) {
      const name = option.dataset.modelName;
      const geography = option.dataset.modelGeography;
      option.textContent =
        option.dataset.installed === "true"
          ? `${name} · ${geography}`
          : translateOwned(
              "web.modelui.option",
              `${name} · ${geography} · download required`,
              { name, geography },
            );
    }
  }
}

function showWorkbench() {
  document.querySelector(".workbench").hidden = false;
  document.querySelectorAll("[data-workflow-panel]").forEach((panel) => {
    panel.classList.remove("active");
    panel.hidden = true;
  });
}
