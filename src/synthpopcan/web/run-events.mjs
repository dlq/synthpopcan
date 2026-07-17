const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

export function followRunEvents(runId, { onEvent, onReconnect, onTerminal }) {
  const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
  let closed = false;
  source.addEventListener("progress", (message) => {
    onEvent(JSON.parse(message.data));
  });
  source.addEventListener("open", () => onReconnect?.());
  source.addEventListener("error", () => {
    if (!closed) onReconnect?.();
  });

  const poll = window.setInterval(async () => {
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
      if (!response.ok) return;
      const run = await response.json();
      if (TERMINAL.has(run.status)) {
        close();
        onTerminal(run);
      }
    } catch {
      onReconnect?.();
    }
  }, 250);

  function close() {
    if (closed) return;
    closed = true;
    window.clearInterval(poll);
    source.close();
  }

  return close;
}
