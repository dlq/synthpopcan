import { runBrowserJob } from "./browser-job.mjs";
import { buildModelCliCommands } from "./cli-commands.mjs";
import { numberValue, readFileText } from "./form-utils.mjs";
import { fetchJson } from "./http.mjs";
import {
  appendCliFollowUp,
  showDownloads,
  showError,
  showStatus,
} from "./result-ui.mjs";
import { parseConditions, summarizeModelPayload } from "./tree-model.mjs";
import { showModelSummary } from "./workflow-views.mjs";

export function bindModelWorkflow() {
  const state = {
    text: null,
    label: null,
    cliReference: null,
  };
  const form = document.querySelector("#model-form");
  const generateButton = document.querySelector("#generate-model");
  const readyStatus = document.querySelector("#model-ready-status");

  clearReady(
    "Choose and load a premade model, or inspect a JSON file, before generating.",
  );
  loadCatalogue();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultBox = document.querySelector("#model-result");
    showStatus(resultBox, "Generating rows in the browser...");
    try {
      const modelText = await currentModelText(state);
      const modelPayload = JSON.parse(modelText);
      const result = await runBrowserJob({
        type: "model",
        modelText,
        rows: numberValue("#model-rows"),
        conditionsText: document.querySelector("#model-conditions").value,
        randomSeed: numberValue("#model-random-seed"),
      });
      showDownloads(resultBox, result);
      appendCliFollowUp(
        resultBox,
        buildModelCliCommands(modelPayload, {
          reference: state.cliReference ?? "model.json",
          rows: numberValue("#model-rows"),
          randomSeed: numberValue("#model-random-seed"),
          conditions: parseConditions(
            document.querySelector("#model-conditions").value,
          ),
        }),
      );
    } catch (error) {
      showError(resultBox, error);
    }
  });

  document.querySelector("#inspect-model-file").addEventListener("click", async () => {
    const resultBox = document.querySelector("#model-inspect-result");
    showStatus(resultBox, "Inspecting the selected model...");
    try {
      const payload = JSON.parse(await currentModelText(state));
      const summary = summarizeModelPayload(payload);
      const label = state.label ?? state.cliReference ?? "Selected model";
      applyDefaults(summary);
      markReady(summary, label);
      showModelSummary(resultBox, summary, label);
    } catch (error) {
      clearReady("The selected JSON could not be inspected.");
      showError(resultBox, error);
    }
  });

  document.querySelector("#model-file").addEventListener("change", () => {
    state.text = null;
    state.label = null;
    state.cliReference = document.querySelector("#model-file").files?.[0]?.name ?? null;
    document.querySelector("#premade-model").value = "";
    clearReady("Inspect the selected JSON before generating.");
  });

  document.querySelector("#premade-model").addEventListener("change", (event) => {
    document.querySelector("#load-premade-model").disabled = !event.target.value;
    state.text = null;
    state.label = null;
    state.cliReference = null;
    clearReady(
      event.target.value
        ? "Select Use premade model to load and inspect this package."
        : "Choose and load a premade model, or inspect a JSON file, before generating.",
    );
  });

  document.querySelector("#load-premade-model").addEventListener("click", async () => {
    const resultBox = document.querySelector("#model-inspect-result");
    const select = document.querySelector("#premade-model");
    const button = document.querySelector("#load-premade-model");
    const modelId = select.value;
    showStatus(resultBox, "Loading the premade model...");
    button.disabled = true;
    try {
      if (!modelId) throw new Error("Choose a premade model first.");
      const option = select.selectedOptions[0];
      const needsDownload = option?.dataset.installed === "false";
      let payload;
      if (needsDownload) {
        showDownloadStatus(option);
        const result = await fetchJson(
          `/api/models/${encodeURIComponent(modelId)}/fetch`,
          { method: "POST" },
        );
        payload = result.model;
        await loadCatalogue(modelId);
      } else {
        payload = await fetchJson(`/api/models/${encodeURIComponent(modelId)}`);
      }
      state.text = JSON.stringify(payload);
      state.label = select.selectedOptions[0]?.textContent ?? modelId;
      state.cliReference = modelId;
      document.querySelector("#model-file").value = "";
      const summary = summarizeModelPayload(payload);
      applyDefaults(summary);
      markReady(summary, state.label);
      showModelSummary(resultBox, summary, state.label);
    } catch (error) {
      clearReady("The premade model could not be loaded.");
      showError(resultBox, error);
    } finally {
      hideDownloadStatus();
      button.disabled = !select.value;
    }
  });

  async function loadCatalogue(selectedModelId = null) {
    const modelSelect = document.querySelector("#premade-model");
    const smallAreaSelect = document.querySelector("#small-area-premade-model");
    try {
      const payload = await fetchJson("/api/models");
      populateModelSelect(modelSelect, payload.models, { showDownloadStatus: true });
      populateModelSelect(smallAreaSelect, payload.models);
      if (selectedModelId) modelSelect.value = selectedModelId;
      document.querySelector("#load-premade-model").disabled = !modelSelect.value;
    } catch {
      setModelSelectUnavailable(modelSelect);
      setModelSelectUnavailable(smallAreaSelect);
    }
  }

  function markReady(summary, label) {
    form.querySelectorAll("input").forEach((input) => {
      input.disabled = false;
    });
    generateButton.disabled = false;
    readyStatus.className = "selection-estimate success";
    readyStatus.textContent = `Ready: ${label}. ${summary.outputs}.`;
  }

  function clearReady(message) {
    form.querySelectorAll("input").forEach((input) => {
      input.disabled = true;
    });
    generateButton.disabled = true;
    readyStatus.className = "selection-estimate";
    readyStatus.textContent = message;
    document.querySelector("#model-row-label-text").textContent = "Rows or households";
    document.querySelector("#model-conditions-hint").textContent =
      "Available condition columns appear after the model is loaded.";
  }
}

