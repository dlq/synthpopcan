import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAgeSexControlRows,
  buildAgeSexSeedRows,
  buildControlTemplateRows,
  buildSeedTemplateRows,
} from "../../src/synthpopcan/web/starter-files.mjs";

test("builds runnable age sex demo files", () => {
  assert.deepEqual(buildAgeSexSeedRows(), [
    { id: "1", age: "young", sex: "F" },
    { id: "2", age: "young", sex: "M" },
    { id: "3", age: "old", sex: "F" },
    { id: "4", age: "old", sex: "M" },
  ]);
  assert.deepEqual(buildAgeSexControlRows(), [
    { margin: "age", dimensions: "age", age: "young", sex: "", count: "60" },
    { margin: "age", dimensions: "age", age: "old", sex: "", count: "40" },
    { margin: "sex", dimensions: "sex", age: "", sex: "F", count: "50" },
    { margin: "sex", dimensions: "sex", age: "", sex: "M", count: "50" },
  ]);
});

test("builds simple seed and control templates from dimensions", () => {
  assert.deepEqual(buildSeedTemplateRows(["age", "sex"]), [
    { id: "seed-1", age: "", sex: "" },
  ]);
  assert.deepEqual(buildControlTemplateRows(["age", "sex"]), [
    { margin: "age", dimensions: "age", age: "", sex: "", count: "" },
    { margin: "sex", dimensions: "sex", age: "", sex: "", count: "" },
  ]);
});
