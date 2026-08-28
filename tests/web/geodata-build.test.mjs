import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { gunzip, gzip } from "node:zlib";

import { buildGeodataRelease } from "../../scripts/build_geodata_release.mjs";
import { simplifyAllBoundaries } from "../../scripts/simplify_all_boundaries.mjs";

const gunzipAsync = promisify(gunzip);
const gzipAsync = promisify(gzip);
const silentStream = { write() {} };

function sha256(contents) {
  return createHash("sha256").update(contents).digest("hex");
}

test("all-boundary simplification merges reports when a partial run resumes", async () => {
  const boundaryRoot = await mkdtemp(join(tmpdir(), "synthpopcan-boundaries-"));
  const boundaryDirectory = join(boundaryRoot, "2021", "boundaries");
  await mkdir(boundaryDirectory, { recursive: true });
  const firstInput = join(boundaryDirectory, "2021-boundary-csd.geojson");
  const secondInput = join(boundaryDirectory, "2021-boundary-da.geojson");
  await writeFile(firstInput, "first");
  await writeFile(secondInput, "second");

  let failDa = true;
  const calls = [];
  const simplify = async ({ inputPath, outputPath }) => {
    calls.push(basename(inputPath));
    if (failDa && inputPath === secondInput) throw new Error("interrupted");
    await writeFile(outputPath, `simplified ${basename(inputPath)}`);
    return {
      input: basename(inputPath),
      output: basename(outputPath),
      features: 1,
      keep: 0.1,
      coordinatePrecision: 5,
      representation: "display-only-topology-preserving-weighted-simplification",
    };
  };

  const firstRun = await simplifyAllBoundaries({
    boundaryRoot,
    simplify,
    stdout: silentStream,
    stderr: silentStream,
  });
  assert.equal(firstRun.boundaries.length, 1);
  assert.deepEqual(firstRun.failures, [{ input: secondInput, error: "interrupted" }]);

  failDa = false;
  const resumed = await simplifyAllBoundaries({
    boundaryRoot,
    simplify,
    stdout: silentStream,
    stderr: silentStream,
  });
  assert.deepEqual(
    resumed.boundaries.map((report) => report.input).sort(),
    [basename(firstInput), basename(secondInput)].sort(),
  );
  assert.deepEqual(resumed.failures, []);
  assert.deepEqual(calls, [
    basename(firstInput),
    basename(secondInput),
    basename(secondInput),
  ]);

  const manifest = JSON.parse(
    await readFile(join(boundaryRoot, "boundary-display-simplification.json"), "utf8"),
  );
  assert.deepEqual(manifest.boundaries, resumed.boundaries);
  assert.deepEqual(manifest.failures, []);
  assert.match(manifest.boundaries[0].inputSha256, /^[0-9a-f]{64}$/);
  assert.match(manifest.boundaries[0].outputSha256, /^[0-9a-f]{64}$/);
  assert.equal(
    (await readdir(boundaryRoot)).some((name) => name.endsWith(".tmp")),
    false,
  );
  assert.equal(
    (await readdir(boundaryDirectory)).some((name) => name.endsWith(".tmp")),
    false,
  );
});

test("all-boundary simplification rebuilds unreported or changed outputs", async () => {
  const boundaryRoot = await mkdtemp(join(tmpdir(), "synthpopcan-boundary-resume-"));
  const boundaryDirectory = join(boundaryRoot, "2021", "boundaries");
  await mkdir(boundaryDirectory, { recursive: true });
  const inputPath = join(boundaryDirectory, "2021-boundary-da.geojson");
  const outputPath = inputPath.replace(/\.geojson$/, "-display-topo.geojson");
  await writeFile(inputPath, "source version one");
  await writeFile(outputPath, "unreported interrupted output");

  let calls = 0;
  const simplify = async () => {
    calls += 1;
    await writeFile(outputPath, `simplified call ${calls}`);
    return {
      input: basename(inputPath),
      output: basename(outputPath),
      features: 1,
      keep: 0.1,
      coordinatePrecision: 5,
      representation: "display-only-topology-preserving-weighted-simplification",
    };
  };
  const options = {
    boundaryRoot,
    simplify,
    stdout: silentStream,
    stderr: silentStream,
  };

  const first = await simplifyAllBoundaries(options);
  assert.equal(calls, 1);
  assert.equal(first.boundaries.length, 1);
  assert.equal(first.boundaries[0].inputSizeBytes, "source version one".length);
  assert.equal(first.boundaries[0].outputSizeBytes, "simplified call 1".length);

  await simplifyAllBoundaries(options);
  assert.equal(calls, 1, "a matching fingerprint should resume without rebuilding");

  const manifestPath = join(boundaryRoot, "boundary-display-simplification.json");
  const incompatibleManifest = JSON.parse(await readFile(manifestPath, "utf8"));
  incompatibleManifest.boundaries[0].keep = 0.2;
  await writeFile(manifestPath, JSON.stringify(incompatibleManifest));
  await simplifyAllBoundaries(options);
  assert.equal(calls, 2, "an incompatible simplification report must be rebuilt");

  await writeFile(outputPath, "tampered output");
  await simplifyAllBoundaries(options);
  assert.equal(calls, 3, "a changed output must be rebuilt");

  await writeFile(inputPath, "source version two");
  await simplifyAllBoundaries(options);
  assert.equal(calls, 4, "a changed source must be rebuilt");
});

