export function validateSmallAreaDraft(draft) {
  const candidatePair = Boolean(draft.candidateHouseholds && draft.candidatePersons);
  if (Boolean(draft.candidateHouseholds) !== Boolean(draft.candidatePersons)) {
    throw new Error("Choose both candidate household and person CSV files.");
  }
  const modelSource = Boolean(draft.packageFile || draft.modelId);
  if (modelSource === candidatePair) {
    throw new Error("Choose one model/package or one linked candidate pair.");
  }
  if (!draft.controlsFile) throw new Error("Choose household controls CSV.");
  if (draft.controlPackId && !draft.personControlsFile) {
    throw new Error("Reviewed control packs require a person controls CSV.");
  }
  if (Boolean(draft.controlPackId) !== Boolean(draft.controlPackEvidenceFile)) {
    throw new Error(
      "Choose both a reviewed control pack and its control-pack evidence JSON.",
    );
  }
  return draft;
}

export async function buildSmallAreaRequest(draft, upload) {
  validateSmallAreaDraft(draft);
  const controls = await upload(draft.controlsFile);
  const inputs = { controls_upload_id: controls.upload_id };
  if (draft.candidateHouseholds && draft.candidatePersons) {
    const [households, persons] = await Promise.all([
      upload(draft.candidateHouseholds),
      upload(draft.candidatePersons),
    ]);
    inputs.candidate_households_upload_id = households.upload_id;
    inputs.candidate_persons_upload_id = persons.upload_id;
  } else if (draft.packageFile) {
    const uploaded = await upload(draft.packageFile);
    inputs.package_upload_id = uploaded.upload_id;
  } else {
    inputs.model_id = draft.modelId;
  }
  if (draft.personControlsFile) {
    const uploaded = await upload(draft.personControlsFile);
    inputs.person_controls_upload_id = uploaded.upload_id;
  }
  if (draft.controlPackId && draft.controlPackEvidenceFile) {
    const uploaded = await upload(draft.controlPackEvidenceFile);
    inputs.control_pack_id = draft.controlPackId;
    inputs.control_pack_evidence_upload_id = uploaded.upload_id;
  }
  if (draft.boundariesFile) {
    const uploaded = await upload(draft.boundariesFile);
    inputs.boundaries_upload_id = uploaded.upload_id;
  }
  return { workflow: "small_area", inputs, options: draft.options };
}
