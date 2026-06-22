import assert from "node:assert/strict";
import test from "node:test";

import {
  generateLinkedPopulation,
  generateTreeRows,
  modelFromPayload,
  packageModels,
  summarizeModelPayload,
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
  assert.deepEqual(summary.conditions, ["geo"]);
  assert.equal(summary.privacy, "marked as publishable candidate");
  assert.match(summary.linkage, /Household size comes from household_size/);
  assert.deepEqual(
    summary.models.map((model) => model.name),
    ["Household model", "Person model"],
  );
  assert.equal(
    summary.models[0].text,
    "conditional-frequency; targets household_size, tenure; conditions geo",
  );
});
