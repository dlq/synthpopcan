export const SMALL_AREA_MESSAGE_IDS = {
  "Prepare a small-area synthesis": "web.smallarea.ui001",
  "Python-backed preflight": "web.smallarea.ui002",
  "Choose a linked model and normalized geographic controls. Preflight checks compatibility, scale, and disk before the durable run starts.":
    "web.smallarea.ui003",
  "Premade linked model": "web.smallarea.ui004",
  "Or candidate households CSV": "web.smallarea.ui005",
  "Candidate persons CSV": "web.smallarea.ui006",
  "Household controls CSV": "web.smallarea.ui007",
  "Person controls CSV": "web.smallarea.ui008",
  "Reviewed control pack": "web.smallarea.ui009",
  "Raw normalized controls": "web.smallarea.ui010",
  "Control-pack evidence JSON": "web.smallarea.ui011",
  "Conditional census tract controls": "web.smallarea.ui012",
  "Select a matching 2016 or 2021 broad tract pack and upload the source for each family you want to fit.":
    "web.smallarea.ui013",
  "Marital status pack": "web.smallarea.ui014",
  "Marital status tract CSV": "web.smallarea.ui015",
  "Education pack": "web.smallarea.ui016",
  "Education Profile CSV or ZIP": "web.smallarea.ui017",
  "Labour-force status pack": "web.smallarea.ui018",
  "Labour-force Profile CSV or ZIP": "web.smallarea.ui019",
  "Work activity pack": "web.smallarea.ui020",
  "Work activity Profile CSV or ZIP": "web.smallarea.ui021",
  "Whole-household realization": "web.smallarea.ui022",
  "Midpoint rounding": "web.smallarea.ui023",
  "Improve with swaps": "web.smallarea.ui024",
  "Joint solver": "web.smallarea.ui025",
  Hybrid: "web.smallarea.ui026",
  "Zero targets": "web.smallarea.ui027",
  "Treat as structural zeros": "web.smallarea.ui028",
  "Allow residuals at observed zeros": "web.smallarea.ui029",
  "Boundary GeoJSON for map": "web.smallarea.ui030",
  "Geography dimension": "web.smallarea.ui031",
  "Output geography column": "web.smallarea.ui032",
  "Candidate households": "web.smallarea.ui033",
  "Calibration pool size": "web.smallarea.ui034",
  "Use all candidates": "web.smallarea.ui035",
  "Average persons per household": "web.smallarea.ui036",
  "Generation seed": "web.smallarea.ui037",
  "Subsample seed": "web.smallarea.ui038",
  "Estimate and prepare": "web.smallarea.ui039",
  None: "web.smallarea.ui040",
  "A published linked household/person model. Downloadable models are fetched by the generated CLI commands when needed.":
    "web.smallarea.ui041",
  "Use a local linked package JSON instead of a premade model ID.":
    "web.smallarea.ui042",
  "Use an existing validated household CSV instead of generating candidates from a model. A person CSV is also required.":
    "web.smallarea.ui043",
  "Linked person candidates accompanying the candidate household CSV.":
    "web.smallarea.ui044",
  "Normalized household controls containing one target geography dimension and household-level margins.":
    "web.smallarea.ui045",
  "Optional person-level controls used for joint linked calibration. They are included in the CLI command but not needed for the scale estimate.":
    "web.smallarea.ui046",
  "Optional reviewed 2016 or 2021 household/person control contract. Raw normalized controls remain available when no pack is selected.":
    "web.smallarea.ui047",
  "Required with a reviewed pack. This strict JSON binds the pack, source revision, universe, geography, and exact household/person control tables.":
    "web.smallarea.ui048",
  "Optional prepared WGS-84 GeoJSON whose features use a geo_id property matching the output geography values.":
    "web.smallarea.ui049",
  "The geography dimension in the controls, such as ct or ada.": "web.smallarea.ui050",
  "The column written to generated household and person rows. Usually this matches the geography dimension.":
    "web.smallarea.ui051",
  "Number of candidate households generated from the model before calibration. This is not the final population count.":
    "web.smallarea.ui052",
  "Optional candidate subset fitted for each target geography. Smaller pools make exploratory runs faster.":
    "web.smallarea.ui053",
  "Used only to estimate person rows in the final linked output.":
    "web.smallarea.ui054",
  "Makes candidate generation reproducible without changing which generated candidates are selected for calibration.":
    "web.smallarea.ui055",
  "Controls the calibration-pool subsample independently from candidate generation. Vary it to test sensitivity.":
    "web.smallarea.ui056",
  "Uploading and checking the planned small-area run...": "web.smallarea.dynamic001",
  "Inputs changed. Estimate the run again before starting.": "web.smallarea.dynamic002",
  "Preflight complete. Review the scale before starting the durable run.":
    "web.smallarea.dynamic003",
  "Preflight found insufficient workspace capacity.": "web.smallarea.dynamic004",
  "Target geographies": "web.smallarea.dynamic005",
  "Target households": "web.smallarea.dynamic006",
  "Estimated persons": "web.smallarea.dynamic007",
  "Candidate pool": "web.smallarea.dynamic008",
  "Too little disk space": "web.smallarea.dynamic009",
  "Control pack": "web.smallarea.dynamic010",
  "Start durable small-area run": "web.smallarea.dynamic011",
  "Starting the durable small-area run...": "web.smallarea.dynamic012",
  "Choose a prepared model": "web.smallarea.extra002",
  "Premade models unavailable": "web.smallarea.dynamic014",
  "Reviewed control packs are unavailable; raw normalized controls remain available.":
    "web.smallarea.dynamic015",
  "Small-area linked synthesis": "web.smallarea.dynamic016",
  "Generate and calibrate linked households and people for small areas.":
    "web.smallarea.dynamic017",
  "Linked candidates were generated, calibrated, and validated in Python.":
    "web.smallarea.dynamic018",
  "Assigned household preview": "web.smallarea.dynamic019",
  "Assigned person preview": "web.smallarea.dynamic020",
  "Assigned households": "web.smallarea.dynamic021",
  "Assigned persons": "web.smallarea.dynamic022",
  "Non-converged geographies": "web.smallarea.dynamic023",
  "Largest residual": "web.smallarea.dynamic024",
  "Realized maximum error": "web.smallarea.dynamic025",
  "Calibration mode": "web.smallarea.dynamic026",
  "Not reported": "web.smallarea.dynamic027",
  "None above tolerance": "web.smallarea.dynamic028",
  "Workspace capacity": "web.smallarea.extra001",
  "No premade model selected": "web.smallarea.extra003",
};
