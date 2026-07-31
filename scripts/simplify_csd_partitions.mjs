/** Simplify the large national 2021 CSD GeoJSON one province/territory at a time. */

import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";

import { simplifyBoundaries } from "./simplify_boundaries.mjs";

const inputPath = "data/derived/statcan/census/2021/boundaries/2021-boundary-csd.geojson";
const outputDirectory = "data/derived/statcan/census/2021/boundaries";
const manifestPath = join(outputDirectory, "2021-boundary-csd-display-topo.json");
const allPruids = ["10", "11", "12", "13", "24", "35", "46", "47", "48", "59", "60", "61", "62"];
const pruids = process.argv.slice(2).length ? process.argv.slice(2) : allPruids;
if (pruids.some((pruid) => !allPruids.includes(pruid))) {
  throw new Error(`unsupported PRUID; choose one of: ${allPruids.join(", ")}`);
}

function extractPartition(pruid, outputPath) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      "jq",
      [
        "-c",
        "--arg",
        "pruid",
        pruid,
        '{type:"FeatureCollection",features:[.features[] | select(.properties.PRUID == $pruid)]}',
        inputPath,
      ],
      { stdio: ["ignore", "pipe", "pipe"] },
    );
    const output = [];
    const errors = [];
    child.stdout.on("data", (chunk) => output.push(chunk));
    child.stderr.on("data", (chunk) => errors.push(chunk));
    child.on("error", reject);
    child.on("close", async (code) => {
      if (code !== 0) {
        reject(new Error(`jq failed for PRUID ${pruid}: ${Buffer.concat(errors).toString("utf8")}`));
        return;
      }
      try {
        await writeFile(outputPath, Buffer.concat(output));
        resolve();
      } catch (error) {
        reject(error);
      }
    });
  });
}

const temporaryDirectory = await mkdtemp(join(tmpdir(), "synthpopcan-csd-"));
let reports = [];
try {
  const previous = JSON.parse(await readFile(manifestPath, "utf8"));
  if (Array.isArray(previous.boundaries)) reports = previous.boundaries;
} catch {
  // No prior batch manifest exists yet.
}
try {
  for (const pruid of pruids) {
    const partitionPath = join(temporaryDirectory, `${pruid}.geojson`);
    const outputPath = join(outputDirectory, `2021-boundary-csd-${pruid}-display-topo.geojson`);
    process.stderr.write(`Extracting and simplifying CSD PRUID ${pruid}\n`);
    await extractPartition(pruid, partitionPath);
    const report = await simplifyBoundaries({ inputPath: partitionPath, outputPath });
    reports = [...reports.filter((item) => item.output !== report.output), report];
    process.stdout.write(`${JSON.stringify(report)}\n`);
    await writeFile(
      manifestPath,
      `${JSON.stringify(
        {
          representation: "display-only-topology-preserving-weighted-simplification",
          partitionedBy: "PRUID",
          keep: 0.1,
          coordinatePrecision: 5,
          boundaries: reports,
        },
        null,
        2,
      )}\n`,
    );
  }
} finally {
  await rm(temporaryDirectory, { recursive: true, force: true });
}
