import assert from "node:assert/strict";
import test from "node:test";

import {
  generateLinkedPopulation,
  generateTreeRows,
  modelFromPayload,
  packageModels,
  summarizeModelPayload,
  validateLinkedPopulationOutput,
} from "../../src/synthpopcan/web/tree-model.mjs";

const householdModel = {
  schema_version: "synthpopcan-tree-model-v1",
  model_type: "conditional-frequency",
  release_class: "publishable_candidate",
  spec: {
    level: "household",
    target_columns: ["household_size", "tenure"],
    conditioning_columns: ["geo"],
    geography_column: "geo",
    random_seed: 7,
  },
  source_format: "csv-v1",
  records_trained: 1,
  groups: [
    {
      conditions: { geo: "QC" },
      support: 1,
      outcomes: [{ values: { household_size: "2", tenure: "owner" }, weight: 1 }],
    },
  ],
  global_outcomes: [{ values: { household_size: "2", tenure: "owner" }, weight: 1 }],
  privacy: { publishable: true },
};

const personModel = {
  schema_version: "synthpopcan-tree-model-v1",
  model_type: "conditional-frequency",
  release_class: "publishable_candidate",
  spec: {
    level: "person",
    target_columns: ["age_group", "sex"],
    conditioning_columns: ["geo", "household_size", "tenure"],
    geography_column: "geo",
    random_seed: 11,
  },
  source_format: "csv-v1",
  records_trained: 1,
  groups: [
    {
      conditions: { geo: "QC", household_size: "2", tenure: "owner" },
      support: 1,
      outcomes: [{ values: { age_group: "adult", sex: "F" }, weight: 1 }],
    },
  ],
  global_outcomes: [{ values: { age_group: "adult", sex: "F" }, weight: 1 }],
  privacy: { publishable: true },
};

test("generates rows from a conditional-frequency model", () => {
  const rows = generateTreeRows(modelFromPayload(householdModel), {
    rows: 2,
    conditions: { geo: "QC" },
    randomSeed: 13,
  });

  assert.deepEqual(rows, [
    {
      synthetic_id: "1",
      geo: "QC",
      household_size: "2",
      tenure: "owner",
    },
    {
      synthetic_id: "2",
      geo: "QC",
      household_size: "2",
      tenure: "owner",
    },
  ]);
});

test("generates linked household and person rows from embedded package models", () => {
  const packagePayload = {
    schema_version: "synthpopcan-linked-tree-package-v1",
    package_type: "linked_household_person",
    household_size_column: "household_size",
    privacy: { publishable_candidate: true },
    models: { household: householdModel, person: personModel },
  };
  const { householdModel: household, personModel: person } =
    packageModels(packagePayload);

  const generated = generateLinkedPopulation(household, person, {
    households: 1,
    householdConditions: { geo: "QC" },
    randomSeed: 13,
  });

  assert.deepEqual(generated.households, [
    {
      synthetic_household_id: "1",
      geo: "QC",
      household_size: "2",
      tenure: "owner",
    },
  ]);
  assert.deepEqual(generated.persons, [
    {
      synthetic_person_id: "1",
      synthetic_household_id: "1",
      geo: "QC",
      household_size: "2",
      tenure: "owner",
      age_group: "adult",
      sex: "F",
    },
    {
      synthetic_person_id: "2",
      synthetic_household_id: "1",
      geo: "QC",
      household_size: "2",
      tenure: "owner",
      age_group: "adult",
      sex: "F",
    },
  ]);
});

test("validates generated linked household and person rows", () => {
  const summary = validateLinkedPopulationOutput(
    [
      {
        synthetic_household_id: "1",
        household_size: "2",
      },
    ],
    [
      { synthetic_person_id: "1", synthetic_household_id: "1" },
      { synthetic_person_id: "2", synthetic_household_id: "1" },
    ],
    { householdSizeColumn: "household_size" },
  );

  assert.equal(summary.status, "passed");
  assert.deepEqual(summary.items, [
    { title: "Households generated", text: "1" },
    { title: "Persons generated", text: "2" },
    {
      title: "Household links",
      text: "2 of 2 person row(s) link to known households.",
    },
    {
      title: "Household sizes",
      text: "1 of 1 household row(s) match household_size.",
    },
  ]);
});

