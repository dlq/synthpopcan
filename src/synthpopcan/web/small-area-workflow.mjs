import { numberValue, optionalNumberValue } from "./form-utils.mjs";
import { resultItem, revokeDownloads, showError, showStatus } from "./result-ui.mjs";
import { createRun, preflightRun, uploadCsv } from "./run-api.mjs";

export function bindSmallAreaWorkflow() {
  const form = document.querySelector("#small-area-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultBox = document.querySelector("#small-area-result");
    showStatus(resultBox, "Uploading and checking the planned small-area run...");
    try {
      const request = await buildRequest();
      const preflight = await preflightRun(request);
      showEstimate(resultBox, preflight);
    } catch (error) {
      showError(resultBox, error);
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

async function buildRequest() {
  const modelSelect = document.querySelector("#small-area-premade-model");
  const packageFile = document.querySelector("#small-area-model-file").files?.[0];
  if (!packageFile && !modelSelect.value)
    throw new Error("Choose a premade linked model or a package JSON file.");
  const controlsFile = document.querySelector("#small-area-controls-file").files?.[0];
  if (!controlsFile) throw new Error("Choose household controls CSV.");
  const personControlsFile = document.querySelector("#small-area-person-controls-file")
    .files?.[0];
  const boundariesFile = document.querySelector("#small-area-boundaries-file")
    .files?.[0];
  const controls = await uploadCsv(controlsFile);
  const inputs = { controls_upload_id: controls.upload_id };
  if (packageFile) {
    const uploaded = await uploadCsv(packageFile);
    inputs.package_upload_id = uploaded.upload_id;
  } else {
    inputs.model_id = modelSelect.value;
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

function showEstimate(element, preflight) {
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
    button.disabled = true;
    showStatus(element, "Starting the durable small-area run...");
    try {
      const run = await createRun(preflight.request);
      document.dispatchEvent(
        new CustomEvent("synthpopcan:run-created", { detail: run }),
      );
    } catch (error) {
      showError(element, error);
    }
  });
  element.append(button);
}
