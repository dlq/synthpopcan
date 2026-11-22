import { fetchJson } from "./http.mjs";
import { initializeLocalization } from "./localization-ui.mjs";
import { bindRunsWorkbench } from "./runs-workbench.mjs";
import { bindSmallAreaWorkflow } from "./small-area-workflow.mjs";

async function startApp() {
  const [bootstrap, localization] = await Promise.all([
    fetchJson("/api/app"),
    initializeLocalization(),
  ]);
  prepareHelpLabels(localization);
  bindRunsWorkbench(bootstrap, localization);
  bindSmallAreaWorkflow(localization);
}

function prepareHelpLabels(localization) {
  document.querySelectorAll(".help-label[data-help]").forEach((label) => {
    label.tabIndex = 0;
    label.setAttribute("role", "note");
    const field = label.parentElement.querySelector("input, select");
    const originalName = label.textContent.trim();
    const marker = document.createElement("span");
    marker.className = "help-marker";
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = "?";
    label.append(marker);
    const tooltip = document.createElement("span");
    tooltip.className = "help-popup";
    tooltip.setAttribute("aria-hidden", "true");
    label.append(tooltip);
    const render = () => {
      const name =
        label.querySelector("[data-i18n]")?.textContent?.trim() || originalName;
      const translated = label.dataset.i18nHelp
        ? localization.translate(label.dataset.i18nHelp)
        : "Message unavailable.";
      const help =
        translated === "Message unavailable." ? label.dataset.help : translated;
      label.setAttribute("aria-label", `${name}. ${help}`);
      if (field) field.setAttribute("aria-label", name);
      tooltip.textContent = help;
    };
    render();
    localization.subscribe(render);
  });
}

await startApp();