test("reports linked output validation warnings", () => {
  const summary = validateLinkedPopulationOutput(
    [
      {
        synthetic_household_id: "1",
        household_size: "2",
      },
    ],
    [
      { synthetic_person_id: "1", synthetic_household_id: "1" },
      { synthetic_person_id: "2", synthetic_household_id: "missing" },
    ],
    { householdSizeColumn: "household_size" },
  );

  assert.equal(summary.status, "warning");
  assert.deepEqual(summary.items, [
    { title: "Households generated", text: "1" },
    { title: "Persons generated", text: "2" },
    {
      title: "Household links",
      text: "1 of 2 person row(s) link to known households; 1 unknown household reference(s).",
    },
    {
      title: "Household sizes",
      text: "0 of 1 household row(s) match household_size; 1 mismatch(es).",
    },
  ]);
});

test("summarizes linked model packages for browser inspection", () => {
  const packagePayload = {
    schema_version: "synthpopcan-linked-tree-package-v1",
    package_type: "linked_household_person",
    household_size_column: "household_size",
    privacy: { publishable_candidate: true },
    models: { household: householdModel, person: personModel },
  };

  const summary = summarizeModelPayload(packagePayload);

  assert.equal(summary.kind, "Linked household/person package");
  assert.equal(summary.rowsLabel, "Households to generate");
  assert.equal(summary.outputs, "Household CSV and person CSV");
  assert.equal(summary.source, "Source not listed");
  assert.equal(summary.trainingData, "Training data not listed");
  assert.equal(summary.privacyDetails, "No raw/source identifier status listed");
  assert.deepEqual(summary.generationDefault, {
    households: "10",
    conditions: "geo=QC",
  });
  assert.deepEqual(summary.warnings, [
    "No source provenance is listed for this package.",
  ]);
  assert.deepEqual(summary.conditions, ["geo"]);
  assert.equal(summary.privacy, "marked as publishable candidate");
  assert.match(summary.linkage, /Household size comes from household_size/);
  assert.deepEqual(
    summary.models.map((model) => model.name),
    ["Household model", "Person model"],
  );
  assert.equal(
    summary.models[0].text,
    "conditional-frequency; 1 training records; targets household_size, tenure; conditions geo",
  );
});

test("summarizes provenance and privacy details for prepared model packages", () => {
  const packagePayload = {
    schema_version: "synthpopcan-linked-tree-package-v1",
    package_type: "linked_household_person",
    household_size_column: "household_size",
    privacy: {
      publishable_candidate: true,
      contains_raw_rows: false,
      contains_source_identifiers: false,
      source: "synthetic toy rows only",
    },
    provenance: {
      source: "SynthPopCan bundled demo",
      training_data: "hand-authored synthetic toy distribution",
      contains_real_microdata: false,
    },
    review: {
      status: "safe demo",
      note: "Trained from synthetic toy rows; safe to distribute.",
    },
    generation_defaults: {
      households: 10,
      conditions: "geo=Demo North",
    },
    models: { household: householdModel, person: personModel },
  };

  const summary = summarizeModelPayload(packagePayload);

  assert.equal(summary.source, "SynthPopCan bundled demo");
  assert.equal(summary.trainingData, "hand-authored synthetic toy distribution");
  assert.equal(
    summary.privacyDetails,
    "raw rows: no; source identifiers: no; source: synthetic toy rows only",
  );
  assert.deepEqual(summary.generationDefault, {
    households: "10",
    conditions: "geo=Demo North",
  });
  assert.deepEqual(summary.warnings, [
    "Trained from synthetic toy rows; safe to distribute.",
  ]);
});
