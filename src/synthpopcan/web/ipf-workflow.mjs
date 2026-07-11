import { runBrowserJob } from "./browser-job.mjs";
import { buildIpfCliCommands, shellQuote } from "./cli-commands.mjs";
import { parseCsv, stringifyCsv } from "./csv.mjs";
import {
  clearResultBox,
  downloadText,
  fillFileInput,
  numberValue,
  readFileText,
  updateFileReadyState,
  valueOrNull,
} from "./form-utils.mjs";
import {
  appendCliFollowUp,
  appendDownloads,
  resultItem,
  revokeDownloads,
  showDownloads,
  showError,
  showStatus,
} from "./result-ui.mjs";
import {
  buildAgeSexControlRows,
  buildAgeSexSeedRows,
  buildControlTemplateRows,
  buildSeedTemplateRows,
  parseDimensionList,
} from "./starter-files.mjs";
import { fetchWdsDownloadUrl, fetchWdsMetadata, searchWdsTables } from "./statcan.mjs";
import {
  buildSeedRowsFromControlRows,
  chooseWdsDataCsvEntry,
  normalizeWdsRows,
  resolveWdsDimensions,
  snapshotWdsRows,
  suggestWdsColumns,
} from "./wds-normalize.mjs";
import {
  ageCategoriesForScheme,
  buildWdsSelectionManifest,
  detailedCategories,
  filterWdsControlRows,
  summarizeWdsSelection,
} from "./wds-selection.mjs";
import { showWdsMetadata, showWdsSearchResults } from "./workflow-views.mjs";
import { csvEntries, readZipEntries } from "./zip.mjs";

const workflowButtons = document.querySelectorAll("[data-workflow-tab]");
const workflowPanels = document.querySelectorAll("[data-workflow-panel]");
const setupPathButtons = document.querySelectorAll("[data-setup-path-tab]");
const setupPathPanels = document.querySelectorAll("[data-setup-path-panel]");
const ipfForm = document.querySelector("#ipf-form");
const ipfOutputKind = document.querySelector("#ipf-output-kind");
const ipfOutputHint = document.querySelector("#ipf-output-hint");
const wdsSearchForm = document.querySelector("#wds-search-form");
const wdsExplainForm = document.querySelector("#wds-explain-form");
const wdsSearchResult = document.querySelector("#wds-search-result");
const wdsMetadataResult = document.querySelector("#wds-metadata-result");
const wdsGeneratedResult = document.querySelector("#wds-generated-result");
const ipfFileInputs = document.querySelectorAll(".ipf-file-input");
let loadedWdsTable = null;
let wdsFilterState = new Map();

bindPanelTabs(workflowButtons, workflowPanels, "workflowTab", "workflowPanel");
bindPanelTabs(setupPathButtons, setupPathPanels, "setupPathTab", "setupPathPanel");
enhanceHelpLabels();
updateIpfOutputHint();
ipfOutputKind.addEventListener("change", updateIpfOutputHint);
ipfFileInputs.forEach((input) => {
  input.addEventListener("change", () => updateFileReadyState(input));
});

function updateIpfOutputHint() {
  ipfOutputHint.textContent =
    ipfOutputKind.value === "expanded"
      ? "One integerized row per synthetic record. Browser runs are limited to 100,000 records; larger estimates are reported before a file is created."
      : "One row per seed profile with its fitted, possibly fractional weight. Use this compact file for weighted analysis or large populations.";
}

