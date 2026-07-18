import assert from "node:assert/strict";
import test from "node:test";

import { createOperationSequencer } from "../../src/synthpopcan/web/operation-sequencer.mjs";

test("newer operations supersede older completions of the same kind", () => {
  const operations = createOperationSequencer();
  const first = operations.begin("preflight");
  const second = operations.begin("preflight");

  assert.equal(first.isCurrent(), false);
  assert.equal(second.isCurrent(), true);
});

test("invalidating one operation kind leaves unrelated work current", () => {
  const operations = createOperationSequencer();
  const upload = operations.begin("upload");
  const catalogue = operations.begin("catalogue");

  operations.invalidate("upload");

  assert.equal(upload.isCurrent(), false);
  assert.equal(catalogue.isCurrent(), true);
});

test("invalidating all operations prevents every pending completion", () => {
  const operations = createOperationSequencer();
  const upload = operations.begin("upload");
  const preflight = operations.begin("preflight");

  operations.invalidateAll();

  assert.equal(upload.isCurrent(), false);
  assert.equal(preflight.isCurrent(), false);
});
