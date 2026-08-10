import assert from "node:assert/strict";
import test from "node:test";

import {
  artifactUrl,
  cancelRun,
  createRun,
  getRun,
  listControlPacks,
  listRuns,
  preflightRun,
  previewArtifact,
  uploadCsv,
} from "../../src/synthpopcan/web/run-api.mjs";

test("streams CSV uploads without reading the File in JavaScript", async () => {
  const originalFetch = globalThis.fetch;
  const file = { name: "seed.csv", type: "text/csv", size: 12 };
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response(
      JSON.stringify({ upload_id: "upload-1", display_name: "seed.csv" }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    );
  };
  try {
    const result = await uploadCsv(file);
    assert.equal(result.upload_id, "upload-1");
    assert.equal(request.url, "/api/uploads");
    assert.equal(request.options.body, file);
    assert.equal(request.options.headers["X-Filename"], "seed.csv");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("reports upload errors from the local API", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "upload rejected" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  try {
    await assert.rejects(() => uploadCsv({ name: "bad.csv", type: "" }), {
      message: "upload rejected",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("builds durable run API requests and artifact URLs", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await listRuns();
    await listControlPacks();
    await getRun("run/id");
    await preflightRun({ workflow: "ipf" });
    await createRun({ workflow: "ipf" });
    await cancelRun("run/id");
    await previewArtifact("run/id", "artifact/id", 7);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.deepEqual(
    calls.map((call) => [call.url, call.options?.method ?? "GET"]),
    [
      ["/api/runs", "GET"],
      ["/api/control-packs", "GET"],
      ["/api/runs/run%2Fid", "GET"],
      ["/api/preflight", "POST"],
      ["/api/runs", "POST"],
      ["/api/runs/run%2Fid/cancel", "POST"],
      ["/api/runs/run%2Fid/artifacts/artifact%2Fid/preview?rows=7", "GET"],
    ],
  );
  assert.equal(
    artifactUrl("run/id", "artifact/id"),
    "/api/runs/run%2Fid/artifacts/artifact%2Fid",
  );
});
