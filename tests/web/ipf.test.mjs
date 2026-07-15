import assert from "node:assert/strict";
import test from "node:test";

import {
  expandRecords,
  fitIpf,
  integerizeWeights,
  readControlTable,
  weightsToRows,
} from "../../src/synthpopcan/web/ipf.mjs";

test("fits two one-way margins and exports weight rows", () => {
  const seedRows = [
    { id: "1", age: "young", sex: "F" },
    { id: "2", age: "young", sex: "M" },
    { id: "3", age: "old", sex: "F" },
    { id: "4", age: "old", sex: "M" },
  ];
  const controls = readControlTable([
    { margin: "age", dimensions: "age", age: "young", sex: "", count: "60" },
    { margin: "age", dimensions: "age", age: "old", sex: "", count: "40" },
    { margin: "sex", dimensions: "sex", age: "", sex: "F", count: "50" },
    { margin: "sex", dimensions: "sex", age: "", sex: "M", count: "50" },
  ]);

  const result = fitIpf(seedRows, controls.margins, { tolerance: 1e-9 });

  assert.equal(result.converged, true);
  assert.deepEqual(
    result.weights.map((weight) => Math.round(weight)),
    [30, 30, 20, 20],
  );
  assert.deepEqual(weightsToRows(seedRows, result.weights), [
    { id: "1", age: "young", sex: "F", weight: "30" },
    { id: "2", age: "young", sex: "M", weight: "30" },
    { id: "3", age: "old", sex: "F", weight: "20" },
    { id: "4", age: "old", sex: "M", weight: "20" },
  ]);
});

test("compact weights preserve complete seed profiles with a collision-safe column", () => {
  assert.deepEqual(
    weightsToRows(
      [
        {
          id: "seed-a",
          age: "young",
          sex: "F",
          weight: "original",
          fitted_weight: "also-original",
        },
      ],
      [12.5],
    ),
    [
      {
        id: "seed-a",
        age: "young",
        sex: "F",
        weight: "original",
        fitted_weight: "also-original",
        fitted_weight_2: "12.5",
      },
    ],
  );
});

test("expands fitted weights into synthetic records", () => {
  const rows = expandRecords(
    [
      { id: "a", age: "young" },
      { id: "b", age: "old" },
    ],
    [1.2, 2.8],
  );

  assert.deepEqual(rows, [
    { synthetic_id: "1", seed_id: "a", age: "young" },
    { synthetic_id: "2", seed_id: "b", age: "old" },
    { synthetic_id: "3", seed_id: "b", age: "old" },
    { synthetic_id: "4", seed_id: "b", age: "old" },
  ]);
});

test("matches Python systematic integerization fixtures", () => {
  const fractionalPool = [...Array(28).fill(6.78 / 28), ...Array(22).fill(7.42 / 22)];
  assert.deepEqual(integerizeWeights([]), []);
  assert.deepEqual(integerizeWeights([0]), [0]);
  assert.deepEqual(integerizeWeights([0.01, 0.02, 0.03]), [0, 0, 0]);
  assert.deepEqual(integerizeWeights([0.49, 0.49, 0.49]), [0, 1, 0]);
  assert.deepEqual(integerizeWeights([1.2, 2.8]), [1, 3]);
  assert.deepEqual(integerizeWeights([0.5]), [0]);
  assert.deepEqual(integerizeWeights([1.5]), [2]);
  assert.deepEqual(integerizeWeights([2.5]), [2]);
  assert.deepEqual(integerizeWeights([3.5]), [4]);
  assert.deepEqual(
    integerizeWeights(fractionalPool),
    [
      0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0,
      1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0,
    ],
  );
});

test("rejects invalid controls and non-finite integerization weights", () => {
  assert.throws(
    () =>
      readControlTable([{ margin: "age", dimensions: "age", age: "old", count: -1 }]),
    /invalid count/,
  );
  assert.throws(() => integerizeWeights([Number.NaN]), /finite/);
  assert.throws(() => integerizeWeights([Number.POSITIVE_INFINITY]), /finite/);
  assert.throws(() => integerizeWeights([-1]), /non-negative/);
  assert.throws(
    () => expandRecords([{ id: "seed-a", synthetic_id: "raw" }], [1]),
    /reserved generated columns/,
  );
});
