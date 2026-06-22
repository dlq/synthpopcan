export function buildAgeSexSeedRows() {
  return [
    { id: "1", age: "young", sex: "F" },
    { id: "2", age: "young", sex: "M" },
    { id: "3", age: "old", sex: "F" },
    { id: "4", age: "old", sex: "M" },
  ];
}

export function buildAgeSexControlRows() {
  return [
    { margin: "age", dimensions: "age", age: "young", sex: "", count: "60" },
    { margin: "age", dimensions: "age", age: "old", sex: "", count: "40" },
    { margin: "sex", dimensions: "sex", age: "", sex: "F", count: "50" },
    { margin: "sex", dimensions: "sex", age: "", sex: "M", count: "50" },
  ];
}

export function buildSeedTemplateRows(dimensions) {
  return [
    Object.fromEntries([
      ["id", "seed-1"],
      ...cleanDimensions(dimensions).map((d) => [d, ""]),
    ]),
  ];
}

export function buildControlTemplateRows(dimensions) {
  const cleaned = cleanDimensions(dimensions);
  return cleaned.map((dimension) => {
    return Object.fromEntries([
      ["margin", dimension],
      ["dimensions", dimension],
      ...cleaned.map((column) => [column, ""]),
      ["count", ""],
    ]);
  });
}

export function parseDimensionList(value) {
  return cleanDimensions(String(value).split(/[,\n]/));
}

function cleanDimensions(dimensions) {
  const seen = new Set();
  return dimensions
    .map((dimension) => String(dimension).trim())
    .filter((dimension) => dimension !== "")
    .filter((dimension) => {
      if (seen.has(dimension)) {
        return false;
      }
      seen.add(dimension);
      return true;
    });
}
