from __future__ import annotations

from dataclasses import dataclass

from .output_service_paths import OutputServicePlan


@dataclass(frozen=True)
class OutputServiceCommand:
    action: str
    command: tuple[str, ...]
    working_directory: str
    note: str

    @property
    def command_line(self) -> str:
        return " ".join(_quote(part) for part in self.command)


@dataclass(frozen=True)
class OutputServiceRunnerPlan:
    start: OutputServiceCommand | None
    stop: OutputServiceCommand | None
    warning: str
    execution_allowed: bool

    @property
    def available(self) -> bool:
        return self.start is not None or self.stop is not None

    @property
    def executable(self) -> bool:
        return self.available and self.execution_allowed

    @property
    def summary(self) -> str:
        if not self.available:
            return "Output-service runner commands are not available."
        available = []
        if self.start is not None:
            available.append("start")
        if self.stop is not None:
            available.append("stop")
        return f"Output-service runner commands prepared: {', '.join(available)}."


def _quote(value: str) -> str:
    if not value:
        return '""'
    if any(ch.isspace() for ch in value) or any(ch in value for ch in ('"', "'")):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def build_runner_plan(service_plan: OutputServicePlan) -> OutputServiceRunnerPlan:
    if not service_plan.available:
        return OutputServiceRunnerPlan(
            start=None,
            stop=None,
            warning="Output-service assets are missing, so no runner commands can be prepared.",
            execution_allowed=False,
        )

    start = None
    stop = None
    warning = ""
    execution_allowed = service_plan.execution_allowed
    if not execution_allowed:
        warning = (
            "Dry-run only: the discovered scripts are reference-only and may read another "
            "folder's settings file. PySide6 must use copied/package-local runtime assets "
            "before enabling real process execution."
        )

    if service_plan.start_script is not None:
        start = OutputServiceCommand(
            action="start",
            command=(
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(service_plan.start_script),
            ),
            working_directory=str(service_plan.start_script.parent),
            note="Starts the DualSense output server through the existing script.",
        )
    elif service_plan.server_executable is not None:
        start = OutputServiceCommand(
            action="start",
            command=(
                str(service_plan.server_executable),
                "--event-port",
                "18801",
                "--no-keys",
            ),
            working_directory=str(service_plan.server_executable.parent),
            note="Starts the published DualSense output server executable.",
        )
    elif service_plan.server_dll is not None:
        start = OutputServiceCommand(
            action="start",
            command=(
                "dotnet",
                str(service_plan.server_dll),
                "--event-port",
                "18801",
                "--no-keys",
            ),
            working_directory=str(service_plan.server_dll.parent),
            note="Starts the published DualSense output server DLL through dotnet.",
        )
    elif service_plan.server_project is not None:
        start = OutputServiceCommand(
            action="start",
            command=(
                "dotnet",
                "build",
                str(service_plan.server_project),
                "--nologo",
                "-v",
                "minimal",
            ),
            working_directory=str(service_plan.server_project.parent),
            note="Build command only; process start command still needs a published DLL/exe target.",
        )

    if service_plan.stop_script is not None:
        stop = OutputServiceCommand(
            action="stop",
            command=(
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(service_plan.stop_script),
            ),
            working_directory=str(service_plan.stop_script.parent),
            note="Stops the DualSense output server through the existing script.",
        )

    return OutputServiceRunnerPlan(
        start=start,
        stop=stop,
        warning=warning,
        execution_allowed=execution_allowed,
    )
