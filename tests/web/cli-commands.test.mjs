import assert from "node:assert/strict";
import test from "node:test";

import {
  buildIpfCliCommands,
  buildModelCliCommands,
  buildSmallAreaCliCommands,
  shellQuote,
} from "../../src/synthpopcan/web/cli-commands.mjs";

test("quotes shell values and builds reproducible IPF commands", () => {
  assert.equal(shellQuote("researcher's seed.csv"), `'researcher'"'"'s seed.csv'`);
  const commands = buildIpfCliCommands({
    seedName: "seed.csv",
    controlsName: "controls.csv",
    weightField: "start weight",
    maxIterations: 50,
    tolerance: 0.0001,
  });
  assert.match(commands[1], /--weight-field 'start weight'/);
  assert.match(commands[1], /--max-iterations 50/);
});

test("builds linked model generation commands", () => {
  const commands = buildModelCliCommands(
    { schema_version: "synthpopcan-linked-tree-package-v1" },
    {
      reference: "demo-model",
      rows: 12,
      randomSeed: 13,
      conditions: { geo: "QC" },
    },
  );
  assert.match(commands[0], /inspect-package 'demo-model'/);
  assert.match(commands[1], /--condition 'geo=QC'/);
  assert.match(commands[1], /--households 12/);
});

test("adds Census household-size grouping to small-area commands", () => {
  const commands = buildSmallAreaCliCommands({
    modelReference: "montreal-cma-2016-all-fields",
    modelDistribution: "download",
    controlsName: "ct-controls.csv",
    personControlsName: null,
    controlDimensions: ["ct", "household_size_group", "TENUR"],
    geographyDimension: "ct",
    geographyColumn: "ct",
    candidateHouseholds: 20_000,
    poolSize: 10_000,
    averagePersons: 2.22,
    randomSeed: 13,
    subsampleSeed: 42,
  });
  assert.match(commands[0], /models fetch/);
  assert.match(commands[2], /--max-household-size 5/);
  assert.match(commands[2], /--household-size-group-column household_size_group/);
  assert.match(commands[2], /--random-seed 13/);
  assert.match(commands[2], /--subsample-seed 42/);
});
