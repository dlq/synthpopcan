export function readControlTable(rows) {
  const grouped = new Map();
  const dimensions = new Set();

  rows.forEach((row, index) => {
    const rowNumber = index + 2;
    const marginDimensions = parseDimensions(row.dimensions ?? "");
    if (marginDimensions.length === 0) {
      throw new Error(`controls row ${rowNumber} has no dimensions`);
    }
    const count = Number(row.count);
    if (!Number.isFinite(count) || count < 0) {
      throw new Error(`controls row ${rowNumber} has invalid count`);
    }
    const marginName = String(row.margin ?? "").trim() || marginDimensions.join("|");
    const existing = grouped.get(marginName);
    if (existing && existing.dimensions.join("|") !== marginDimensions.join("|")) {
      throw new Error(`controls row ${rowNumber} mixes dimensions`);
    }
    const group = existing ?? {
      name: marginName,
      dimensions: marginDimensions,
      targets: new Map(),
    };
    const key = marginDimensions.map((dimension) => row[dimension] ?? "");
    const keyText = JSON.stringify(key);
    if (group.targets.has(keyText)) {
      throw new Error(`controls row ${rowNumber} duplicates target ${keyText}`);
    }
    group.targets.set(keyText, { key, target: count });
    marginDimensions.forEach((dimension) => {
      dimensions.add(dimension);
    });
    grouped.set(marginName, group);
  });

  return {
    margins: Array.from(grouped.values()).map((group) => ({
      name: group.name,
      dimensions: group.dimensions,
      targets: Array.from(group.targets.values()),
    })),
    dimensions: Array.from(dimensions),
  };
}

export function fitIpf(
  records,
  margins,
  { weightField = null, maxIterations = 100, tolerance = 1e-6 } = {},
) {
  if (records.length === 0) {
    throw new Error("IPF requires at least one seed record");
  }
  if (margins.length === 0) {
    throw new Error("IPF requires at least one margin");
  }
  const weights = initialWeights(records, weightField);
  const indexedMargins = indexMargins(records, margins);
  let maxAbsError = Number.POSITIVE_INFINITY;

  for (let iteration = 1; iteration <= maxIterations; iteration += 1) {
    indexedMargins.forEach((indexedMargin) => {
      indexedMargin.targets.forEach(({ keyText, target }) => {
        const indexes = indexedMargin.recordIndexes.get(keyText) ?? [];
        const current = indexes.reduce((total, recordIndex) => {
          return total + weights[recordIndex];
        }, 0);
        if (current === 0) {
          if (target === 0) {
            return;
          }
          throw new Error(
            `margin ${indexedMargin.dimensions.join(",")} target ${keyText} has no seed records`,
          );
        }
        const ratio = target / current;
        indexes.forEach((recordIndex) => {
          weights[recordIndex] *= ratio;
        });
      });
    });

    maxAbsError = calculateMaxAbsError(weights, indexedMargins);
    if (maxAbsError <= tolerance) {
      return { records, weights, converged: true, iterations: iteration, maxAbsError };
    }
  }
  return { records, weights, converged: false, iterations: maxIterations, maxAbsError };
}

export function weightsToRows(records, weights, idField = "id") {
  const existingColumns = new Set(records.flatMap((record) => Object.keys(record)));
  let weightColumn = "weight";
  let suffix = 1;
  while (existingColumns.has(weightColumn)) {
    weightColumn = suffix === 1 ? "fitted_weight" : `fitted_weight_${suffix}`;
    suffix += 1;
  }
  return records.map((record, index) => ({
    ...record,
    ...(idField in record ? {} : { seed_id: String(index + 1) }),
    [weightColumn]: formatNumber(weights[index]),
  }));
}

