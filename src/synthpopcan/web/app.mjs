import { fetchJson } from "./http.mjs";
import { bindModelWorkflow } from "./model-workflow.mjs";
import { bindRunsWorkbench } from "./runs-workbench.mjs";
import { bindSmallAreaWorkflow } from "./small-area-workflow.mjs";

async function startApp() {
  const bootstrap = await fetchJson("/api/app");
  bindRunsWorkbench(bootstrap);
  bindModelWorkflow();
  bindSmallAreaWorkflow();
}

await startApp();
