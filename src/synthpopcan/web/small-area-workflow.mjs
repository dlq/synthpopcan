import { numberValue, optionalNumberValue } from "./form-utils.mjs";
import { createOperationSequencer } from "./operation-sequencer.mjs";
import { resultItem, revokeDownloads, showError, showStatus } from "./result-ui.mjs";
import { createRun, listControlPacks, preflightRun, uploadCsv } from "./run-api.mjs";
import { SMALL_AREA_MESSAGE_IDS } from "./small-area-messages.mjs";
import {
  buildSmallAreaRequest,
  SmallAreaValidationError,
  validateSmallAreaDraft,
} from "./small-area-request.mjs";

let localizationRuntime = null;
const localizedViews = new Map();

function bindView(element, render) {
  localizedViews.set(element, render);
  render();
}

function message(id, fallback, params = {}) {
  const translated = localizationRuntime?.translate(id, params);
  return translated && translated !== "Message unavailable." ? translated : fallback;
}

function setOwnedText(element, text) {
  const id = SMALL_AREA_MESSAGE_IDS[text];
  if (!Object.hasOwn(SMALL_AREA_MESSAGE_IDS, text)) {
    localizedViews.delete(element);
    element.textContent = text;
    return;
  }
  bindView(element, () => {
    element.textContent = message(id, text);
  });
}

function showOwnedStatus(element, text) {
  showStatus(element, "");
  setOwnedText(element, text);
}

function showSmallAreaError(element, error) {
  localizedViews.delete(element);
  if (!(error instanceof SmallAreaValidationError)) {
    showError(element, error);
    return;
  }
  showStatus(element, "");
  element.className = "result-box error";
  const families = {
    marital_status: "web.smallarea.family.marital",
    education: "web.smallarea.family.education",
    labour_force: "web.smallarea.family.labour",
    work_activity: "web.smallarea.family.work",
  };
  bindView(element, () => {
    const id = `web.smallarea.error.${error.code}`;
    const familyId = families[error.family];
    const params =
      error.code === "family" && familyId
        ? { family: message(familyId, error.family) }
        : {};
    element.textContent = message(id, error.message, params);
  });
}

export function bindSmallAreaWorkflow(localization) {
  localizationRuntime = localization;
  localization.subscribe(() => {
    for (const [element, render] of localizedViews) {
      if (!element.isConnected) localizedViews.delete(element);
      else render();
    }
  });
  const form = document.querySelector("#small-area-form");
  const operations = createOperationSequencer();
  const controlPackSelect = document.querySelector("#small-area-control-pack");
  const controlPackEvidence = document.querySelector(
    "#small-area-control-pack-evidence-file",
  );
  void populateControlPackSelect(controlPackSelect).catch(() => {
    const original =
      "Reviewed control packs are unavailable; raw normalized controls remain available.";
    bindView(controlPackSelect, () => {
      controlPackSelect.title = message(SMALL_AREA_MESSAGE_IDS[original], original);
    });
  });
  controlPackSelect.addEventListener("change", () => {
    const selected = controlPackSelect.selectedOptions[0];
    const geography = selected?.dataset.geographyLevel;
    controlPackEvidence.required = Boolean(controlPackSelect.value);
    if (geography) {
      const dimension = document.querySelector("#small-area-geo-dimension");
      const output = document.querySelector("#small-area-geo-column");
      dimension.value = geography;
      output.value = geography;
      delete output.dataset.edited;
    }
  });
  form.addEventListener("input", () => invalidatePreparedEstimate(operations));
  form.addEventListener("change", () => invalidatePreparedEstimate(operations));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const operation = operations.begin("prepare");
    const resultBox = document.querySelector("#small-area-result");
    showOwnedStatus(resultBox, "Uploading and checking the planned small-area run...");
    resultBox.dataset.workflowState = "preparing";
    try {
      const draft = snapshotDraft();
      const request = await buildSmallAreaRequest(draft, uploadCsv);
      if (!operation.isCurrent()) return;
      const preflight = await preflightRun(request);
      if (!operation.isCurrent()) return;
      showEstimate(resultBox, preflight, operations);
    } catch (error) {
      if (operation.isCurrent()) {
        showSmallAreaError(resultBox, error);
        resultBox.dataset.workflowState = "";
      }
    }
  });

  document
    .querySelector("#small-area-premade-model")
    .addEventListener("change", (event) => {
      if (event.target.value)
        document.querySelector("#small-area-model-file").value = "";
    });
  document
    .querySelector("#small-area-model-file")
    .addEventListener("change", (event) => {
      if (event.target.files?.length)
        document.querySelector("#small-area-premade-model").value = "";
    });
  document
    .querySelector("#small-area-geo-dimension")
    .addEventListener("input", (event) => {
      const output = document.querySelector("#small-area-geo-column");
      if (!output.dataset.edited) output.value = event.target.value;
    });
  document
    .querySelector("#small-area-geo-column")
    .addEventListener("input", (event) => {
      event.target.dataset.edited = "true";
    });
}

function invalidatePreparedEstimate(operations) {
  operations.invalidate("prepare");
  operations.invalidate("start");
  const resultBox = document.querySelector("#small-area-result");
  if (["preparing", "prepared", "starting"].includes(resultBox.dataset.workflowState)) {
    showOwnedStatus(
      resultBox,
      "Inputs changed. Estimate the run again before starting.",
    );
    resultBox.dataset.workflowState = "";
  }
}

