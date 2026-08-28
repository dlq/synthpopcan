import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSmallAreaRequest,
  validateSmallAreaDraft,
} from "../../src/synthpopcan/web/small-area-request.mjs";

const file = (name) => ({ name });
const upload = async (value) => ({ upload_id: `upload-${value.name}` });

test("builds a complete model-backed small-area request", async () => {
  const options = { candidate_households: 100, random_seed: null };
  const request = await buildSmallAreaRequest(
    {
      modelId: "",
      packageFile: file("package.json"),
      candidateHouseholds: null,
      candidatePersons: null,
      controlsFile: file("controls.csv"),
      personControlsFile: file("person-controls.csv"),
      controlPackId: "core-da-v1",
      controlPackEvidenceFile: file("evidence.json"),
      boundariesFile: file("boundaries.geojson"),
      options,
    },
    upload,
  );

  assert.deepEqual(request, {
    workflow: "small_area",
    inputs: {
      controls_upload_id: "upload-controls.csv",
      package_upload_id: "upload-package.json",
      person_controls_upload_id: "upload-person-controls.csv",
      control_pack_id: "core-da-v1",
      control_pack_evidence_upload_id: "upload-evidence.json",
      boundaries_upload_id: "upload-boundaries.geojson",
    },
    options,
  });
});

test("builds candidate-backed and catalogue-backed small-area requests", async () => {
  const candidate = await buildSmallAreaRequest(
    {
      modelId: "",
      packageFile: null,
      candidateHouseholds: file("households.csv"),
      candidatePersons: file("persons.csv"),
      controlsFile: file("controls.csv"),
      personControlsFile: null,
      controlPackId: "",
      controlPackEvidenceFile: null,
      boundariesFile: null,
      options: {},
    },
    upload,
  );
  assert.deepEqual(candidate.inputs, {
    controls_upload_id: "upload-controls.csv",
    candidate_households_upload_id: "upload-households.csv",
    candidate_persons_upload_id: "upload-persons.csv",
  });

  const catalogue = await buildSmallAreaRequest(
    {
      modelId: "demo-linked",
      packageFile: null,
      candidateHouseholds: null,
      candidatePersons: null,
      controlsFile: file("controls.csv"),
      personControlsFile: null,
      controlPackId: "",
      controlPackEvidenceFile: null,
      boundariesFile: null,
      options: { candidate_households: 20 },
    },
    upload,
  );
  assert.equal(catalogue.inputs.model_id, "demo-linked");
});

test("validates small-area source and control combinations before uploading", () => {
  const valid = {
    modelId: "demo-linked",
    packageFile: null,
    candidateHouseholds: null,
    candidatePersons: null,
    controlsFile: file("controls.csv"),
    personControlsFile: null,
    controlPackId: "",
    controlPackEvidenceFile: null,
  };
  assert.equal(validateSmallAreaDraft(valid), valid);
  assert.throws(
    () =>
      validateSmallAreaDraft({
        ...valid,
        modelId: "",
        candidateHouseholds: file("households.csv"),
      }),
    /both candidate household and person/,
  );
  assert.throws(
    () => validateSmallAreaDraft({ ...valid, modelId: "" }),
    /Choose one model\/package/,
  );
  assert.throws(
    () =>
      validateSmallAreaDraft({
        ...valid,
        candidateHouseholds: file("households.csv"),
        candidatePersons: file("persons.csv"),
      }),
    /Choose one model\/package/,
  );
  assert.throws(
    () => validateSmallAreaDraft({ ...valid, controlsFile: null }),
    /Choose household controls CSV/,
  );
  assert.throws(
    () => validateSmallAreaDraft({ ...valid, controlPackId: "core-da-v1" }),
    /require a person controls CSV/,
  );
  assert.throws(
    () =>
      validateSmallAreaDraft({
        ...valid,
        controlPackEvidenceFile: file("evidence.json"),
      }),
    /Choose both a reviewed control pack/,
  );
});
