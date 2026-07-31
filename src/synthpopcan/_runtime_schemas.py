"""Runtime validation models for untrusted JSON and process boundaries."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _BoundaryModel(BaseModel):
    """Reject coercion and unexpected fields at external data boundaries."""

    model_config = ConfigDict(extra="forbid", strict=True)


class IPFRunInputs(_BoundaryModel):
    seed_upload_id: str = ""
    controls_upload_id: str = ""


class IPFRunOptions(_BoundaryModel):
    weight_column: str | None = None
    max_iterations: int = 100
    tolerance: float = 1e-6
    allow_nonconverged: bool = False


class IPFRunRequest(_BoundaryModel):
    workflow: Literal["ipf"]
    inputs: IPFRunInputs
    options: IPFRunOptions = Field(default_factory=IPFRunOptions)


class ModelRunInputs(_BoundaryModel):
    model_id: str | None = None
    package_upload_id: str | None = None


class ModelRunOptions(_BoundaryModel):
    households: int = 10
    conditions: dict[str, str] = Field(default_factory=dict)
    random_seed: int | None = None
    household_size_column: str | None = None
    chunk_size: int = 1000


class ModelRunRequest(_BoundaryModel):
    workflow: Literal["model"]
    inputs: ModelRunInputs
    options: ModelRunOptions = Field(default_factory=ModelRunOptions)


class SmallAreaRunInputs(_BoundaryModel):
    model_id: str | None = None
    package_upload_id: str | None = None
    candidate_households_upload_id: str | None = None
    candidate_persons_upload_id: str | None = None
    controls_upload_id: str = ""
    person_controls_upload_id: str | None = None
    boundaries_upload_id: str | None = None


class SmallAreaRunOptions(_BoundaryModel):
    candidate_households: int = 0
    geography_dimension: str = ""
    geography_column: str | None = None
    geography_universe: dict[str, Any] | None = None
    conditions: dict[str, str] = Field(default_factory=dict)
    random_seed: int | None = None
    pool_size: int | None = None
    subsample_seed: int = 42
    max_household_size: int | None = None
    household_size_group_column: str = "household_size_group"
    include_weights: bool = False
    chunk_size: int = 1000
    geography_id_field: str = "geo_id"
    map_title: str = "Synthetic Population"
    average_persons_per_household: float = 2.22


class SmallAreaRunRequest(_BoundaryModel):
    workflow: Literal["small_area"]
    inputs: SmallAreaRunInputs
    options: SmallAreaRunOptions


RunRequest = Annotated[
    IPFRunRequest | ModelRunRequest | SmallAreaRunRequest,
    Field(discriminator="workflow"),
]
RUN_REQUEST_ADAPTER: TypeAdapter[RunRequest] = TypeAdapter(RunRequest)


class WDSSeedControlsRequest(_BoundaryModel):
    product_id: str = Field(default="", alias="productId")
    dimensions: str | list[str] | None = None
    count_column: str | None = Field(default=None, alias="countColumn")


class SmallAreaEstimateRequest(_BoundaryModel):
    controls_csv: str = Field(default="", alias="controlsCsv")
    geography_dimension: str = Field(default="", alias="geographyDimension")
    candidate_households: int = Field(default=0, alias="candidateHouseholds")
    pool_size: int | None = Field(default=None, alias="poolSize")
    average_persons_per_household: float = Field(
        default=2.22,
        alias="averagePersonsPerHousehold",
    )


class UploadMetadata(_BoundaryModel):
    upload_id: str
    display_name: str
    media_type: str
    byte_size: int
    sha256: str
    created_at: str
    claimed_by: str | None
    path: str


class RunInput(_BoundaryModel):
    logical_name: str
    upload_id: str
    display_name: str
    path: str
    media_type: str
    byte_size: int
    sha256: str


class RunArtifact(_BoundaryModel):
    artifact_id: str
    logical_name: str
    filename: str
    path: str
    media_type: str
    byte_size: int
    sha256: str
    row_count: int | None


class RunManifest(_BoundaryModel):
    schema_version: Literal["synthpopcan-run-v1"]
    run_id: str
    workflow: Literal["ipf", "model", "small_area"]
    status: Literal[
        "queued",
        "running",
        "cancelling",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
    ]
    created_at: str
    started_at: str | None
    finished_at: str | None
    synthpopcan_version: str
    request: dict[str, Any]
    random_seed: int | None
    inputs: list[RunInput]
    artifacts: list[RunArtifact]
    summary: dict[str, Any]
    error: dict[str, Any] | None
    reproduction: dict[str, Any] | None
    assurance: dict[str, Any] | None


class RunEvent(_BoundaryModel):
    id: int
    timestamp: str
    stage: str
    message: str
    completed: int | None
    total: int | None


class WorkerProgressEvent(_BoundaryModel):
    stage: str
    message: str
    completed: int | None = None
    total: int | None = None


class WorkerProgressMessage(_BoundaryModel):
    type: Literal["progress"]
    event: WorkerProgressEvent


class WorkerSucceededMessage(_BoundaryModel):
    type: Literal["succeeded"]
    artifacts: list[RunArtifact]
    summary: dict[str, Any]
    reproduction: dict[str, Any]


class WorkerError(_BoundaryModel):
    kind: str
    message: str


class WorkerFailedMessage(_BoundaryModel):
    type: Literal["failed"]
    error: WorkerError


class WorkerCancelledMessage(_BoundaryModel):
    type: Literal["cancelled"]


WorkerMessage = Annotated[
    WorkerProgressMessage
    | WorkerSucceededMessage
    | WorkerFailedMessage
    | WorkerCancelledMessage,
    Field(discriminator="type"),
]
WORKER_MESSAGE_ADAPTER: TypeAdapter[WorkerMessage] = TypeAdapter(WorkerMessage)
