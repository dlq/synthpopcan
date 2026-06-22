const WDS_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest";

export async function searchWdsTables(query, limit = 10) {
  const response = await fetch(`${WDS_BASE_URL}/getAllCubesListLite`);
  if (!response.ok) {
    throw new Error(`StatCan WDS search failed with HTTP ${response.status}`);
  }
  return searchWdsInventoryRows(await response.json(), query, limit);
}

export function searchWdsInventoryRows(rows, query, limit = 10) {
  const terms = String(query).toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) {
    throw new Error("Enter at least one search term.");
  }
  const matches = [];
  for (const row of rows) {
    const haystack = [
      row.productId,
      row.cansimId,
      row.cubeTitleEn,
      row.cubeTitleFr,
      row.cubeStartDate,
      row.cubeEndDate,
    ]
      .join(" ")
      .toLowerCase();
    if (terms.every((term) => haystack.includes(term))) {
      matches.push({
        productId: String(row.productId ?? ""),
        cansimId: String(row.cansimId ?? ""),
        title: String(row.cubeTitleEn ?? ""),
        startDate: String(row.cubeStartDate ?? ""),
        endDate: String(row.cubeEndDate ?? ""),
      });
      if (matches.length >= limit) {
        break;
      }
    }
  }
  return matches;
}

export async function fetchWdsMetadata(productId) {
  const response = await fetch(`${WDS_BASE_URL}/getCubeMetadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify([{ productId: Number(productId) }]),
  });
  if (!response.ok) {
    throw new Error(`StatCan WDS metadata failed with HTTP ${response.status}`);
  }
  const payload = await response.json();
  const first = payload[0];
  if (first?.status !== "SUCCESS" || !first?.object) {
    throw new Error(`StatCan WDS returned no metadata for ${productId}.`);
  }
  return summarizeWdsMetadata(first.object);
}

export async function fetchWdsDownloadUrl(
  productId,
  { fetchImpl = fetch, lang = "en" } = {},
) {
  if (!productId) {
    throw new Error("Enter a StatCan product ID first.");
  }
  const response = await fetchImpl(
    `${WDS_BASE_URL}/getFullTableDownloadCSV/${encodeURIComponent(productId)}/${lang}`,
  );
  if (!response.ok) {
    throw new Error(`download URL lookup returned HTTP ${response.status}`);
  }
  const payload = await response.json();
  if (payload.status !== "SUCCESS" || !payload.object) {
    throw new Error("StatCan did not return a downloadable ZIP URL.");
  }
  return payload.object;
}

export function summarizeWdsMetadata(metadata) {
  const dimensions = extractDimensionNames(metadata);
  return {
    productId: String(metadata.productId ?? ""),
    title: String(metadata.cubeTitleEn ?? ""),
    dateRange: formatDateRange(metadata.cubeStartDate, metadata.cubeEndDate),
    dimensions,
    hint: buildIpfHint(dimensions),
    suggestedControlColumns: dimensions,
  };
}

function formatDateRange(startDate, endDate) {
  const start = String(startDate ?? "").slice(0, 10);
  const end = String(endDate ?? "").slice(0, 10);
  if (start && end && start !== end) {
    return `${start} to ${end}`;
  }
  return start || end || "Not provided";
}

function extractDimensionNames(metadata) {
  const dimensions = Array.isArray(metadata.dimension)
    ? metadata.dimension
    : Array.isArray(metadata.dimensions)
      ? metadata.dimensions
      : [];
  return dimensions
    .map((dimension) => {
      return (
        dimension.dimensionNameEn ??
        dimension.dimensionName ??
        dimension.memberNameEn ??
        ""
      );
    })
    .map(String)
    .filter(Boolean);
}

function buildIpfHint(dimensions) {
  const normalized = dimensions.map((dimension) => dimension.toLowerCase());
  const hasGeography = normalized.some((dimension) => dimension.includes("geo"));
  const hasAge = normalized.some((dimension) => dimension.includes("age"));
  const hasSex = normalized.some(
    (dimension) => dimension === "sex" || dimension.includes("sex"),
  );
  const parts = [];
  if (hasGeography) {
    parts.push("geography");
  }
  if (hasAge) {
    parts.push("age group");
  }
  if (hasSex) {
    parts.push("sex");
  }
  if (hasAge && hasSex) {
    return `This looks plausible for IPF if your seed has matching ${joinHumanList(parts)} columns.`;
  }
  return "Inspect this table before IPF; use only dimensions that already exist in your seed CSV.";
}

function joinHumanList(items) {
  if (items.length < 2) {
    return items.join("");
  }
  return `${items.slice(0, -1).join(", ")}, and ${items.at(-1)}`;
}
