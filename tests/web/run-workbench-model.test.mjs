import assert from "node:assert/strict";
import test from "node:test";

import {
  buildIpfRequest,
  buildModelOptions,
  buildModelRequest,
  describeResidual,
  fileLabel,
  formatBytes,
  ipfPreflightView,
  modelPreflightItems,
  parseConditions,
  runResultView,
  workflowTitle,
} from "../../src/synthpopcan/web/run-workbench-model.mjs";

test("builds IPF and model workbench requests", () => {
  assert.deepEqual(
    buildIpfRequest({
      uploads: {
        seed: { upload_id: "seed-1" },
        controls: { upload_id: "controls-1" },
      },
      weightColumn: "",
      maxIterations: 500,
      tolerance: 0.001,
      allowNonconverged: true,
    }),
    {
      workflow: "ipf",
      inputs: {
        seed_upload_id: "seed-1",
        controls_upload_id: "controls-1",
      },
      options: {
        weight_column: null,
        max_iterations: 500,
        tolerance: 0.001,
        allow_nonconverged: true,
      },
    },
  );

  const options = buildModelOptions({
    households: 12,
    conditions: " geo = Demo North, code=a=b ",
    randomSeed: null,
  });
  assert.deepEqual(options, {
    households: 12,
    conditions: { geo: "Demo North", code: "a=b" },
    random_seed: null,
    chunk_size: 1000,
  });
  assert.deepEqual(buildModelRequest({ model_id: "demo" }, options), {
    workflow: "model",
    inputs: { model_id: "demo" },
    options,
  });
  assert.throws(() => parseConditions("missing-separator"), /name=value pairs/);
  assert.deepEqual(parseConditions(""), {});
});

test("turns IPF and model preflight payloads into diagnostics", () => {
  const ipf = ipfPreflightView({
    input_diagnostics: {
      seed_records: 4,
      control_margins: 2,
      dimensions: [
        { dimension: "age", status: "ok", detail: "supported" },
        { dimension: "sex", status: "missing", detail: "sex is missing" },
      ],
      unsupported_cells: [{}, { detail: "old has no support" }],
    },
    estimate: {
      compact_output_rows: 4,
      population_total: 100,
      output_bytes: 1536,
      enough_disk: false,
    },
  });
  assert.deepEqual(ipf.items, [
    ["Seed records", 4],
    ["Control margins", 2],
    ["Dimensions", "age, sex"],
    ["Compact output rows", 4],
    ["Fitted population total", 100],
    ["Estimated artifact size", "1.5 KB"],
    ["Workspace capacity", "Insufficient disk space"],
  ]);
  assert.deepEqual(ipf.problems, [
    "sex is missing",
    "A control cell has no matching seed support.",
    "old has no support",
  ]);

  const model = modelPreflightItems({
    model_diagnostics: {
      name: "Demo linked model",
      privacy: {
        publishable_candidate: true,
        review_status: "",
        safe_demo: true,
      },
      conditions: ["geo"],
    },
    estimate: {
      households: 10,
      output_bytes: 512,
      storage_basis: "bounded estimate",
      enough_disk: true,
    },
  });
  assert.deepEqual(model, [
    ["Package", "Demo linked model"],
    ["Publishable candidate", "Yes"],
    ["Privacy review", "Safe synthetic demo"],
    ["Supported conditions", "geo"],
    ["Requested households", 10],
    ["Planning storage allowance", "512 B"],
    ["Storage estimate basis", "bounded estimate"],
    ["Workspace capacity", "Enough disk space"],
  ]);
});

test("describes each durable result workflow without DOM state", () => {
  const ipf = runResultView({
    workflow: "ipf",
    summary: {
      converged: true,
      iterations: 8,
      max_abs_error: 0.01,
      seed_records: 4,
    },
  });
  assert.equal(ipf.intro, null);
  assert.equal(ipf.showSecondaryPreview, false);
  assert.deepEqual(ipf.previews, [["primary", "weights"]]);
  assert.deepEqual(ipf.diagnostics[0], ["Converged", "Yes"]);

  const model = runResultView({
    workflow: "model",
    summary: {
      generated_households: 4,
      generated_persons: 9,
      linked_validation_passed: false,
      package: null,
    },
  });
  assert.equal(model.showSecondaryPreview, true);
  assert.deepEqual(model.previews, [
    ["primary", "households"],
    ["secondary", "persons"],
  ]);
  assert.deepEqual(model.diagnostics.at(-1), ["Package", "Prepared linked model"]);

  const smallArea = runResultView({
    workflow: "small_area",
    summary: {
      assigned_households: 6,
      assigned_persons: 14,
      total_geographies: 2,
      non_converged_count: 1,
      max_abs_error: 0.5,
      largest_residuals: [
        {
          abs_error: 0.5,
          geography: "001",
          margin: "tenure",
          categories: { tenure: "owner" },
        },
      ],
      calibration_mode: "integerized",
    },
  });
  assert.match(smallArea.warning, /1 geographies did not converge/);
  assert.deepEqual(smallArea.diagnostics[5], [
    "Largest residual",
    "0.5 in 001 · tenure · tenure=owner",
  ]);
  assert.deepEqual(smallArea.diagnostics[6], [
    "Realized maximum error",
    "Not reported",
  ]);
});

test("formats workbench labels and fallback descriptions", () => {
  assert.equal(describeResidual(null), "None above tolerance");
  assert.equal(
    describeResidual({ abs_error: 1, geography: "002", margin: "size" }),
    "1 in 002 · size",
  );
  assert.equal(formatBytes(10_240), "10 KB");
  assert.equal(fileLabel(null), "Choose one CSV.");
  assert.equal(fileLabel({ name: "seed.csv", size: 2048 }), "seed.csv · 2.0 KB");
  assert.equal(workflowTitle("ipf"), "IPF from margin tables");
  assert.equal(workflowTitle("model"), "Generate from a prepared model");
  assert.equal(workflowTitle("small_area"), "Small-area linked synthesis");
});
