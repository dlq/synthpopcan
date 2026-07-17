import assert from "node:assert/strict";
import test from "node:test";

import { followRunEvents } from "../../src/synthpopcan/web/run-events.mjs";

class FakeEventSource {
  static instance;

  constructor(url) {
    this.url = url;
    this.listeners = new Map();
    this.closed = false;
    FakeEventSource.instance = this;
  }

  addEventListener(name, callback) {
    this.listeners.set(name, callback);
  }

  emit(name, payload = {}) {
    this.listeners.get(name)?.(payload);
  }

  close() {
    this.closed = true;
  }
}

test("follows progress and closes after a terminal manifest", async () => {
  const originalEventSource = globalThis.EventSource;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let poll;
  let intervalCleared = false;
  const events = [];
  let terminal;
  globalThis.EventSource = FakeEventSource;
  globalThis.window = {
    setInterval(callback) {
      poll = callback;
      return 19;
    },
    clearInterval(id) {
      assert.equal(id, 19);
      intervalCleared = true;
    },
  };
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ run_id: "run-1", status: "succeeded" }), {
      headers: { "Content-Type": "application/json" },
    });
  try {
    followRunEvents("run/id", {
      onEvent: (event) => events.push(event),
      onTerminal: (run) => {
        terminal = run;
      },
    });
    assert.equal(FakeEventSource.instance.url, "/api/runs/run%2Fid/events");
    FakeEventSource.instance.emit("progress", {
      data: JSON.stringify({ id: 1, message: "Started" }),
    });
    await poll();
    assert.deepEqual(events, [{ id: 1, message: "Started" }]);
    assert.equal(terminal.status, "succeeded");
    assert.equal(FakeEventSource.instance.closed, true);
    assert.equal(intervalCleared, true);
  } finally {
    globalThis.EventSource = originalEventSource;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});
