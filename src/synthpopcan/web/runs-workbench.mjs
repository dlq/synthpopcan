import { stringifyCsv } from "./csv.mjs";
import {
  artifactUrl,
  cancelRun,
  createRun,
  getRun,
  listRuns,
  preflightRun,
  previewArtifact,
  uploadCsv,
} from "./run-api.mjs";
import { followRunEvents } from "./run-events.mjs";
import { renderRunList } from "./run-list.mjs";
import { buildAgeSexControlRows, buildAgeSexSeedRows } from "./starter-files.mjs";

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

export function bindRunsWorkbench(bootstrap) {
  const state = {
    runs: [],
    selectedRun: null,
    uploads: null,
    preflight: null,
    stopEvents: null,
  };
  document.querySelector("#workspace-location").textContent = bootstrap.workspace;
  document.querySelector("#new-run").addEventListener("click", () => newDraft(state));
  document
    .querySelector("#use-demo-ipf")
    .addEventListener("click", () => useDemoFiles());
  document.querySelector("#ipf-seed-file").addEventListener("change", filesChanged);
  document.querySelector("#ipf-controls-file").addEventListener("change", filesChanged);
  document
    .querySelector("#upload-inputs")
    .addEventListener("click", () => uploadInputs(state));
  document
    .querySelector("#check-preflight")
    .addEventListener("click", () => checkPreflight(state));
  document.querySelector("#start-run").addEventListener("click", () => startRun(state));
  document
    .querySelector("#cancel-run")
    .addEventListener("click", () => requestCancel(state));
  document.querySelectorAll("[data-go-step]").forEach((button) => {
    button.addEventListener("click", () => showStep(button.dataset.goStep));
  });
  bindLegacyTools();
  refreshRuns(state, true);
}

