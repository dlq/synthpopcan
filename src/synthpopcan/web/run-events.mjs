const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
const TERMINAL_STREAM_GRACE_MS = 3000;

export function followRunEvents(runId, { onEvent, onReconnect, onTerminal }) {
  const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
  let closed = false;
  let terminalRun = null;
  let terminalStage = null;
  let terminalTimer = null;
  source.addEventListener("progress", (message) => {
    if (closed) return;
    const event = JSON.parse(message.data);
    onEvent(event);
    if (TERMINAL.has(event.stage)) {
      terminalStage = event.stage;
      if (terminalRun?.status === terminalStage) finish();
    }
  });
  source.addEventListener("open", () => onReconnect?.());
  source.addEventListener("error", () => {
    if (!closed) onReconnect?.();
  });

  const poll = window.setInterval(async () => {
    if (closed || terminalRun) return;
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
      if (!response.ok || closed) return;
      const run = await response.json();
      if (closed || terminalRun || !TERMINAL.has(run.status)) return;
      terminalRun = run;
      if (terminalStage === run.status) finish();
      else terminalTimer = window.setTimeout(finish, TERMINAL_STREAM_GRACE_MS);
    } catch {
      if (!closed) onReconnect?.();
    }
  }, 250);

  function finish() {
    if (closed || !terminalRun) return;
    close();
    onTerminal(terminalRun);
  }

  function close() {
    if (closed) return;
    closed = true;
    window.clearInterval(poll);
    if (terminalTimer !== null) window.clearTimeout(terminalTimer);
    source.close();
  }

  return close;
}
