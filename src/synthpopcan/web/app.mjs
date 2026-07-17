import { fetchJson } from "./http.mjs";
import { bindRunsWorkbench } from "./runs-workbench.mjs";
import { bindSmallAreaWorkflow } from "./small-area-workflow.mjs";

async function startApp() {
  const bootstrap = await fetchJson("/api/app");
  bindRunsWorkbench(bootstrap);
  bindSmallAreaWorkflow();
}

await startApp();
