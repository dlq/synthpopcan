export const WDS_SELECTION_SCHEMA = "synthpopcan-wds-selection-v1";

export function detailedCategories(values) {
  const detailed = values.filter((value) => !isAggregateCategory(value));
  return detailed.length > 0 ? detailed : [...values];
}

export function ageCategoriesForScheme(values, scheme) {
  if (scheme === "single-year") {
    return values.filter(
      (value) => /^\d+ years?$/.test(value) || /^\d+ years and over$/.test(value),
    );
  }
  if (scheme === "five-year") {
    return values.filter((value) => {
      const match = /^(\d+) to (\d+) years$/.exec(value);
      return match ? Number(match[2]) - Number(match[1]) === 4 : false;
    });
  }
  return [...values];
}

export function filterWdsControlRows(rows, categories) {
  return rows.filter((row) =>
    Object.entries(categories).every(
      ([dimension, values]) => values.length > 0 && values.includes(row[dimension]),
    ),
  );
}

export function summarizeWdsSelection(rows) {
  return {
    cells: rows.length,
    estimatedTotal: Math.round(
      rows.reduce((total, row) => total + Number(row.count || 0), 0),
    ),
  };
}

export function buildWdsSelectionManifest({ productId, referencePeriod, categories }) {
  return {
    schema_version: WDS_SELECTION_SCHEMA,
    product_id: productId,
    reference_period: referencePeriod,
    categories,
  };
}

function isAggregateCategory(value) {
  return /^(all|both|total)\b/i.test(value);
}
