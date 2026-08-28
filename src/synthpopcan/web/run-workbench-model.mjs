export function buildIpfRequest({
  uploads,
  weightColumn,
  maxIterations,
  tolerance,
  allowNonconverged,
}) {
  return {
    workflow: "ipf",
    inputs: {
      seed_upload_id: uploads.seed.upload_id,
      controls_upload_id: uploads.controls.upload_id,
    },
    options: {
      weight_column: weightColumn || null,
      max_iterations: maxIterations,
      tolerance,
      allow_nonconverged: allowNonconverged,
    },
  };
}

export function buildModelOptions({ households, conditions, randomSeed }) {
  return {
    households,
    conditions: parseConditions(conditions),
    random_seed: randomSeed,
    chunk_size: 1000,
  };
}

export function buildModelRequest(inputs, options) {
  return { workflow: "model", inputs, options };
}

export function parseConditions(value) {
  const conditions = {};
  for (const item of value.split(",")) {
    if (!item.trim()) continue;
    const separator = item.indexOf("=");
    if (separator < 1) throw new Error("Conditions must use name=value pairs.");
    conditions[item.slice(0, separator).trim()] = item.slice(separator + 1).trim();
  }
  return conditions;
}

export function ipfPreflightView(preflight) {
  const diagnostics = preflight.input_diagnostics;
  const estimate = preflight.estimate;
  return {
    items: [
      ["Seed records", diagnostics.seed_records],
      ["Control margins", diagnostics.control_margins],
      [
        "Dimensions",
        diagnostics.dimensions?.map((item) => item.dimension).join(", ") || "—",
      ],
      ["Compact output rows", estimate.compact_output_rows],
      ["Fitted population total", estimate.population_total],
      ["Estimated artifact size", formatBytes(estimate.output_bytes)],
      [
        "Workspace capacity",
        estimate.enough_disk ? "Enough disk space" : "Insufficient disk space",
      ],
    ],
    problems: [
      ...diagnostics.dimensions
        .filter((item) => item.status !== "ok")
        .map((item) => item.detail),
      ...diagnostics.unsupported_cells.map(
        (item) => item.detail ?? "A control cell has no matching seed support.",
      ),
    ],
  };
}

export function modelPreflightItems(preflight) {
  const model = preflight.model_diagnostics;
  return [
    ["Package", model.name],
    ["Publishable candidate", model.privacy.publishable_candidate ? "Yes" : "No"],
    [
      "Privacy review",
      model.privacy.review_status ||
        (model.privacy.safe_demo ? "Safe synthetic demo" : "Recorded"),
    ],
    ["Supported conditions", model.conditions.join(", ") || "None"],
    ["Requested households", preflight.estimate.households],
    ["Planning storage allowance", formatBytes(preflight.estimate.output_bytes)],
    ["Storage estimate basis", preflight.estimate.storage_basis],
    [
      "Workspace capacity",
      preflight.estimate.enough_disk ? "Enough disk space" : "Insufficient disk space",
    ],
  ];
}

export function runResultView(run) {
  if (run.workflow === "model") {
    return {
      intro:
        "Linked household and person artifacts were generated and validated in Python.",
      previewHeading: "Household output preview",
      secondaryPreviewHeading: "Person output preview",
      showSecondaryPreview: true,
      diagnostics: [
        ["Generated households", run.summary.generated_households],
        ["Generated persons", run.summary.generated_persons],
        [
          "Linked validation",
          run.summary.linked_validation_passed ? "Passed" : "Failed",
        ],
        ["Package", run.summary.package?.name || "Prepared linked model"],
      ],
      previews: [
        ["primary", "households"],
        ["secondary", "persons"],
      ],
      warning: null,
    };
  }
  if (run.workflow === "small_area") {
    return {
      intro: "Linked candidates were generated, calibrated, and validated in Python.",
      previewHeading: "Assigned household preview",
      secondaryPreviewHeading: "Assigned person preview",
      showSecondaryPreview: true,
      diagnostics: [
        ["Assigned households", run.summary.assigned_households],
        ["Assigned persons", run.summary.assigned_persons],
        ["Target geographies", run.summary.total_geographies],
        ["Non-converged geographies", run.summary.non_converged_count],
        ["Maximum absolute error", run.summary.max_abs_error],
        ["Largest residual", describeResidual(run.summary.largest_residuals?.[0])],
        [
          "Realized maximum error",
          run.summary.realized_max_abs_error ?? "Not reported",
        ],
        ["Calibration mode", run.summary.calibration_mode],
      ],
      previews: [
        ["primary", "households"],
        ["secondary", "persons"],
      ],
      warning:
        run.summary.non_converged_count > 0
          ? `${run.summary.non_converged_count} geographies did not converge. Review report.json and the largest residual before using the output.`
          : null,
    };
  }
  return {
    intro: null,
    previewHeading: "Weighted output preview",
    secondaryPreviewHeading: null,
    showSecondaryPreview: false,
    diagnostics: [
      ["Converged", run.summary.converged ? "Yes" : "No"],
      ["Iterations", run.summary.iterations],
      ["Maximum absolute error", run.summary.max_abs_error],
      ["Seed records", run.summary.seed_records],
    ],
    previews: [["primary", "weights"]],
    warning: null,
  };
}

export function describeResidual(residual) {
  if (!residual) return "None above tolerance";
  const categories = Object.entries(residual.categories ?? {})
    .map(([key, value]) => `${key}=${value}`)
    .join(", ");
  return `${residual.abs_error} in ${residual.geography} · ${residual.margin}${categories ? ` · ${categories}` : ""}`;
}

export function workflowTitle(workflow) {
  if (workflow === "model") return "Generate from a prepared model";
  if (workflow === "small_area") return "Small-area linked synthesis";
  return "IPF from margin tables";
}

export function fileLabel(file) {
  return file ? `${file.name} · ${formatBytes(file.size)}` : "Choose one CSV.";
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
}
