const WDS_METADATA_COLUMNS = new Set([
  "STATUS",
  "SYMBOL",
  "TERMINATED",
  "DECIMALS",
  "SCALAR_FACTOR",
  "SCALAR_ID",
  "VECTOR",
  "COORDINATE",
  "DGUID",
  "UOM",
  "UOM_ID",
]);

export function normalizeWdsRows(
  rows,
  { dimensions, countColumn, marginName = "wds" },
) {
  if (!rows.length) {
    throw new Error("WDS table has no rows.");
  }
  const outputDimensions = dimensions
    .map((dimension) => dimension.trim())
    .filter(Boolean);
  if (!outputDimensions.length) {
    throw new Error("Choose at least one WDS dimension.");
  }
  const seen = new Set();
  const controlRows = [];
  rows.forEach((row, index) => {
    const rowNumber = index + 2;
    if (row[countColumn] === "") {
      return;
    }
    const count = Number(row[countColumn]);
    if (!Number.isFinite(count)) {
      throw new Error(`WDS row ${rowNumber} has invalid count.`);
    }
    const key = JSON.stringify(
      outputDimensions.map((dimension) => row[dimension] ?? ""),
    );
    if (seen.has(key)) {
      throw new Error(`WDS row ${rowNumber} duplicates control cell ${key}.`);
    }
    seen.add(key);
    controlRows.push(
      Object.fromEntries([
        ["margin", marginName],
        ["dimensions", outputDimensions.join(",")],
        ...outputDimensions.map((dimension) => [dimension, row[dimension] ?? ""]),
        ["count", String(count)],
      ]),
    );
  });
  return controlRows;
}

export function buildSeedRowsFromControlRows(controlRows) {
  const seen = new Set();
  const seedRows = [];
  controlRows.forEach((row) => {
    const dimensions = String(row.dimensions)
      .split(",")
      .map((dimension) => dimension.trim())
      .filter(Boolean);
    const values = Object.fromEntries(
      dimensions.map((dimension) => [dimension, row[dimension] ?? ""]),
    );
    const key = JSON.stringify(values);
    if (!seen.has(key)) {
      seen.add(key);
      seedRows.push({ id: `seed-${seedRows.length + 1}`, ...values });
    }
  });
  return seedRows;
}

export function chooseWdsDataCsvEntry(entries) {
  const csvEntries = entries.filter((entry) =>
    entry.name.toLowerCase().endsWith(".csv"),
  );
  const dataEntries = csvEntries.filter(
    (entry) => !entry.name.toLowerCase().includes("metadata"),
  );
  const selected = dataEntries[0] ?? csvEntries[0];
  if (!selected) {
    throw new Error("No CSV file found inside the WDS ZIP.");
  }
  return selected;
}

export function resolveWdsDimensions(rows, dimensions) {
  const columns = Object.keys(rows[0] ?? {});
  const columnsByLowercase = new Map(
    columns.map((column) => [column.toLowerCase(), column]),
  );
  return dimensions
    .map((dimension) => dimension.trim())
    .filter(Boolean)
    .map((dimension) => {
      if (columns.includes(dimension)) {
        return dimension;
      }
      if (dimension.toLowerCase() === "geography" && columns.includes("GEO")) {
        return "GEO";
      }
      return columnsByLowercase.get(dimension.toLowerCase()) ?? dimension;
    });
}

export function snapshotWdsRows(rows, dimensions) {
  if (
    !rows.length ||
    !Object.hasOwn(rows[0], "REF_DATE") ||
    dimensions.includes("REF_DATE")
  ) {
    return { rows, referencePeriod: null };
  }
  const referencePeriods = [
    ...new Set(rows.map((row) => row.REF_DATE).filter(Boolean)),
  ].sort(compareReferencePeriods);
  const referencePeriod = referencePeriods.at(-1) ?? null;
  if (referencePeriod === null) {
    return { rows, referencePeriod: null };
  }
  return {
    rows: rows.filter((row) => row.REF_DATE === referencePeriod),
    referencePeriod,
  };
}

export function suggestWdsColumns(rows) {
  if (!rows.length) {
    return { dimensions: [], countColumn: "VALUE" };
  }
  const columns = Object.keys(rows[0]);
  const numericColumns = columns.filter((column) => {
    if (column.toUpperCase() === "VALUE") {
      return true;
    }
    if (WDS_METADATA_COLUMNS.has(column.toUpperCase())) {
      return false;
    }
    return (
      rows.slice(0, 25).some((row) => row[column] !== "") &&
      rows
        .slice(0, 25)
        .filter((row) => row[column] !== "")
        .every((row) => Number.isFinite(Number(row[column])))
    );
  });
  const countColumn = numericColumns.includes("VALUE")
    ? "VALUE"
    : (numericColumns[0] ?? "VALUE");
  const dimensions = columns.filter((column) => {
    return column !== countColumn && !WDS_METADATA_COLUMNS.has(column.toUpperCase());
  });
  return { dimensions, countColumn };
}

function compareReferencePeriods(left, right) {
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber - rightNumber;
  }
  return left.localeCompare(right, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}