export function expandRecords(records, weights, idField = "id") {
  const reserved = new Set(["synthetic_id", "seed_id"]);
  const conflicting = Array.from(
    new Set(
      records.flatMap((record) =>
        Object.keys(record).filter((key) => reserved.has(key) && key !== idField),
      ),
    ),
  ).sort();
  if (conflicting.length > 0) {
    throw new Error(
      `seed records use reserved generated columns: ${conflicting.join(", ")}`,
    );
  }
  const counts = integerizeWeights(weights);
  const expanded = [];
  let syntheticId = 1;
  records.forEach((record, recordIndex) => {
    const seedId = String(record[idField] ?? recordIndex + 1);
    const attributes = Object.fromEntries(
      Object.entries(record).filter(([key]) => key !== idField),
    );
    for (let count = 0; count < counts[recordIndex]; count += 1) {
      expanded.push({
        synthetic_id: String(syntheticId),
        seed_id: seedId,
        ...attributes,
      });
      syntheticId += 1;
    }
  });
  return expanded;
}

export function integerizeWeights(weights) {
  weights.forEach((weight) => {
    if (!Number.isFinite(weight)) {
      throw new Error("weights must be finite");
    }
    if (weight < 0) {
      throw new Error("weights must be non-negative");
    }
  });
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  const targetTotal = roundHalfToEven(total);
  if (targetTotal < 0) {
    throw new Error("integerized total cannot be negative");
  }
  const counts = weights.map(() => 0);
  if (targetTotal === 0) return counts;

  const step = total / targetTotal;
  let recordIndex = 0;
  let cumulative = weights[0];
  for (let draw = 0; draw < targetTotal; draw += 1) {
    const point = (draw + 0.5) * step;
    while (recordIndex < weights.length - 1 && point >= cumulative - 1e-10) {
      recordIndex += 1;
      cumulative += weights[recordIndex];
    }
    counts[recordIndex] += 1;
  }
  return counts;
}

function roundHalfToEven(value) {
  const floor = Math.floor(value);
  const fraction = value - floor;
  if (fraction < 0.5) return floor;
  if (fraction > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

function parseDimensions(value) {
  return String(value)
    .split(/[|,]/)
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

function initialWeights(records, weightField) {
  if (!weightField) {
    return records.map(() => 1);
  }
  return records.map((record) => {
    const weight = Number(record[weightField]);
    if (!Number.isFinite(weight) || weight < 0) {
      throw new Error(`invalid seed weight in field ${weightField}`);
    }
    return weight;
  });
}

function indexMargins(records, margins) {
  return margins.map((margin) => {
    const recordIndexes = new Map();
    records.forEach((record, index) => {
      const key = margin.dimensions.map((dimension) => {
        if (!(dimension in record)) {
          throw new Error(`record is missing dimension ${dimension}`);
        }
        return String(record[dimension]);
      });
      const keyText = JSON.stringify(key);
      recordIndexes.set(keyText, [...(recordIndexes.get(keyText) ?? []), index]);
    });
    const targets = margin.targets.map(({ key, target }) => {
      const keyText = JSON.stringify(key.map(String));
      if (target > 0 && !recordIndexes.has(keyText)) {
        throw new Error(
          `margin ${margin.dimensions.join(",")} target ${keyText} has no seed records`,
        );
      }
      return { keyText, target };
    });
    return { dimensions: margin.dimensions, targets, recordIndexes };
  });
}

function calculateMaxAbsError(weights, indexedMargins) {
  let maxAbsError = 0;
  indexedMargins.forEach((indexedMargin) => {
    indexedMargin.targets.forEach(({ keyText, target }) => {
      const total = (indexedMargin.recordIndexes.get(keyText) ?? []).reduce(
        (sum, recordIndex) => sum + weights[recordIndex],
        0,
      );
      maxAbsError = Math.max(maxAbsError, Math.abs(total - target));
    });
  });
  return maxAbsError;
}

function formatNumber(value) {
  return Number.isInteger(value)
    ? String(value)
    : String(Number(value.toPrecision(12)));
}
