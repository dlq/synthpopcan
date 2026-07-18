import { numberValue, optionalNumberValue } from "./form-utils.mjs";
import { createOperationSequencer } from "./operation-sequencer.mjs";
import { resultItem, revokeDownloads, showError, showStatus } from "./result-ui.mjs";
import { createRun, preflightRun, uploadCsv } from "./run-api.mjs";

export function bindSmallAreaWorkflow() {
  const form = document.querySelector("#small-area-form");
  const operations = createOperationSequencer();
  form.addEventListener("input", () => invalidatePreparedEstimate(operations));
  form.addEventListener("change", () => invalidatePreparedEstimate(operations));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const operation = operations.begin("prepare");
    const resultBox = document.querySelector("#small-area-result");
    showStatus(resultBox, "Uploading and checking the planned small-area run...");
    try {
      const draft = snapshotDraft();
      const request = await buildRequest(draft);
      if (!operation.isCurrent()) return;
      const preflight = await preflightRun(request);
      if (!operation.isCurrent()) return;
      showEstimate(resultBox, preflight, operations);
    } catch (error) {
      if (operation.isCurrent()) showError(resultBox, error);
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
  if (
    resultBox.querySelector(".primary-action") ||
    resultBox.textContent.startsWith("Uploading and checking") ||
    resultBox.textContent.startsWith("Starting the durable")
  ) {
    showStatus(resultBox, "Inputs changed. Estimate the run again before starting.");
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
  if (Boolean(candidateHouseholds) !== Boolean(candidatePersons))
    throw new Error("Choose both candidate household and person CSV files.");
  const hasModelSource = Boolean(packageFile || modelSelect.value);
  const hasCandidateSource = Boolean(candidateHouseholds && candidatePersons);
  if (hasModelSource === hasCandidateSource)
    throw new Error("Choose one model/package or one linked candidate pair.");
  const controlsFile = document.querySelector("#small-area-controls-file").files?.[0];
  if (!controlsFile) throw new Error("Choose household controls CSV.");
  const personControlsFile = document.querySelector("#small-area-person-controls-file")
    .files?.[0];
  const boundariesFile = document.querySelector("#small-area-boundaries-file")
    .files?.[0];
  return {
    modelId: modelSelect.value,
    packageFile,
    candidateHouseholds,
    candidatePersons,
    controlsFile,
    personControlsFile,
    boundariesFile,
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
    },
  };
}

async function buildRequest(draft) {
  const {
    modelId,
    packageFile,
    candidateHouseholds,
    candidatePersons,
    controlsFile,
    personControlsFile,
    boundariesFile,
    options,
  } = draft;
  const controls = await uploadCsv(controlsFile);
  const inputs = { controls_upload_id: controls.upload_id };
  if (candidateHouseholds && candidatePersons) {
    const [households, persons] = await Promise.all([
      uploadCsv(candidateHouseholds),
      uploadCsv(candidatePersons),
    ]);
    inputs.candidate_households_upload_id = households.upload_id;
    inputs.candidate_persons_upload_id = persons.upload_id;
  } else if (packageFile) {
    const uploaded = await uploadCsv(packageFile);
    inputs.package_upload_id = uploaded.upload_id;
  } else {
    inputs.model_id = modelId;
  }
  if (personControlsFile) {
    const uploaded = await uploadCsv(personControlsFile);
    inputs.person_controls_upload_id = uploaded.upload_id;
  }
  if (boundariesFile) {
    const uploaded = await uploadCsv(boundariesFile);
    inputs.boundaries_upload_id = uploaded.upload_id;
  }
  return {
    workflow: "small_area",
    inputs,
    options,
  };
}

function showEstimate(element, preflight, operations) {
  const estimate = preflight.estimate;
  revokeDownloads(element);
  element.className = `result-box ${preflight.ready ? "success" : "warning"}`;
  element.textContent = preflight.ready
    ? "Preflight complete. Review the scale before starting the durable run."
    : "Preflight found insufficient workspace capacity.";
  const summary = document.createElement("div");
  summary.className = "result-list compact-result-list";
  summary.append(
    resultItem("Target geographies", estimate.target_geographies.toLocaleString()),
    resultItem("Target households", estimate.target_households.toLocaleString()),
    resultItem("Estimated persons", estimate.estimated_persons.toLocaleString()),
    resultItem(
      "Candidate pool",
      `${estimate.calibration_pool_size.toLocaleString()} of ${estimate.candidate_households.toLocaleString()}`,
    ),
    resultItem(
      "Workspace capacity",
      estimate.enough_disk ? "Enough disk space" : "Too little disk space",
    ),
  );
  element.append(summary);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "primary-action";
  button.textContent = "Start durable small-area run";
  button.disabled = !preflight.ready;
  button.addEventListener("click", async () => {
    const operation = operations.begin("start");
    const request = structuredClone(preflight.request);
    button.disabled = true;
    showStatus(element, "Starting the durable small-area run...");
    try {
      const run = await createRun(request);
      document.dispatchEvent(
        new CustomEvent("synthpopcan:run-created", {
          detail: { run, select: operation.isCurrent() },
        }),
      );
    } catch (error) {
      if (operation.isCurrent()) showError(element, error);
    }
  });
  element.append(button);
}
