import { previewCsv } from "./preview.mjs";

export function showStatus(element, message) {
  revokeDownloads(element);
  element.className = "result-box";
  element.textContent = message;
}

export function showError(element, error) {
  revokeDownloads(element);
  element.className = "result-box error";
  element.textContent = error instanceof Error ? error.message : String(error);
}

export function showDownloads(element, { message, downloads, validation = null }) {
  revokeDownloads(element);
  element.className = "result-box success";
  const messageElement = document.createElement("p");
  messageElement.className = "result-message";
  messageElement.textContent = message;
  element.replaceChildren(messageElement);
  if (validation) {
    appendValidationSummary(element, validation);
  }
  appendDownloads(element, downloads);
  appendPreviews(element, downloads);
}

export function appendDownloads(element, downloads) {
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

export function resultItem(title, text) {
  const item = document.createElement("div");
  item.className = "result-item";
  item.append(resultText(title, text));
  return item;
}

export function resultText(title, text) {
  const fragment = document.createDocumentFragment();
  const titleElement = document.createElement("strong");
  titleElement.textContent = title;
  const textElement = document.createElement("span");
  textElement.textContent = text;
  fragment.append(titleElement, textElement);
  return fragment;
}

export function revokeDownloads(element) {
  element.querySelectorAll("[data-object-url]").forEach((link) => {
    URL.revokeObjectURL(link.dataset.objectUrl);
  });
}

function appendPreviews(element, downloads) {
  const previews = document.createElement("div");
  previews.className = "preview-list";
  downloads.forEach((download) => {
    previews.append(previewBlock(download));
  });
  element.append(previews);
}

function appendValidationSummary(element, validation) {
  const summary = document.createElement("section");
  summary.className = `validation-summary ${validation.status ?? "passed"}`;
  const heading = document.createElement("h4");
  heading.textContent = "Validation summary";
  const list = document.createElement("div");
  list.className = "validation-list";
  validation.items.forEach((item) => {
    list.append(resultItem(item.title, item.text));
  });
  summary.append(heading, list);
  element.append(summary);
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
