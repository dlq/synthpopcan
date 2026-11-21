import { getLocalizationRuntime } from "./localization-ui.mjs";

const ACTIVE = new Set(["queued", "running", "cancelling"]);
const bindings = new WeakMap();
const WORKFLOWS = {
  ipf: ["web.workflow.ipf", "IPF"],
  model: ["web.workflow.model", "Model"],
  small_area: ["web.workflow.smallarea", "Small area"],
};
const STATUSES = {
  draft: ["web.status.draft", "Draft"],
  queued: ["web.status.queued", "Queued"],
  running: ["web.status.running", "Running"],
  cancelling: ["web.status.cancelling", "Cancelling"],
  succeeded: ["web.status.succeeded", "Succeeded"],
  failed: ["web.status.failed", "Failed"],
  cancelled: ["web.status.cancelled", "Cancelled"],
  interrupted: ["web.status.interrupted", "Interrupted"],
};

function label(runtime, entry) {
  if (!runtime) return entry[1];
  const translated = runtime.translate(entry[0]);
  return translated === "Message unavailable." ? entry[1] : translated;
}

export function localizedStatus(status, runtime = getLocalizationRuntime()) {
  const key = status.toLowerCase();
  return Object.hasOwn(STATUSES, key)
    ? label(runtime, STATUSES[key])
    : status.charAt(0).toUpperCase() + status.slice(1);
}

export function renderRunList(element, runs, selectedRunId, onSelect) {
  let binding = bindings.get(element);
  if (!binding) {
    const runtime = getLocalizationRuntime();
    binding = { runtime, rows: [], empty: null };
    bindings.set(element, binding);
    runtime?.subscribe(() => updateLabels(binding));
  }
  binding.rows = [];
  binding.empty = null;
  element.replaceChildren();
  if (runs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    binding.empty = empty;
    element.append(empty);
  }
  for (const run of runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-list-item";
    button.classList.toggle("selected", run.run_id === selectedRunId);
    button.setAttribute("aria-pressed", String(run.run_id === selectedRunId));
    const title = document.createElement("strong");
    const detail = document.createElement("span");
    const status = document.createElement("i");
    status.className = `status-dot ${ACTIVE.has(run.status) ? "active" : run.status}`;
    status.setAttribute("aria-hidden", "true");
    button.append(status, title, detail);
    button.addEventListener("click", () => onSelect(run));
    binding.rows.push({ run, title, detail });
    element.append(button);
  }
  updateLabels(binding);
}

function updateLabels(binding) {
  const runtime = binding.runtime;
  if (binding.empty) {
    binding.empty.textContent = label(runtime, [
      "web.runs.empty",
      "No runs yet. Start with the demo or your own CSV files.",
    ]);
  }
  for (const { run, title, detail } of binding.rows) {
    const workflow = label(
      runtime,
      Object.hasOwn(WORKFLOWS, run.workflow) ? WORKFLOWS[run.workflow] : WORKFLOWS.ipf,
    );
    const status = localizedStatus(run.status, runtime);
    const date = new Intl.DateTimeFormat(runtime?.locale, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(run.created_at));
    title.textContent = `${workflow} · ${date}`;
    detail.textContent = `${status} · ${run.run_id.slice(-12)}`;
  }
}
