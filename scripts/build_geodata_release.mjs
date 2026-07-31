/** Build compressed, checksummed display-boundary release assets. */

import { createHash } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { pipeline } from "node:stream/promises";
import { Transform } from "node:stream";
import { createGzip } from "node:zlib";

const outputDirectory = "data/derived/geodata/release-assets/v1";
const releaseBaseUrl = process.env.SYNTHPOPCAN_GEODATA_RELEASE_BASE_URL?.replace(/\/$/, "");
const pruidPattern = /-(10|11|12|13|24|35|46|47|48|59|60|61|62)-display-topo\.geojson$/;
const pruidByAbbreviation = {
  ab: "48", bc: "59", mb: "46", nb: "13", nl: "10", ns: "12", nt: "61",
  nu: "62", on: "35", pe: "11", qc: "24", sk: "47", yt: "60",
};

async function paths(directory, pattern) {
  return (await readdir(directory))
    .filter((name) => pattern.test(name))
    .map((name) => join(directory, name))
    .sort();
}

const sources = [
  ...(await paths("data/derived/statcan/census/2016/boundaries", /-display-topo\.geojson$/)),
  "data/derived/statcan/census/2021/boundaries/2021-boundary-ct-display-topo.geojson",
  ...(await paths("data/work/canada-ada-2021/boundaries", /-display-topo\.geojson$/)),
  ...(await paths("data/work/canada-da-2021/boundaries", /-display-topo\.geojson$/)),
  ...(await paths("data/derived/statcan/census/2021/boundaries", /csd-..-display-topo\.geojson$/)),
];
const requested = process.argv.slice(2);
const selectedSources = requested.length
  ? sources.filter((sourcePath) => requested.some((value) => sourcePath.includes(value)))
  : sources;
if (requested.length && !selectedSources.length) {
  throw new Error(`no release source matched: ${requested.join(", ")}`);
}

function metadata(sourcePath, compressedPath, sourceStats, compressedStats, sha256, compressedSha256) {
  const name = basename(sourcePath);
  const year = Number(name.slice(0, 4));
  const level = name.match(/boundary-(ada|da|ct|csd)/)?.[1];
  const pruid = name.match(pruidPattern)?.[1]
    ?? pruidByAbbreviation[name.match(/-([a-z]{2})-display-topo\.geojson$/)?.[1]]
    ?? null;
  if (!level) throw new Error(`cannot infer geography level from ${name}`);
  return {
    id: `${year}-${level}${pruid ? `-${pruid}` : "-canada"}`,
    census_year: year,
    geography_level: level,
    pruid,
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

await mkdir(outputDirectory, { recursive: true });
let assets = [];
try {
  const previous = JSON.parse(await readFile(join(outputDirectory, "geodata-catalogue.json"), "utf8"));
  if (Array.isArray(previous.assets)) assets = previous.assets;
} catch {
  // The first batch creates the catalogue.
}
for (const sourcePath of selectedSources) {
  const outputPath = join(outputDirectory, `${basename(sourcePath)}.gz`);
  if (
    assets.some((asset) => asset.filename === basename(outputPath))
    && (await stat(outputPath).catch(() => null))
  ) {
    const sourceStats = await stat(sourcePath);
    const compressedStats = await stat(outputPath);
    const asset = metadata(
      sourcePath,
      outputPath,
      sourceStats,
      compressedStats,
      await sha256File(sourcePath),
      await sha256File(outputPath),
    );
    assets = [
      ...assets.filter(
        (item) => item.id !== asset.id && item.filename !== asset.filename,
      ),
      asset,
    ].sort((left, right) => left.id.localeCompare(right.id));
    await writeFile(
      join(outputDirectory, "geodata-catalogue.json"),
      `${JSON.stringify({ schema_version: "synthpopcan-geodata-catalogue-v1", release_version: "v1", assets }, null, 2)}\n`,
    );
    process.stdout.write(`Recorded ${asset.id}\n`);
    continue;
  }
  const hash = createHash("sha256");
  const hashingStream = new Transform({
    transform(chunk, _encoding, callback) {
      hash.update(chunk);
      callback(null, chunk);
    },
  });
  await pipeline(
    createReadStream(sourcePath),
    hashingStream,
    createGzip({ level: 9 }),
    createWriteStream(outputPath),
  );
  const sourceStats = await stat(sourcePath);
  const compressedStats = await stat(outputPath);
  const sha256 = hash.digest("hex");
  const compressedSha256 = await sha256File(outputPath);
  const asset = metadata(sourcePath, outputPath, sourceStats, compressedStats, sha256, compressedSha256);
  assets = [
    ...assets.filter(
      (item) => item.id !== asset.id && item.filename !== asset.filename,
    ),
    asset,
  ].sort((left, right) => left.id.localeCompare(right.id));
  process.stdout.write(`${asset.id}\n`);
  await writeFile(
    join(outputDirectory, "geodata-catalogue.json"),
    `${JSON.stringify({ schema_version: "synthpopcan-geodata-catalogue-v1", release_version: "v1", assets }, null, 2)}\n`,
  );
}
