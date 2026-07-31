import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { simplifyBoundaries } from "../../scripts/simplify_boundaries.mjs";

const boundaries = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { geo_id: "left" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [0, 0],
            [1, 0],
            [1, 0.2],
            [0.9, 0.5],
            [1, 0.8],
            [1, 1],
            [0, 1],
            [0, 0],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { geo_id: "right" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [1, 0],
            [2, 0],
            [2, 1],
            [1, 1],
            [1, 0.8],
            [0.9, 0.5],
            [1, 0.2],
            [1, 0],
          ],
        ],
      },
    },
  ],
};

test("topology-preserving boundary simplification preserves shared edges", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-topology-"));
  const inputPath = join(directory, "canonical.geojson");
  const outputPath = join(directory, "display.geojson");
  await writeFile(inputPath, JSON.stringify(boundaries));

  const report = await simplifyBoundaries({ inputPath, outputPath, keep: 0.5 });
  const result = JSON.parse(await readFile(outputPath, "utf8"));
  assert.equal(report.features, 2);
  assert.ok(report.outputCoordinates < report.inputCoordinates);
  assert.ok(report.protectedCoastlineArcs > 0);
  assert.deepEqual(result.features.map((item) => item.properties.geo_id).sort(), [
    "left",
    "right",
  ]);

  const left = result.features.find((item) => item.properties.geo_id === "left");
  const right = result.features.find((item) => item.properties.geo_id === "right");
  const leftShared = left.geometry.coordinates[0].filter(([x]) => x === 1);
  const rightShared = right.geometry.coordinates[0].filter(([x]) => x === 1).reverse();
  assert.deepEqual(leftShared, rightShared);
  const coast = (ring) =>
    [...new Set(ring.filter(([x]) => x === 0).map(JSON.stringify))].sort();
  assert.deepEqual(
    coast(
      result.features.find((item) => item.properties.geo_id === "left").geometry
        .coordinates[0],
    ),
    coast(boundaries.features[0].geometry.coordinates[0]),
  );
});
