const ACTIVE = new Set(["queued", "running", "cancelling"]);

export function renderRunList(element, runs, selectedRunId, onSelect) {
  element.replaceChildren();
  if (runs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No runs yet. Start with the demo or your own CSV files.";
    element.append(empty);
    return;
  }
  for (const run of runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-list-item";
    button.classList.toggle("selected", run.run_id === selectedRunId);
    button.setAttribute("aria-pressed", String(run.run_id === selectedRunId));
    const title = document.createElement("strong");
    title.textContent = `IPF · ${shortDate(run.created_at)}`;
    const detail = document.createElement("span");
    detail.textContent = `${statusLabel(run.status)} · ${shortId(run.run_id)}`;
    const status = document.createElement("i");
    status.className = `status-dot ${ACTIVE.has(run.status) ? "active" : run.status}`;
    status.setAttribute("aria-hidden", "true");
    button.append(status, title, detail);
    button.addEventListener("click", () => onSelect(run));
    element.append(button);
  }
}

function shortId(runId) {
  return runId.slice(-12);
}

function shortDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(status) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
