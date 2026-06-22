import { resultItem, resultText, revokeDownloads } from "./result-ui.mjs";

export function showWdsSearchResults(element, rows) {
  revokeDownloads(element);
  element.className = "result-box success";
  if (rows.length === 0) {
    element.textContent = "No matching WDS tables found.";
    return;
  }
  element.textContent = "Matching WDS tables. Select a result to fill Product ID.";
  const list = document.createElement("div");
  list.className = "result-list";
  rows.forEach((row) => {
    const item = document.createElement("button");
    item.className = "result-item";
    item.type = "button";
    item.append(
      resultText(
        `${row.productId} · ${row.title}`,
        `${row.cansimId} · ${row.startDate} to ${row.endDate}`,
      ),
    );
    item.addEventListener("click", () => {
      document.querySelector("#wds-product-id").value = row.productId;
    });
    list.append(item);
  });
  element.append(list);
}

export function showWdsMetadata(element, summary) {
  revokeDownloads(element);
  element.className = "result-box success";
  element.textContent = `${summary.productId}: ${summary.title}`;
  const list = document.createElement("div");
  list.className = "result-list wds-metadata-list";
  list.append(
    resultItem("Dates", summary.dateRange),
    resultItem("Dimensions", summary.dimensions.join(", ")),
    resultItem("IPF note", summary.hint),
    resultItem(
      "Next",
      "Use Generate from Product ID to fill the IPF inputs. Downloaded StatCan ZIP is only for tables you already have or for static deployments without the local helper.",
    ),
  );
  element.append(list);
  document.querySelector("#starter-dimensions").value =
    summary.suggestedControlColumns.join(", ");
  document.querySelector("#wds-dimensions").value =
    summary.suggestedControlColumns.join(", ");
}

export function showModelSummary(element, summary, sourceLabel = null) {
  revokeDownloads(element);
  element.className = "result-box success";
  element.textContent = sourceLabel
    ? `${sourceLabel}: ${summary.kind}. ${summary.outputs}.`
    : `${summary.kind}. ${summary.outputs}.`;
  const overview = document.createElement("div");
  overview.className = "model-overview-note";
  overview.append(resultItem("Package summary", modelOverviewText(summary)));
  element.append(overview);
  if (summary.linkage) {
    const linkage = document.createElement("div");
    linkage.className = "model-linkage-note";
    linkage.append(resultItem("How household/person linkage works", summary.linkage));
    element.append(linkage);
  }
  const modelDetails = document.createElement("div");
  modelDetails.className = "model-detail-list";
  const heading = document.createElement("strong");
  heading.textContent = "Included models";
  modelDetails.append(heading);
  summary.models.forEach((model) => {
    modelDetails.append(resultItem(model.name, model.text));
  });
  element.append(modelDetails);
  const terms = document.createElement("div");
  terms.className = "model-terms-list";
  const termsHeading = document.createElement("strong");
  termsHeading.textContent = "Terms used";
  terms.append(
    termsHeading,
    resultItem(
      "Publishable candidate",
      "A model package marked as suitable for sharing after privacy checks; it should not contain raw training rows.",
    ),
    resultItem(
      "Conditions",
      "Optional input columns used to filter generation, such as geo or household_size.",
    ),
    resultItem("Targets", "Columns the model generates in the synthetic output."),
    resultItem(
      "Conditional-frequency",
      "A simple tabular model that samples from observed category frequencies within matching condition groups.",
    ),
  );
  element.append(terms);
}

function modelOverviewText(summary) {
  const conditions =
    summary.conditions.length > 0
      ? summary.conditions.join(", ")
      : "no required conditioning columns";
  return `${summary.privacy}; release ${summary.release}; ${summary.rowsLabel.toLowerCase()}; generates ${summary.outputs}; conditions: ${conditions}.`;
}
