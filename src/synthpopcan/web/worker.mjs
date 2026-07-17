import { stringifyCsv } from "./csv.mjs";
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
  if (job.type === "model") {
    return runModelJob(job);
  }
  throw new Error("unknown browser job");
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