function snapshotDraft() {
  const modelSelect = document.querySelector("#small-area-premade-model");
  const packageFile = document.querySelector("#small-area-model-file").files?.[0];
  const candidateHouseholds = document.querySelector(
    "#small-area-candidate-households-file",
  ).files?.[0];
  const candidatePersons = document.querySelector("#small-area-candidate-persons-file")
    .files?.[0];
  const controlsFile = document.querySelector("#small-area-controls-file").files?.[0];
  const personControlsFile = document.querySelector("#small-area-person-controls-file")
    .files?.[0];
  const controlPackId = document.querySelector("#small-area-control-pack").value;
  const controlPackEvidenceFile = document.querySelector(
    "#small-area-control-pack-evidence-file",
  ).files?.[0];
  const boundariesFile = document.querySelector("#small-area-boundaries-file")
    .files?.[0];
  const conditionalControls = [
    ["marital_status", "marital-status", "controls", "marital status"],
    ["education", "education", "profile", "education"],
    ["labour_force", "labour-force", "profile", "labour-force"],
    ["work_activity", "work-activity", "profile", "work activity"],
  ].map(([family, id, source, label]) => ({
    family,
    source,
    label,
    pack: document.querySelector(`#small-area-${id}-pack`).value,
    file: document.querySelector(`#small-area-${id}-${source}-file`).files?.[0],
  }));
  const draft = validateSmallAreaDraft({
    modelId: modelSelect.value,
    packageFile,
    candidateHouseholds,
    candidatePersons,
    controlsFile,
    personControlsFile,
    controlPackId,
    controlPackEvidenceFile,
    boundariesFile,
    conditionalControls,
  });
  return {
    ...draft,
    options: {
      candidate_households: numberValue("#small-area-candidate-households"),
      geography_dimension: document
        .querySelector("#small-area-geo-dimension")
        .value.trim(),
      geography_column: document.querySelector("#small-area-geo-column").value.trim(),
      conditions: {},
      average_persons_per_household: numberValue("#small-area-average-persons"),
      random_seed: optionalNumberValue("#small-area-random-seed"),
      pool_size: optionalNumberValue("#small-area-pool-size"),
      subsample_seed: numberValue("#small-area-subsample-seed"),
      chunk_size: 1000,
      geography_id_field: "geo_id",
      map_title: "Synthetic Population",
      integerization: document.querySelector("#small-area-integerization").value,
      joint_solver: document.querySelector("#small-area-joint-solver").value,
      zero_target_policy: document.querySelector("#small-area-zero-target-policy")
        .value,
    },
  };
}

function showEstimate(element, preflight, operations) {
  const estimate = preflight.estimate;
  revokeDownloads(element);
  element.dataset.workflowState = "prepared";
  element.className = `result-box ${preflight.ready ? "success" : "warning"}`;
  localizedViews.delete(element);
  element.replaceChildren();
  const heading = document.createElement("p");
  setOwnedText(
    heading,
    preflight.ready
      ? "Preflight complete. Review the scale before starting the durable run."
      : "Preflight found insufficient workspace capacity.",
  );
  element.append(heading);
  const summary = document.createElement("div");
  summary.className = "result-list compact-result-list";
  const addItem = (label, renderValue) => {
    const item = resultItem(label, "");
    setOwnedText(item.querySelector("strong"), label);
    bindView(item.querySelector("span"), () => {
      item.querySelector("span").textContent = renderValue();
    });
    summary.append(item);
  };
  const number = (value) =>
    new Intl.NumberFormat(localizationRuntime.locale).format(value);
  addItem("Target geographies", () => number(estimate.target_geographies));
  addItem("Target households", () => number(estimate.target_households));
  addItem("Estimated persons", () => number(estimate.estimated_persons));
  addItem("Candidate pool", () =>
    message(
      "web.smallarea.pool",
      `${number(estimate.calibration_pool_size)} of ${number(estimate.candidate_households)}`,
      {
        selected: estimate.calibration_pool_size,
        total: estimate.candidate_households,
      },
    ),
  );
  addItem("Workspace capacity", () =>
    estimate.enough_disk
      ? message("web.ipfui.m061", "Enough disk space")
      : message(
          SMALL_AREA_MESSAGE_IDS["Too little disk space"],
          "Too little disk space",
        ),
  );
  const pack = preflight.control_pack_plan?.pack;
  if (pack?.identifier) {
    addItem("Control pack", () => pack.identifier);
  }
  element.append(summary);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "primary-action";
  setOwnedText(button, "Start durable small-area run");
  button.disabled = !preflight.ready;
  button.addEventListener("click", async () => {
    const operation = operations.begin("start");
    const request = structuredClone(preflight.request);
    button.disabled = true;
    showOwnedStatus(element, "Starting the durable small-area run...");
    element.dataset.workflowState = "starting";
    try {
      const run = await createRun(request);
      document.dispatchEvent(
        new CustomEvent("synthpopcan:run-created", {
          detail: { run, select: operation.isCurrent() },
        }),
      );
    } catch (error) {
      if (operation.isCurrent()) {
        showSmallAreaError(element, error);
        element.dataset.workflowState = "";
      }
    }
  });
  element.append(button);
}

async function populateControlPackSelect(select) {
  const payload = await listControlPacks();
  for (const pack of payload.control_packs ?? []) {
    const option = document.createElement("option");
    option.value = pack.identifier;
    option.dataset.geographyLevel = String(pack.geography_level).toLowerCase();
    option.textContent = `${pack.census_vintage} ${String(
      pack.geography_level,
    ).toUpperCase()} — ${pack.label}`;
    select.append(option);
  }
}
