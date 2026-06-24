export function modelFromPayload(payload) {
  if (payload.schema_version !== "synthpopcan-tree-model-v1") {
    throw new Error("unsupported tree model schema");
  }
  if (!["conditional-frequency", "cart"].includes(payload.model_type)) {
    throw new Error("unsupported tree model type");
  }
  return payload;
}

export function packageModels(packagePayload) {
  if (packagePayload.schema_version !== "synthpopcan-linked-tree-package-v1") {
    throw new Error("unsupported linked model package schema");
  }
  if (packagePayload.privacy?.publishable_candidate !== true) {
    throw new Error("linked package is not marked as a publishable candidate");
  }
  const householdModel = modelFromPayload(packagePayload.models?.household ?? {});
  const personModel = modelFromPayload(packagePayload.models?.person ?? {});
  return {
    householdModel,
    personModel,
    householdSizeColumn: packagePayload.household_size_column ?? "household_size",
  };
}

export function summarizeModelPayload(payload) {
  if (payload.schema_version === "synthpopcan-linked-tree-package-v1") {
    const { householdModel, personModel, householdSizeColumn } = packageModels(payload);
    return {
      kind: "Linked household/person package",
      schemaVersion: payload.schema_version,
      release: releaseText(payload),
      privacy: privacyText(payload.privacy),
      privacyDetails: privacyDetailsText(payload.privacy),
      source: provenanceText(payload.provenance, "source", "Source not listed"),
      trainingData: provenanceText(
        payload.provenance,
        "training_data",
        "Training data not listed",
      ),
      generationDefault: generationDefault(payload, householdModel),
      warnings: modelWarnings(payload),
      rowsLabel: "Households to generate",
      outputs: "Household CSV and person CSV",
      linkage: `Household size comes from ${householdSizeColumn}; person rows are generated inside each synthetic household.`,
      models: [
        { name: "Household model", text: modelSummaryText(householdModel) },
        { name: "Person model", text: modelSummaryText(personModel) },
      ],
      conditions: householdModel.spec?.conditioning_columns ?? [],
    };
  }

  const model = modelFromPayload(payload);
  return {
    kind: `${model.spec?.level ?? "single-level"} model`,
    schemaVersion: model.schema_version,
    release: releaseText(model),
    privacy: privacyText(model.privacy),
    privacyDetails: privacyDetailsText(model.privacy),
    source: provenanceText(model.provenance, "source", "Source not listed"),
    trainingData: provenanceText(
      model.provenance,
      "training_data",
      "Training data not listed",
    ),
    generationDefault: generationDefault(payload, model),
    warnings: modelWarnings(model),
    rowsLabel: "Rows to generate",
    outputs: "Synthetic rows CSV",
    linkage: "",
    models: [
      {
        name: `${model.spec?.level ?? "Single-level"} model`,
        text: modelSummaryText(model),
      },
    ],
    conditions: model.spec?.conditioning_columns ?? [],
  };
}

export function generateTreeRows(
  model,
  { rows, conditions = {}, randomSeed = null } = {},
) {
  if (model.model_type === "conditional-frequency") {
    return generateFrequencyRows(model, { rows, conditions, randomSeed });
  }
  return generateCartRows(model, { rows, conditions, randomSeed });
}

function modelSummaryText(model) {
  const targets = (model.spec?.target_columns ?? []).join(", ") || "none listed";
  const conditioning =
    (model.spec?.conditioning_columns ?? []).join(", ") || "none listed";
  const records = Number.isFinite(Number(model.records_trained))
    ? `${Number(model.records_trained).toLocaleString()} training records; `
    : "";
  return `${model.model_type}; ${records}targets ${targets}; conditions ${conditioning}`;
}

function releaseText(payload) {
  return payload.release_class ?? payload.package_type ?? "not listed";
}

function privacyText(privacy) {
  if (!privacy) {
    return "not listed";
  }
  if (privacy.publishable_candidate === true || privacy.publishable === true) {
    return "marked as publishable candidate";
  }
  return "not marked as publishable candidate";
}

function privacyDetailsText(privacy) {
  if (!privacy) {
    return "No raw/source identifier status listed";
  }
  if (
    privacy.contains_raw_rows === undefined &&
    privacy.contains_source_identifiers === undefined &&
    !privacy.source
  ) {
    return "No raw/source identifier status listed";
  }
  const rawRows = yesNo(privacy.contains_raw_rows);
  const sourceIds = yesNo(privacy.contains_source_identifiers);
  const source = privacy.source ? `; source: ${privacy.source}` : "";
  return `raw rows: ${rawRows}; source identifiers: ${sourceIds}${source}`;
}

function yesNo(value) {
  if (value === true) {
    return "yes";
  }
  if (value === false) {
    return "no";
  }
  return "not listed";
}

function provenanceText(provenance, key, fallback) {
  const value = provenance?.[key];
  return value ? String(value) : fallback;
}

function generationDefault(payload, model) {
  const defaults = payload.generation_defaults ?? {};
  return {
    households: String(defaults.households ?? 10),
    conditions: String(
      defaults.conditions ?? exampleConditions(model.spec?.conditioning_columns, model),
    ),
  };
}

