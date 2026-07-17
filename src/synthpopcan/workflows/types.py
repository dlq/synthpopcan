"""Shared request, result, progress, and reproduction types."""

from __future__ import annotations

__all__ = [
    "IPFExpandRequest",
    "IPFExpandResult",
    "IPFFitRequest",
    "IPFFitResult",
    "IPFValidationRequest",
    "IPFValidationResult",
    "ProgressCallback",
    "ReproductionCommand",
    "WorkflowReproduction",
    "WorkflowProgress",
]

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, TypeAlias


@dataclass(frozen=True)
class WorkflowProgress:
    """One structured, presentation-independent workflow progress event."""

    stage: str
    message: str
    completed: int | None = None
    total: int | None = None

    def as_dict(self) -> dict[str, str | int | None]:
        """Return a JSON-serializable event representation."""
        return {
            "stage": self.stage,
            "message": self.message,
            "completed": self.completed,
            "total": self.total,
        }


class ProgressCallback(Protocol):
    """Callable accepted by workflows that report coarse progress."""

    def __call__(self, event: WorkflowProgress) -> None: ...


ProgressReporter: TypeAlias = ProgressCallback | Callable[[WorkflowProgress], None]


@dataclass(frozen=True)
class ReproductionCommand:
    """Structured command that can be rendered safely for a local shell."""

    program: str
    arguments: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return the durable structured form stored in future run manifests."""
        return {"program": self.program, "arguments": list(self.arguments)}

    def render(self) -> str:
        """Render the command with POSIX shell quoting."""
        return shlex.join((self.program, *self.arguments))


@dataclass(frozen=True)
class WorkflowReproduction:
    """Canonical workflow request paired with its shell-safe CLI equivalent."""

    request: dict[str, object]
    command: ReproductionCommand

    def as_dict(self) -> dict[str, object]:
        """Return the representation stored in a durable run manifest."""
        return {
            "request": self.request,
            "command": self.command.as_dict(),
            "shell": self.command.render(),
        }


@dataclass(frozen=True)
class IPFFitRequest:
    """File-backed IPF fitting request shared by CLI and HTTP adapters."""

    seed_path: Path
    controls_path: Path
    output_path: Path
    weight_column: str | None = None
    max_iterations: int = 100
    tolerance: float = 1e-6
    allow_nonconverged: bool = False
    report_path: Path | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the canonical structured file-backed workflow request."""
        return {
            "workflow": "ipf",
            "operation": "fit",
            "inputs": {
                "seed": str(self.seed_path),
                "controls": str(self.controls_path),
            },
            "options": {
                "weight_column": self.weight_column,
                "max_iterations": self.max_iterations,
                "tolerance": self.tolerance,
                "allow_nonconverged": self.allow_nonconverged,
            },
            "outputs": {
                "weights": str(self.output_path),
                "report": str(self.report_path) if self.report_path else None,
            },
        }

    def reproduction(self) -> WorkflowReproduction:
        """Build the canonical CLI equivalent of this request."""
        arguments = [
            "ipf",
            "fit",
            "--seed",
            str(self.seed_path),
            "--controls",
            str(self.controls_path),
            "--out",
            str(self.output_path),
        ]
        if self.weight_column is not None:
            arguments.extend(("--weight-column", self.weight_column))
        if self.max_iterations != 100:
            arguments.extend(("--max-iterations", str(self.max_iterations)))
        if self.tolerance != 1e-6:
            arguments.extend(("--tolerance", str(self.tolerance)))
        if self.allow_nonconverged:
            arguments.append("--allow-nonconverged")
        if self.report_path is not None:
            arguments.extend(("--report", str(self.report_path)))
        command = ReproductionCommand("synthpopcan", tuple(arguments))
        return WorkflowReproduction(request=self.as_dict(), command=command)


@dataclass(frozen=True)
class IPFFitResult:
    """Completed compact-weight IPF workflow result."""

    output_path: Path
    report_path: Path | None
    report: dict[str, Any]
    reproduction: WorkflowReproduction


@dataclass(frozen=True)
class IPFExpandRequest:
    """Request to stream compact fitted weights into expanded records."""

    weights_path: Path
    output_path: Path
    weight_column: str = "weight"

    def as_dict(self) -> dict[str, object]:
        """Return the canonical structured expansion request."""
        return {
            "workflow": "ipf",
            "operation": "expand",
            "inputs": {"weights": str(self.weights_path)},
            "options": {"weight_column": self.weight_column},
            "outputs": {"population": str(self.output_path)},
        }

    def reproduction(self) -> WorkflowReproduction:
        """Build the canonical CLI equivalent of this request."""
        arguments = [
            "ipf",
            "expand",
            "--weights",
            str(self.weights_path),
            "--out",
            str(self.output_path),
        ]
        if self.weight_column != "weight":
            arguments.extend(("--weight-column", self.weight_column))
        command = ReproductionCommand("synthpopcan", tuple(arguments))
        return WorkflowReproduction(request=self.as_dict(), command=command)


@dataclass(frozen=True)
class IPFExpandResult:
    """Completed expanded-population workflow result."""

    output_path: Path
    output_rows: int
    reproduction: WorkflowReproduction


@dataclass(frozen=True)
class IPFValidationRequest:
    """Request to validate a weighted or expanded population artifact."""

    population_path: Path
    controls_path: Path
    artifact_kind: Literal["weights", "expanded"]
    weight_column: str = "weight"
    tolerance: float = 1e-6

    def as_dict(self) -> dict[str, object]:
        """Return the canonical structured validation request."""
        return {
            "workflow": "ipf",
            "operation": "validate",
            "inputs": {
                "population": str(self.population_path),
                "controls": str(self.controls_path),
            },
            "options": {
                "artifact_kind": self.artifact_kind,
                "weight_column": self.weight_column,
                "tolerance": self.tolerance,
            },
        }

    def reproduction(self) -> WorkflowReproduction:
        """Build the canonical CLI equivalent of this request."""
        arguments = [
            "validate",
            "ipf",
            "--population",
            str(self.population_path),
            "--controls",
            str(self.controls_path),
            "--kind",
            self.artifact_kind,
        ]
        if self.weight_column != "weight":
            arguments.extend(("--weight-column", self.weight_column))
        if self.tolerance != 1e-6:
            arguments.extend(("--tolerance", str(self.tolerance)))
        command = ReproductionCommand("synthpopcan", tuple(arguments))
        return WorkflowReproduction(request=self.as_dict(), command=command)


@dataclass(frozen=True)
class IPFValidationResult:
    """Completed validation workflow result."""

    report: dict[str, Any]
    reproduction: WorkflowReproduction
