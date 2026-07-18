from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .output_service_paths import OutputServicePlan


REQUIRED_PUBLISHED_FILES = (
    "DualSenseOutputServer.exe",
    "DualSenseOutputServer.dll",
    "DualSenseOutputServer.deps.json",
    "DualSenseOutputServer.runtimeconfig.json",
    "NAudio.Core.dll",
    "NAudio.Wasapi.dll",
)

OPTIONAL_PUBLISHED_FILES = (
    "NAudio.dll",
    "NAudio.Asio.dll",
    "NAudio.Midi.dll",
    "NAudio.WinForms.dll",
    "NAudio.WinMM.dll",
)


@dataclass(frozen=True)
class OutputServicePackageAudit:
    runtime_root: Path
    missing_required: tuple[str, ...]
    present_required: tuple[str, ...]
    present_optional: tuple[str, ...]
    execution_allowed: bool

    @property
    def ok(self) -> bool:
        return self.execution_allowed and not self.missing_required

    @property
    def summary(self) -> str:
        if self.ok:
            return f"Package-local output runtime is complete: {self.runtime_root}"
        if not self.execution_allowed:
            return "Output runtime is reference-only; package-local runtime is required."
        return f"Output runtime is missing: {', '.join(self.missing_required)}"


def audit_output_service_package(plan: OutputServicePlan) -> OutputServicePackageAudit:
    runtime_root = plan.runtime_root
    present_required = tuple(
        name for name in REQUIRED_PUBLISHED_FILES if (runtime_root / name).exists()
    )
    missing_required = tuple(
        name for name in REQUIRED_PUBLISHED_FILES if not (runtime_root / name).exists()
    )
    present_optional = tuple(
        name for name in OPTIONAL_PUBLISHED_FILES if (runtime_root / name).exists()
    )
    return OutputServicePackageAudit(
        runtime_root=runtime_root,
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        execution_allowed=plan.execution_allowed,
    )
