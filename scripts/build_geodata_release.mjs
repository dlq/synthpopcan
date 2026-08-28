/** Build compressed, checksummed display-boundary release assets. */

import { createHash, randomUUID } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import {
  copyFile,
  mkdir,
  open,
  readFile,
  readdir,
  rename,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { basename, join } from "node:path";
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { pathToFileURL } from "node:url";
import { createGunzip, createGzip } from "node:zlib";

const DEFAULT_OUTPUT_DIRECTORY = "data/derived/geodata/release-assets/v1";
const BUILD_LOCK_FILENAME = ".geodata-release-build.lock";
const pruidPattern = /-(10|11|12|13|24|35|46|47|48|59|60|61|62)-display-topo\.geojson$/;
const pruidByAbbreviation = {
  ab: "48",
  bc: "59",
  mb: "46",
  nb: "13",
  nl: "10",
  ns: "12",
  nt: "61",
  nu: "62",
  on: "35",
  pe: "11",
  qc: "24",
  sk: "47",
  yt: "60",
};

async function paths(directory, pattern) {
  return (await readdir(directory))
    .filter((name) => pattern.test(name))
    .map((name) => join(directory, name))
    .sort();
}

async function releaseSources() {
  return [
    ...(await paths(
      "data/derived/statcan/census/2016/boundaries",
      /-display-topo\.geojson$/,
    )),
    "data/derived/statcan/census/2021/boundaries/2021-boundary-ct-display-topo.geojson",
    ...(await paths("data/work/canada-ada-2021/boundaries", /-display-topo\.geojson$/)),
    ...(await paths("data/work/canada-da-2021/boundaries", /-display-topo\.geojson$/)),
    ...(await paths(
      "data/derived/statcan/census/2021/boundaries",
      /csd-..-display-topo\.geojson$/,
    )),
  ];
}

function geographyIdentity(sourcePath) {
  const name = basename(sourcePath);
  const year = Number(name.slice(0, 4));
  const level = name.match(/boundary-(ada|da|ct|csd)/)?.[1];
  const pruid =
    name.match(pruidPattern)?.[1] ??
    pruidByAbbreviation[name.match(/-([a-z]{2})-display-topo\.geojson$/)?.[1]] ??
    null;
  if (!Number.isInteger(year) || !level) {
    throw new Error(`cannot infer geography identity from ${name}`);
  }
  return { id: `${year}-${level}${pruid ? `-${pruid}` : "-canada"}`, year, level, pruid };
}

function metadata({
  compressedPath,
  sourceStats,
  compressedStats,
  sha256,
  compressedSha256,
  releaseBaseUrl,
  identity,
}) {
  return {
    id: identity.id,
    census_year: identity.year,
    geography_level: identity.level,
    pruid: identity.pruid,
    filename: basename(compressedPath),
    ...(releaseBaseUrl ? { url: `${releaseBaseUrl}/${basename(compressedPath)}` } : {}),
    size_bytes: compressedStats.size,
    sha256: compressedSha256,
    uncompressed_size_bytes: sourceStats.size,
    uncompressed_sha256: sha256,
    representation: "display-only-topology-preserving-weighted-simplification",
    coastline_policy: "unshared exterior arcs preserved exactly",
    source: "Statistics Canada census boundary file",
  };
}

async function sha256File(path) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

async function fileFingerprint(path) {
  const before = await stat(path);
  const sha256 = await sha256File(path);
  const after = await stat(path);
  if (
    before.size !== after.size ||
    before.mtimeMs !== after.mtimeMs ||
    before.ctimeMs !== after.ctimeMs ||
    before.ino !== after.ino
  ) {
    throw new Error(`file changed while fingerprinting ${path}`);
  }
  return { sha256, size: after.size };
}

async function gzipMetadata(path) {
  const compressedHash = createHash("sha256");
  const uncompressedHash = createHash("sha256");
  let compressedSize = 0;
  let uncompressedSize = 0;
  const compressedHashingStream = new Transform({
    transform(chunk, _encoding, callback) {
      compressedHash.update(chunk);
      compressedSize += chunk.length;
      callback(null, chunk);
    },
  });
  for await (const chunk of createReadStream(path)
    .pipe(compressedHashingStream)
    .pipe(createGunzip())) {
    uncompressedHash.update(chunk);
    uncompressedSize += chunk.length;
  }
  return {
    sha256: compressedHash.digest("hex"),
    size: compressedSize,
    uncompressedSha256: uncompressedHash.digest("hex"),
    uncompressedSize,
  };
}

function sourceMatches(left, right) {
  return left.sha256 === right.sha256 && left.size === right.size;
}

function gzipMatchesSource(gzip, source) {
  return (
    gzip.uncompressedSha256 === source.sha256 && gzip.uncompressedSize === source.size
  );
}

function temporaryAssetPath(outputDirectory) {
  return join(outputDirectory, `.geodata-asset.${process.pid}.${randomUUID()}.tmp`);
}

async function stageReusableAsset(candidatePaths, outputDirectory, source) {
  for (const candidatePath of candidatePaths) {
    const temporaryPath = temporaryAssetPath(outputDirectory);
    try {
      await copyFile(candidatePath, temporaryPath);
      const compressed = await gzipMetadata(temporaryPath);
      if (gzipMatchesSource(compressed, source)) {
        return { temporaryPath, compressed };
      }
    } catch (error) {
      if (error.code !== "ENOENT" && !String(error.code).startsWith("Z_")) throw error;
    }
    await unlink(temporaryPath).catch(() => undefined);
  }
  return null;
}

async function compressFileStaged(sourcePath, outputDirectory) {
  const temporaryPath = temporaryAssetPath(outputDirectory);
  const sourceHash = createHash("sha256");
  const compressedHash = createHash("sha256");
  let sourceSize = 0;
  let compressedSize = 0;
  const hashingStream = new Transform({
    transform(chunk, _encoding, callback) {
      sourceHash.update(chunk);
      sourceSize += chunk.length;
      callback(null, chunk);
    },
  });
  const compressedHashingStream = new Transform({
    transform(chunk, _encoding, callback) {
      compressedHash.update(chunk);
      compressedSize += chunk.length;
      callback(null, chunk);
    },
  });
  try {
    await pipeline(
      createReadStream(sourcePath),
      hashingStream,
      createGzip({ level: 9 }),
      compressedHashingStream,
      createWriteStream(temporaryPath, { flags: "wx" }),
    );
    return {
      temporaryPath,
      source: { sha256: sourceHash.digest("hex"), size: sourceSize },
      compressed: { sha256: compressedHash.digest("hex"), size: compressedSize },
    };
  } catch (error) {
    await unlink(temporaryPath).catch(() => undefined);
    throw error;
  }
}

function contentAddressedFilename(sourcePath, compressedSha256) {
  const name = basename(sourcePath);
  const suffix = ".geojson";
  if (!name.endsWith(suffix)) {
    return `${name}.${compressedSha256}.gz`;
  }
  return `${name.slice(0, -suffix.length)}.${compressedSha256}${suffix}.gz`;
}

async function publishStagedAsset(temporaryPath, outputPath, expectedSha256) {
  const existingSha256 = await sha256File(outputPath).catch((error) => {
    if (error.code === "ENOENT") return null;
    throw error;
  });
  if (existingSha256 === expectedSha256) {
    await unlink(temporaryPath);
    return;
  }
  await rename(temporaryPath, outputPath);
}

function catalogueAssetPath(outputDirectory, asset) {
  if (!asset) return null;
  if (typeof asset.filename !== "string" || basename(asset.filename) !== asset.filename) {
    throw new Error(`invalid catalogue asset filename for ${asset.id ?? "unknown asset"}`);
  }
  return join(outputDirectory, asset.filename);
}

async function writeFileAtomic(path, contents) {
  const temporaryPath = `${path}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporaryPath, contents, { flag: "wx" });
    await rename(temporaryPath, path);
  } catch (error) {
    await unlink(temporaryPath).catch(() => undefined);
    throw error;
  }
}

async function acquireBuildLock(outputDirectory) {
  const path = join(outputDirectory, BUILD_LOCK_FILENAME);
  const token = randomUUID();
  let handle;
  try {
    handle = await open(path, "wx");
    await handle.writeFile(
      `${JSON.stringify({ token, pid: process.pid, acquired_at: new Date().toISOString() })}\n`,
    );
  } catch (error) {
    await handle?.close().catch(() => undefined);
    if (handle) await unlink(path).catch(() => undefined);
    if (error.code === "EEXIST") {
      throw new Error(
        `another geodata release build holds ${path}; if no build is running, inspect and remove the stale lock`,
        { cause: error },
      );
    }
    throw error;
  }

  let released = false;
  return async () => {
    if (released) return;
    released = true;
    await handle.close();
    let owner;
    try {
      owner = JSON.parse(await readFile(path, "utf8"));
    } catch (error) {
      if (error.code === "ENOENT") return;
      throw new Error(`could not verify geodata release lock ownership at ${path}`, {
        cause: error,
      });
    }
    if (owner.token !== token) {
      throw new Error(`geodata release lock ownership changed at ${path}`);
    }
    await unlink(path);
  };
}

async function loadCatalogue(cataloguePath) {
  try {
    const catalogue = JSON.parse(await readFile(cataloguePath, "utf8"));
    if (!Array.isArray(catalogue.assets)) throw new Error("assets must be an array");
    return catalogue.assets;
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw new Error(`could not load ${cataloguePath}: ${error.message}`, { cause: error });
  }
}

function catalogueContents(assets) {
  return `${JSON.stringify(
    {
      schema_version: "synthpopcan-geodata-catalogue-v1",
      release_version: "v1",
      assets,
    },
    null,
    2,
  )}\n`;
}

export async function buildGeodataRelease({
  sourcePaths,
  outputDirectory = DEFAULT_OUTPUT_DIRECTORY,
  releaseBaseUrl = process.env.SYNTHPOPCAN_GEODATA_RELEASE_BASE_URL?.replace(/\/$/, ""),
  stdout = process.stdout,
  fingerprintSource = fileFingerprint,
}) {
  await mkdir(outputDirectory, { recursive: true });
  const releaseLock = await acquireBuildLock(outputDirectory);
  try {
    const cataloguePath = join(outputDirectory, "geodata-catalogue.json");
    let assets = await loadCatalogue(cataloguePath);
    const messages = [];
    const requestedSources = sourcePaths.map((sourcePath) => ({
      sourcePath,
      identity: geographyIdentity(sourcePath),
    }));

    for (const { sourcePath, identity } of requestedSources) {
      const previousAsset = assets.find((item) => item.id === identity.id);
      const legacyPath = join(outputDirectory, `${basename(sourcePath)}.gz`);
      const candidatePaths = [
        ...new Set(
          [catalogueAssetPath(outputDirectory, previousAsset), legacyPath].filter(Boolean),
        ),
      ];
      const initialSource = await fingerprintSource(sourcePath);
      let staged = await stageReusableAsset(candidatePaths, outputDirectory, initialSource);
      let source;
      let reused = false;

      try {
        if (staged) {
          const stableSource = await fingerprintSource(sourcePath);
          if (!sourceMatches(initialSource, stableSource)) {
            throw new Error(`source changed while validating ${sourcePath}`);
          }
          source = stableSource;
          reused = true;
        } else {
          const compressed = await compressFileStaged(sourcePath, outputDirectory);
          staged = {
            temporaryPath: compressed.temporaryPath,
            compressed: compressed.compressed,
          };
          const stableSource = await fingerprintSource(sourcePath);
          if (!sourceMatches(compressed.source, stableSource)) {
            throw new Error(`source changed while compressing ${sourcePath}`);
          }
          source = stableSource;
        }

        const filename = contentAddressedFilename(sourcePath, staged.compressed.sha256);
        const outputPath = join(outputDirectory, filename);
        await publishStagedAsset(
          staged.temporaryPath,
          outputPath,
          staged.compressed.sha256,
        );
        const asset = metadata({
          compressedPath: outputPath,
          sourceStats: source,
          compressedStats: staged.compressed,
          sha256: source.sha256,
          compressedSha256: staged.compressed.sha256,
          releaseBaseUrl,
          identity,
        });
        assets = [
          ...assets.filter((item) => item.id !== asset.id),
          asset,
        ].sort((left, right) => left.id.localeCompare(right.id));
        messages.push(`${reused ? "Recorded " : ""}${asset.id}\n`);
      } finally {
        if (staged) await unlink(staged.temporaryPath).catch(() => undefined);
      }
    }

    if (requestedSources.length > 0) {
      await writeFileAtomic(cataloguePath, catalogueContents(assets));
      for (const message of messages) stdout.write(message);
    }
    return {
      schema_version: "synthpopcan-geodata-catalogue-v1",
      release_version: "v1",
      assets,
    };
  } finally {
    await releaseLock();
  }
}

async function main() {
  const sources = await releaseSources();
  const requested = process.argv.slice(2);
  const selectedSources = requested.length
    ? sources.filter((sourcePath) => requested.some((value) => sourcePath.includes(value)))
    : sources;
  if (requested.length && !selectedSources.length) {
    throw new Error(`no release source matched: ${requested.join(", ")}`);
  }
  await buildGeodataRelease({ sourcePaths: selectedSources });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
