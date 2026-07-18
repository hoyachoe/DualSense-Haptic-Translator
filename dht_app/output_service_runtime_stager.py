from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .output_service_package import OPTIONAL_PUBLISHED_FILES, REQUIRED_PUBLISHED_FILES


RUNTIME_STAGE_FILES = REQUIRED_PUBLISHED_FILES + OPTIONAL_PUBLISHED_FILES


@dataclass(frozen=True)
class OutputRuntimeStageResult:
    source_root: Path
    target_root: Path
    copied: tuple[str, ...]
    missing_required: tuple[str, ...]
    missing_optional: tuple[str, ...]
    execute: bool

    @property
    def ok(self) -> bool:
        return not self.missing_required

    @property
    def summary(self) -> str:
        if not self.ok:
            return f"Output runtime staging blocked. Missing: {', '.join(self.missing_required)}"
        if self.execute:
            return f"Output runtime staged: {len(self.copied)} file(s)."
        return f"Output runtime staging ready: {len(self.copied)} file(s)."


def plan_output_runtime_stage(
    source_root: Path | str,
    target_root: Path | str,
) -> OutputRuntimeStageResult:
    return stage_output_runtime(source_root, target_root, execute=False)


def stage_output_runtime(
    source_root: Path | str,
    target_root: Path | str,
    execute: bool = False,
) -> OutputRuntimeStageResult:
    source = Path(source_root)
    target = Path(target_root)
    missing_required = tuple(
        name for name in REQUIRED_PUBLISHED_FILES if not (source / name).is_file()
    )
    missing_optional = tuple(
        name for name in OPTIONAL_PUBLISHED_FILES if not (source / name).is_file()
    )
    copyable = tuple(name for name in RUNTIME_STAGE_FILES if (source / name).is_file())
    if execute and not missing_required:
        target.mkdir(parents=True, exist_ok=True)
        for name in copyable:
            shutil.copy2(source / name, target / name)
    return OutputRuntimeStageResult(
        source_root=source,
        target_root=target,
        copied=copyable,
        missing_required=missing_required,
        missing_optional=missing_optional,
        execute=execute,
    )
