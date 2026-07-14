import { buildSmallAreaCliCommands } from "./cli-commands.mjs";
import {
  numberValue,
  optionalNumberValue,
  readFileText,
  valueOrNull,
} from "./form-utils.mjs";
import { fetchJson } from "./http.mjs";
import {
  appendCliFollowUp,
  resultItem,
  revokeDownloads,
  showError,
  showStatus,
} from "./result-ui.mjs";

export function bindSmallAreaWorkflow() {
  const form = document.querySelector("#small-area-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultBox = document.querySelector("#small-area-result");
    showStatus(resultBox, "Checking the planned small-area run...");
    try {
      const model = selectedModel();
      const response = await fetchJson("/api/small-area/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          controlsCsv: await readFileText("#small-area-controls-file"),
          geographyDimension: valueOrNull("#small-area-geo-dimension"),
          candidateHouseholds: numberValue("#small-area-candidate-households"),
          poolSize: optionalNumberValue("#small-area-pool-size"),
          averagePersonsPerHousehold: numberValue("#small-area-average-persons"),
        }),
      });
      showEstimate(resultBox, response, model);
    } catch (error) {
      showError(resultBox, error);
    }
  });

  document
    .querySelector("#small-area-premade-model")
    .addEventListener("change", (event) => {
      if (event.target.value) {
        document.querySelector("#small-area-model-file").value = "";
      }
    });
  document
    .querySelector("#small-area-model-file")
    .addEventListener("change", (event) => {
      if (event.target.files?.length) {
        document.querySelector("#small-area-premade-model").value = "";
      }
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

function selectedModel() {
  const select = document.querySelector("#small-area-premade-model");
  const uploaded = document.querySelector("#small-area-model-file").files?.[0];
  if (uploaded) return { reference: uploaded.name, distribution: "local" };
  if (select.value) {
    return {
      reference: select.value,
      distribution: select.selectedOptions[0]?.dataset.distribution,
    };
  }
  throw new Error("Choose a premade linked model or a package JSON file.");
}

function showEstimate(element, response, model) {
  const estimate = response.estimate;
  const cliRecommended = estimate.recommended_surface === "cli_or_python_api";
  revokeDownloads(element);
  element.className = `result-box ${cliRecommended ? "warning" : "success"}`;
  element.textContent = cliRecommended
    ? "Preflight complete. Use the CLI for this run size."
    : "Preflight complete. This is a small run, but 0.5.0 still hands synthesis to the CLI.";
  const summary = document.createElement("div");
  summary.className = "result-list compact-result-list";
  summary.append(
    resultItem("Target geographies", estimate.target_geographies.toLocaleString()),
    resultItem("Target households", estimate.target_households.toLocaleString()),
    resultItem("Estimated persons", estimate.estimated_persons.toLocaleString()),
    resultItem(
      "Estimated output rows",
      estimate.estimated_total_output_rows.toLocaleString(),
    ),
    resultItem(
      "Calibration pool",
      `${estimate.calibration_pool_size.toLocaleString()} of ${estimate.candidate_households.toLocaleString()} candidates`,
    ),
    resultItem(
      "Recommended surface",
      cliRecommended ? "CLI or Python API" : "Web app scale, CLI execution",
    ),
  );
  element.append(summary);
  const guidance = document.createElement("div");
  guidance.className = "model-warning-note";
  guidance.append(resultItem("Planning guidance", estimate.guidance.join(" ")));
  element.append(guidance);
  appendCliFollowUp(
    element,
    buildSmallAreaCliCommands({
      modelReference: model.reference,
      modelDistribution: model.distribution,
      controlsName: document.querySelector("#small-area-controls-file").files[0].name,
      personControlsName: document.querySelector("#small-area-person-controls-file")
        .files?.[0]?.name,
      controlDimensions: response.controlDimensions,
      geographyDimension: document
        .querySelector("#small-area-geo-dimension")
        .value.trim(),
      geographyColumn: document.querySelector("#small-area-geo-column").value.trim(),
      candidateHouseholds: numberValue("#small-area-candidate-households"),
      poolSize: optionalNumberValue("#small-area-pool-size"),
      averagePersons: numberValue("#small-area-average-persons"),
      randomSeed: numberValue("#small-area-random-seed"),
      subsampleSeed: numberValue("#small-area-subsample-seed"),
    }),
  );
}
