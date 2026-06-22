import { parseCsv, stringifyCsv } from "./csv.mjs";
import { previewCsv } from "./preview.mjs";
import {
  buildAgeSexControlRows,
  buildAgeSexSeedRows,
  buildControlTemplateRows,
  buildSeedTemplateRows,
  parseDimensionList,
} from "./starter-files.mjs";
import { fetchWdsDownloadUrl, fetchWdsMetadata, searchWdsTables } from "./statcan.mjs";
import { summarizeModelPayload } from "./tree-model.mjs";
import {
  buildSeedRowsFromControlRows,
  chooseWdsDataCsvEntry,
  normalizeWdsRows,
  resolveWdsDimensions,
  snapshotWdsRows,
  suggestWdsColumns,
} from "./wds-normalize.mjs";
import { csvEntries, readZipEntries } from "./zip.mjs";

const workflowButtons = document.querySelectorAll("[data-workflow-tab]");
const workflowPanels = document.querySelectorAll("[data-workflow-panel]");
const ipfForm = document.querySelector("#ipf-form");
const modelForm = document.querySelector("#model-form");
const wdsSearchForm = document.querySelector("#wds-search-form");
const wdsExplainForm = document.querySelector("#wds-explain-form");
let selectedModelText = null;
let selectedModelLabel = null;
let nextJobId = 1;

workflowButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const workflow = button.dataset.workflowTab;
    workflowButtons.forEach((item) => {
      item.classList.toggle("selected", item === button);
    });
    workflowPanels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.workflowPanel === workflow);
    });
  });
});

document.querySelector("#use-demo-ipf").addEventListener("click", () => {
  fillFileInput(
    "#ipf-seed-file",
    "demo-age-sex-seed.csv",
    stringifyCsv(buildAgeSexSeedRows()),
  );
  fillFileInput(
    "#ipf-controls-file",
    "demo-age-sex-controls.csv",
    stringifyCsv(buildAgeSexControlRows()),
  );
  document.querySelector("#ipf-weight-field").value = "";
  document.querySelector("#ipf-output-kind").value = "weights";
  showStatus(
    document.querySelector("#ipf-result"),
    "Demo seed and controls are loaded. Keep the defaults and select Run IPF.",
  );
});

loadPremadeModelCatalogue();

document.querySelector("#download-seed-template").addEventListener("click", () => {
  try {
    const dimensions = starterDimensions();
    downloadText(
      "synthpopcan-seed-template.csv",
      stringifyCsv(buildSeedTemplateRows(dimensions)),
      "text/csv",
    );
  } catch (error) {
    showError(document.querySelector("#ipf-result"), error);
  }
});

document.querySelector("#download-controls-template").addEventListener("click", () => {
  try {
    const dimensions = starterDimensions();
    downloadText(
      "synthpopcan-controls-template.csv",
      stringifyCsv(buildControlTemplateRows(dimensions)),
      "text/csv",
    );
  } catch (error) {
    showError(document.querySelector("#ipf-result"), error);
  }
});

wdsSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const resultBox = document.querySelector("#wds-result");
  const query = document.querySelector("#wds-search-query").value;
  showStatus(resultBox, "Searching StatCan WDS from the browser...");
  try {
    const rows = await searchWdsTables(query, 6);
    showWdsSearchResults(resultBox, rows);
  } catch (error) {
    showError(
      resultBox,
      new Error(
        `Browser search could not reach StatCan WDS. Try the CLI command instead: synthpopcan statcan wds search "${query}" --limit 10. ${error.message}`,
      ),
    );
  }
});

wdsExplainForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const resultBox = document.querySelector("#wds-result");
  const productId = document.querySelector("#wds-product-id").value.trim();
  showStatus(resultBox, "Inspecting StatCan WDS metadata from the browser...");
  try {
    const summary = await fetchWdsMetadata(productId);
    showWdsMetadata(resultBox, summary);
  } catch (error) {
    showError(
      resultBox,
      new Error(
        `Browser metadata lookup could not reach StatCan WDS. Try the CLI command instead: synthpopcan statcan wds explain ${productId}. ${error.message}`,
      ),
    );
  }
});

