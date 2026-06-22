import assert from "node:assert/strict";
import test from "node:test";

import { previewCsv } from "../../src/synthpopcan/web/preview.mjs";

test("previews a bounded number of csv rows and columns", () => {
  const preview = previewCsv("id,name,count,extra\n1,F,30,a\n2,M,20,b\n3,X,10,c\n", {
    maxRows: 2,
    maxColumns: 3,
  });

  assert.deepEqual(preview.columns, ["id", "name", "count"]);
  assert.equal(preview.hiddenColumnCount, 1);
  assert.equal(preview.hasMoreRows, true);
  assert.deepEqual(preview.rows, [
    { id: "1", name: "F", count: "30", extra: "a" },
    { id: "2", name: "M", count: "20", extra: "b" },
  ]);
});

test("previews quoted csv values", () => {
  const preview = previewCsv('id,name\n1,"Montréal, QC"\n');

  assert.deepEqual(preview.rows, [{ id: "1", name: "Montréal, QC" }]);
});
