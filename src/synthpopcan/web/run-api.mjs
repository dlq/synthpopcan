import { fetchJson } from "./http.mjs";

export async function uploadCsv(file) {
  const response = await fetch("/api/uploads", {
    method: "POST",
    headers: {
      "Content-Type": file.type || "text/csv",
      "X-Filename": file.name,
    },
    body: file,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error ?? `Upload returned HTTP ${response.status}`);
  }
  return response.json();
}

export function listRuns() {
  return fetchJson("/api/runs");
}

export function listControlPacks() {
  return fetchJson("/api/control-packs");
}

export function getRun(runId) {
  return fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
}

export function preflightRun(request) {
  return fetchJson("/api/preflight", jsonRequest(request));
}

export function createRun(request) {
  return fetchJson("/api/runs", jsonRequest(request));
}

export function cancelRun(runId) {
  return fetchJson(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
  });
}

export function artifactUrl(runId, artifactId) {
  return `/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`;
}

export function previewArtifact(runId, artifactId, rows = 10) {
  const url = `${artifactUrl(runId, artifactId)}/preview?rows=${rows}`;
  return fetchJson(url);
}

function jsonRequest(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