document
  .querySelector("#generate-from-product-id")
  .addEventListener("click", async () => {
    const resultBox = document.querySelector("#wds-result");
    const productId = document.querySelector("#wds-product-id").value.trim();
    showStatus(resultBox, "Fetching the StatCan table and filling the IPF files...");
    try {
      if (!productId) {
        throw new Error("Enter a Product ID first.");
      }
      const generated = await generateSeedAndControlsFromProduct(productId);
      loadGeneratedIpfFiles(generated);
      showGeneratedWdsResult(resultBox, generated, productId);
    } catch (error) {
      if (error.downloadUrl) {
        showWdsDownloadFallback(resultBox, productId, error.downloadUrl, error);
      } else {
        showError(resultBox, error);
      }
    }
  });

document
  .querySelector("#generate-from-downloaded-zip")
  .addEventListener("click", async () => {
    const resultBox = document.querySelector("#wds-result");
    const file = document.querySelector("#wds-zip-file").files?.[0];
    showStatus(
      resultBox,
      "Reading the selected StatCan ZIP and filling the IPF files...",
    );
    try {
      if (!file) {
        throw new Error("Choose a downloaded StatCan ZIP first.");
      }
      const generated = await generateSeedAndControlsFromZip(await file.arrayBuffer());
      loadGeneratedIpfFiles(generated);
      showGeneratedWdsResult(resultBox, generated, file.name);
    } catch (error) {
      showError(resultBox, error);
    }
  });

ipfForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const resultBox = document.querySelector("#ipf-result");
  showStatus(resultBox, "Running IPF in the browser...");

  try {
    const result = await runBrowserJob({
      type: "ipf",
      seedText: await readFileText("#ipf-seed-file"),
      controlsText: await readFileText("#ipf-controls-file"),
      weightField: valueOrNull("#ipf-weight-field"),
      outputKind: document.querySelector("#ipf-output-kind").value,
      maxExpandedRows: 100000,
      maxIterations: numberValue("#ipf-max-iterations"),
      tolerance: numberValue("#ipf-tolerance"),
    });
    showDownloads(resultBox, result);
  } catch (error) {
    showError(resultBox, error);
  }
});

modelForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const resultBox = document.querySelector("#model-result");
  showStatus(resultBox, "Generating rows in the browser...");

  try {
    const result = await runBrowserJob({
      type: "model",
      modelText: await currentModelText(),
      rows: numberValue("#model-rows"),
      conditionsText: document.querySelector("#model-conditions").value,
      randomSeed: numberValue("#model-random-seed"),
    });
    showDownloads(resultBox, result);
  } catch (error) {
    showError(resultBox, error);
  }
});

document.querySelector("#inspect-model-file").addEventListener("click", async () => {
  const resultBox = document.querySelector("#model-inspect-result");
  showStatus(resultBox, "Inspecting the selected model...");
  try {
    const payload = JSON.parse(await currentModelText());
    showModelSummary(resultBox, summarizeModelPayload(payload), selectedModelLabel);
  } catch (error) {
    showError(resultBox, error);
  }
});

document.querySelector("#model-file").addEventListener("change", () => {
  selectedModelText = null;
  selectedModelLabel = null;
  document.querySelector("#premade-model").value = "";
});

document.querySelector("#load-premade-model").addEventListener("click", async () => {
  const resultBox = document.querySelector("#model-inspect-result");
  const select = document.querySelector("#premade-model");
  const modelId = select.value;
  showStatus(resultBox, "Loading the premade model...");
  try {
    if (!modelId) {
      throw new Error("Choose a premade model first.");
    }
    const payload = await fetchJson(`/api/models/${encodeURIComponent(modelId)}`);
    selectedModelText = JSON.stringify(payload);
    selectedModelLabel = select.selectedOptions[0]?.textContent ?? modelId;
    document.querySelector("#model-file").value = "";
    showModelSummary(resultBox, summarizeModelPayload(payload), selectedModelLabel);
  } catch (error) {
    showError(resultBox, error);
  }
});