function enhanceHelpLabels() {
  document.querySelectorAll(".help-label").forEach((label) => {
    label.tabIndex = 0;
    label.setAttribute("role", "button");
    label.setAttribute("aria-expanded", "false");
    label.setAttribute("aria-label", `${label.textContent}. ${label.dataset.help}`);
    const toggle = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const open = !label.classList.contains("open");
      document.querySelectorAll(".help-label.open").forEach((other) => {
        other.classList.remove("open");
        other.setAttribute("aria-expanded", "false");
      });
      label.classList.toggle("open", open);
      label.setAttribute("aria-expanded", String(open));
    };
    label.addEventListener("click", toggle);
    label.addEventListener("focus", () => {
      label.setAttribute("aria-expanded", "true");
    });
    label.addEventListener("blur", () => {
      if (!label.classList.contains("open")) {
        label.setAttribute("aria-expanded", "false");
      }
    });
    label.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") toggle(event);
      if (event.key === "Escape") {
        label.classList.remove("open");
        label.setAttribute("aria-expanded", "false");
      }
    });
  });
}

function bindPanelTabs(buttons, panels, buttonDataKey, panelDataKey) {
  const activate = (button) => {
    const selectedValue = button.dataset[buttonDataKey];
    buttons.forEach((item) => {
      const selected = item === button;
      item.classList.toggle("selected", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    panels.forEach((panel) => {
      const active = panel.dataset[panelDataKey] === selectedValue;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => activate(button));
  });
  const selectedButton = [...buttons].find((button) =>
    button.classList.contains("selected"),
  );
  if (selectedButton) {
    activate(selectedButton);
  }
}

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
  ipfOutputKind.value = "expanded";
  updateIpfOutputHint();
  showStatus(
    document.querySelector("#ipf-result"),
    "Demo seed and controls are loaded. Keep the defaults and select Run IPF.",
  );
});

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
  const query = document.querySelector("#wds-search-query").value;
  resetWdsRefinement();
  clearResultBox(wdsMetadataResult);
  clearResultBox(wdsGeneratedResult);
  showStatus(wdsSearchResult, "Searching StatCan WDS from the browser...");
  try {
    const rows = await searchWdsTables(query, 6);
    showWdsSearchResults(wdsSearchResult, rows);
  } catch (error) {
    showError(
      wdsSearchResult,
      new Error(
        `Browser search could not reach StatCan WDS. Try the CLI command instead: synthpopcan statcan wds search "${query}" --limit 10. ${error.message}`,
      ),
    );
  }
});

wdsExplainForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const productId = document.querySelector("#wds-product-id").value.trim();
  resetWdsRefinement();
  clearResultBox(wdsGeneratedResult);
  showStatus(wdsMetadataResult, "Inspecting StatCan WDS metadata from the browser...");
  try {
    const summary = await fetchWdsMetadata(productId);
    showWdsMetadata(wdsMetadataResult, summary);
  } catch (error) {
    showError(
      wdsMetadataResult,
      new Error(
        `Browser metadata lookup could not reach StatCan WDS. Try the CLI command instead: synthpopcan statcan wds explain ${productId}. ${error.message}`,
      ),
    );
  }
});

document.querySelector("#use-recommended-wds").addEventListener("click", () => {
  document.querySelector("#wds-product-id").value = "17100005";
  document.querySelector("#generate-from-product-id").click();
});

document
  .querySelector("#generate-from-product-id")
  .addEventListener("click", async () => {
    const productId = document.querySelector("#wds-product-id").value.trim();
    showStatus(
      wdsGeneratedResult,
      "Fetching the StatCan table and filling the IPF files...",
    );
    try {
      if (!productId) {
        throw new Error("Enter a Product ID first.");
      }
      const generated = await generateSeedAndControlsFromProduct(productId);
      prepareWdsRefinement(generated, productId, productId);
    } catch (error) {
      if (error.downloadUrl) {
        showWdsDownloadFallback(
          wdsGeneratedResult,
          productId,
          error.downloadUrl,
          error,
        );
      } else {
        showError(wdsGeneratedResult, error);
      }
    }
  });

