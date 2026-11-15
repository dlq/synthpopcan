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

test("drains terminal progress even when the manifest finishes first", async () => {
  const originalEventSource = globalThis.EventSource;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let poll;
  let timeout;
  let intervalCleared = false;
  let timeoutCleared = false;
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
    setTimeout(callback, delay) {
      assert.equal(delay, 3000);
      timeout = callback;
      return 20;
    },
    clearTimeout(id) {
      assert.equal(id, 20);
      timeoutCleared = true;
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
    assert.equal(terminal, undefined);
    assert.equal(FakeEventSource.instance.closed, false);
    FakeEventSource.instance.emit("progress", {
      data: JSON.stringify({ id: 2, stage: "succeeded", message: "Done" }),
    });
    assert.deepEqual(
      events.map((event) => event.id),
      [1, 2],
    );
    assert.equal(terminal.status, "succeeded");
    assert.equal(FakeEventSource.instance.closed, true);
    assert.equal(intervalCleared, true);
    assert.equal(timeoutCleared, true);
    timeout();
    assert.equal(events.length, 2);
  } finally {
    globalThis.EventSource = originalEventSource;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});

test("still completes if the terminal progress event is unavailable", async () => {
  const originalEventSource = globalThis.EventSource;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let poll;
  let timeout;
  let terminal;
  globalThis.EventSource = FakeEventSource;
  globalThis.window = {
    setInterval(callback) {
      poll = callback;
      return 19;
    },
    clearInterval() {},
    setTimeout(callback) {
      timeout = callback;
      return 20;
    },
    clearTimeout() {},
  };
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ status: "failed" }), {
      headers: { "Content-Type": "application/json" },
    });
  try {
    followRunEvents("run-1", {
      onEvent() {},
      onTerminal: (run) => {
        terminal = run;
      },
    });
    await poll();
    assert.equal(terminal, undefined);
    timeout();
    assert.equal(terminal.status, "failed");
    assert.equal(FakeEventSource.instance.closed, true);
  } finally {
    globalThis.EventSource = originalEventSource;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});

test("finishes promptly when terminal progress precedes the manifest", async () => {
  const originalEventSource = globalThis.EventSource;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let poll;
  let terminal;
  globalThis.EventSource = FakeEventSource;
  globalThis.window = {
    setInterval(callback) {
      poll = callback;
      return 19;
    },
    clearInterval() {},
    setTimeout() {
      assert.fail("terminal event already arrived");
    },
    clearTimeout() {},
  };
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ status: "succeeded" }), {
      headers: { "Content-Type": "application/json" },
    });
  try {
    followRunEvents("run-1", {
      onEvent() {},
      onTerminal: (run) => {
        terminal = run;
      },
    });
    FakeEventSource.instance.emit("progress", {
      data: JSON.stringify({ id: 1, stage: "succeeded" }),
    });
    await poll();
    assert.equal(terminal.status, "succeeded");
    assert.equal(FakeEventSource.instance.closed, true);
  } finally {
    globalThis.EventSource = originalEventSource;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});

test("does not report a terminal run after the follower is closed", async () => {
  const originalEventSource = globalThis.EventSource;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let poll;
  let resolveFetch;
  let terminal;
  globalThis.EventSource = FakeEventSource;
  globalThis.window = {
    setInterval(callback) {
      poll = callback;
      return 19;
    },
    clearInterval() {},
    clearTimeout() {},
  };
  globalThis.fetch = () =>
    new Promise((resolve) => {
      resolveFetch = resolve;
    });
  try {
    const close = followRunEvents("run-1", {
      onEvent() {},
      onTerminal: (run) => {
        terminal = run;
      },
    });
    const pending = poll();
    close();
    resolveFetch(new Response(JSON.stringify({ status: "succeeded" })));
    await pending;
    assert.equal(terminal, undefined);
    assert.equal(FakeEventSource.instance.closed, true);
  } finally {
    globalThis.EventSource = originalEventSource;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});
