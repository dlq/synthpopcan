/** Generate display-only topology-preserving derivatives for canonical boundaries. */

import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  readFile,
  readdir,
  rename,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

import { simplifyBoundaries } from "./simplify_boundaries.mjs";

const DEFAULT_BOUNDARY_ROOT = "data/derived/statcan/census";
const REPRESENTATION = "display-only-topology-preserving-weighted-simplification";
const KEEP = 0.1;
const COORDINATE_PRECISION = 5;

async function canonicalBoundaries(boundaryRoot) {
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

async function loadManifest(manifestPath) {
  try {
    const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
    if (!Array.isArray(manifest.boundaries) || !Array.isArray(manifest.failures)) {
      throw new Error("boundaries and failures must be arrays");
    }
    return manifest;
  } catch (error) {
    if (error.code === "ENOENT") return { boundaries: [], failures: [] };
    throw new Error(`could not load ${manifestPath}: ${error.message}`, { cause: error });
  }
}

async function writeManifestAtomic(manifestPath, manifest) {
  const temporaryPath = `${manifestPath}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporaryPath, `${JSON.stringify(manifest, null, 2)}\n`, { flag: "wx" });
    await rename(temporaryPath, manifestPath);
  } catch (error) {
    await unlink(temporaryPath).catch(() => undefined);
    throw error;
  }
}

function reportKey(report) {
  return report.output ?? report.input;
}

async function fileFingerprint(path) {
  const before = await stat(path);
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  const after = await stat(path);
  if (
    before.size !== after.size ||
    before.mtimeMs !== after.mtimeMs ||
    before.ctimeMs !== after.ctimeMs ||
    before.ino !== after.ino
  ) {
    throw new Error(`file changed while fingerprinting ${path}`);
  }
  return { size: after.size, sha256: hash.digest("hex") };
}

function fingerprintMatches(report, input, output) {
  return (
    report?.representation === REPRESENTATION &&
    report.keep === KEEP &&
    report.coordinatePrecision === COORDINATE_PRECISION &&
    report?.inputSizeBytes === input.size &&
    report.inputSha256 === input.sha256 &&
    report.outputSizeBytes === output.size &&
    report.outputSha256 === output.sha256
  );
}

async function resumableReport({ reports, inputPath, outputPath }) {
  const outputName = basename(outputPath);
  const report = reports.get(outputName);
  if (!report || report.input !== basename(inputPath) || report.output !== outputName) {
    return null;
  }
  try {
    const [input, output] = await Promise.all([
      fileFingerprint(inputPath),
      fileFingerprint(outputPath),
    ]);
    return fingerprintMatches(report, input, output) ? report : null;
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function ordered(values, key) {
  return [...values].sort((left, right) => key(left).localeCompare(key(right)));
}

function manifestContents(reports, failures) {
  return {
    representation: REPRESENTATION,
    keep: KEEP,
    coordinatePrecision: COORDINATE_PRECISION,
    boundaries: ordered(reports.values(), reportKey),
    failures: ordered(failures.values(), (failure) => failure.input),
  };
}

export async function simplifyAllBoundaries({
  boundaryRoot = DEFAULT_BOUNDARY_ROOT,
  manifestPath = join(boundaryRoot, "boundary-display-simplification.json"),
  simplify = simplifyBoundaries,
  stdout = process.stdout,
  stderr = process.stderr,
} = {}) {
  const previous = await loadManifest(manifestPath);
  const reports = new Map(previous.boundaries.map((report) => [reportKey(report), report]));
  const failures = new Map(previous.failures.map((failure) => [failure.input, failure]));

  for (const inputPath of await canonicalBoundaries(boundaryRoot)) {
    const outputPath = inputPath.replace(/\.geojson$/, "-display-topo.geojson");
    const resumable = await resumableReport({ reports, inputPath, outputPath });
    if (resumable) {
      stderr.write(`Skipping existing ${outputPath}\n`);
      failures.delete(inputPath);
      continue;
    }

    const inputName = basename(inputPath);
    const outputName = basename(outputPath);
    reports.delete(outputName);
    reports.delete(inputName);
    failures.delete(inputPath);
    stderr.write(`Simplifying ${inputPath}\n`);
    try {
      const inputBefore = await fileFingerprint(inputPath);
      const rawReport = await simplify({ inputPath, outputPath });
      const [inputAfter, output] = await Promise.all([
        fileFingerprint(inputPath),
        fileFingerprint(outputPath),
      ]);
      if (
        inputBefore.size !== inputAfter.size ||
        inputBefore.sha256 !== inputAfter.sha256
      ) {
        throw new Error(`source changed while simplifying ${inputPath}`);
      }
      const report = {
        ...rawReport,
        inputSizeBytes: inputAfter.size,
        inputSha256: inputAfter.sha256,
        outputSizeBytes: output.size,
        outputSha256: output.sha256,
      };
      reports.set(reportKey(report), report);
      stdout.write(`${JSON.stringify(report)}\n`);
    } catch (error) {
      const failure = { input: inputPath, error: error.message };
      failures.set(inputPath, failure);
      stderr.write(`Could not simplify ${inputPath}: ${error.message}\n`);
    }

    await writeManifestAtomic(manifestPath, manifestContents(reports, failures));
  }

  const manifest = manifestContents(reports, failures);
  await writeManifestAtomic(manifestPath, manifest);
  return { boundaries: manifest.boundaries, failures: manifest.failures };
}

async function main() {
  const result = await simplifyAllBoundaries();
  if (result.failures.length) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