function exampleConditions(conditioningColumns = [], model) {
  const firstGroup = model.groups?.[0]?.conditions ?? {};
  return conditioningColumns
    .map((column) => {
      const value = firstGroup[column] ?? "VALUE";
      return `${column}=${value}`;
    })
    .join(", ");
}

function modelWarnings(payload) {
  const warnings = [];
  if (payload.review?.note) {
    warnings.push(String(payload.review.note));
  }
  if (!payload.provenance?.source) {
    warnings.push("No source provenance is listed for this package.");
  }
  if (payload.provenance?.contains_real_microdata === true) {
    warnings.push("This package reports real microdata in its provenance.");
  }
  return warnings;
}

export function generateLinkedPopulation(
  householdModel,
  personModel,
  {
    households,
    householdConditions = {},
    householdSizeColumn = "household_size",
    randomSeed = null,
  } = {},
) {
  if (householdModel.spec?.level !== "household") {
    throw new Error("household model must have level 'household'");
  }
  if (personModel.spec?.level !== "person") {
    throw new Error("person model must have level 'person'");
  }
  const rng = seededRandom(randomSeed ?? householdModel.spec.random_seed ?? 0);
  const generatedHouseholds = generateTreeRows(householdModel, {
    rows: households,
    conditions: householdConditions,
    randomSeed,
  });
  const linkedHouseholds = [];
  const linkedPersons = [];
  let nextPersonId = 1;

  generatedHouseholds.forEach((generatedHousehold, index) => {
    const householdId = String(index + 1);
    const household = {
      synthetic_household_id: householdId,
      ...stripSyntheticId(generatedHousehold),
    };
    linkedHouseholds.push(household);
    const householdSize = readHouseholdSize(household, householdSizeColumn);
    const personConditions = householdConditionsForPersonModel(household, personModel);
    const generatedPersons = generateTreeRows(personModel, {
      rows: householdSize,
      conditions: personConditions,
      randomSeed: Math.floor(rng() * (2 ** 31 - 1)) + 1,
    });
    generatedPersons.forEach((person) => {
      linkedPersons.push({
        synthetic_person_id: String(nextPersonId),
        synthetic_household_id: householdId,
        ...stripSyntheticId(person),
      });
      nextPersonId += 1;
    });
  });

  return { households: linkedHouseholds, persons: linkedPersons };
}

export function validateLinkedPopulationOutput(
  households,
  persons,
  { householdSizeColumn = "household_size" } = {},
) {
  const householdIds = new Set(
    households.map((household) => household.synthetic_household_id),
  );
  const linkedPersonCount = persons.filter((person) =>
    householdIds.has(person.synthetic_household_id),
  ).length;
  const unknownHouseholdReferences = persons.length - linkedPersonCount;
  const peopleByHousehold = countPeopleByHousehold(persons);
  const householdSizeMatches = households.filter((household) => {
    const expectedSize = Number(household[householdSizeColumn]);
    if (!Number.isFinite(expectedSize)) {
      return false;
    }
    const actualSize = peopleByHousehold.get(household.synthetic_household_id) ?? 0;
    return expectedSize === actualSize;
  }).length;
  const householdSizeMismatches = households.length - householdSizeMatches;
  const status =
    unknownHouseholdReferences === 0 && householdSizeMismatches === 0
      ? "passed"
      : "warning";

  return {
    status,
    items: [
      { title: "Households generated", text: String(households.length) },
      { title: "Persons generated", text: String(persons.length) },
      {
        title: "Household links",
        text: householdLinksText(
          linkedPersonCount,
          persons.length,
          unknownHouseholdReferences,
        ),
      },
      {
        title: "Household sizes",
        text: householdSizesText(
          householdSizeMatches,
          households.length,
          householdSizeColumn,
          householdSizeMismatches,
        ),
      },
    ],
  };
}

function countPeopleByHousehold(persons) {
  const counts = new Map();
  persons.forEach((person) => {
    const householdId = person.synthetic_household_id;
    counts.set(householdId, (counts.get(householdId) ?? 0) + 1);
  });
  return counts;
}

function householdLinksText(linkedPersonCount, personCount, unknownReferences) {
  const base = `${linkedPersonCount} of ${personCount} person row(s) link to known households.`;
  if (unknownReferences === 0) {
    return base;
  }
  return `${base.slice(0, -1)}; ${unknownReferences} unknown household reference(s).`;
}

function householdSizesText(
  householdSizeMatches,
  householdCount,
  householdSizeColumn,
  householdSizeMismatches,
) {
  const base = `${householdSizeMatches} of ${householdCount} household row(s) match ${householdSizeColumn}.`;
  if (householdSizeMismatches === 0) {
    return base;
  }
  return `${base.slice(0, -1)}; ${householdSizeMismatches} mismatch(es).`;
}

