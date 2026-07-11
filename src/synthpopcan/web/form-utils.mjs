import { revokeDownloads } from "./result-ui.mjs";

export function fillFileInput(selector, filename, text) {
  const input = document.querySelector(selector);
  const file = new File([text], filename, { type: "text/csv" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  updateFileReadyState(input);
}

export function updateFileReadyState(input) {
  input.classList.toggle("file-ready", Boolean(input.files?.length));
}

export function clearResultBox(element) {
  revokeDownloads(element);
  element.className = "result-box";
  element.replaceChildren();
}

export function downloadText(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function readFileText(selector) {
  const input = document.querySelector(selector);
  const file = input.files?.[0];
  if (!file) {
    throw new Error(`Choose a file for ${input.labels?.[0]?.textContent.trim()}.`);
  }
  return file.text();
}

export function valueOrNull(selector) {
  const value = document.querySelector(selector).value.trim();
  return value === "" ? null : value;
}

export function numberValue(selector) {
  const input = document.querySelector(selector);
  const value = Number(input.value);
  if (!Number.isFinite(value)) {
    throw new Error(`${input.labels?.[0]?.textContent.trim()} must be a number.`);
  }
  return value;
}

export function optionalNumberValue(selector) {
  const input = document.querySelector(selector);
  if (input.value.trim() === "") return null;
  return numberValue(selector);
}
