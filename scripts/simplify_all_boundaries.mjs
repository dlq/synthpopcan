/** Generate display-only topology-preserving derivatives for canonical boundaries. */

import { access, readdir, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

import { simplifyBoundaries } from "./simplify_boundaries.mjs";

const boundaryRoot = "data/derived/statcan/census";
const manifestPath = join(boundaryRoot, "boundary-display-simplification.json");

async function canonicalBoundaries() {
  const results = [];
  for (const year of await readdir(boundaryRoot)) {
    const directory = join(boundaryRoot, year, "boundaries");
    try {
      if (!(await stat(directory)).isDirectory()) continue;
    } catch {
      continue;
    }
    for (const filename of await readdir(directory)) {
      if (filename.endsWith(".geojson") && !filename.endsWith("-display-topo.geojson")) {
        results.push(join(directory, filename));
      }
    }
  }
  return results.sort();
}

const reports = [];
const failures = [];
for (const inputPath of await canonicalBoundaries()) {
  const outputPath = inputPath.replace(/\.geojson$/, "-display-topo.geojson");
  try {
    await access(outputPath);
    process.stderr.write(`Skipping existing ${outputPath}\n`);
    continue;
  } catch {
    // The output has not been written yet.
  }
  process.stderr.write(`Simplifying ${inputPath}\n`);
  try {
    reports.push(await simplifyBoundaries({ inputPath, outputPath }));
    process.stdout.write(`${JSON.stringify(reports.at(-1))}\n`);
  } catch (error) {
    const failure = { input: inputPath, error: error.message };
    failures.push(failure);
    process.stderr.write(`Could not simplify ${inputPath}: ${error.message}\n`);
  }
  await writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        representation: "display-only-topology-preserving-weighted-simplification",
        keep: 0.1,
        coordinatePrecision: 5,
        boundaries: reports,
        failures,
      },
      null,
      2,
    )}\n`,
  );
}
if (failures.length) process.exitCode = 1;
