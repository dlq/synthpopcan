/**
 * Produce a topology-preserving, display-only GeoJSON boundary file.
 *
 * Usage:
 *   npm run simplify:boundaries -- INPUT.geojson OUTPUT.geojson [--keep 0.10]
 *
 * The canonical input is never changed.  The TopoJSON topology stores a shared
 * border once, so weighted simplification removes the same vertices from both
 * sides of every adjacent polygon.  The output is appropriate for web maps,
 * not analysis or spatial joins.
 */

import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";

import { feature } from "topojson-client";
import { topology } from "topojson-server";
import { presimplify, quantile, simplify } from "topojson-simplify";

const DEFAULT_KEEP = 0.1;
const DEFAULT_COORDINATE_PRECISION = 5;
const TOPOLOGY_QUANTIZATION = 10_000_000;

function usage(message) {
  if (message) process.stderr.write(`Error: ${message}\n\n`);
  process.stderr.write(
    "Usage: npm run simplify:boundaries -- INPUT.geojson OUTPUT.geojson [--keep 0.10] [--precision 5]\n",
  );
}

function parseArgs(args) {
  const positional = [];
  let keep = DEFAULT_KEEP;
  let coordinatePrecision = DEFAULT_COORDINATE_PRECISION;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--keep") {
      keep = Number(args[++index]);
      continue;
    }
    if (arg === "--precision") {
      coordinatePrecision = Number(args[++index]);
      continue;
    }
    positional.push(arg);
  }
  if (positional.length !== 2) throw new Error("input and output paths are required");
  if (!Number.isFinite(keep) || keep <= 0 || keep > 1) {
    throw new Error("--keep must be a number in (0, 1]");
  }
  if (!Number.isInteger(coordinatePrecision) || coordinatePrecision < 0 || coordinatePrecision > 9) {
    throw new Error("--precision must be an integer from 0 to 9");
  }
  return { inputPath: positional[0], outputPath: positional[1], keep, coordinatePrecision };
}

function coordinateCount(value) {
  if (!Array.isArray(value)) return 0;
  if (value.length === 2 && value.every(Number.isFinite)) return 1;
  return value.reduce((total, child) => total + coordinateCount(child), 0);
}

function featureIds(collection) {
  return collection.features.map((item) => item.properties?.geo_id).sort();
}

function referencedArcCounts(topology) {
  const counts = new Array(topology.arcs.length).fill(0);
  const countArcs = (arcs) => {
    for (const arc of arcs) {
      if (Array.isArray(arc)) {
        countArcs(arc);
      } else {
        counts[arc < 0 ? ~arc : arc] += 1;
      }
    }
  };
  const visitGeometry = (geometry) => {
    if (!geometry) return;
    if (geometry.type === "GeometryCollection") {
      for (const child of geometry.geometries) visitGeometry(child);
    } else if ("arcs" in geometry) {
      countArcs(geometry.arcs);
    }
  };
  for (const geometry of Object.values(topology.objects)) visitGeometry(geometry);
  return counts;
}

function preserveUnsharedArcs(weighted) {
  const references = referencedArcCounts(weighted);
  let protectedArcs = 0;
  for (const [index, arc] of weighted.arcs.entries()) {
    if (references[index] !== 1) continue;
    protectedArcs += 1;
    for (const point of arc) point[2] = Infinity;
  }
  return protectedArcs;
}

function roundCoordinates(value, precision) {
  if (!Array.isArray(value)) return value;
  if (value.length === 2 && value.every(Number.isFinite)) {
    return value.map((coordinate) => Number(coordinate.toFixed(precision)));
  }
  return value.map((item) => roundCoordinates(item, precision));
}

export async function simplifyBoundaries({
  inputPath,
  outputPath,
  keep = DEFAULT_KEEP,
  coordinatePrecision = DEFAULT_COORDINATE_PRECISION,
}) {
  const source = JSON.parse(await readFile(inputPath, "utf8"));
  if (source.type !== "FeatureCollection" || !Array.isArray(source.features)) {
    throw new Error("input must be a GeoJSON FeatureCollection");
  }
  if (source.features.some((item) => !item.properties?.geo_id)) {
    throw new Error("every input feature must have a non-empty properties.geo_id");
  }

  const sourceCoordinates = coordinateCount(source.features.map((item) => item.geometry?.coordinates));
  const encoded = topology({ boundaries: source }, TOPOLOGY_QUANTIZATION);
  const weighted = presimplify(encoded);
  // A boundary used by one polygon is an exterior edge: coastline, island,
  // provincial edge, or an unmatched edge in imperfect source topology. Keep
  // it exact. Only shared interior arcs are eligible for simplification.
  const protectedCoastlineArcs = preserveUnsharedArcs(weighted);
  // topojson.quantile sorts weights descending, so ``keep`` directly selects
  // the retained fraction. (Using 1 - keep would retain the opposite share.)
  const threshold = quantile(weighted, keep);
  const output = feature(simplify(weighted, threshold), "boundaries");
  if (output.type !== "FeatureCollection") {
    throw new Error("topology conversion did not produce a FeatureCollection");
  }
  for (const item of output.features) {
    if (item.geometry) {
      item.geometry.coordinates = roundCoordinates(item.geometry.coordinates, coordinatePrecision);
    }
  }
  if (output.features.length !== source.features.length) {
    throw new Error("simplification changed the feature count");
  }
  if (JSON.stringify(featureIds(output)) !== JSON.stringify(featureIds(source))) {
    throw new Error("simplification changed the geo_id set");
  }

  await writeFile(outputPath, JSON.stringify(output), "utf8");
  const outputCoordinates = coordinateCount(output.features.map((item) => item.geometry?.coordinates));
  return {
    input: basename(inputPath),
    output: basename(outputPath),
    features: output.features.length,
    keep,
    coordinatePrecision,
    inputCoordinates: sourceCoordinates,
    outputCoordinates,
    coordinateReduction: 1 - outputCoordinates / sourceCoordinates,
    protectedCoastlineArcs,
    representation: "display-only-topology-preserving-weighted-simplification",
  };
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    usage(error.message);
    process.exitCode = 2;
    return;
  }
  try {
    const report = await simplifyBoundaries(options);
    process.stdout.write(`${JSON.stringify(report)}\n`);
  } catch (error) {
    process.stderr.write(`Error: ${error.message}\n`);
    process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
