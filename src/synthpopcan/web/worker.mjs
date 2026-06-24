import { parseCsv, stringifyCsv } from "./csv.mjs";
import { expandRecords, fitIpf, readControlTable, weightsToRows } from "./ipf.mjs";
import {
  generateLinkedPopulation,
  generateTreeRows,
  modelFromPayload,
  packageModels,
  parseConditions,
  validateLinkedPopulationOutput,
} from "./tree-model.mjs";

self.addEventListener("message", (event) => {
  const { id, job } = event.data;
  try {
    const result = runJob(job);
    self.postMessage({ id, ok: true, result });
  } catch (error) {
    self.postMessage({
      id,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

function runJob(job) {
  if (job.type === "ipf") {
    return runIpfJob(job);
  }
  if (job.type === "model") {
    return runModelJob(job);
  }
  throw new Error("unknown browser job");
}

function runIpfJob(job) {
  const seedRows = parseCsv(job.seedText);
  const controlRows = parseCsv(job.controlsText);
  const controlTable = readControlTable(controlRows);
  const fit = fitIpf(seedRows, controlTable.margins, {
    weightField: job.weightField,
    maxIterations: job.maxIterations,
    tolerance: job.tolerance,
  });
  const expandedRowCount = Math.round(
    fit.weights.reduce((total, weight) => total + weight, 0),
  );
  if (job.outputKind === "expanded" && expandedRowCount > job.maxExpandedRows) {
    throw new Error(
      `Expanded rows would create about ${formatNumber(expandedRowCount)} records. Use Weights CSV for browser runs, or run the CLI when you really need a full expanded file.`,
    );
  }
  const outputRows =
    job.outputKind === "expanded"
      ? expandRecords(seedRows, fit.weights)
      : weightsToRows(seedRows, fit.weights);
  const filename =
    job.outputKind === "expanded"
      ? "synthpopcan-ipf-expanded.csv"
      : "synthpopcan-ipf-weights.csv";

  return {
    message: `IPF ${fit.converged ? "converged" : "stopped"} after ${fit.iterations} iteration(s). Max absolute error: ${formatNumber(fit.maxAbsError)}.`,
    downloads: [{ filename, text: stringifyCsv(outputRows), type: "text/csv" }],
  };
}

function runModelJob(job) {
  const payload = JSON.parse(job.modelText);
  const conditions = parseConditions(job.conditionsText);

  if (payload.schema_version === "synthpopcan-linked-tree-package-v1") {
    const { householdModel, personModel, householdSizeColumn } = packageModels(payload);
    const generated = generateLinkedPopulation(householdModel, personModel, {
      households: job.rows,
      householdConditions: conditions,
      householdSizeColumn,
      randomSeed: job.randomSeed,
    });
    return {
      message: `Generated ${generated.households.length} household row(s) and ${generated.persons.length} person row(s).`,
      validation: validateLinkedPopulationOutput(
        generated.households,
        generated.persons,
        { householdSizeColumn },
      ),
      downloads: [
        {
          filename: "synthpopcan-households.csv",
          text: stringifyCsv(generated.households),
          type: "text/csv",
        },
        {
          filename: "synthpopcan-persons.csv",
          text: stringifyCsv(generated.persons),
          type: "text/csv",
        },
      ],
    };
  }

  const model = modelFromPayload(payload);
  const generatedRows = generateTreeRows(model, {
    rows: job.rows,
    conditions,
    randomSeed: job.randomSeed,
  });
  return {
    message: `Generated ${generatedRows.length} synthetic row(s).`,
    downloads: [
      {
        filename: "synthpopcan-model-rows.csv",
        text: stringifyCsv(generatedRows),
        type: "text/csv",
      },
    ],
  };
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(6)));
}
