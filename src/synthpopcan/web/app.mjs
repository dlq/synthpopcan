import { fetchJson } from "./http.mjs";
import { bindRunsWorkbench } from "./runs-workbench.mjs";
import { bindSmallAreaWorkflow } from "./small-area-workflow.mjs";

async function startApp() {
  const bootstrap = await fetchJson("/api/app");
  prepareHelpLabels();
  bindRunsWorkbench(bootstrap);
  bindSmallAreaWorkflow();
}

function prepareHelpLabels() {
  document.querySelectorAll(".help-label[data-help]").forEach((label) => {
    const name = label.textContent.trim();
    label.tabIndex = 0;
    label.setAttribute("role", "note");
    label.setAttribute("aria-label", `${name}. ${label.dataset.help}`);
    const field = label.parentElement.querySelector("input, select");
    if (field) field.setAttribute("aria-label", name);
    const marker = document.createElement("span");
    marker.className = "help-marker";
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = "?";
    label.append(marker);
    const tooltip = document.createElement("span");
    tooltip.className = "help-popup";
    tooltip.setAttribute("aria-hidden", "true");
    tooltip.textContent = label.dataset.help;
    label.append(tooltip);
  });
}

await startApp();