document
  .querySelector("#generate-from-downloaded-zip")
  .addEventListener("click", async () => {
    const file = document.querySelector("#wds-zip-file").files?.[0];
    showStatus(
      wdsGeneratedResult,
      "Reading the selected StatCan ZIP and filling the IPF files...",
    );
    try {
      if (!file) {
        throw new Error("Choose a downloaded StatCan ZIP first.");
      }
      const generated = await generateSeedAndControlsFromZip(await file.arrayBuffer());
      prepareWdsRefinement(
        generated,
        file.name,
        document.querySelector("#wds-product-id").value.trim() || file.name,
      );
    } catch (error) {
      showError(wdsGeneratedResult, error);
    }
  });

document.querySelector("#apply-wds-selection").addEventListener("click", () => {
  try {
    applyWdsSelection();
  } catch (error) {
    showError(wdsGeneratedResult, error);
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
      outputKind: ipfOutputKind.value,
      maxExpandedRows: 100000,
      maxIterations: numberValue("#ipf-max-iterations"),
      tolerance: numberValue("#ipf-tolerance"),
    });
    showDownloads(resultBox, result);
    appendCliFollowUp(
      resultBox,
      buildIpfCliCommands({
        seedName: document.querySelector("#ipf-seed-file").files[0].name,
        controlsName: document.querySelector("#ipf-controls-file").files[0].name,
        weightField: valueOrNull("#ipf-weight-field"),
        maxIterations: numberValue("#ipf-max-iterations"),
        tolerance: numberValue("#ipf-tolerance"),
      }),
    );
  } catch (error) {
    showError(resultBox, error);
  }
});

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
    document.querySelector("#wds-dimensions").value = payload.dimensions.join(", ");
    document.querySelector("#wds-count-column").value = payload.countColumn;
    return {
      seedRows: parseCsv(payload.seedCsv),
      controlRows: parseCsv(payload.controlsCsv),
      dimensions: payload.dimensions,
      countColumn: payload.countColumn,
      csvMember: payload.csvMember,
      referencePeriod: payload.referencePeriod,
      categories: payload.categories,
      estimatedTotal: payload.estimatedTotal,
      unitRows: payload.unitRows ?? [],
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
    categories: Object.fromEntries(
      dimensions.map((dimension) => [
        dimension,
        [...new Set(snapshot.rows.map((row) => row[dimension] ?? ""))],
      ]),
    ),
    estimatedTotal: Math.round(
      controlRows.reduce((total, row) => total + Number(row.count), 0),
    ),
    unitRows: snapshot.rows
      .filter((row) => row[countColumn] !== "")
      .map((row) => ({
        ...Object.fromEntries(
          dimensions.map((dimension) => [dimension, row[dimension] ?? ""]),
        ),
        unit: row.UOM ?? "",
      })),
  };
}

function parseWdsCsv(text) {
  return parseCsv(text);
}

function currentWdsDimensions() {
  return parseDimensionList(document.querySelector("#wds-dimensions").value);
}

function prepareWdsRefinement(generated, sourceLabel, productId) {
  loadedWdsTable = { ...generated, sourceLabel, productId };
  wdsFilterState = new Map();
  const fields = document.querySelector("#wds-refinement-fields");
  fields.replaceChildren();
  generated.dimensions.forEach((dimension) => {
    const values = generated.categories[dimension] ?? [];
    const filter = buildWdsFilter(dimension, values);
    wdsFilterState.set(dimension, filter);
    fields.append(filter.element);
    filter.control.addEventListener("change", updateWdsSelectionEstimate);
  });
  document.querySelector("#wds-refinement").hidden = false;
  showStatus(
    wdsGeneratedResult,
    `Loaded ${generated.controlRows.length.toLocaleString()} cells from ${sourceLabel}. Refine the table, then generate the selected IPF files.`,
  );
  updateWdsSelectionEstimate();
}

function resetWdsRefinement() {
  loadedWdsTable = null;
  wdsFilterState = new Map();
  document.querySelector("#wds-refinement").hidden = true;
  document.querySelector("#wds-refinement-fields").replaceChildren();
}

