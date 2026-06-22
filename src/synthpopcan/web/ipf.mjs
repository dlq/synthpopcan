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
    if (!Number.isFinite(count)) {
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
  return records.map((record, index) => ({
    seed_id: String(record[idField] ?? index + 1),
    weight: formatNumber(weights[index]),
  }));
}

export function expandRecords(records, weights, idField = "id") {
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
  const floors = weights.map((weight) => {
    if (weight < 0) {
      throw new Error("weights must be non-negative");
    }
    return Math.trunc(weight);
  });
  const targetTotal = Math.round(weights.reduce((total, weight) => total + weight, 0));
  const remaining = targetTotal - floors.reduce((total, value) => total + value, 0);
  if (remaining < 0) {
    throw new Error("integerized total cannot be negative");
  }
  const remainders = weights
    .map((weight, index) => ({ index, remainder: weight - Math.trunc(weight) }))
    .sort(
      (left, right) => right.remainder - left.remainder || left.index - right.index,
    );
  const counts = [...floors];
  remainders.slice(0, remaining).forEach(({ index }) => {
    counts[index] += 1;
  });
  return counts;
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
