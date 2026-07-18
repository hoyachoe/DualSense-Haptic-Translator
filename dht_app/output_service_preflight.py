from __future__ import annotations

from dataclasses import dataclass

from .output_service_package import OutputServicePackageAudit
from .output_service_paths import OutputServicePlan
from .output_service_runner import OutputServiceRunnerPlan
from .output_service_settings import OutputServiceSettingsPlan


@dataclass(frozen=True)
class OutputPreflightCheck:
    name: str
    ok: bool
    message: str
    warning: bool = False

    @property
    def status(self) -> str:
        if self.ok:
            return "OK"
        return "WARN" if self.warning else "FAIL"


@dataclass(frozen=True)
class OutputPreflightResult:
    checks: tuple[OutputPreflightCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok or check.warning for check in self.checks)

    @property
    def ready_to_execute(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def summary(self) -> str:
        failures = [check for check in self.checks if not check.ok and not check.warning]
        warnings = [check for check in self.checks if not check.ok and check.warning]
        if not failures and not warnings:
            return "DualSense output preflight passed."
        if failures:
            return f"DualSense output preflight blocked by {len(failures)} issue(s)."
        return f"DualSense output preflight has {len(warnings)} warning(s)."

    @property
    def details(self) -> str:
        return " | ".join(
            f"{check.status} {check.name}: {check.message}" for check in self.checks
        )


def run_output_preflight(
    selected_device: str,
    service_plan: OutputServicePlan,
    runner_plan: OutputServiceRunnerPlan,
    package_audit: OutputServicePackageAudit,
    settings_plan: OutputServiceSettingsPlan | None,
) -> OutputPreflightResult:
    selected_device = selected_device.strip()
    checks: list[OutputPreflightCheck] = [
        OutputPreflightCheck(
            "DualSense device",
            bool(selected_device),
            selected_device or "No selected playback endpoint.",
        ),
        OutputPreflightCheck(
            "Output assets",
            service_plan.available,
            service_plan.summary,
        ),
        OutputPreflightCheck(
            "Package runtime",
            package_audit.ok,
            package_audit.summary,
        ),
        OutputPreflightCheck(
            "Runner",
            runner_plan.executable,
            runner_plan.summary,
        ),
    ]
    if runner_plan.warning:
        checks.append(
            OutputPreflightCheck(
                "Runner policy",
                False,
                runner_plan.warning,
                warning=True,
            )
        )
    if settings_plan is None:
        checks.append(
            OutputPreflightCheck(
                "Settings handoff",
                False,
                "Output-service settings handoff was not planned.",
            )
        )
    else:
        checks.append(
            OutputPreflightCheck(
                "Settings handoff",
                settings_plan.write_allowed,
                settings_plan.summary,
            )
        )
    return OutputPreflightResult(tuple(checks))