export function parseConditions(text) {
  const conditions = {};
  String(text ?? "")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((item) => {
      const equalsIndex = item.indexOf("=");
      if (equalsIndex === -1) {
        throw new Error(`condition ${item} must use name=value`);
      }
      const key = item.slice(0, equalsIndex).trim();
      const value = item.slice(equalsIndex + 1).trim();
      if (!key) {
        throw new Error("condition name cannot be empty");
      }
      conditions[key] = value;
    });
  return conditions;
}

function generateFrequencyRows(model, { rows, conditions, randomSeed }) {
  validatePositiveRows(rows);
  const rng = seededRandom(randomSeed ?? model.spec?.random_seed ?? 0);
  const generated = [];
  for (let index = 1; index <= rows; index += 1) {
    const group = chooseGroup(model, conditions, rng);
    const outcome = weightedChoice(group.outcomes, (item) => item.weight, rng);
    generated.push({
      synthetic_id: String(index),
      ...group.conditions,
      ...outcome.values,
    });
  }
  return generated;
}

function generateCartRows(model, { rows, conditions, randomSeed }) {
  validatePositiveRows(rows);
  validateConditionColumns(model.spec.conditioning_columns, conditions);
  const rng = seededRandom(randomSeed ?? model.spec?.random_seed ?? 0);
  const featureRow = Object.fromEntries(
    model.spec.conditioning_columns.map((column) => [column, conditions[column] ?? ""]),
  );
  const encoded = encodeConditions(
    featureRow,
    model.spec.conditioning_columns,
    model.feature_categories,
  );
  const leafId = cartLeafId(model, encoded);
  const values = model.cart.value[leafId];
  const outcomes = model.target_classes
    .map((targetClass, index) => ({ values: targetClass, weight: values[index] ?? 0 }))
    .filter((outcome) => outcome.weight > 0);
  const generated = [];
  for (let index = 1; index <= rows; index += 1) {
    const outcome = weightedChoice(outcomes, (item) => item.weight, rng);
    generated.push({
      synthetic_id: String(index),
      ...featureRow,
      ...outcome.values,
    });
  }
  return generated;
}

function chooseGroup(model, conditions, rng) {
  if (Object.keys(conditions).length === 0) {
    return weightedChoice(model.groups, (group) => group.support, rng);
  }
  validateConditionColumns(model.spec.conditioning_columns, conditions);
  const matches = model.groups.filter((group) => {
    return Object.entries(conditions).every(([column, value]) => {
      return group.conditions[column] === value;
    });
  });
  if (matches.length > 0) {
    return weightedChoice(matches, (group) => group.support, rng);
  }
  return {
    conditions: Object.fromEntries(
      model.spec.conditioning_columns.map((column) => [
        column,
        conditions[column] ?? "",
      ]),
    ),
    support: model.global_outcomes.reduce(
      (total, outcome) => total + outcome.weight,
      0,
    ),
    outcomes: model.global_outcomes,
  };
}

function validateConditionColumns(conditioningColumns, conditions) {
  const allowed = new Set(conditioningColumns);
  const unknown = Object.keys(conditions).filter((column) => !allowed.has(column));
  if (unknown.length > 0) {
    throw new Error(`unknown conditioning columns: ${unknown.join(", ")}`);
  }
}

function validatePositiveRows(rows) {
  if (!Number.isInteger(rows) || rows <= 0) {
    throw new Error("rows must be greater than zero");
  }
}

function encodeConditions(record, conditioningColumns, featureCategories) {
  return conditioningColumns.flatMap((column) => {
    const value = record[column] ?? "";
    return featureCategories[column].map((category) => (value === category ? 1 : 0));
  });
}

function cartLeafId(model, encoded) {
  let nodeId = 0;
  while (model.cart.children_left[nodeId] !== model.cart.children_right[nodeId]) {
    const featureIndex = model.cart.feature[nodeId];
    const threshold = model.cart.threshold[nodeId];
    nodeId =
      encoded[featureIndex] <= threshold
        ? model.cart.children_left[nodeId]
        : model.cart.children_right[nodeId];
  }
  return nodeId;
}

function householdConditionsForPersonModel(household, personModel) {
  const missing = personModel.spec.conditioning_columns.filter(
    (column) => !(column in household),
  );
  if (missing.length > 0) {
    throw new Error(`household row is missing columns: ${missing.join(", ")}`);
  }
  return Object.fromEntries(
    personModel.spec.conditioning_columns.map((column) => [column, household[column]]),
  );
}

function readHouseholdSize(row, column) {
  const value = Number(row[column]);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`household size ${row[column]} is not a positive whole number`);
  }
  return value;
}

function stripSyntheticId(row) {
  return Object.fromEntries(
    Object.entries(row).filter(([column]) => column !== "synthetic_id"),
  );
}

function weightedChoice(items, weightFunction, rng) {
  const total = items.reduce((sum, item) => sum + weightFunction(item), 0);
  if (total <= 0) {
    throw new Error("cannot sample from non-positive weights");
  }
  const threshold = rng() * total;
  let cumulative = 0;
  for (const item of items) {
    cumulative += weightFunction(item);
    if (threshold <= cumulative) {
      return item;
    }
  }
  return items.at(-1);
}

function seededRandom(seed) {
  let state = Number(seed) >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
}