test("geodata release rebuilds stale and corrupt compressed assets", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-"));
  const outputDirectory = join(directory, "release");
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(sourcePath, "source version one");

  const first = await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  const firstAsset = first.assets[0];
  const firstOutputPath = join(outputDirectory, firstAsset.filename);
  assert.match(firstAsset.filename, /\.[0-9a-f]{64}\.geojson\.gz$/);
  assert.equal(
    (await gunzipAsync(await readFile(firstOutputPath))).toString(),
    "source version one",
  );

  await writeFile(sourcePath, "source version two is different");
  const second = await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  const secondAsset = second.assets[0];
  const secondOutputPath = join(outputDirectory, secondAsset.filename);
  assert.notEqual(secondAsset.filename, firstAsset.filename);
  assert.equal(
    (await gunzipAsync(await readFile(secondOutputPath))).toString(),
    "source version two is different",
  );
  assert.equal(
    (await gunzipAsync(await readFile(firstOutputPath))).toString(),
    "source version one",
    "the asset referenced by the prior catalogue must remain immutable",
  );

  await writeFile(secondOutputPath, "not a gzip stream");
  const repaired = await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  const repairedOutputPath = join(outputDirectory, repaired.assets[0].filename);
  assert.equal(
    (await gunzipAsync(await readFile(repairedOutputPath))).toString(),
    "source version two is different",
  );
  const catalogue = JSON.parse(
    await readFile(join(outputDirectory, "geodata-catalogue.json"), "utf8"),
  );
  assert.equal(catalogue.assets.length, 1);
  assert.equal(
    catalogue.assets[0].uncompressed_sha256,
    sha256("source version two is different"),
  );
  assert.equal(catalogue.assets[0].sha256, sha256(await readFile(repairedOutputPath)));
});

test("a partial geodata release preserves unselected catalogue assets", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-partial-"));
  const outputDirectory = join(directory, "release");
  const daSource = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  const csdSource = join(directory, "2021-boundary-csd-on-display-topo.geojson");
  await writeFile(daSource, "da version one");
  await writeFile(csdSource, "csd version one");
  await buildGeodataRelease({
    sourcePaths: [daSource, csdSource],
    outputDirectory,
    stdout: silentStream,
  });
  const originalCatalogue = JSON.parse(
    await readFile(join(outputDirectory, "geodata-catalogue.json"), "utf8"),
  );
  const originalCsd = originalCatalogue.assets.find(
    (asset) => asset.id === "2021-csd-35",
  );

  await writeFile(daSource, "da version two");
  const partial = await buildGeodataRelease({
    sourcePaths: [daSource],
    outputDirectory,
    stdout: silentStream,
  });
  assert.equal(partial.assets.length, 2);
  assert.deepEqual(
    partial.assets.find((asset) => asset.id === "2021-csd-35"),
    originalCsd,
  );
  assert.equal(
    partial.assets.find((asset) => asset.id === "2021-da-24").uncompressed_sha256,
    sha256("da version two"),
  );
});

test("a failed geodata build leaves the existing catalogue intact", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-atomic-"));
  const outputDirectory = join(directory, "release");
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(sourcePath, "valid source");
  await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  const cataloguePath = join(outputDirectory, "geodata-catalogue.json");
  const before = await readFile(cataloguePath, "utf8");
  const invalidSource = join(directory, "unclassifiable-display-topo.geojson");
  await writeFile(invalidSource, "invalid source");

  await assert.rejects(
    buildGeodataRelease({
      sourcePaths: [invalidSource],
      outputDirectory,
      stdout: silentStream,
    }),
    /cannot infer geography identity/,
  );
  assert.equal(await readFile(cataloguePath, "utf8"), before);
  assert.equal(
    (await readdir(outputDirectory)).some((name) => name.endsWith(".tmp")),
    false,
  );
});

test("a later source failure does not partially commit an earlier asset", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-batch-"));
  const outputDirectory = join(directory, "release");
  const validSource = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(validSource, "source version one");
  await buildGeodataRelease({
    sourcePaths: [validSource],
    outputDirectory,
    stdout: silentStream,
  });
  const cataloguePath = join(outputDirectory, "geodata-catalogue.json");
  const before = await readFile(cataloguePath, "utf8");
  const beforeAsset = JSON.parse(before).assets[0];
  await writeFile(validSource, "source version two");
  const invalidSource = join(directory, "2021-boundary-da-on-display-topo.geojson");

  await assert.rejects(
    buildGeodataRelease({
      sourcePaths: [validSource, invalidSource],
      outputDirectory,
      stdout: silentStream,
    }),
    /ENOENT/,
  );
  assert.equal(await readFile(cataloguePath, "utf8"), before);
  assert.equal(
    (
      await gunzipAsync(await readFile(join(outputDirectory, beforeAsset.filename)))
    ).toString(),
    "source version one",
  );
  assert.equal(
    (await readdir(outputDirectory)).filter((name) => name.endsWith(".gz")).length,
    2,
    "the earlier staged asset may remain unreferenced without changing the catalogue",
  );
  assert.equal(
    (await readdir(outputDirectory)).some((name) => name.endsWith(".lock")),
    false,
  );
});

