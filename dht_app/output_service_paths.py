from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputServicePlan:
    app_root: Path
    source: str
    runtime_root: Path
    server_root: Path | None
    server_project: Path | None
    server_executable: Path | None
    server_dll: Path | None
    start_script: Path | None
    stop_script: Path | None
    logs_root: Path

    @property
    def available(self) -> bool:
        return (
            self.server_executable is not None
            or self.server_dll is not None
            or self.server_project is not None
            or self.start_script is not None
        )

    @property
    def execution_allowed(self) -> bool:
        return self.source in {
            "package runtime folder",
            "candidate folder",
            "packaged internal runtime folder",
            "packaged internal folder",
        }

    @property
    def summary(self) -> str:
        if not self.available:
            return "Output-service assets were not found."
        return f"Output-service assets found from {self.source}."

    @property
    def details(self) -> str:
        if not self.available:
            return f"Search root: {self.app_root}"
        parts = [f"runtime root: {self.runtime_root}", f"server root: {self.server_root}"]
        if self.server_executable is not None:
            parts.append(f"exe: {self.server_executable.name}")
        if self.server_dll is not None:
            parts.append(f"dll: {self.server_dll.name}")
        if self.server_project is not None:
            parts.append(f"project: {self.server_project.name}")
        if self.start_script is not None:
            parts.append(f"start: {self.start_script.name}")
        if self.stop_script is not None:
            parts.append(f"stop: {self.stop_script.name}")
        return "; ".join(parts)


def _existing(path: Path) -> Path | None:
    return path if path.exists() else None


def _make_plan(app_root: Path, source: str, root: Path) -> OutputServicePlan | None:
    server_root = root / "dualsense_output_server"
    server_project = _existing(server_root / "DualSenseOutputServer.csproj")
    server_executable = _existing(root / "DualSenseOutputServer.exe")
    server_dll = _existing(root / "DualSenseOutputServer.dll")
    start_script = _existing(root / "start_haptic_server.ps1")
    stop_script = _existing(root / "stop_haptic_server.ps1")
    if (
        not server_root.exists()
        and server_executable is None
        and server_dll is None
        and start_script is None
        and stop_script is None
    ):
        return None
    return OutputServicePlan(
        app_root=app_root,
        source=source,
        runtime_root=root,
        server_root=server_root if server_root.exists() else None,
        server_project=server_project,
        server_executable=server_executable,
        server_dll=server_dll,
        start_script=start_script,
        stop_script=stop_script,
        logs_root=root / "logs",
    )


def discover_output_service(app_root: Path | None = None) -> OutputServicePlan:
    """Find DualSense output-service assets without starting any process."""

    root = Path(app_root) if app_root is not None else Path(__file__).resolve().parent
    candidates = (
        ("package runtime folder", root / "runtime"),
        ("candidate folder", root),
        ("packaged internal runtime folder", root / "_internal" / "runtime"),
        ("packaged internal folder", root / "_internal"),
        ("stable Tkinter sibling folder", root.parent / "DualSense Haptic Translator"),
    )
    for source, candidate_root in candidates:
        plan = _make_plan(root, source, candidate_root)
        if plan is not None and plan.available:
            return plan
    return OutputServicePlan(
        app_root=root,
        source="none",
        runtime_root=root,
        server_root=None,
        server_project=None,
        server_executable=None,
        server_dll=None,
        start_script=None,
        stop_script=None,
        logs_root=root / "logs",
    )