function bindLegacyTools() {
  document.querySelectorAll("[data-workflow-tab]").forEach((button) => {
    button.addEventListener("click", () => {
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
  try {
    state.runs = (await listRuns()).runs;
    renderRunList(
      document.querySelector("#runs-list"),
      state.runs,
      state.selectedRun?.run_id,
      (run) => selectRun(state, run),
    );
    if (selectNewest && state.runs.length > 0) await selectRun(state, state.runs[0]);
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function newDraft(state) {
  state.stopEvents?.();
  state.stopEvents = null;
  state.selectedRun = null;
  state.uploads = null;
  state.preflight = null;
  for (const id of ["#ipf-seed-file", "#ipf-controls-file"])
    document.querySelector(id).value = "";
  filesChanged();
  setRunHeading("New durable run", "IPF from margin tables", "Draft");
  clearResults();
  showMessage("", "");
  showStep("inputs");
  renderRunList(document.querySelector("#runs-list"), state.runs, null, (run) =>
    selectRun(state, run),
  );
}

function useDemoFiles() {
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
  filesChanged();
  showMessage("Demo files are ready to upload.", "success");
}

function setInputFiles(selector, files) {
  const transfer = new DataTransfer();
  for (const file of files) transfer.items.add(file);
  document.querySelector(selector).files = transfer.files;
}

function filesChanged() {
  const seed = document.querySelector("#ipf-seed-file").files?.[0];
  const controls = document.querySelector("#ipf-controls-file").files?.[0];
  document.querySelector("#seed-upload-status").textContent = fileLabel(seed);
  document.querySelector("#controls-upload-status").textContent = fileLabel(controls);
  document.querySelector("#upload-inputs").disabled = !(seed && controls);
}

function fileLabel(file) {
  return file ? `${file.name} · ${formatBytes(file.size)}` : "Choose one CSV.";
}

async function uploadInputs(state) {
  const button = document.querySelector("#upload-inputs");
  button.disabled = true;
  showMessage("Streaming the two CSV files into the local workspace…", "");
  try {
    const seedFile = document.querySelector("#ipf-seed-file").files[0];
    const controlsFile = document.querySelector("#ipf-controls-file").files[0];
    const [seed, controls] = await Promise.all([
      uploadCsv(seedFile),
      uploadCsv(controlsFile),
    ]);
    state.uploads = { seed, controls };
    showMessage("Inputs uploaded and fingerprinted.", "success");
    showStep("configure");
  } catch (error) {
    showMessage(error.message, "error");
    button.disabled = false;
  }
}

function buildRequest(state) {
  return {
    workflow: "ipf",
    inputs: {
      seed_upload_id: state.uploads.seed.upload_id,
      controls_upload_id: state.uploads.controls.upload_id,
    },
    options: {
      weight_column: document.querySelector("#ipf-weight-field").value.trim() || null,
      max_iterations: Number(document.querySelector("#ipf-max-iterations").value),
      tolerance: Number(document.querySelector("#ipf-tolerance").value),
      allow_nonconverged: document.querySelector("#ipf-allow-nonconverged").checked,
    },
  };
}

async function checkPreflight(state) {
  showMessage("Checking input structure and workspace capacity…", "");
  try {
    state.preflight = await preflightRun(buildRequest(state));
    const problems = renderPreflight(state.preflight);
    document.querySelector("#start-run").disabled = !state.preflight.ready;
    showStep("preflight");
    if (state.preflight.ready) {
      showMessage("Preflight passed. The run is ready to start.", "success");
    } else if (problems.length === 0) {
      showMessage("Preflight found a workspace capacity problem.", "error");
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function renderPreflight(preflight) {
  const diagnostics = preflight.input_diagnostics;
  const estimate = preflight.estimate;
  const items = [
    ["Seed records", diagnostics.seed_records],
    ["Control margins", diagnostics.control_margins],
    [
      "Dimensions",
      diagnostics.dimensions?.map((item) => item.dimension).join(", ") || "—",
    ],
    ["Expected weighted rows", estimate.output_rows],
    ["Estimated artifact size", formatBytes(estimate.output_bytes)],
    [
      "Workspace capacity",
      estimate.enough_disk ? "Enough disk space" : "Insufficient disk space",
    ],
  ];
  renderDiagnostics(document.querySelector("#preflight-results"), items);
  const problems = [
    ...diagnostics.dimensions
      .filter((item) => item.status !== "ok")
      .map((item) => item.detail),
    ...diagnostics.unsupported_cells.map(
      (item) => item.detail ?? "A control cell has no matching seed support.",
    ),
  ];
  if (problems.length) showMessage(problems.join(" "), "error");
  return problems;
}

async function startRun(state) {
  document.querySelector("#start-run").disabled = true;
  showMessage("Creating the durable run…", "");
  try {
    const run = await createRun(state.preflight.request);
    state.selectedRun = run;
    setRunHeading(`Run ${run.run_id.slice(-12)}`, "IPF from margin tables", run.status);
    showStep("run");
    showMessage("Run queued. You can safely refresh this page.", "success");
    await refreshRuns(state);
    followRun(state, run.run_id);
  } catch (error) {
    showMessage(error.message, "error");
    document.querySelector("#start-run").disabled = false;
  }
}

function followRun(state, runId) {
  state.stopEvents?.();
  const events = document.querySelector("#progress-events");
  events.replaceChildren();
  state.stopEvents = followRunEvents(runId, {
    onEvent: (event) => appendProgressEvent(events, event),
    onReconnect: () => document.querySelector("#run-progress").removeAttribute("value"),
    onTerminal: async (run) => {
      state.selectedRun = run;
      state.stopEvents = null;
      await refreshRuns(state);
      await showTerminalRun(state, run);
    },
  });
}

function appendProgressEvent(list, event) {
  const item = document.createElement("li");
  item.textContent = event.message;
  item.dataset.eventId = event.id;
  list.append(item);
  const progress = document.querySelector("#run-progress");
  if (event.completed != null && event.total)
    progress.value = (event.completed / event.total) * 100;
}

async function requestCancel(state) {
  if (!state.selectedRun) return;
  document.querySelector("#cancel-run").disabled = true;
  try {
    const run = await cancelRun(state.selectedRun.run_id);
    state.selectedRun = run;
    setRunStatus(run.status);
    showMessage("Cancellation requested.", "warning");
  } catch (error) {
    showMessage(error.message, "error");
    document.querySelector("#cancel-run").disabled = false;
  }
}

async function selectRun(state, summary) {
  try {
    const run = await getRun(summary.run_id);
    state.selectedRun = run;
    renderRunList(
      document.querySelector("#runs-list"),
      state.runs,
      run.run_id,
      (item) => selectRun(state, item),
    );
    setRunHeading(`Run ${run.run_id.slice(-12)}`, "IPF from margin tables", run.status);
    if (TERMINAL.has(run.status)) await showTerminalRun(state, run);
    else {
      showStep("run");
      showMessage("Reconnected to the durable run.", "success");
      followRun(state, run.run_id);
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function showTerminalRun(_state, run) {
  setRunStatus(run.status);
  document.querySelector("#cancel-run").disabled = true;
  if (run.status !== "succeeded") {
    showStep("run");
    const message = run.error?.message ?? `Run ${run.status}.`;
    showMessage(message, run.status === "cancelled" ? "warning" : "error");
    return;
  }
  showStep("results");
  showMessage("Run completed and persisted in the workspace.", "success");
  renderDiagnostics(document.querySelector("#fit-diagnostics"), [
    ["Converged", run.summary.converged ? "Yes" : "No"],
    ["Iterations", run.summary.iterations],
    ["Maximum absolute error", run.summary.max_abs_error],
    ["Seed records", run.summary.seed_records],
  ]);
  const artifacts = document.querySelector("#run-artifacts");
  artifacts.replaceChildren();
  for (const artifact of run.artifacts) {
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = artifactUrl(run.run_id, artifact.artifact_id);
    link.textContent = `Download ${artifact.filename}`;
    artifacts.append(link);
  }
  const weights = run.artifacts.find((item) => item.logical_name === "weights");
  if (weights)
    renderPreview(
      document.querySelector("#weights-preview"),
      await previewArtifact(run.run_id, weights.artifact_id),
    );
  document.querySelector("#reproduction-command").textContent =
    run.reproduction?.shell ?? "";
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
    term.textContent = label;
    const detail = document.createElement("span");
    detail.textContent = String(value ?? "—");
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

function setRunHeading(kicker, title, status) {
  document.querySelector("#run-kicker").textContent = kicker;
  document.querySelector("#run-title").textContent = title;
  setRunStatus(status);
}

function setRunStatus(status) {
  const element = document.querySelector("#run-status");
  element.className = `run-status ${status}`;
  element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function showMessage(message, kind) {
  const element = document.querySelector("#workbench-message");
  element.className = `result-box ${kind}`.trim();
  element.textContent = message;
}

function clearResults() {
  for (const selector of [
    "#preflight-results",
    "#fit-diagnostics",
    "#weights-preview",
    "#run-artifacts",
    "#progress-events",
  ])
    document.querySelector(selector).replaceChildren();
  document.querySelector("#reproduction-command").textContent = "";
  document.querySelector("#start-run").disabled = true;
  document.querySelector("#cancel-run").disabled = false;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
}