test("geodata release migrates a legacy mutable filename without invalidating it", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-legacy-"));
  const outputDirectory = join(directory, "release");
  await mkdir(outputDirectory, { recursive: true });
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  const source = Buffer.from("legacy source");
  await writeFile(sourcePath, source);
  const legacyFilename = `${basename(sourcePath)}.gz`;
  const legacyPath = join(outputDirectory, legacyFilename);
  const compressed = await gzipAsync(source);
  await writeFile(legacyPath, compressed);
  await writeFile(
    join(outputDirectory, "geodata-catalogue.json"),
    JSON.stringify({
      schema_version: "synthpopcan-geodata-catalogue-v1",
      release_version: "v1",
      assets: [
        {
          id: "2021-da-24",
          census_year: 2021,
          geography_level: "da",
          pruid: "24",
          filename: legacyFilename,
          size_bytes: compressed.length,
          sha256: sha256(compressed),
          uncompressed_size_bytes: source.length,
          uncompressed_sha256: sha256(source),
        },
      ],
    }),
  );

  const result = await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  assert.notEqual(result.assets[0].filename, legacyFilename);
  assert.match(result.assets[0].filename, /\.[0-9a-f]{64}\.geojson\.gz$/);
  assert.deepEqual(await readFile(legacyPath), compressed);
  assert.deepEqual(
    await readFile(join(outputDirectory, result.assets[0].filename)),
    compressed,
  );
});

test("geodata release refuses source changes before publishing staged bytes", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-race-"));
  const outputDirectory = join(directory, "release");
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(sourcePath, "stable source");
  let fingerprints = 0;
  const fingerprintSource = async (path) => {
    const contents = await readFile(path);
    fingerprints += 1;
    return {
      size: contents.length,
      sha256: fingerprints === 2 ? "0".repeat(64) : sha256(contents),
    };
  };

  await assert.rejects(
    buildGeodataRelease({
      sourcePaths: [sourcePath],
      outputDirectory,
      stdout: silentStream,
      fingerprintSource,
    }),
    /source changed while compressing/,
  );
  const outputNames = await readdir(outputDirectory);
  assert.deepEqual(outputNames, []);
});

test("geodata release rechecks the source before reusing a compressed asset", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-reuse-race-"));
  const outputDirectory = join(directory, "release");
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(sourcePath, "stable source");
  await buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
  });
  const cataloguePath = join(outputDirectory, "geodata-catalogue.json");
  const before = await readFile(cataloguePath, "utf8");
  let fingerprints = 0;
  const fingerprintSource = async (path) => {
    const contents = await readFile(path);
    fingerprints += 1;
    return {
      size: contents.length,
      sha256: fingerprints === 2 ? "f".repeat(64) : sha256(contents),
    };
  };

  await assert.rejects(
    buildGeodataRelease({
      sourcePaths: [sourcePath],
      outputDirectory,
      stdout: silentStream,
      fingerprintSource,
    }),
    /source changed while validating/,
  );
  assert.equal(await readFile(cataloguePath, "utf8"), before);
  assert.equal(
    (await readdir(outputDirectory)).some((name) => name.endsWith(".tmp")),
    false,
  );
});

test("geodata release refuses a concurrent writer and releases its lock", async () => {
  const directory = await mkdtemp(join(tmpdir(), "synthpopcan-geodata-lock-"));
  const outputDirectory = join(directory, "release");
  const sourcePath = join(directory, "2021-boundary-da-qc-display-topo.geojson");
  await writeFile(sourcePath, "stable source");
  let announceEntry;
  let releaseFirst;
  const entered = new Promise((resolve) => {
    announceEntry = resolve;
  });
  const gate = new Promise((resolve) => {
    releaseFirst = resolve;
  });
  let paused = false;
  const blockingFingerprint = async (path) => {
    const contents = await readFile(path);
    if (!paused) {
      paused = true;
      announceEntry();
      await gate;
    }
    return { size: contents.length, sha256: sha256(contents) };
  };
  const first = buildGeodataRelease({
    sourcePaths: [sourcePath],
    outputDirectory,
    stdout: silentStream,
    fingerprintSource: blockingFingerprint,
  });
  await entered;
  try {
    await assert.rejects(
      buildGeodataRelease({
        sourcePaths: [sourcePath],
        outputDirectory,
        stdout: silentStream,
      }),
      /another geodata release build holds/,
    );
  } finally {
    releaseFirst();
  }
  await first;
  assert.equal(
    (await readdir(outputDirectory)).some((name) => name.endsWith(".lock")),
    false,
  );
});
