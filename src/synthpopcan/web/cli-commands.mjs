export function buildIpfCliCommands({
  seedName,
  controlsName,
  weightField,
  maxIterations,
  tolerance,
}) {
  const common = `--seed ${shellQuote(seedName)} --controls ${shellQuote(controlsName)}`;
  const fitOptions = [
    common,
    "--out synthpopcan-ipf-weights.csv",
    `--max-iterations ${maxIterations}`,
    `--tolerance ${tolerance}`,
    "--report synthpopcan-ipf-report.json",
  ];
  if (weightField) fitOptions.push(`--weight-field ${shellQuote(weightField)}`);
  return [
    `# Confirm that the seed rows cover every control category.\nsynthpopcan ipf check-inputs ${common}`,
    `# Fit one compact IPF weight per seed row and save a convergence report.\nsynthpopcan ipf fit ${fitOptions.join(" ")}`,
    "# Integerize the fitted weights into one row per synthetic record.\nsynthpopcan ipf expand --weights synthpopcan-ipf-weights.csv --out synthpopcan-population.csv",
  ];
}

export function buildModelCliCommands(
  payload,
  { reference, rows, randomSeed, conditions },
) {
  const conditionOptions = Object.entries(conditions).map(
    ([column, value]) => `--condition ${shellQuote(`${column}=${value}`)}`,
  );
  if (payload.schema_version === "synthpopcan-linked-tree-package-v1") {
    return [
      `# Review the linked model package before generating households and people.\nsynthpopcan tree inspect-package ${shellQuote(reference)}`,
      [
        `# Generate linked household and person CSVs with the same browser settings.\nsynthpopcan tree generate-from-package ${shellQuote(reference)}`,
        `--households ${rows}`,
        ...conditionOptions,
        "--households-out synthpopcan-households.csv",
        "--persons-out synthpopcan-persons.csv",
        "--manifest-out synthpopcan-generation-manifest.json",
        `--random-seed ${randomSeed}`,
      ].join(" "),
    ];
  }
  return [
    [
      `# Generate synthetic rows from this model with the same browser settings.\nsynthpopcan tree generate ${shellQuote(reference)}`,
      `--rows ${rows}`,
      ...conditionOptions,
      "--out synthpopcan-tree-rows.csv",
      "--manifest-out synthpopcan-generation-manifest.json",
      `--random-seed ${randomSeed}`,
    ].join(" "),
  ];
}

export function buildSmallAreaCliCommands({
  modelReference,
  modelDistribution,
  controlsName,
  personControlsName,
  controlDimensions,
  geographyDimension,
  geographyColumn,
  candidateHouseholds,
  poolSize,
  averagePersons,
  randomSeed,
}) {
  const commands = [];
  if (modelDistribution === "download") {
    commands.push(
      `# Download and verify the published linked model package.\nsynthpopcan models fetch ${shellQuote(modelReference)}`,
    );
  }
  const estimateOptions = [
    `--controls ${shellQuote(controlsName)}`,
    `--geo-dimension ${shellQuote(geographyDimension)}`,
    `--candidate-households ${candidateHouseholds}`,
    `--average-persons-per-household ${averagePersons}`,
  ];
  if (poolSize !== null) estimateOptions.push(`--pool-size ${poolSize}`);
  commands.push(
    `# Recheck output scale before starting the full run.\nsynthpopcan geo estimate-run ${estimateOptions.join(" ")}`,
  );

  const synthesisOptions = [
    `synthpopcan geo synthesize-from-package ${shellQuote(modelReference)}`,
    `--households ${candidateHouseholds}`,
    `--controls ${shellQuote(controlsName)}`,
  ];
  if (personControlsName) {
    synthesisOptions.push(`--person-controls ${shellQuote(personControlsName)}`);
  }
  synthesisOptions.push(
    `--geo-dimension ${shellQuote(geographyDimension)}`,
    `--geo-column ${shellQuote(geographyColumn)}`,
  );
  if (controlDimensions.includes("household_size_group")) {
    synthesisOptions.push(
      "--max-household-size 5",
      "--household-size-group-column household_size_group",
    );
  }
  synthesisOptions.push(
    "--households-out small-area-households.csv",
    "--persons-out small-area-persons.csv",
    "--weights-out small-area-weights.csv",
    "--report small-area-report.json",
    `--random-seed ${randomSeed}`,
  );
  if (poolSize !== null) synthesisOptions.push(`--pool-size ${poolSize}`);
  commands.push(
    `# Generate linked candidates, calibrate whole households, and write review artifacts.\n${synthesisOptions.join(" ")}`,
  );
  return commands;
}

export function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}