function buildWdsFilter(dimension, values) {
  const lower = dimension.toLowerCase();
  if (lower === "geo" || lower.includes("geograph")) {
    return selectFilter(dimension, values, "geography").withPlaceholder(
      "Choose one geography",
    );
  }
  if (lower.includes("gender") || lower === "sex") {
    const detail = detailedCategories(values);
    return modeFilter(
      dimension,
      [
        ["detail", `Detailed categories (${detail.join(", ")})`],
        ...values.map((value) => [`only:${value}`, `Only ${value}`]),
        ["all", "All categories (may overlap)"],
      ],
      "gender",
      { values, detail },
    );
  }
  if (lower.includes("age")) {
    const modes = [];
    if (ageCategoriesForScheme(values, "single-year").length > 0) {
      modes.push(["single-year", "Single-year ages"]);
    }
    if (ageCategoriesForScheme(values, "five-year").length > 0) {
      modes.push(["five-year", "Five-year age groups"]);
    }
    modes.push(["all", "All age categories (may overlap)"]);
    return modeFilter(dimension, modes, "age", { values });
  }
  return selectFilter(dimension, values, "category").withAllOption();
}

function selectFilter(dimension, values, kind) {
  const { element, control } = filterShell(dimension);
  values.forEach((value) => {
    control.append(new Option(value, value));
  });
  const filter = { element, control, dimension, kind, values };
  filter.withPlaceholder = (label) => {
    control.prepend(new Option(label, "", true, true));
    return filter;
  };
  filter.withAllOption = () => {
    control.prepend(new Option("All categories", "__all__", true, true));
    return filter;
  };
  return filter;
}

function modeFilter(dimension, modes, kind, extra) {
  const { element, control } = filterShell(dimension);
  modes.forEach(([value, label]) => {
    control.append(new Option(label, value));
  });
  return { element, control, dimension, kind, ...extra };
}