function runBrowserJob(job) {
  return new Promise((resolve, reject) => {
    const id = nextJobId;
    nextJobId += 1;
    const worker = new Worker(new URL("./worker.mjs", import.meta.url), {
      type: "module",
    });
    worker.addEventListener("message", (event) => {
      if (event.data.id !== id) {
        return;
      }
      worker.terminate();
      if (event.data.ok) {
        resolve(event.data.result);
      } else {
        reject(new Error(event.data.error));
      }
    });
    worker.addEventListener("error", (error) => {
      worker.terminate();
      reject(error);
    });
    worker.postMessage({ id, job });
  });
}

async function fetchWdsZip(productId) {
  const downloadUrl = await fetchWdsDownloadUrl(productId);
  try {
    const zipResponse = await fetch(downloadUrl);
    if (!zipResponse.ok) {
      throw new Error(`ZIP download returned HTTP ${zipResponse.status}`);
    }
    return zipResponse.arrayBuffer();
  } catch (error) {
    error.downloadUrl = downloadUrl;
    error.browserFetchFailed = true;
    throw error;
  }
}

async function loadPremadeModelCatalogue() {
  const select = document.querySelector("#premade-model");
  try {
    const payload = await fetchJson("/api/models");
    payload.models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = `${model.name} (${model.geography})`;
      option.title = model.description;
      select.append(option);
    });
  } catch {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Premade models unavailable";
    select.replaceChildren(option);
  }
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request returned HTTP ${response.status}`);
  }
  return response.json();
}

async function currentModelText() {
  if (selectedModelText !== null) {
    return selectedModelText;
  }
  return readFileText("#model-file");
}

async function generateSeedAndControlsFromProduct(productId) {
  const response = await fetch("/api/wds/seed-controls", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      productId,
      dimensions: currentWdsDimensions(),
      countColumn: document.querySelector("#wds-count-column").value.trim() || "VALUE",
    }),
  });
  if (response.ok) {
    const payload = await response.json();
    return {
      seedRows: parseCsv(payload.seedCsv),
      controlRows: parseCsv(payload.controlsCsv),
      dimensions: payload.dimensions,
      countColumn: payload.countColumn,
      csvMember: payload.csvMember,
      referencePeriod: payload.referencePeriod,
      downloadUrl: payload.downloadUrl,
      source: "local-helper",
    };
  }
  if (![404, 405, 501].includes(response.status)) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error ?? `Local helper returned HTTP ${response.status}`);
  }
  try {
    const zipBuffer = await fetchWdsZip(productId);
    return {
      ...(await generateSeedAndControlsFromZip(zipBuffer)),
      source: "browser-fetch",
    };
  } catch (error) {
    error.localHelperUnavailable = true;
    throw error;
  }
}

async function generateSeedAndControlsFromZip(zipBuffer) {
  const entries = csvEntries(await readZipEntries(zipBuffer));
  const entry = chooseWdsDataCsvEntry(entries);
  const rows = parseWdsCsv(entry.text);
  const suggestion = suggestWdsColumns(rows);
  const requestedDimensions = parseDimensionList(
    document.querySelector("#wds-dimensions").value || suggestion.dimensions.join(", "),
  );
  const dimensions = resolveWdsDimensions(rows, requestedDimensions);
  const countColumn =
    document.querySelector("#wds-count-column").value.trim() || suggestion.countColumn;
  document.querySelector("#wds-dimensions").value = dimensions.join(", ");
  document.querySelector("#wds-count-column").value = countColumn;
  const snapshot = snapshotWdsRows(rows, dimensions);
  const controlRows = normalizeWdsRows(snapshot.rows, {
    dimensions,
    countColumn,
    marginName: "wds",
  });
  const seedRows = buildSeedRowsFromControlRows(controlRows);
  return {
    seedRows,
    controlRows,
    dimensions,
    countColumn,
    csvMember: entry.name,
    referencePeriod: snapshot.referencePeriod,
  };
}

function parseWdsCsv(text) {
  return parseCsv(text);
}

function currentWdsDimensions() {
  const dimensions = parseDimensionList(
    document.querySelector("#wds-dimensions").value,
  );
  if (dimensions.length > 0) {
    return dimensions;
  }
  return parseDimensionList(document.querySelector("#starter-dimensions").value);
}

function loadGeneratedIpfFiles({ seedRows, controlRows }) {
  fillFileInput("#ipf-seed-file", "generated-wds-seed.csv", stringifyCsv(seedRows));
  fillFileInput(
    "#ipf-controls-file",
    "generated-wds-controls.csv",
    stringifyCsv(controlRows),
  );
  document.querySelector("#ipf-weight-field").value = "";
  document.querySelector("#ipf-output-kind").value = "weights";
}

function showGeneratedWdsResult(element, generated, sourceLabel) {
  revokeDownloads(element);
  element.className = "result-box success";
  const snapshotNote = generated.referencePeriod
    ? ` using REF_DATE ${generated.referencePeriod}`
    : "";
  const sourceNote =
    generated.source === "local-helper" ? " through the local Python helper" : "";
  const message = document.createElement("p");
  message.className = "result-message";
  message.textContent = `Generated ${generated.seedRows.length} seed rows and ${generated.controlRows.length} control rows from ${sourceLabel}${snapshotNote}${sourceNote}. The IPF form is filled and ready to run; downloads are `;
  const optional = document.createElement("strong");
  optional.className = "optional-note";
  optional.textContent = "optional";
  message.append(optional, ".");
  element.replaceChildren(message);
  appendDownloads(element, [
    {
      filename: "generated-wds-seed.csv",
      text: stringifyCsv(generated.seedRows),
      type: "text/csv",
    },
    {
      filename: "generated-wds-controls.csv",
      text: stringifyCsv(generated.controlRows),
      type: "text/csv",
    },
  ]);
}

function showWdsDownloadFallback(element, productId, downloadUrl, error) {
  revokeDownloads(element);
  element.className = "result-box warning";
  element.textContent = fallbackMessage(error);
  const list = document.createElement("div");
  list.className = "result-list";
  const linkItem = document.createElement("div");
  linkItem.className = "result-item";
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.className = "download-link";
  link.textContent = `Download ${productId} WDS ZIP`;
  link.target = "_blank";
  link.rel = "noreferrer";
  linkItem.append(link);
  list.append(
    linkItem,
    resultItem(
      "After download",
      "Choose the ZIP as the Downloaded StatCan ZIP, then select Use selected ZIP.",
    ),
    resultItem("Why this happened", fallbackReason(error)),
  );
  element.append(list);
}

function fallbackMessage(error) {
  if (error.localHelperUnavailable) {
    return "The local Python helper was not available, and the browser could not fetch the StatCan ZIP directly.";
  }
  return "The browser could not fetch the StatCan ZIP directly.";
}

function fallbackReason(error) {
  if (error.localHelperUnavailable) {
    return "This page is probably being served by an older static-only server. Restart `synthpopcan serve` so /api/wds/seed-controls is available. The browser fallback also failed because StatCan's ZIP download is blocked by browser cross-origin rules.";
  }
  if (error.browserFetchFailed) {
    return "StatCan's ZIP download can be opened by a browser tab, but JavaScript fetch is blocked by browser cross-origin rules.";
  }
  return error.message;
}

function starterDimensions() {
  const dimensions = parseDimensionList(
    document.querySelector("#starter-dimensions").value,
  );
  if (dimensions.length === 0) {
    throw new Error("Enter at least one template dimension.");
  }
  return dimensions;
}

function fillFileInput(selector, filename, text) {
  const input = document.querySelector(selector);
  const file = new File([text], filename, { type: "text/csv" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
}

function downloadText(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showWdsSearchResults(element, rows) {
  revokeDownloads(element);
  element.className = "result-box success";
  if (rows.length === 0) {
    element.textContent = "No matching WDS tables found.";
    return;
  }
  element.textContent = "Matching WDS tables. Select a result to fill Product ID.";
  const list = document.createElement("div");
  list.className = "result-list";
  rows.forEach((row) => {
    const item = document.createElement("button");
    item.className = "result-item";
    item.type = "button";
    item.innerHTML = `<strong>${escapeHtml(row.productId)} · ${escapeHtml(row.title)}</strong><span>${escapeHtml(row.cansimId)} · ${escapeHtml(row.startDate)} to ${escapeHtml(row.endDate)}</span>`;
    item.addEventListener("click", () => {
      document.querySelector("#wds-product-id").value = row.productId;
    });
    list.append(item);
  });
  element.append(list);
}

function showWdsMetadata(element, summary) {
  revokeDownloads(element);
  element.className = "result-box success";
  element.textContent = `${summary.productId}: ${summary.title}`;
  const list = document.createElement("div");
  list.className = "result-list wds-metadata-list";
  list.append(
    resultItem("Dates", summary.dateRange),
    resultItem("Dimensions", summary.dimensions.join(", ")),
    resultItem("IPF note", summary.hint),
    resultItem(
      "Next",
      "Use Generate from Product ID to fill the IPF inputs. Downloaded StatCan ZIP is only for tables you already have or for static deployments without the local helper.",
    ),
  );
  element.append(list);
  document.querySelector("#starter-dimensions").value =
    summary.suggestedControlColumns.join(", ");
  document.querySelector("#wds-dimensions").value =
    summary.suggestedControlColumns.join(", ");
}

function showModelSummary(element, summary, sourceLabel = null) {
  revokeDownloads(element);
  element.className = "result-box success";
  element.textContent = sourceLabel
    ? `${sourceLabel}: ${summary.kind}. ${summary.outputs}.`
    : `${summary.kind}. ${summary.outputs}.`;
  const overview = document.createElement("div");
  overview.className = "model-overview-note";
  overview.append(resultItem("Package summary", modelOverviewText(summary)));
  element.append(overview);
  if (summary.linkage) {
    const linkage = document.createElement("div");
    linkage.className = "model-linkage-note";
    linkage.append(resultItem("How household/person linkage works", summary.linkage));
    element.append(linkage);
  }
  const modelDetails = document.createElement("div");
  modelDetails.className = "model-detail-list";
  const heading = document.createElement("strong");
  heading.textContent = "Included models";
  modelDetails.append(heading);
  summary.models.forEach((model) => {
    modelDetails.append(resultItem(model.name, model.text));
  });
  element.append(modelDetails);
  const terms = document.createElement("div");
  terms.className = "model-terms-list";
  const termsHeading = document.createElement("strong");
  termsHeading.textContent = "Terms used";
  terms.append(
    termsHeading,
    resultItem(
      "Publishable candidate",
      "A model package marked as suitable for sharing after privacy checks; it should not contain raw training rows.",
    ),
    resultItem(
      "Conditions",
      "Optional input columns used to filter generation, such as geo or household_size.",
    ),
    resultItem("Targets", "Columns the model generates in the synthetic output."),
    resultItem(
      "Conditional-frequency",
      "A simple tabular model that samples from observed category frequencies within matching condition groups.",
    ),
  );
  element.append(terms);
}

function modelOverviewText(summary) {
  const conditions =
    summary.conditions.length > 0
      ? summary.conditions.join(", ")
      : "no required conditioning columns";
  return `${summary.privacy}; release ${summary.release}; ${summary.rowsLabel.toLowerCase()}; generates ${summary.outputs}; conditions: ${conditions}.`;
}

function resultItem(title, text) {
  const item = document.createElement("div");
  item.className = "result-item";
  item.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span>`;
  return item;
}

