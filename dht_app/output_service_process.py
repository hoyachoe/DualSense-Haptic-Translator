from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .output_service_runner import OutputServiceRunnerPlan
from .output_service_settings import OutputServiceSettingsPlan


@dataclass(frozen=True)
class OutputServiceProcessResult:
    message: str
    details: str
    ok: bool
    pid: int | None = None


class OutputServiceProcessManager:
    """Owns a package-local DualSense output service process."""

    def __init__(self):
        self.process: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(
        self,
        runner_plan: OutputServiceRunnerPlan,
        logs_root: Path,
        settings_plan: OutputServiceSettingsPlan | None = None,
        execute: bool = False,
    ) -> OutputServiceProcessResult:
        if not runner_plan.executable or runner_plan.start is None:
            return OutputServiceProcessResult(
                "DualSense output service start blocked.",
                runner_plan.summary,
                ok=False,
            )
        if self.running:
            return OutputServiceProcessResult(
                "DualSense output service already running.",
                f"pid={self.process.pid}",
                ok=True,
                pid=self.process.pid,
            )
        command = _command_with_settings(runner_plan.start.command, settings_plan)
        command_line = _command_line(command)
        if not execute:
            return OutputServiceProcessResult(
                "DualSense output service start ready.",
                f"Dry-run command: {command_line}",
                ok=True,
            )

        logs_root.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_root / "haptic_server_latest.out.log"
        stderr_path = logs_root / "haptic_server_latest.err.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                command,
                cwd=runner_plan.start.working_directory,
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as exc:
            stdout_handle.close()
            stderr_handle.close()
            return OutputServiceProcessResult(
                "DualSense output service start failed.",
                str(exc),
                ok=False,
            )
        stdout_handle.close()
        stderr_handle.close()
        return OutputServiceProcessResult(
            "DualSense output service started.",
            f"pid={self.process.pid}; stdout={stdout_path}; stderr={stderr_path}",
            ok=True,
            pid=self.process.pid,
        )

    def stop(self, execute: bool = False) -> OutputServiceProcessResult:
        if not self.running:
            return OutputServiceProcessResult(
                "DualSense output service is not running.",
                "No owned process is active.",
                ok=True,
            )
        if not execute:
            return OutputServiceProcessResult(
                "DualSense output service stop ready.",
                f"Dry-run stop for pid={self.process.pid}",
                ok=True,
                pid=self.process.pid,
            )
        pid = self.process.pid
        self.process.terminate()
        try:
            self.process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2.0)
        self.process = None
        return OutputServiceProcessResult(
            "DualSense output service stopped.",
            f"pid={pid}",
            ok=True,
            pid=pid,
        )


def _command_with_settings(
    command: tuple[str, ...],
    settings_plan: OutputServiceSettingsPlan | None,
) -> tuple[str, ...]:
    if settings_plan is None or not settings_plan.write_allowed:
        return command
    if not command:
        return command
    executable = command[0].lower()
    runs_published_server = executable.endswith("dualsenseoutputserver.exe") or (
        executable.endswith("dotnet")
        and len(command) > 1
        and command[1].lower().endswith("dualsenseoutputserver.dll")
    )
    if not runs_published_server:
        return command
    payload = settings_plan.payload
    result = list(command)
    if payload.haptic_audio_device:
        result += ["--output-device", payload.haptic_audio_device]
    result += ["--master-gain-percent", str(payload.dsx_audio_volume_percent)]
    if payload.dsx_udp_enabled:
        result.append("--no-trigger-hid")
    return tuple(result)


def _quote(value: str) -> str:
    if not value:
        return '""'
    if any(ch.isspace() for ch in value) or any(ch in value for ch in ('"', "'")):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _command_line(command: tuple[str, ...]) -> str:
    return " ".join(_quote(part) for part in command)