function filterShell(dimension) {
  const element = document.createElement("label");
  element.className = "wds-filter";
  const title = document.createElement("span");
  title.textContent = dimension;
  const control = document.createElement("select");
  control.id = `wds-filter-${dimension.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  control.setAttribute("aria-label", dimension);
  element.append(title, control);
  return { element, control };
}

function currentWdsCategorySelection() {
  return Object.fromEntries(
    [...wdsFilterState].map(([dimension, filter]) => {
      if (filter.kind === "geography") {
        return [dimension, filter.control.value ? [filter.control.value] : []];
      }
      if (filter.kind === "gender") {
        const mode = filter.control.value;
        if (mode === "detail") return [dimension, filter.detail];
        if (mode === "all") return [dimension, filter.values];
        return [dimension, [mode.slice("only:".length)]];
      }
      if (filter.kind === "age") {
        return [dimension, ageCategoriesForScheme(filter.values, filter.control.value)];
      }
      return [
        dimension,
        filter.control.value === "__all__" ? filter.values : [filter.control.value],
      ];
    }),
  );
}

function currentWdsSelectionResult() {
  if (!loadedWdsTable) {
    throw new Error("Load WDS categories first.");
  }
  const categories = currentWdsCategorySelection();
  if (Object.values(categories).some((values) => values.length === 0)) {
    return { categories, rows: [], cells: 0, estimatedTotal: 0, incomplete: true };
  }
  const rows = filterWdsControlRows(loadedWdsTable.controlRows, categories);
  const unitRows = filterWdsControlRows(loadedWdsTable.unitRows, categories);
  const units = [...new Set(unitRows.map((row) => row.unit).filter(Boolean))];
  return {
    categories,
    rows,
    units,
    ...summarizeWdsSelection(rows),
    incomplete: false,
  };
}

function updateWdsSelectionEstimate() {
  const estimate = document.querySelector("#wds-selection-estimate");
  const applyButton = document.querySelector("#apply-wds-selection");
  const result = currentWdsSelectionResult();
  if (result.incomplete) {
    estimate.className = "selection-estimate";
    estimate.textContent = "Choose a geography to calculate the selected population.";
    applyButton.disabled = true;
    return;
  }
  const unit = result.units.length > 0 ? ` Unit: ${result.units.join(", ")}.` : "";
  const tooLarge = result.estimatedTotal > 100000;
  const overlapping = [...wdsFilterState.values()].some(
    (filter) => filter.control.value === "all",
  );
  const countLikeUnit =
    result.units.length === 0 ||
    result.units.every((value) =>
      /(count|number|person|people|household)/i.test(value),
    );
  const warning = tooLarge || overlapping || !countLikeUnit;
  const notes = [];
  if (tooLarge) notes.push("Use compact weights or narrow the selection further.");
  else notes.push("This fits the browser expansion limit.");
  if (overlapping)
    notes.push("The selected category mode may contain overlapping totals.");
  if (!countLikeUnit) notes.push("Confirm that VALUE is a count before using IPF.");
  estimate.className = `selection-estimate ${warning ? "warning" : "success"}`;
  estimate.textContent = `${result.cells.toLocaleString()} control cells; about ${result.estimatedTotal.toLocaleString()} expanded records.${unit} ${notes.join(" ")}`;
  applyButton.disabled = result.cells === 0;
}

function applyWdsSelection() {
  const selection = currentWdsSelectionResult();
  if (selection.incomplete || selection.cells === 0) {
    throw new Error("Choose categories that match at least one WDS cell.");
  }
  const selected = {
    ...loadedWdsTable,
    seedRows: buildSeedRowsFromControlRows(selection.rows),
    controlRows: selection.rows,
  };
  const manifest = buildWdsSelectionManifest({
    productId: loadedWdsTable.productId,
    referencePeriod: loadedWdsTable.referencePeriod,
    categories: selection.categories,
  });
  loadGeneratedIpfFiles(selected);
  ipfOutputKind.value = selection.estimatedTotal > 100000 ? "weights" : "expanded";
  updateIpfOutputHint();
  showGeneratedWdsResult(
    wdsGeneratedResult,
    selected,
    loadedWdsTable.sourceLabel,
    manifest,
  );
}

function loadGeneratedIpfFiles({ seedRows, controlRows }) {
  fillFileInput("#ipf-seed-file", "generated-wds-seed.csv", stringifyCsv(seedRows));
  fillFileInput(
    "#ipf-controls-file",
    "generated-wds-controls.csv",
    stringifyCsv(controlRows),
  );
  document.querySelector("#ipf-weight-field").value = "";
  ipfOutputKind.value = "expanded";
  updateIpfOutputHint();
}

function showGeneratedWdsResult(element, generated, sourceLabel, selectionManifest) {
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
    {
      filename: "synthpopcan-wds-selection.json",
      text: `${JSON.stringify(selectionManifest, null, 2)}\n`,
      type: "application/json",
    },
  ]);
  appendCliFollowUp(element, wdsCliCommands(generated, selectionManifest));
}

function wdsCliCommands(generated, selectionManifest) {
  const dimensions = shellQuote(generated.dimensions.join(","));
  const productId = selectionManifest.product_id;
  const zipPath = /^\d+$/.test(productId)
    ? `data/raw/statcan/wds/${productId}-eng.zip`
    : generated.csvMember;
  const commands = [];
  if (/^\d+$/.test(productId)) {
    commands.push(
      `# Download the complete StatCan WDS table used by this browser workflow.\nsynthpopcan statcan wds fetch ${productId} --out-dir data/raw/statcan/wds`,
    );
  }
  commands.push(
    `# Rebuild normalized controls using the category selection downloaded above.\nsynthpopcan controls from-wds ${shellQuote(zipPath)} --dimensions ${dimensions} --count-column ${shellQuote(generated.countColumn)} --selection synthpopcan-wds-selection.json --out controls.csv`,
    "# Confirm that the generated seed covers every selected control category.\nsynthpopcan ipf check-inputs --seed generated-wds-seed.csv --controls controls.csv",
  );
  return commands;
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
