import "./ipf-workflow.mjs";

import { fetchJson } from "./http.mjs";
import { bindModelWorkflow } from "./model-workflow.mjs";
import { bindSmallAreaWorkflow } from "./small-area-workflow.mjs";

async function startApp() {
  await fetchJson("/api/app");
  bindModelWorkflow();
  bindSmallAreaWorkflow();
}

await startApp();