function populateModelSelect(select, models, { showDownloadStatus = false } = {}) {
  const placeholder = new Option("No premade model selected", "");
  select.replaceChildren(placeholder);
  models.forEach((model) => {
    const option = new Option(
      showDownloadStatus && !model.installed
        ? `${model.name} (${model.geography}) - download required`
        : `${model.name} (${model.geography})`,
      model.id,
    );
    option.title = modelOptionTitle(model);
    option.dataset.installed = String(model.installed);
    option.dataset.distribution = model.distribution;
    if (model.size_bytes) option.dataset.sizeBytes = String(model.size_bytes);
    select.append(option);
  });
}

function setModelSelectUnavailable(select) {
  select.replaceChildren(new Option("Premade models unavailable", ""));
}

function modelOptionTitle(model) {
  return [
    model.description,
    `Vintage: ${model.census_vintage ?? "not listed"}`,
    `Release: ${model.release_status ?? "not listed"}`,
    `Asset version: ${model.release_version ?? "not listed"}`,
    `Availability: ${model.installed ? "ready" : "downloaded automatically when selected"}`,
    `Source: ${model.provenance ?? "not listed"}`,
    `Privacy: ${model.privacy ?? "not listed"}`,
    `Limits: ${model.generation_limits ?? "not listed"}`,
    `Known limitations: ${model.known_limitations ?? "not listed"}`,
  ]
    .filter(Boolean)
    .join(" ");
}

function showDownloadStatus(option) {
  const status = document.querySelector("#model-download-status");
  const size = Number(option?.dataset.sizeBytes);
  const sizeNote = Number.isFinite(size) && size > 0 ? ` (${formatBytes(size)})` : "";
  document.querySelector("#model-download-message").textContent =
    `Downloading premade model${sizeNote}. The package will be verified before use.`;
  status.hidden = false;
}

function hideDownloadStatus() {
  document.querySelector("#model-download-status").hidden = true;
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB compressed`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB compressed`;
}

function applyDefaults(summary) {
  const defaults = summary.generationDefault;
  document.querySelector("#model-rows").value = defaults.households;
  document.querySelector("#model-conditions").value = defaults.conditions;
  document.querySelector("#model-row-label-text").textContent = summary.linkage
    ? "Households"
    : "Rows";
  document.querySelector("#model-conditions-hint").textContent =
    summary.conditions.length > 0
      ? `Available condition columns: ${summary.conditions.join(", ")}.`
      : "This model does not require condition columns.";
}

async function currentModelText(state) {
  if (state.text !== null) return state.text;
  return readFileText("#model-file");
}