async function readFileText(selector) {
  const input = document.querySelector(selector);
  const file = input.files?.[0];
  if (!file) {
    throw new Error(`Choose a file for ${input.labels?.[0]?.textContent.trim()}.`);
  }
  return file.text();
}

function valueOrNull(selector) {
  const value = document.querySelector(selector).value.trim();
  return value === "" ? null : value;
}

function numberValue(selector) {
  const input = document.querySelector(selector);
  const value = Number(input.value);
  if (!Number.isFinite(value)) {
    throw new Error(`${input.labels?.[0]?.textContent.trim()} must be a number.`);
  }
  return value;
}

function showStatus(element, message) {
  revokeDownloads(element);
  element.className = "result-box";
  element.textContent = message;
}

function showError(element, error) {
  revokeDownloads(element);
  element.className = "result-box error";
  element.textContent = error instanceof Error ? error.message : String(error);
}

function showDownloads(element, { message, downloads }) {
  revokeDownloads(element);
  element.className = "result-box success";
  const messageElement = document.createElement("p");
  messageElement.className = "result-message";
  messageElement.textContent = message;
  element.replaceChildren(messageElement);
  appendDownloads(element, downloads);
  appendPreviews(element, downloads);
}

function appendDownloads(element, downloads) {
  const list = document.createElement("div");
  list.className = "download-list";
  downloads.forEach((download) => {
    const url = URL.createObjectURL(new Blob([download.text], { type: download.type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = download.filename;
    link.className = "download-link";
    link.textContent = `Download ${download.filename}`;
    link.dataset.objectUrl = url;
    list.append(link);
  });
  element.append(list);
}

function appendPreviews(element, downloads) {
  const previews = document.createElement("div");
  previews.className = "preview-list";
  downloads.forEach((download) => {
    previews.append(previewBlock(download));
  });
  element.append(previews);
}

function previewBlock(download) {
  const preview = previewCsv(download.text);
  const block = document.createElement("section");
  block.className = "preview-block";
  const heading = document.createElement("h4");
  heading.textContent = `Preview: ${download.filename}`;
  const note = document.createElement("p");
  note.className = "preview-note";
  note.textContent = previewNote(preview);
  block.append(heading, note);
  if (preview.columns.length === 0 || preview.rows.length === 0) {
    const empty = document.createElement("p");
    empty.className = "preview-note";
    empty.textContent = "No rows to preview.";
    block.append(empty);
    return block;
  }
  const tableWrap = document.createElement("div");
  tableWrap.className = "preview-table-wrap";
  const table = document.createElement("table");
  table.className = "preview-table";
  table.append(previewHead(preview.columns), previewBody(preview));
  tableWrap.append(table);
  block.append(tableWrap);
  return block;
}

function previewNote(preview) {
  const columnNote =
    preview.hiddenColumnCount > 0
      ? ` Showing ${preview.columns.length} columns; ${preview.hiddenColumnCount} more column(s) are in the CSV.`
      : "";
  const rowNote = preview.hasMoreRows ? " More rows are in the CSV." : "";
  return `First ${Math.min(preview.rowLimit, preview.rows.length)} row(s).${columnNote}${rowNote}`;
}

function previewHead(columns) {
  const head = document.createElement("thead");
  const row = document.createElement("tr");
  columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    row.append(cell);
  });
  head.append(row);
  return head;
}

function previewBody(preview) {
  const body = document.createElement("tbody");
  preview.rows.forEach((previewRow) => {
    const row = document.createElement("tr");
    preview.columns.forEach((column) => {
      const cell = document.createElement("td");
      cell.textContent = previewRow[column] ?? "";
      row.append(cell);
    });
    body.append(row);
  });
  return body;
}

function revokeDownloads(element) {
  element.querySelectorAll("[data-object-url]").forEach((link) => {
    URL.revokeObjectURL(link.dataset.objectUrl);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
